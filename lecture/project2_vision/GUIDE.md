# 프로젝트 2 가이드

노트북: [Project2_Appliance_Vision_Tuning_Skeleton.ipynb](/home/user/lecture/project2_vision/Project2_Appliance_Vision_Tuning_Skeleton.ipynb)

## 목표

- 경량 비전 분류 모델 학습
- `predict(image) -> {label, confidence, recommendation}` 구현
- 10장 inference 테이블 생성
- ONNX export 연결

## 제공 데이터

- `data/manifest.csv`
- `data/images/train/...`
- `data/images/val/...`
- `data/labels.json`

## 필수 구현 항목

- `build_model()`
- `train_one_epoch()`
- `evaluate()`
- `predict()`
- `export_to_onnx()`

## 최소 통과 기준

- `ResNet18` 기반 2-class 분류기 구현
- train / val 로더 실행
- validation accuracy 출력
- val 10장 inference 결과를 DataFrame 또는 CSV로 저장
- `artifacts/filter_classifier.onnx` 생성

## 권장 구현 순서

1. 데이터 확인
2. 모델 정의
3. train loop 작성
4. evaluate 작성
5. predict 작성
6. demo inference 테이블 작성
7. ONNX export

## 확장 아이디어

- confusion matrix 시각화
- onnxruntime 추론 추가
- project1 Agent에 vision 결과 연결
