from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


ROOT = Path("/home/user/lecture")


def md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip() + "\n")


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip() + "\n")


def project1_cells():
    return [
        md(
            """
            # 프로젝트 1. SmartHome Care Copilot

            `day1`의 흐름을 바탕으로 제품 탑재형 고객지원/원격진단 Agent를 직접 구현하는 실습입니다.

            ## 목표
            - `Router -> Structured Output -> Tool Calling -> Manual RAG -> Handoff`를 end-to-end로 연결
            - 위험 작업(`firmware update`, `factory reset`)은 **confirm 2턴** 후에만 실행
            - role(`customer/support/admin`) 기반으로 툴 접근 가드
            - `NO_HIT`일 때는 추가 질문 생성

            ## 필수 산출물
            - `DeviceActionPlan` 또는 `SupportReport` 같은 구조화 스키마
            - 더미 툴 4개 이상
            - 매뉴얼 문서 3종 이상 + 출처 태그 포함 검색
            - 5개 시나리오 테스트 로그
            """
        ),
        md(
            """
            ## 진행 순서

            1. 데이터 로딩
            2. Pydantic 스키마 정의
            3. 매뉴얼 검색 함수 구현
            4. 디바이스/티켓 툴 구현
            5. 의도 분류기(`build_action_plan`) 구현
            6. `run_support_turn()`에서 confirm/handoff/tool loop 연결
            7. 마지막 테스트 셀로 시나리오 검증

            아래 셀에는 `TODO`가 남아 있습니다. 각 TODO를 채운 뒤 테스트 셀을 실행하세요.
            """
        ),
        code(
            """
            # 선택: 최초 1회만 실행
            # %pip install -r ../requirements.txt
            """
        ),
        code(
            """
            from __future__ import annotations

            import json
            import re
            from pathlib import Path
            from typing import Any, Literal, Optional

            import pandas as pd
            from pydantic import BaseModel, Field

            BASE_DIR = Path.cwd()
            DATA_DIR = BASE_DIR / "data"
            MANUAL_DIR = DATA_DIR / "manuals"

            def load_json(path: Path):
                with path.open(encoding="utf-8") as f:
                    return json.load(f)

            devices = load_json(DATA_DIR / "devices.json")
            events = load_json(DATA_DIR / "events.json")
            policies = load_json(DATA_DIR / "policies.json")
            scenarios = load_json(DATA_DIR / "scenarios.json")
            tickets = load_json(DATA_DIR / "tickets.json")

            pd.DataFrame(scenarios)
            """
        ),
        md(
            """
            ## Step 1. Structured Output 스키마 정의

            최소한 아래 두 스키마는 사용하세요.
            - `DeviceActionPlan`: 사용자 발화를 구조화한 중간 표현
            - `SupportReport`: 최종 응답 구조

            필요하면 필드를 더 추가해도 됩니다.
            """
        ),
        code(
            """
            Role = Literal["customer", "support", "admin"]
            Intent = Literal["manual_info", "device_control", "troubleshooting", "handoff"]


            class DeviceActionPlan(BaseModel):
                intent: Intent
                device_id: Optional[str] = None
                device_type: Optional[str] = None
                action: Optional[str] = None
                question: Optional[str] = None
                symptom: Optional[str] = None
                error_code: Optional[str] = None
                safety_risk: bool = False
                confirmed: bool = False
                missing_fields: list[str] = Field(default_factory=list)


            class SupportReport(BaseModel):
                title: str
                intent: Intent
                severity: Literal["low", "medium", "high"]
                reply: str
                evidence: list[str] = Field(default_factory=list)
                recommended_actions: list[str] = Field(default_factory=list)
                follow_up_question: Optional[str] = None
                needs_handoff: bool = False
                needs_confirmation: bool = False
                pending_action: Optional[dict[str, Any]] = None
                ticket: Optional[dict[str, Any]] = None


            SupportReport(
                title="schema_check",
                intent="manual_info",
                severity="low",
                reply="ok",
            )
            """
        ),
        md(
            """
            ## Step 2. 룰 / 헬퍼 정의

            이 셀은 그대로 사용해도 되고, 필요하면 키워드를 더 추가해도 됩니다.
            """
        ),
        code(
            """
            DEVICE_KEYWORDS = {
                "robot_vacuum": ["로봇청소기", "청소기", "vacuum"],
                "washing_machine": ["세탁기", "washer"],
                "air_conditioner": ["에어컨", "aircon", "ac"],
                "remote_hub": ["앱", "와이파이", "wifi", "wi-fi", "허브", "연결"],
            }

            SAFETY_KEYWORDS = ["연기", "과열", "탄 냄새", "타는 냄새", "가스", "누전", "불꽃", "스파크"]
            YES_WORDS = ["예", "네", "응", "확인", "진행", "동의", "yes", "y", "ok"]
            NO_WORDS = ["아니", "아니오", "취소", "중단", "no", "n"]

            DEVICE_ID_RE = re.compile(r"DEV-\\d{4}")
            ERROR_CODE_RE = re.compile(r"\\b[A-Z0-9]{2,5}\\b")


            def detect_device_type(message: str) -> Optional[str]:
                lowered = message.lower()
                for device_type, keywords in DEVICE_KEYWORDS.items():
                    if any(keyword in lowered for keyword in keywords):
                        return device_type
                return None


            def resolve_device_id(device_type: Optional[str]) -> Optional[str]:
                if device_type is None:
                    return None
                for device_id, device in devices.items():
                    if device.get("device_type") == device_type:
                        return device_id
                return None
            """
        ),
        md(
            """
            ## Step 3. Manual RAG 구현

            요구사항:
            - 입력: `query`, `device_type`
            - 출력: `[{citation, text}, ...]` 형태의 리스트
            - citation 예시: `[manual:manual_washer:chunk2]`
            - 검색 결과가 없으면 빈 리스트를 반환
            - `NO_HIT`일 때는 이후 단계에서 추가 질문을 만들 수 있어야 함

            힌트:
            - 가장 단순하게는 토큰 겹침 개수로 점수화해도 충분합니다.
            - 먼저 `manual_*.txt`를 줄 단위로 chunking 해보세요.
            """
        ),
        code(
            """
            def search_manual(query: str, device_type: Optional[str], top_k: int = 3) -> list[dict[str, str]]:
                # TODO:
                # 1) manual_*.txt 파일을 읽는다.
                # 2) device_type에 맞는 매뉴얼만 우선 필터링한다.
                # 3) query와 겹치는 키워드 수로 점수를 만든다.
                # 4) [{"citation": ..., "text": ...}, ...] 형태로 반환한다.
                raise NotImplementedError("search_manual()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 4. 더미 Tool 구현

            필수 후보:
            - `get_device_status(device_id)`
            - `get_recent_events(device_id, limit=3)`
            - `run_remote_diagnosis(device_id)`
            - `set_device_setting(device_id, setting, value)`
            - `create_service_ticket(device_id, summary, severity)`
            - `update_firmware(device_id, target_version, confirmed=False)`
            - `factory_reset(device_id, confirmed=False)`

            반환 형식은 딕셔너리 또는 `ToolResult` 스타일의 딕셔너리로 통일하세요.
            """
        ),
        code(
            """
            def get_device_status(device_id: str) -> dict[str, Any]:
                # TODO: devices.json에서 상태 조회
                raise NotImplementedError


            def get_recent_events(device_id: str, limit: int = 3) -> dict[str, Any]:
                # TODO: events.json에서 최근 이벤트 조회
                raise NotImplementedError


            def run_remote_diagnosis(device_id: str) -> dict[str, Any]:
                # TODO:
                # - washer + 5C -> drain issue
                # - vacuum + suction_health=low -> filter warning
                # - remote_hub + wifi disconnected -> network warning
                raise NotImplementedError


            def set_device_setting(device_id: str, setting: str, value: Any) -> dict[str, Any]:
                # TODO: 비위험 설정 변경
                raise NotImplementedError


            def create_service_ticket(device_id: str, summary: str, severity: str) -> dict[str, Any]:
                # TODO: tickets 리스트에 append할 새 티켓 생성
                raise NotImplementedError


            def update_firmware(device_id: str, target_version: str, confirmed: bool = False) -> dict[str, Any]:
                # TODO: confirmed=False면 confirmation_required 반환
                raise NotImplementedError


            def factory_reset(device_id: str, confirmed: bool = False) -> dict[str, Any]:
                # TODO: confirmed=False면 confirmation_required 반환
                raise NotImplementedError
            """
        ),
        md(
            """
            ## Step 5. Router / Structured Plan 구현

            최소 규칙:
            - 안전 키워드가 있으면 `handoff`
            - 매뉴얼/방법/가이드/설명 요청이면 `manual_info`
            - 에러/증상/안됨/약함/상태 요청이면 `troubleshooting`
            - 업데이트/초기화/온도/모드 변경이면 `device_control`
            - `device_id` 또는 `device_type`이 없으면 `missing_fields`에 기록
            """
        ),
        code(
            """
            def build_action_plan(message: str) -> DeviceActionPlan:
                # TODO:
                # 1) device_id, device_type, error_code 추출
                # 2) intent 분류
                # 3) safety_risk 판정
                # 4) missing_fields 계산
                raise NotImplementedError("build_action_plan()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 6. End-to-End 실행 함수 구현

            요구사항:
            - `run_support_turn(message, role="customer", session_id="demo")`
            - confirm 2턴 필요 시 `SESSIONS[session_id]`에 `pending_action` 저장
            - `customer`는 위험 작업 실행 불가
            - `support/admin`만 `run_remote_diagnosis`, `create_service_ticket` 허용
            - 매뉴얼 검색 결과가 없으면 추가 질문 생성
            - 최종 결과는 `SupportReport`로 반환
            """
        ),
        code(
            """
            SESSIONS: dict[str, Optional[dict[str, Any]]] = {}


            def run_support_turn(message: str, role: Role = "customer", session_id: str = "demo") -> SupportReport:
                # TODO:
                # 1) pending_action이 있으면 yes/no confirm 처리
                # 2) build_action_plan() 호출
                # 3) handoff / manual_info / troubleshooting / device_control 분기
                # 4) evidence, recommended_actions, follow_up_question 조립
                raise NotImplementedError("run_support_turn()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 7. 시나리오 테스트

            아래 5개 시나리오는 반드시 통과하도록 구현하세요.
            """
        ),
        code(
            """
            pd.DataFrame(scenarios)
            """
        ),
        code(
            """
            # TODO 구현 후 실행해보세요.
            #
            # for item in scenarios:
            #     report = run_support_turn(item["input"], role="support", session_id=item["id"])
            #     print("=" * 80)
            #     print(item["id"], item["expected_intent"])
            #     print(report.model_dump())
            """
        ),
        md(
            """
            ## Bonus

            아래 중 하나를 추가하면 `day1` 실습과 더 자연스럽게 이어집니다.
            - OpenAI 응답으로 `DeviceActionPlan`을 파싱
            - LangChain tool calling으로 툴 루프 구현
            - LangGraph로 `router -> manual/control/troubleshoot/handoff` 그래프화
            """
        ),
    ]


