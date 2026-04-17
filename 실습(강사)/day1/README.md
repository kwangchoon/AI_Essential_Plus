# 1일차 실습(업데이트) — 제품 탑재형 AI 시나리오 버전

본 폴더는 기존 범용 예제를 **로보틱스/스마트 생활가전(제품 탑재형 AI)** 시나리오로 “껍데기”를 입혀 업데이트한 실습 자료입니다.
- 실제 기업 데이터/현업 시스템은 전혀 포함하지 않으며, 모든 문서/로그/정책/기기 상태는 강의용 **더미 데이터**입니다.

---

## 공통 시나리오: 스마트홈 허브 + 생활가전/로봇
학습자는 “제품에 LLM이 어떻게 탑재되는지”를 아래 관점에서 경험합니다.

1) 자연어 요청을 안전하게 **분류/라우팅**  
2) 실행 전 단계에서 **구조화(JSON)/검증**  
3) 실제 실행은 LLM이 아니라 **도구(API/SDK) 호출**로 수행  
4) 근거가 필요한 답변은 **매뉴얼 기반 RAG**로 생성  
5) 위험 작업은 **확인/권한/에스컬레이션**이 필요

---

## 파일 구성
- DAY1_00_Agentic_Prompt_ProductAI_ADV.ipynb  
  요청 라우팅 + 단계별 프롬프트 체인 + Self-check + 모델 게이팅

- DAY1_01_FunctionCalling_ProductAI_ADV.ipynb  
  Function calling으로 기기 제어/원격진단/티켓 생성(더미) + 위험 작업 가드

- DAY1_02_Agents_ProductAI_ADV.ipynb  
  권한(role) 기반 ToolRuntime 가드 + Structured Output + 멀티턴 메모리

- DAY1_03_MultiAgent_Telemetry_ProductAI_ADV.ipynb  
  Fleet 텔레메트리(더미) 분석: Main ↔ DataAnalyst(Python) ↔ Writer ↔ QA

- DAY1_04_StructuredOutput_ProductAI_ADV.ipynb  
  자연어 → (device_control / troubleshooting / manual_info) 스키마로 파싱 + Repair

- DAY1_05_AgenticRAG_Manual_ProductAI_ADV.ipynb  
  매뉴얼/트러블슈팅 문서(더미) 생성 + RAG 에이전트 + 출처 강제

- DAY1_06_LangGraph_ProductAI_ADV.ipynb  
  LangGraph로 Router → (Manual/Control/Troubleshoot/Handoff) 워크플로우 구성

---

## 실행 팁
- 대부분 노트북은 OpenAI API 키가 필요합니다.
- 비용/속도 목적이면 기본 모델을 `gpt-4o-mini`로 두고, 필요한 파트만 큰 모델로 게이팅하세요.
- 기업 보안 환경을 고려해, 외부 데이터 다운로드 없이도 동작하도록 더미 데이터를 노트북 내부에서 생성합니다.