# 프로젝트 1 가이드

노트북: [Project1_SmartHome_Care_Copilot_Skeleton.ipynb](/home/user/lecture/project1_agent/Project1_SmartHome_Care_Copilot_Skeleton.ipynb)

## 목표

- 제품 탑재형 고객지원 Agent 흐름을 직접 구현
- `Router -> Structured Output -> Tool Calling -> RAG -> Handoff`
- 위험 작업은 confirm 2턴, role 가드 포함

## 제공 데이터

- `data/devices.json`
- `data/events.json`
- `data/manuals/manual_*.txt`
- `data/scenarios.json`
- `data/tickets.json`
- `data/telemetry_sample.csv`

## 필수 구현 항목

- `DeviceActionPlan`
- `SupportReport`
- `search_manual()`
- `get_device_status()`
- `get_recent_events()`
- `run_remote_diagnosis()`
- `create_service_ticket()`
- `update_firmware()`
- `factory_reset()`
- `build_action_plan()`
- `run_support_turn()`

## 최소 통과 기준

- `세탁기 5C 에러` 시 매뉴얼 근거 + 원격진단 + 조치 제안
- `로봇청소기 흡입이 약해요` 시 필터/브러시 점검 안내
- `앱 연결이 안 돼요` 시 Wi-Fi 관련 안내
- `펌웨어 업데이트 해줘` 시 confirm 2턴 동작
- `탄 냄새/과열` 시 즉시 handoff

## 권장 구현 순서

1. 스키마 정의
2. Manual 검색
3. Tool 함수 작성
4. Router 작성
5. 최종 turn 함수 작성
6. 시나리오 테스트

## 확장 아이디어

- OpenAI structured output으로 `DeviceActionPlan` 파싱
- LangChain tool calling loop
- LangGraph subgraph 분리
