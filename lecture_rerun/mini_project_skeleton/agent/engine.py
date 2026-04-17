from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .data_store import SupportDataStore
from .rag import ManualSearcher
from .schemas import DeviceActionPlan, PendingAction, Role, ServiceTicket, SupportReport, ToolResult
from .tools import SupportTools


DEVICE_KEYWORDS = {
    "robot_vacuum": ["로봇청소기", "청소기", "vacuum"],
    "washing_machine": ["세탁기", "washer"],
    "air_conditioner": ["에어컨", "냉방기", "ac"],
    "remote_hub": ["앱", "허브", "와이파이", "wifi", "wi-fi", "연결"],
}
SAFETY_KEYWORDS = ["연기", "과열", "가스", "탄 냄새", "타는 냄새", "누전", "불꽃", "스파크"]
YES_WORDS = ["예", "네", "응", "확인", "진행", "동의", "yes", "y", "ok"]
NO_WORDS = ["아니", "아니오", "취소", "중단", "no", "n"]
ERROR_RE = re.compile(r"\b[A-Z0-9]{2,5}\b")
DEVICE_ID_RE = re.compile(r"DEV-\d{4}")


class SupportCopilot:
    def __init__(self, data_dir: str | Path | None = None):
        base_dir = Path(data_dir or Path(__file__).resolve().parent / "data")
        self.store = SupportDataStore(base_dir)
        self.tools = SupportTools(self.store)
        self.searcher = ManualSearcher(base_dir / "manuals")
        self.sessions: dict[str, PendingAction | None] = {}

    def process(self, message: str, role: Role = "customer", session_id: str = "default") -> SupportReport:
        pending = self.sessions.get(session_id)
        if pending:
            return self._handle_confirmation(message, pending, session_id)

        plan = self._build_plan(message)
        if plan.safety_risk:
            return self._build_handoff_report(message, plan)
        if plan.intent == "manual_info":
            return self._handle_manual(plan)
        if plan.intent == "troubleshooting":
            return self._handle_troubleshooting(plan, role)
        return self._handle_device_control(plan, role, session_id)

    def _build_plan(self, message: str) -> DeviceActionPlan:
        lowered = message.lower()
        device_id_match = DEVICE_ID_RE.search(message)
        device_id = device_id_match.group(0) if device_id_match else None
        device_type = None
        if device_id:
            device = self.store.get_device(device_id)
            if device:
                device_type = device.get("device_type")
        if not device_type:
            for candidate, keywords in DEVICE_KEYWORDS.items():
                if any(keyword in lowered for keyword in keywords):
                    device_type = candidate
                    break

        safety_risk = any(keyword in message for keyword in SAFETY_KEYWORDS)
        error_match = ERROR_RE.search(message)
        error_code = error_match.group(0) if error_match and error_match.group(0) != "DEV" else None

        action = None
        intent = "manual_info"
        symptom = None

        if any(keyword in lowered for keyword in ["업데이트", "firmware"]):
            intent = "device_control"
            action = "update_firmware"
        elif any(keyword in lowered for keyword in ["초기화", "factory reset", "reset"]):
            intent = "device_control"
            action = "factory_reset"
        elif any(keyword in lowered for keyword in ["온도", "temperature"]):
            intent = "device_control"
            action = "set_temperature"
        elif any(keyword in lowered for keyword in ["모드", "mode", "세기"]):
            intent = "device_control"
            action = "set_mode"
        elif error_code or any(keyword in message for keyword in ["에러", "안 돼", "약해", "고장", "진단", "증상", "상태"]):
            intent = "troubleshooting"
            symptom = message
        else:
            intent = "manual_info"

        missing_fields: list[str] = []
        if intent in {"device_control", "troubleshooting"} and not device_id and not device_type:
            missing_fields.append("device_id_or_type")
        if intent == "manual_info" and not device_type:
            missing_fields.append("device_type")

        question = message if intent == "manual_info" else None
        return DeviceActionPlan(
            intent=intent,  # type: ignore[arg-type]
            device_id=device_id,
            device_type=device_type,  # type: ignore[arg-type]
            action=action,
            question=question,
            symptom=symptom,
            error_code=error_code,
            safety_risk=safety_risk,
            missing_fields=missing_fields,
        )

    def _handle_manual(self, plan: DeviceActionPlan) -> SupportReport:
        if plan.missing_fields:
            return SupportReport(
                title="추가 정보 필요",
                intent="manual_info",
                severity="low",
                reply="매뉴얼 검색 전에 제품 종류를 먼저 확인해야 합니다.",
                follow_up_question="로봇청소기 / 세탁기 / 에어컨 / 앱 연결 중 어떤 기기 문제인가요?",
            )

        hits = self.searcher.search(plan.question or "", plan.device_type)
        if not hits:
            return SupportReport(
                title="매뉴얼 근거 없음",
                intent="manual_info",
                severity="low",
                reply="현재 더미 매뉴얼에서 바로 찾은 항목이 없습니다.",
                follow_up_question="모델명, 증상, 에러코드 중 하나를 더 알려주실 수 있나요?",
                recommended_actions=["NO_HIT일 때는 모델/증상/에러코드를 추가로 질문"],
            )

        evidence = [f"{hit['citation']} {hit['text']}" for hit in hits]
        actions = [hit["text"] for hit in hits if not hit["text"].startswith("[")][:2]
        if not actions:
            actions = [hit["text"] for hit in hits[:2]]
        reply = "매뉴얼 근거를 기준으로 우선 확인할 항목을 정리했습니다."
        return SupportReport(
            title="매뉴얼 안내",
            intent="manual_info",
            severity="low",
            reply=reply,
            evidence=evidence,
            recommended_actions=actions,
        )

    def _handle_troubleshooting(self, plan: DeviceActionPlan, role: Role) -> SupportReport:
        if plan.missing_fields:
            return SupportReport(
                title="진단 정보 부족",
                intent="troubleshooting",
                severity="medium",
                reply="원격진단 전에 어떤 기기인지 더 확인해야 합니다.",
                follow_up_question="기기 종류나 모델, 표시된 에러코드를 알려주세요.",
            )

        device_id = plan.device_id or self._resolve_device_id(plan.device_type)
        if not device_id:
            return SupportReport(
                title="기기 식별 실패",
                intent="troubleshooting",
                severity="medium",
                reply="등록된 기기와 연결되지 않아 상태를 조회할 수 없습니다.",
                follow_up_question="기기 ID(예: DEV-2002)를 알려주세요.",
            )

        tool_results = [
            self.tools.get_device_status(device_id),
            self.tools.get_recent_events(device_id, limit=3),
        ]
        if role in {"support", "admin"}:
            tool_results.append(self.tools.run_remote_diagnosis(device_id))
        else:
            tool_results.append(ToolResult(ok=False, tool="run_remote_diagnosis", error="role_required:support_or_admin"))
        device = self.store.get_device(device_id) or {}
        query = " ".join(part for part in [plan.symptom or "", plan.error_code or "", device.get("model", "")] if part)
        manual_hits = self.searcher.search(query, device.get("device_type"))
        evidence = self._collect_evidence(tool_results, manual_hits)

        severity = "medium"
        recommended_actions = ["최근 진단 결과와 매뉴얼 점검 절차를 순서대로 수행"]
        if plan.error_code == "5C":
            recommended_actions = [
                "배수 필터 이물질을 제거하고 배수 호스 꺾임 여부를 확인",
                "응급 배수 후 동일 증상이 반복되면 서비스 점검으로 이관",
            ]
        elif device.get("device_type") == "robot_vacuum":
            recommended_actions = [
                "필터와 브러시를 분리해 청소한 뒤 흡입력을 다시 확인",
                "도킹부와 범퍼 센서 오염도 함께 확인",
            ]
        elif device.get("device_type") == "remote_hub":
            recommended_actions = [
                "2.4GHz Wi-Fi 연결 여부와 앱 로그인 상태를 다시 확인",
                "라우터 재부팅 후 앱에서 기기 재등록을 시도",
            ]

        ticket: ServiceTicket | None = None
        if role in {"support", "admin"} and (
            plan.error_code == "5C" or any(keyword in (plan.symptom or "") for keyword in ["반복", "계속", "지속"])
        ):
            ticket_result = self.tools.create_service_ticket(device_id, plan.symptom or "원격진단 후 후속 점검 필요", severity)
            tool_results.append(ticket_result)
            ticket_payload = ticket_result.payload.get("ticket")
            if ticket_payload:
                ticket = ServiceTicket(**ticket_payload)

        reply = "상태 조회, 최근 이벤트, 원격진단, 매뉴얼 근거를 합쳐 현재 조치 순서를 정리했습니다."
        return SupportReport(
            title="원격진단 결과",
            intent="troubleshooting",
            severity=severity,
            reply=reply,
            evidence=evidence,
            recommended_actions=recommended_actions,
            needs_handoff=False,
            ticket=ticket,
            tool_results=tool_results,
        )

    def _handle_device_control(self, plan: DeviceActionPlan, role: Role, session_id: str) -> SupportReport:
        if plan.missing_fields:
            return SupportReport(
                title="제어 정보 부족",
                intent="device_control",
                severity="low",
                reply="제어 요청을 실행하려면 대상 기기를 먼저 지정해야 합니다.",
                follow_up_question="기기 ID(예: DEV-3003) 또는 제품 종류를 알려주세요.",
            )

        device_id = plan.device_id or self._resolve_device_id(plan.device_type)
        if not device_id:
            return SupportReport(
                title="기기 식별 실패",
                intent="device_control",
                severity="medium",
                reply="등록된 기기를 찾지 못해 요청을 실행할 수 없습니다.",
                follow_up_question="기기 ID를 알려주세요.",
            )

        if plan.action in {"update_firmware", "factory_reset"}:
            if role != "admin":
                return SupportReport(
                    title="권한 부족",
                    intent="device_control",
                    severity="high",
                    reply="펌웨어 업데이트와 공장초기화는 admin 권한이 필요합니다. 사람 상담 또는 관리자 이관이 필요합니다.",
                    recommended_actions=["customer/support는 위험 작업을 직접 실행하지 않음", "관리자 승인 후 confirm 2턴 수행"],
                    needs_handoff=True,
                )
            pending = PendingAction(
                name=plan.action,  # type: ignore[arg-type]
                device_id=device_id,
                args={"target_version": "latest"} if plan.action == "update_firmware" else {},
            )
            self.sessions[session_id] = pending
            return SupportReport(
                title="위험 작업 확인 필요",
                intent="device_control",
                severity="high",
                reply="위험 작업은 2턴 확인 후에만 실행합니다. 진행하려면 '예', 중단하려면 '아니오'라고 답해주세요.",
                recommended_actions=["confirm 2턴 흐름을 유지", "role/confirmed 없으면 실행 금지"],
                needs_confirmation=True,
                pending_action=pending,
            )

        tool_results: list[ToolResult] = []
        if plan.action == "set_temperature":
            temperature = self._extract_number(plan.question or plan.symptom or "") or 24
            tool_results.append(self.tools.set_device_setting(device_id, "target_temp_c", temperature))
        elif plan.action == "set_mode":
            mode = "clean" if "청소" in (plan.question or "") else "cool"
            tool_results.append(self.tools.set_device_setting(device_id, "mode", mode))

        evidence = self._collect_evidence(tool_results, [])
        return SupportReport(
            title="제어 요청 처리",
            intent="device_control",
            severity="low",
            reply="비위험 제어 요청을 더미 디바이스 상태에 반영했습니다.",
            evidence=evidence,
            recommended_actions=["상태 반영 후 앱/허브 화면에서도 변경 여부를 확인"],
            tool_results=tool_results,
        )

    def _handle_confirmation(self, message: str, pending: PendingAction, session_id: str) -> SupportReport:
        lowered = message.lower()
        if any(word in lowered for word in YES_WORDS):
            self.sessions[session_id] = None
            if pending.name == "update_firmware":
                result = self.tools.update_firmware(
                    pending.device_id,
                    pending.args.get("target_version", "latest"),
                    confirmed=True,
                )
            else:
                result = self.tools.factory_reset(pending.device_id, confirmed=True)
            return SupportReport(
                title="위험 작업 완료",
                intent="device_control",
                severity="high",
                reply="사용자 확인 후 위험 작업을 실행했습니다.",
                evidence=self._collect_evidence([result], []),
                recommended_actions=["작업 직후 기기 상태와 연결 상태를 다시 확인"],
                tool_results=[result],
            )

        if any(word in lowered for word in NO_WORDS):
            self.sessions[session_id] = None
            return SupportReport(
                title="위험 작업 취소",
                intent="device_control",
                severity="low",
                reply="요청하신 위험 작업을 취소했습니다.",
                recommended_actions=["필요하면 안전한 대체 조치부터 진행"],
            )

        return SupportReport(
            title="확인 응답 대기",
            intent="device_control",
            severity="medium",
            reply="진행 여부가 불명확합니다. '예' 또는 '아니오'로 답해주세요.",
            needs_confirmation=True,
            pending_action=pending,
        )

    def _build_handoff_report(self, message: str, plan: DeviceActionPlan) -> SupportReport:
        _ = (message, plan)
        return SupportReport(
            title="안전 이슈 즉시 이관",
            intent="handoff",
            severity="high",
            reply="안전 위험이 의심됩니다. 즉시 사용을 중지하고 전원을 차단한 뒤 AS 또는 사람 상담으로 이관하세요.",
            evidence=["safety_risk=true"],
            recommended_actions=[
                "제품 동작 중지 및 전원 차단",
                "연기/과열이 계속되면 현장을 벗어나 안전을 확보",
                "사람 상담 또는 서비스 센터로 즉시 이관",
            ],
            needs_handoff=True,
        )

    def _resolve_device_id(self, device_type: str | None) -> str | None:
        if not device_type:
            return None
        match = self.store.find_device_by_type(device_type)
        return match[0] if match else None

    @staticmethod
    def _extract_number(text: str) -> int | None:
        match = re.search(r"(\d{2})", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _collect_evidence(tool_results: list[ToolResult], manual_hits: list[dict[str, str]]) -> list[str]:
        evidence: list[str] = []
        for result in tool_results:
            if result.ok:
                evidence.append(f"{result.tool}: {result.payload}")
            else:
                evidence.append(f"{result.tool}: {result.error}")
        for hit in manual_hits:
            evidence.append(f"{hit['citation']} {hit['text']}")
        return evidence
