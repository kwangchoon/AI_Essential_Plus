# Mini Project Skeleton

`day1`의 제품 탑재형 Agent 패턴과 `day2`의 비전/ONNX 패턴을 합쳐서 만든 스켈레톤입니다.

## 구성

- `app.py`
  - SmartHome Care Copilot CLI 진입점
  - `router -> structured plan -> tool calls -> manual search -> confirm/handoff` 흐름을 최소 골격으로 구현
- `agent/`
  - `schemas.py`: Pydantic 기반 구조화 출력/상태 스키마
  - `tools.py`: 더미 디바이스 상태, 이벤트, 원격진단, 티켓 생성, 위험 작업 툴
  - `rag.py`: 매뉴얼 검색 뼈대
  - `data/`: 매뉴얼, 상태, 이벤트, 시나리오, 티켓, 텔레메트리 샘플
- `train.py`
  - `filter_clean vs filter_dirty` 이진 분류 학습 스크립트
- `vision/`
  - `dataset.py`: manifest 기반 데이터셋 로더
  - `train.py`: ResNet18 학습/평가 + demo prediction csv 생성
  - `infer.py`: `predict(image) -> {label, confidence, recommendation}`
  - `export_onnx.py`: ONNX export

## day1/day2 매핑

- `DAY1_00`: 입력 분류와 안전성 체크
- `DAY1_01`: tool loop와 더미 디바이스/티켓 함수 시그니처
- `DAY1_02`: role 기반 툴 접근 개념
- `DAY1_03`: 텔레메트리 샘플 데이터 형식
- `DAY1_04`: Pydantic structured output 뼈대
- `DAY1_05`: 매뉴얼 기반 검색 데이터
- `DAY1_06`: confirm 2턴 / handoff 흐름
- `day2 vision`: train/infer 래핑과 제품형 JSON 출력
- `day2 onnx`: export 스크립트 구조

## 실행 예시

```bash
cd /home/user/lecture/mini_project_skeleton
python app.py --message "세탁기 5C 에러가 떠요. 원격진단하고 조치 알려줘" --role support
python app.py --interactive --role admin
python train.py --epochs 3
python -m vision.infer vision/data/images/val/dirty/dirty_00.png
python export_onnx.py
```

## 비고

- Agent 쪽은 오프라인에서도 동작하는 rule-based skeleton입니다.
- 실제 OpenAI/LangChain/LangGraph 연결은 이 구조 위에 바로 얹을 수 있게 파일을 분리해 두었습니다.
- 비전 데이터는 실전용이 아니라 파이프라인 검증용 synthetic sample입니다.