def project2_cells():
    return [
        md(
            """
            # 프로젝트 2. Appliance Vision Tuning

            `day2`의 vision / ONNX 흐름을 바탕으로 제품형 상태 판독 모델을 구현하는 실습입니다.

            ## 목표
            - 간단한 이미지 분류 모델 학습
            - `predict(image) -> {label, confidence, recommendation}` 형태로 래핑
            - 검증용 10장 inference 결과 테이블 생성
            - ONNX export까지 연결

            ## 현재 제공 데이터
            - synthetic `filter_clean` / `filter_dirty` 샘플 이미지
            - `manifest.csv`로 train / val split 제공
            """
        ),
        md(
            """
            ## 진행 순서

            1. 데이터 확인
            2. Dataset / DataLoader 준비
            3. `build_model()` 구현
            4. `train_one_epoch()`와 `evaluate()` 구현
            5. `predict()` 구현
            6. 10장 inference 테이블 생성
            7. `export_to_onnx()` 구현

            모델은 `ResNet18`을 권장합니다.
            """
        ),
        code(
            """
            # 선택: 최초 1회만 실행
            # %pip install -r ../requirements.txt
            """
        ),
        code(
            """
            from __future__ import annotations

            import csv
            import json
            import random
            from pathlib import Path

            import numpy as np
            import pandas as pd
            import torch
            from PIL import Image
            from torch import nn
            from torch.utils.data import DataLoader, Dataset
            from torchvision import models, transforms

            BASE_DIR = Path.cwd()
            DATA_DIR = BASE_DIR / "data"
            ARTIFACT_DIR = BASE_DIR / "artifacts"
            ARTIFACT_DIR.mkdir(exist_ok=True)

            manifest = pd.read_csv(DATA_DIR / "manifest.csv")
            manifest.head()
            """
        ),
        code(
            """
            def set_seed(seed: int = 7):
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)


            set_seed(7)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            device
            """
        ),
        md(
            """
            ## Step 1. Dataset / Transform 준비

            이 부분은 그대로 사용해도 됩니다.
            """
        ),
        code(
            """
            LABEL_TO_ID = {"clean": 0, "dirty": 1}
            ID_TO_LABEL = {0: "clean", 1: "dirty"}
            RECOMMENDATIONS = {
                "clean": "필터 상태가 양호합니다. 정기 점검만 유지하세요.",
                "dirty": "필터 오염 가능성이 높습니다. 청소 또는 교체를 권장합니다.",
            }


            def build_transforms(train: bool, image_size: int = 64):
                ops = [transforms.Resize((image_size, image_size))]
                if train:
                    ops.append(transforms.RandomHorizontalFlip())
                ops.extend(
                    [
                        transforms.ToTensor(),
                        transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
                    ]
                )
                return transforms.Compose(ops)


            class ApplianceVisionDataset(Dataset):
                def __init__(self, manifest_df: pd.DataFrame, split: str, image_size: int = 64):
                    self.rows = manifest_df[manifest_df["split"] == split].reset_index(drop=True)
                    self.transform = build_transforms(train=split == "train", image_size=image_size)

                def __len__(self):
                    return len(self.rows)

                def __getitem__(self, index: int):
                    row = self.rows.iloc[index]
                    image = Image.open(DATA_DIR / row["path"]).convert("RGB")
                    image = self.transform(image)
                    label = LABEL_TO_ID[row["label"]]
                    return image, label, row["path"]
            """
        ),
        md(
            """
            ## Step 2. 모델 정의

            요구사항:
            - `ResNet18` 사용
            - 마지막 FC를 2-class 분류기로 교체
            - 반환값은 `torch.nn.Module`
            """
        ),
        code(
            """
            def build_model(num_classes: int = 2) -> nn.Module:
                # TODO:
                # 1) models.resnet18(...) 생성
                # 2) model.fc를 num_classes에 맞게 교체
                raise NotImplementedError("build_model()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 3. 학습 / 평가 루프 구현

            요구사항:
            - `train_one_epoch`: forward, loss, backward, optimizer step
            - `evaluate`: accuracy 계산
            """
        ),
        code(
            """
            def train_one_epoch(model, loader, criterion, optimizer, device):
                # TODO:
                # - model.train()
                # - batch loop
                # - loss 평균 반환
                raise NotImplementedError("train_one_epoch()를 구현하세요.")


            def evaluate(model, loader, device):
                # TODO:
                # - model.eval()
                # - accuracy 계산
                # - 필요하면 prediction 결과도 같이 반환
                raise NotImplementedError("evaluate()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 4. 학습 실행

            TODO 함수들을 구현한 뒤 아래 셀을 실행하세요.
            """
        ),
        code(
            """
            train_dataset = ApplianceVisionDataset(manifest, split="train", image_size=64)
            val_dataset = ApplianceVisionDataset(manifest, split="val", image_size=64)

            train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, num_workers=0)
            val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False, num_workers=0)

            print("train:", len(train_dataset), "val:", len(val_dataset))
            """
        ),
        code(
            """
            # TODO 구현 후 실행하세요.
            #
            # model = build_model(num_classes=2).to(device)
            # criterion = nn.CrossEntropyLoss()
            # optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            #
            # for epoch in range(3):
            #     train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
            #     val_acc = evaluate(model, val_loader, device)
            #     print(f"epoch={epoch+1} train_loss={train_loss:.4f} val_acc={val_acc:.4f}")
            """
        ),
        md(
            """
            ## Step 5. 제품형 JSON 출력 함수 구현

            요구사항:
            - 입력: 이미지 경로
            - 출력: `{label, confidence, recommendation}`
            """
        ),
        code(
            """
            def predict(image_path: str | Path, model, image_size: int = 64) -> dict[str, object]:
                # TODO:
                # 1) 이미지 로드 및 transform
                # 2) softmax confidence 계산
                # 3) recommendation 매핑
                raise NotImplementedError("predict()를 구현하세요.")
            """
        ),
        md(
            """
            ## Step 6. 10장 inference 결과 테이블 생성
            """
        ),
        code(
            """
            # TODO 구현 후 실행하세요.
            #
            # demo_rows = []
            # val_paths = manifest[manifest["split"] == "val"]["path"].tolist()[:10]
            # for rel_path in val_paths:
            #     result = predict(DATA_DIR / rel_path, model, image_size=64)
            #     demo_rows.append({"image_path": rel_path, **result})
            #
            # demo_df = pd.DataFrame(demo_rows)
            # demo_df
            # demo_df.to_csv(ARTIFACT_DIR / "demo_predictions.csv", index=False)
            """
        ),
        md(
            """
            ## Step 7. ONNX Export 구현

            요구사항:
            - `torch.onnx.export`
            - dummy input shape: `(1, 3, 64, 64)`
            - output file: `artifacts/filter_classifier.onnx`
            """
        ),
        code(
            """
            import onnx


            def export_to_onnx(model, output_path: str | Path, image_size: int = 64):
                # TODO:
                # 1) model.eval()
                # 2) dummy_input 생성
                # 3) torch.onnx.export 호출
                # 4) onnx.checker.check_model 검증
                raise NotImplementedError("export_to_onnx()를 구현하세요.")
            """
        ),
        md(
            """
            ## Bonus

            아래 중 하나를 추가하면 `day2` 흐름과 더 잘 이어집니다.
            - confusion matrix 시각화
            - class imbalance 대응
            - `onnxruntime` 추론 코드 추가
            - `predict()` 결과를 Agent 프로젝트의 recommendation 입력으로 연결
            """
        ),
    ]


def write_notebook(path: Path, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, path)


def main():
    write_notebook(
        ROOT / "project1_agent" / "Project1_SmartHome_Care_Copilot_Skeleton.ipynb",
        project1_cells(),
    )
    write_notebook(
        ROOT / "project2_vision" / "Project2_Appliance_Vision_Tuning_Skeleton.ipynb",
        project2_cells(),
    )
    print("Created student project notebooks.")


if __name__ == "__main__":
    main()
