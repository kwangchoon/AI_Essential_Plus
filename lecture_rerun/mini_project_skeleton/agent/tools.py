from __future__ import annotations

from copy import deepcopy
from typing import Any

from .data_store import SupportDataStore
from .schemas import ToolResult


class SupportTools:
    def __init__(self, store: SupportDataStore):
        self.store = store

    def get_device_status(self, device_id: str) -> ToolResult:
        device = self.store.get_device(device_id)
        if not device:
            return ToolResult(ok=False, tool="get_device_status", error="unknown_device")
        return ToolResult(tool="get_device_status", payload={"device_id": device_id, **deepcopy(device)})

    def get_recent_events(self, device_id: str, limit: int = 5) -> ToolResult:
        if limit <= 0 or limit > 20:
            return ToolResult(ok=False, tool="get_recent_events", error="invalid_limit")
        return ToolResult(
            tool="get_recent_events",
            payload={"device_id": device_id, "events": deepcopy(self.store.get_events(device_id)[-limit:])},
        )

    def run_remote_diagnosis(self, device_id: str) -> ToolResult:
        device = self.store.get_device(device_id)
        if not device:
            return ToolResult(ok=False, tool="run_remote_diagnosis", error="unknown_device")

        diagnosis: dict[str, Any]
        if device["device_type"] == "washing_machine" and device.get("last_error") == "5C":
            diagnosis = {
                "code": "5C",
                "likely_cause": "배수 필터 막힘 또는 배수 호스 꺾임",
                "recommendation": "필터/호스 점검 후 재시도",
            }
        elif device["device_type"] == "robot_vacuum" and device.get("suction_health") == "low":
            diagnosis = {
                "filter_warning": True,
                "likely_cause": "필터 오염 또는 브러시 막힘",
                "recommendation": "필터 청소 후 흡입력을 다시 확인",
            }
        elif device["device_type"] == "remote_hub" and device.get("wifi_status") != "connected":
            diagnosis = {
                "network_warning": True,
                "likely_cause": "2.4GHz Wi-Fi 미연결 또는 비밀번호 오류",
                "recommendation": "라우터 2.4GHz 대역과 앱 재연결 확인",
            }
        else:
            diagnosis = {"status": "no_critical_issue"}

        return ToolResult(tool="run_remote_diagnosis", payload={"device_id": device_id, "diagnosis": diagnosis})

    def set_device_setting(self, device_id: str, setting: str, value: Any) -> ToolResult:
        device = self.store.get_device(device_id)
        if not device:
            return ToolResult(ok=False, tool="set_device_setting", error="unknown_device")

        device[setting] = value
        return ToolResult(
            tool="set_device_setting",
            payload={"device_id": device_id, "updated": {setting: value}, "state": deepcopy(device)},
        )

    def create_service_ticket(self, device_id: str, summary: str, severity: str) -> ToolResult:
        if not self.store.get_device(device_id):
            return ToolResult(ok=False, tool="create_service_ticket", error="unknown_device")
        ticket = self.store.create_ticket(device_id, summary, severity)
        return ToolResult(tool="create_service_ticket", payload={"ticket": ticket})

    def update_firmware(self, device_id: str, target_version: str, confirmed: bool = False) -> ToolResult:
        if not confirmed:
            return ToolResult(ok=False, tool="update_firmware", error="confirmation_required")
        device = self.store.get_device(device_id)
        if not device:
            return ToolResult(ok=False, tool="update_firmware", error="unknown_device")
        device["fw"] = target_version
        return ToolResult(tool="update_firmware", payload={"device_id": device_id, "fw": target_version})

    def factory_reset(self, device_id: str, confirmed: bool = False) -> ToolResult:
        if not confirmed:
            return ToolResult(ok=False, tool="factory_reset", error="confirmation_required")
        device = self.store.get_device(device_id)
        if not device:
            return ToolResult(ok=False, tool="factory_reset", error="unknown_device")

        battery = device.get("battery", 1.0)
        preserved = {"device_type": device["device_type"], "model": device["model"], "fw": device["fw"]}
        device.clear()
        device.update(
            {
                **preserved,
                "status": "reset_done",
                "mode": "idle",
                "battery": battery,
                "last_error": None,
            }
        )
        return ToolResult(tool="factory_reset", payload={"device_id": device_id, "status": "reset_done"})
