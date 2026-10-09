아래는 논문의 실험·데이터 관련 부분이다. 문장마다 <s id="…">로 id가 붙어 있고, 첨부 이미지는 표다(각 이미지 앞에 표 id가 있다).
자료 범위: {{scope}}

<paper>
<title>{{title}}</title>
{{methods}}
<captions>
{{captions}}
</captions>
</paper>

이 논문의 "데이터 뼈대"를 뽑아라. 독자가 이 연구의 데이터가 정확히 무엇이고 어떻게 검증했는지 한눈에 알게 하는 것이 목적이다.

- applicable: 실험·관측·학습 데이터를 다루는 연구면 true. 이론·리뷰·서베이처럼 데이터가 없으면 false로 하고 not_applicable_reason에 이유를 쓴다(이때 fields는 모두 status "not_applicable").
- fields (각 항목은 value, status, calculation, evidence):
  - inputs: 입력 X. 어떤 측정값·처리 조건·특징이며 단위·수준은 무엇인지 (예: 처리 종류, 농도 수준, 시간).
  - outputs: 출력 y. 무엇을 예측하거나 측정했는지.
  - sample_size: 샘플 수. 원 시료 수, 반복 수, 총 데이터 포인트 수를 **구분해서** 쓴다. 논문이 총 개수를 밝히지 않았으면 실험 설계(조건 수 × 시점 수 × 반복 수 등)로 계산하고 status를 "inferred", calculation에 계산식을 쓴다.
  - validation: 데이터를 어떻게 나누고 검증했는지 (학습·검증·테스트 비율, 교차 검증, 외부 검증 여부, 무엇 단위로 나눴는지).
  - metrics: 평가 지표와 보고된 주요 값.
- status: 논문에 직접 쓰여 있으면 "stated", 논문 내용으로부터 계산·추론했으면 "inferred", 논문에서 찾을 수 없으면 "not_stated"(value는 "논문에 명시 안 됨"). 빈칸을 추측으로 채우지 않는다.
- evidence: 각 항목의 근거. stated와 inferred는 최소 하나. not_stated는 빈 배열.
- warnings: 데이터·검증 방식에서 독자가 조심해야 할 점 0~4개. 예: 샘플 수에 비해 복잡한 모델, 테스트셋이 매우 작음, 같은 시료의 반복 측정값이 학습·테스트에 섞였을 가능성, 외부 검증 없음. 논문 근거가 있는 것만, 단정하지 말고 "~일 수 있다"로.
- questions: 이 연구를 데이터 관점에서 의뢰받는다면 먼저 확인할 질문 2~5개 (명시 안 된 항목과 warnings에서 나온다).
- 값은 짧게, 표처럼 한눈에 보이게 쓴다.
