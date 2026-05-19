import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import os
import html as _html
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
당신은 "AI 인생 시나리오 플래너"의 핵심 분석 엔진입니다.

<role>
당신은 한국 직장인의 커리어·재무·생애설계를 통합 분석하는 15년차 커리어 전략가 + 사업 멘토입니다.
- 직설적이지만 인격을 존중하는 코치 톤
- 막연한 격려·일반론·과장된 낙관을 배제하고, 입력 데이터에 근거한 현실적 시나리오만 제시
- 한국어 존댓말 기본, 시나리오 내부 문장은 단정형(~한다, ~이다)으로 작성
</role>

<context>
- 제품: 사용자 15개 항목 입력 → 현실형/도전형/파격형 3가지 인생 시나리오 + 선택 시나리오의 실행 계획 생성
- 호출 환경: Python Streamlit 앱에서 Google Gemini API(gemini-2.5-flash)로 호출, 응답은 json.loads()로 즉시 파싱
- 입력 전달 방식: 사용자 응답 15개가 user 메시지에 키-값 형태(Q1~Q15)로 포함되어 들어옵니다. 누락된 항목이 있으면 해당 항목을 명시적으로 "입력 없음"으로 처리하고 그 항목은 시나리오 근거로 사용하지 마십시오.
- 운영 제약: API 응답은 반드시 단일 JSON 객체 한 개. 다른 문자(코드펜스, 설명, 주석, BOM, 공백 줄바꿈 외 텍스트) 절대 금지.
- 모델: gemini-2.5-flash (무료 티어 우선). 시나리오 품질이 부족할 경우 gemini-2.5-pro로 교체 가능(무료 한도 상이, 동일 프롬프트 호환).
- JSON 안정성: Python 호출 시 response_mime_type="application/json" 및 temperature=0.7 설정 권장 (아래 implementation_note 참조).
</context>

<input_schema>
전달 형식: user 메시지는 아래 평문 형태로 전달됩니다.
  Q1: [값]
  Q2: [값]
  ...
  Q15: [값]

income 기준: 모든 수입 수치는 만원/년(연소득) 기준 정수. 월소득이 아님에 주의.

누락 처리: 항목 값이 비어있거나 "입력 없음"이면 해당 항목은 시나리오 근거에서
제외하고 그 항목을 출력 JSON 근거로 반영하지 않음.

입력 15개 항목 정의:
- Q1 현재 직업·역할 (text)
- Q2 현 상황 만족도 1~10 (int)
- Q3 버틸 수 있는 기간 ∈ {3개월 미만, 6개월, 1년, 1년 이상}
- Q4 돈 받고 팔 수 있는 기술 (text)
- Q5 매달 저축 가능 금액 ∈ {없음, 50만 미만, 50~150만, 150만 이상}
- Q6 가족의 지지 ∈ {강하게 반대, 중립, 지지, 적극 응원}
- Q7 절대 포기할 수 없는 것 (text)
- Q8 가장 두려운 것 (text) ← 시나리오마다 반드시 직접 인용
- Q9 롤모델·닮고 싶은 삶 (text)
- Q10 10년 후 목표 (text)
- Q11 죽기 전 반드시 할 일 (text)
- Q12 5년 전과 달라진 점 (text)
- Q13 현재 가장 큰 고민 (text) ← 최종 메시지에 반드시 직접 인용
- Q14 지금 바꿀 수 있는 것 (text)
- Q15 리포트 보고 첫 행동 (text)
</input_schema>

<task>
다음 순서로 처리합니다.

1단계: 입력 분석
- Q1·Q4(직업/기술)에서 현실적 수입 베이스라인을 추정합니다 (아래 income_rules 참조)
- Q3·Q5·Q6(시간/돈/가족) 3개 변수로 리스크 허용 범위를 결정합니다
- Q8(두려움), Q13(고민)을 시나리오 갈등 축으로 삼습니다
- Q7(포기 불가), Q10(목표), Q11(버킷리스트)을 보상 축으로 삼습니다

2단계: 3가지 시나리오 생성
- 현실형(color: blue): 현 직업 유지·점진 성장. 리스크 최소.
- 도전형(color: green): 부업·이직·소규모 전환. 중간 리스크.
- 파격형(color: purple): 창업·업종 전환·이주. 고리스크 고보상.
각 시나리오는 아래 scenario_requirements를 빠짐없이 충족해야 합니다.

3단계: 추천 산정
- 1차 기준: Q3·Q5·Q6의 안전마진과 Q8 두려움의 강도를 비교해 한 시나리오를 추천합니다.
- 2차 기준(보조): Q10(목표)이 각 시나리오에서 도달 가능한 정도를 보조 지표로 사용합니다
  (목표 도달 가능성이 높은 시나리오에 가중치 부여).
- 두 기준이 충돌할 경우 1차 기준(안전마진)을 우선합니다.
- 추천 이유 3문장은 반드시 Q3·Q5·Q6·Q8 중 ***최소 3개를 명시적으로 인용***합니다.

4단계: 자가 검증(출력 직전)
- 두려움(Q8)이 3개 시나리오 fear_response에 모두 직접 인용되었는가?
- 직업(Q1) 또는 기술(Q4) 명사가 3개 시나리오 description에 모두 등장하는가?
- income 배열이 5개 정수이고, 1년→10년 사이 단조 비현실적 변동(예: 10배 점프)이 없는가?
- next_steps의 must_prepare가 Q5(자금)·Q4(기술)·Q6(가족) 중 최소 2개를 반영했는가?
- JSON 구조가 schema와 일치하는가?
하나라도 위반이면 내부적으로 재작성한 뒤 통과한 결과만 출력합니다.
</task>

<scenario_requirements>
각 시나리오는 다음을 ***모두*** 포함합니다.
1. title: 드라마틱하지만 직군 정체성이 드러나는 6~12자 한국어 제목
2. description: 정확히 2문장. ***Q1 직업 또는 Q4 기술을 1개 이상 직접 언급***.
3. milestones: 1y/3y/5y/10y 각 한 문장. 각 문장에 ***구체 숫자***(금액·인원·횟수·% 중 하나) 1개 이상 포함.
4. income: [현재, 1년, 3년, 5년, 10년] 정수 5개(단위: 만원/년). income_rules 준수.
5. fear_response: Q8 원문을 큰따옴표로 직접 인용한 뒤, 이 시나리오에서 그 두려움이 어떻게 다뤄지는지 2문장 분석.
6. tradeoff: gain 1문장 / lose 1문장. 추상어 금지(예: "성장" X → "주말 사용 가능 시간 8시간 감소" O).
7. tags: 2~3개. 명사형 짧은 태그(예: "안정", "스킬 레버리지", "고변동").
</scenario_requirements>

<income_rules>
- 현재값: Q1 직업·연차 기반 한국 시장 평균 범위로 추정. 명시된 연차/규모 단서가 없으면 보수적 중앙값 사용.
- 변동폭 가이드: 현실형은 연 3~8% 상승, 도전형은 1~2년 정체 또는 감소 후 회복, 파격형은 1~2년 큰 하락 후 5년 차에 현재 대비 ±50% 범위.
- Q5(저축 가능액)가 "없음" 또는 "50만 미만"인 경우 파격형 income 1년 차에 30% 이상 하락 금지(생존 불가 시나리오 회피).
- 비현실적 점프(10배 이상) 절대 금지. 모든 값은 만원 단위 정수.
</income_rules>

<next_steps_requirements>
선택 시나리오의 next_steps는 ***해당 시나리오 1개에 대해서만*** 생성하는 것이 아니라, 3개 시나리오 모두에 대해 각각 채워둡니다(사용자가 어느 것을 선택해도 즉시 표시 가능하도록).

- this_week: 2개. 오늘·이번 주 안에 완료 가능한 동사형 행동.
- one_month: 3개. Q5(자금)·Q4(기술)·Q6(가족) 중 최소 2개 변수를 반영.
- three_months: 2개. 측정 가능한 결과물 포함(예: "포트폴리오 3건 완성").
- must_prepare: 3개. 자금/스킬/관계/시간 중에서 균형 있게.
- must_avoid: 2개. 이 시나리오 유형에서 실제로 흔한 실패 패턴.
- coach_message: 2~3문장. Q13(고민) 또는 Q8(두려움) 또는 Q10(목표) 중 ***최소 2개를 직접 인용***.
</next_steps_requirements>

<output_format>
응답은 아래 JSON 한 개만. 코드펜스·설명·공백 줄바꿈 외 어떤 문자도 추가 금지.
모든 키는 영문, 값은 한국어(income 배열만 정수).

{
  "summary": {
    "insight": "15개 입력 종합 핵심 인사이트 2문장. 입력값 명사를 2개 이상 직접 언급.",
    "conflict": "사용자가 직면한 핵심 갈등 1문장."
  },
  "scenarios": [
    {
      "type": "현실형",
      "color": "blue",
      "title": "",
      "description": "",
      "milestones": { "1y": "", "3y": "", "5y": "", "10y": "" },
      "income": [0, 0, 0, 0, 0],
      "tags": [],
      "fear_response": "",
      "tradeoff": { "gain": "", "lose": "" },
      "next_steps": {
        "this_week": ["", ""],
        "one_month": ["", "", ""],
        "three_months": ["", ""],
        "must_prepare": ["", "", ""],
        "must_avoid": ["", ""],
        "coach_message": ""
      }
    },
    {
      "type": "도전형",
      "color": "green",
      "title": "",
      "description": "",
      "milestones": { "1y": "", "3y": "", "5y": "", "10y": "" },
      "income": [0, 0, 0, 0, 0],
      "tags": [],
      "fear_response": "",
      "tradeoff": { "gain": "", "lose": "" },
      "next_steps": {
        "this_week": ["", ""],
        "one_month": ["", "", ""],
        "three_months": ["", ""],
        "must_prepare": ["", "", ""],
        "must_avoid": ["", ""],
        "coach_message": ""
      }
    },
    {
      "type": "파격형",
      "color": "purple",
      "title": "",
      "description": "",
      "milestones": { "1y": "", "3y": "", "5y": "", "10y": "" },
      "income": [0, 0, 0, 0, 0],
      "tags": [],
      "fear_response": "",
      "tradeoff": { "gain": "", "lose": "" },
      "next_steps": {
        "this_week": ["", ""],
        "one_month": ["", "", ""],
        "three_months": ["", ""],
        "must_prepare": ["", "", ""],
        "must_avoid": ["", ""],
        "coach_message": ""
      }
    }
  ],
  "recommendation": {
    "type": "현실형 | 도전형 | 파격형 중 하나",
    "reason": "3문장. Q3·Q5·Q6·Q8 중 최소 3개 직접 인용.",
    "badge": "AI 추천"
  },
  "final_message": "3~4문장. Q13(고민)·Q10(목표)·Q8(두려움) 모두 직접 인용."
}
</output_format>

<forbidden>
- "열심히 하세요", "할 수 있습니다", "꿈은 이루어진다" 등 자기계발 클리셰
- 입력값을 인용하지 않는 일반론
- JSON 외 어떤 텍스트(인사말·"네 알겠습니다"·후기·코드펜스 ```json 포함)
- income 임의 숫자(근거 규칙 위반)
- 시나리오 type/color 변경
- 영어 시나리오 제목 또는 영어 본문(태그 제외)
</forbidden>

<implementation_note>
이 시스템 프롬프트는 아래 Python generation_config와 함께 사용할 때
JSON 파싱 안정성이 최대화됩니다.
forbidden의 "코드펜스 금지" 규칙을 모델이 어기더라도
API 단에서 자동 차단되어 json.loads 실패가 거의 사라집니다.
구체적인 Python 구현은 PART 2 코드를 참조하십시오.
</implementation_note>

이제 사용자가 user 메시지로 Q1~Q15를 제공할 때까지 대기합니다. 입력이 도착하면 위 절차대로 단 하나의 JSON을 반환합니다.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {
                "insight":  {"type": "string"},
                "conflict": {"type": "string"}
            },
            "required": ["insight", "conflict"]
        },
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type":        {"type": "string"},
                    "color":       {"type": "string"},
                    "title":       {"type": "string"},
                    "description": {"type": "string"},
                    "milestones": {
                        "type": "object",
                        "properties": {
                            "1y":  {"type": "string"},
                            "3y":  {"type": "string"},
                            "5y":  {"type": "string"},
                            "10y": {"type": "string"}
                        },
                        "required": ["1y", "3y", "5y", "10y"]
                    },
                    "income": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "fear_response": {"type": "string"},
                    "tradeoff": {
                        "type": "object",
                        "properties": {
                            "gain": {"type": "string"},
                            "lose": {"type": "string"}
                        },
                        "required": ["gain", "lose"]
                    },
                    "next_steps": {
                        "type": "object",
                        "properties": {
                            "this_week": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "one_month": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "three_months": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "must_prepare": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "must_avoid": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "coach_message": {"type": "string"}
                        },
                        "required": [
                            "this_week", "one_month", "three_months",
                            "must_prepare", "must_avoid", "coach_message"
                        ]
                    }
                },
                "required": [
                    "type", "color", "title", "description",
                    "milestones", "income", "tags", "fear_response",
                    "tradeoff", "next_steps"
                ]
            }
        },
        "recommendation": {
            "type": "object",
            "properties": {
                "type":   {"type": "string"},
                "reason": {"type": "string"},
                "badge":  {"type": "string"}
            },
            "required": ["type", "reason", "badge"]
        },
        "final_message": {"type": "string"}
    },
    "required": ["summary", "scenarios", "recommendation", "final_message"]
}

PROFILE_PATH = "profile.json"

Q3_OPTIONS = ["3개월 미만", "6개월", "1년", "1년 이상"]
Q5_OPTIONS = ["없음", "50만 미만", "50~150만", "150만 이상"]
Q6_OPTIONS = ["강하게 반대", "중립", "지지", "적극 응원"]
INCOME_OPTIONS = [
    "직접 입력 안 함",
    "연봉 3천만원 미만",
    "연봉 3천~5천만원",
    "연봉 5천만원~1억원",
    "연봉 1억원 이상",
    "월급 200만원 미만",
    "월급 200~400만원",
    "월급 400~600만원",
    "월급 600만원 이상",
    "직접 입력",
]

QUESTIONS = [
    {"key": "Q1",     "label": "Q1. 현재 직업·역할",           "type": "text",          "placeholder": "예) 중소기업 영업부장 15년차, 프리랜서 디자이너 10년차"},
    {"key": "INCOME", "label": "현재 연봉 또는 월급",           "type": "income_select", "options": INCOME_OPTIONS},
    {"key": "Q2",     "label": "Q2. 현 상황 만족도",           "type": "slider"},
    {"key": "Q3",  "label": "Q3. 버틸 수 있는 기간",        "type": "select",   "options": Q3_OPTIONS},
    {"key": "Q4",  "label": "Q4. 돈 받고 팔 수 있는 기술",  "type": "text",     "placeholder": "예) 영업·협상 경험, 엑셀·데이터 분석, 콘텐츠 기획"},
    {"key": "Q5",  "label": "Q5. 매달 저축 가능 금액",      "type": "select",   "options": Q5_OPTIONS},
    {"key": "Q6",  "label": "Q6. 가족의 지지",              "type": "select",   "options": Q6_OPTIONS},
    {"key": "Q7",  "label": "Q7. 절대 포기할 수 없는 것",   "type": "text",     "placeholder": "예) 가족과의 저녁 시간, 주말 취미 생활, 건강 관리"},
    {"key": "Q8",  "label": "Q8. 가장 두려운 것",           "type": "text",     "placeholder": "예) 50대에 직장 잃는 것, 노후 준비 없이 나이 드는 것"},
    {"key": "Q9",  "label": "Q9. 롤모델·닮고 싶은 삶",      "type": "text",     "placeholder": "예) 자기 회사 차린 선배, 자유롭게 일하는 프리랜서 지인"},
    {"key": "Q10", "label": "Q10. 10년 후 목표",            "type": "text",     "placeholder": "예) 내 회사 운영, 안정적인 부업 수입 월 300만, 조기 은퇴"},
    {"key": "Q11", "label": "Q11. 죽기 전 반드시 할 일",    "type": "text",     "placeholder": "예) 세계여행, 책 한 권 출판, 자녀 결혼 다 시키기"},
    {"key": "Q12", "label": "Q12. 5년 전과 달라진 점",      "type": "text",     "placeholder": "예) 이직 2번 했음, 아이가 생겼음, 부모님 간병 시작"},
    {"key": "Q13", "label": "Q13. 현재 가장 큰 고민",       "type": "text",     "placeholder": "예) 지금 직장 계속 다닐지 이직할지 모르겠다"},
    {"key": "Q14", "label": "Q14. 지금 바꿀 수 있는 것",    "type": "text",     "placeholder": "예) 퇴근 후 유튜브 보는 2시간을 자기계발로 바꾸기"},
    {"key": "Q15", "label": "Q15. 리포트 보고 첫 행동",     "type": "text",     "placeholder": "예) 통장 잔액 확인, 이직 사이트 둘러보기, 지인에게 연락"},
]


def get_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.7
    )
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config
    )


def build_user_message(inputs: dict, correction: str = "") -> str:
    lines = []
    for i in range(1, 16):
        key = f"Q{i}"
        value = inputs.get(key, "입력 없음")
        lines.append(f"Q{i}: {value}")
        if i == 1:
            income_sel = inputs.get("INCOME_SELECT", "직접 입력 안 함")
            income_txt = inputs.get("INCOME_TEXT", "")
            if income_sel == "직접 입력" and income_txt:
                lines.append(f"현재 소득: {income_txt}")
            elif income_sel not in ("직접 입력 안 함", "직접 입력", ""):
                lines.append(f"현재 소득: {income_sel}")
    msg = "\n".join(lines)
    if correction and correction.strip():
        msg += (
            "\n\n===수정 요청===\n"
            "사용자가 아래 내용이 실제와 다르다고 합니다.\n"
            "이를 반영해서 시나리오를 다시 작성해주세요:\n"
            + correction.strip()
        )
    return msg


def generate_scenarios(inputs: dict, correction: str = "") -> dict:
    model = get_model()
    if model is None:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    user_message = build_user_message(inputs, correction)
    response = model.generate_content(user_message)
    return json.loads(response.text)


def save_profile(inputs: dict):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(inputs, f, ensure_ascii=False, indent=2)


def load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def init_session():
    if "inputs" not in st.session_state:
        st.session_state.inputs = {}
    if "result" not in st.session_state:
        st.session_state.result = None
    if "page" not in st.session_state:
        st.session_state.page = "input"


def _e(s):
    return _html.escape(str(s) if s is not None else "")


def _nl2br(s):
    return _e(s).replace("\n", "<br>")


def _li(lst):
    return "".join(f"<li>{_e(x)}</li>" for x in (lst or []))


def build_result_html(result: dict, inputs: dict) -> str:
    summary      = result.get("summary", {})
    scenarios    = result.get("scenarios", [])
    rec          = result.get("recommendation", {})
    final_msg    = result.get("final_message", "")
    rec_type     = rec.get("type", "")

    COLOR_CLS  = {"blue": "r", "green": "c", "purple": "p"}
    COLOR_VAR  = {"blue": "blue", "green": "green", "purple": "purple"}

    # ── badges
    badges = ""
    if inputs.get("Q1") not in (None, "입력 없음"):
        badges += f'<div class="bdg">직업 <b>{_e(inputs["Q1"])}</b></div>'
    if inputs.get("Q2") not in (None, "입력 없음"):
        badges += f'<div class="bdg">만족도 <b>{_e(inputs["Q2"])} / 10</b></div>'
    if inputs.get("Q3") not in (None, "입력 없음"):
        badges += f'<div class="bdg">버틸 수 있는 기간 <b>{_e(inputs["Q3"])}</b></div>'
    if inputs.get("Q6") not in (None, "입력 없음"):
        badges += f'<div class="bdg">가족 지지 <b>{_e(inputs["Q6"])}</b></div>'

    # ── cards + panels
    cards_html  = ""
    panels_html = ""
    inc = {"r": [0]*5, "c": [0]*5, "p": [0]*5}

    for i, sc in enumerate(scenarios):
        color    = sc.get("color", "blue")
        cls      = COLOR_CLS.get(color, "r")
        cvar     = COLOR_VAR.get(color, "blue")
        sc_type  = sc.get("type", "")
        is_rec   = (sc_type == rec_type)

        inc[cls] = sc.get("income", [0]*5)

        tags_html = "".join(f'<span class="tag">{_e(t)}</span>' for t in sc.get("tags", []))

        ms = sc.get("milestones", {})
        tl_rows = ""
        for yr, lbl in [("1y","1년"),("3y","3년"),("5y","5년"),("10y","10년")]:
            tl_rows += (f'<div class="tl-row">'
                        f'<span class="tl-yr">{lbl}</span>'
                        f'<span class="tl-tx">{_e(ms.get(yr,""))}</span>'
                        f'</div>')

        trf = sc.get("tradeoff", {})
        ai_bdg     = '<span class="ai-bdg">🤖 AI 추천</span>' if is_rec else ""
        rec_border = f' style="border-color:var(--{cvar})"' if is_rec else ""

        cards_html += f"""
  <div class="card card-{cls}" id="card-{i}"{rec_border}>
    <div class="card-top"><span class="type-lbl">{_e(sc_type)}</span>{ai_bdg}</div>
    <div class="card-title">{_e(sc.get("title",""))}</div>
    <div class="card-desc">{_nl2br(sc.get("description",""))}</div>
    <div class="tags">{tags_html}</div>
    <div class="tl-hd">마일스톤</div>
    <div class="tl">{tl_rows}</div>
    <div class="fear">
      <div class="fear-hd">두려움 분석</div>
      <div class="fear-tx">{_nl2br(sc.get("fear_response",""))}</div>
    </div>
    <div class="trf">
      <div class="trf-box trf-g">{_e(trf.get("gain",""))}</div>
      <div class="trf-box trf-l">{_e(trf.get("lose",""))}</div>
    </div>
    <button class="sel-btn" onclick="pick({i})">이 시나리오 선택</button>
  </div>"""

        ns = sc.get("next_steps", {})
        panels_html += f"""
    <div class="panel panel-{cls}" id="panel-{i}">
      <div class="panel-inner">
        <div class="pg">
          <div class="pb" style="--ic:'✅'"><h4>이번 주 바로 할 것</h4><ul>{_li(ns.get("this_week"))}</ul></div>
          <div class="pb" style="--ic:'📌'"><h4>1개월 내 준비 사항</h4><ul>{_li(ns.get("one_month"))}</ul></div>
          <div class="pb" style="--ic:'🎯'"><h4>3개월 내 이룰 것</h4><ul>{_li(ns.get("three_months"))}</ul></div>
          <div class="pb" style="--ic:'⭐'"><h4>반드시 갖춰야 할 것</h4><ul>{_li(ns.get("must_prepare"))}</ul></div>
        </div>
        <div class="avoid-wrap">
          <h4>반드시 피해야 할 것</h4>
          <ul>{_li(ns.get("must_avoid"))}</ul>
        </div>
        <div class="coach">
          <div class="coach-lbl">AI 코치 한 마디</div>
          <div class="coach-tx">{_nl2br(ns.get("coach_message",""))}</div>
        </div>
      </div>
    </div>"""

    # ── chart data
    max_inc = max(max(inc["r"]), max(inc["c"]), max(inc["p"]), 1)

    CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b27;--border:#1f2a3c;--text:#e2e8f0;--muted:#8892a4;
  --blue:#3b82f6;--blue-dark:#1e3a5f;--blue-dim:#0f1e33;
  --green:#10b981;--green-dark:#0d3d2a;--green-dim:#081e14;
  --purple:#8b5cf6;--purple-dark:#2d1b5e;--purple-dim:#16102e;
}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;min-height:100vh;padding:28px 20px 64px;line-height:1.6}
.wrap{max-width:1400px;margin:0 auto}
.hdr{background:var(--surface);border:1px solid var(--border);border-top:2px solid var(--blue);border-radius:12px;padding:28px 32px;margin-bottom:20px}
.hdr-row{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:18px}
.hdr-title{font-size:22px;font-weight:800;letter-spacing:-0.3px;color:#f1f5f9}
.hdr-title span{color:var(--blue)}
.badges{display:flex;flex-wrap:wrap;gap:6px}
.bdg{background:#1a2235;border:1px solid #2a3650;border-radius:6px;padding:4px 10px;font-size:11px;color:var(--muted)}
.bdg b{color:#cbd5e1;font-weight:600}
.insight{font-size:13.5px;line-height:1.85;color:#94a3b8;padding:14px 18px;background:#111827;border-radius:8px;border-left:3px solid var(--blue);margin-bottom:12px}
.conflict{font-size:13px;color:#fbbf24;padding:10px 16px;background:#1c1507;border:1px solid #3d2d0a;border-radius:8px}
.conflict::before{content:"⚡ ";font-weight:700}
.cards-outer{margin-bottom:20px}
.cards-row{display:grid;grid-template-columns:1fr;gap:16px}
@media(min-width:768px){.cards-row{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1280px){.cards-row{grid-template-columns:repeat(3,1fr)}}
.card{border-radius:12px;padding:22px;display:flex;flex-direction:column;gap:12px;transition:transform .2s,box-shadow .2s;cursor:default;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;inset:0;opacity:.04;background:radial-gradient(ellipse at top left,#fff,transparent 70%);pointer-events:none}
.card-r{background:var(--blue-dim);border:1px solid #1d3557}
.card-c{background:var(--green-dim);border:1px solid #0e3728}
.card-p{background:var(--purple-dim);border:1px solid #261648}
.card:hover{transform:translateY(-3px)}
.card-r:hover{box-shadow:0 12px 40px rgba(59,130,246,0.18)}
.card-c:hover{box-shadow:0 12px 40px rgba(16,185,129,0.18)}
.card-p:hover{box-shadow:0 12px 40px rgba(139,92,246,0.18)}
.card.active.card-r{border-color:var(--blue);box-shadow:0 0 0 2px var(--blue),0 12px 40px rgba(59,130,246,0.25)}
.card.active.card-c{border-color:var(--green);box-shadow:0 0 0 2px var(--green),0 12px 40px rgba(16,185,129,0.25)}
.card.active.card-p{border-color:var(--purple);box-shadow:0 0 0 2px var(--purple),0 12px 40px rgba(139,92,246,0.25)}
.card-r{--c:var(--blue);--cd:var(--blue-dark);--ct:#1d3557}
.card-c{--c:var(--green);--cd:var(--green-dark);--ct:#0e3728}
.card-p{--c:var(--purple);--cd:var(--purple-dark);--ct:#261648}
.card-top{display:flex;align-items:center;justify-content:space-between}
.type-lbl{font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--c);background:var(--cd);border:1px solid var(--ct);padding:3px 10px;border-radius:4px}
.ai-bdg{background:var(--green);color:#fff;font-size:10px;font-weight:800;padding:3px 10px;border-radius:4px;letter-spacing:.3px}
.card-title{font-size:18px;font-weight:800;color:#f1f5f9;letter-spacing:-.3px}
.card-desc{font-size:13px;line-height:1.8;color:#94a3b8}
.tags{display:flex;flex-wrap:wrap;gap:5px}
.tag{background:var(--cd);color:var(--c);border:1px solid var(--ct);border-radius:4px;padding:2px 9px;font-size:10px;font-weight:700;letter-spacing:.3px}
.tl-hd{font-size:9px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.tl{display:flex;flex-direction:column;gap:1px;position:relative;padding-left:20px}
.tl::before{content:"";position:absolute;left:4px;top:6px;bottom:6px;width:1px;background:linear-gradient(to bottom,var(--c),transparent)}
.tl-row{display:flex;gap:8px;align-items:flex-start;padding:4px 0;position:relative}
.tl-row::before{content:"";position:absolute;left:-16px;top:9px;width:7px;height:7px;border-radius:50%;background:var(--c);box-shadow:0 0 0 2px var(--bg)}
.tl-yr{font-size:10px;font-weight:800;color:var(--c);min-width:26px;padding-top:1px}
.tl-tx{font-size:12px;color:#94a3b8;line-height:1.6}
.fear{background:var(--cd);border-left:3px solid var(--c);border-radius:0 8px 8px 0;padding:10px 14px}
.fear-hd{font-size:9px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--c);margin-bottom:5px}
.fear-tx{font-size:12px;line-height:1.75;color:#94a3b8;font-style:italic}
.trf{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.trf-box{padding:9px 11px;border-radius:7px;font-size:12px;line-height:1.65}
.trf-g{background:#041d10;border:1px solid #0d3d22;color:#6ee7b7}
.trf-g::before{content:"▲ 얻는 것\A";white-space:pre;font-size:9px;font-weight:800;letter-spacing:.5px;color:#10b981;text-transform:uppercase}
.trf-l{background:#1a0a00;border:1px solid #3d1a00;color:#fdba74}
.trf-l::before{content:"▼ 잃는 것\A";white-space:pre;font-size:9px;font-weight:800;letter-spacing:.5px;color:#f97316;text-transform:uppercase}
.sel-btn{margin-top:auto;padding:11px;border:1px solid var(--c);background:transparent;color:var(--c);border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s;width:100%;letter-spacing:.3px}
.sel-btn:hover,.sel-btn.on{background:var(--c);color:#0d1117}
.panel-wrap{grid-column:1/-1}
.panel{overflow:hidden;max-height:0;transition:max-height .5s cubic-bezier(.4,0,.2,1),opacity .35s;opacity:0}
.panel.open{max-height:3000px;opacity:1}
.panel-inner{border-radius:12px;padding:26px;margin-top:4px;border:1px solid}
.panel-r .panel-inner{background:#0a1220;border-color:#1d3557}
.panel-c .panel-inner{background:#071410;border-color:#0e3728}
.panel-p .panel-inner{background:#0e0c1e;border-color:#261648}
.pg{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:14px}
.pb h4{font-size:9px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
.pb ul{list-style:none;display:flex;flex-direction:column;gap:6px}
.pb li{font-size:12.5px;line-height:1.65;color:#94a3b8;padding-left:20px;position:relative}
.pb li::before{content:var(--ic);position:absolute;left:0;top:0}
.avoid-wrap{background:#130a08;border:1px solid #3d1207;border-radius:8px;padding:14px 16px;margin-bottom:14px}
.avoid-wrap h4{font-size:9px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:#f87171;margin-bottom:8px}
.avoid-wrap ul{list-style:none;display:flex;flex-direction:column;gap:6px}
.avoid-wrap li{font-size:12.5px;line-height:1.65;color:#fca5a5;padding-left:20px;position:relative}
.avoid-wrap li::before{content:"✕";position:absolute;left:2px;top:0;color:#ef4444;font-weight:700}
.coach{border-radius:8px;padding:16px 18px;border:1px solid}
.panel-r .coach{background:#0a1525;border-color:#1d3557}
.panel-c .coach{background:#061410;border-color:#0e3728}
.panel-p .coach{background:#0c0a1c;border-color:#261648}
.coach-lbl{font-size:9px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
.panel-r .coach-lbl{color:var(--blue)}
.panel-c .coach-lbl{color:var(--green)}
.panel-p .coach-lbl{color:var(--purple)}
.coach-tx{font-size:13.5px;line-height:1.9;font-style:italic;color:#cbd5e1}
.panel-r .pb h4{color:var(--blue)}
.panel-c .pb h4{color:var(--green)}
.panel-p .pb h4{color:var(--purple)}
.sec{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px}
.sec-title{font-size:14px;font-weight:800;color:#f1f5f9;margin-bottom:16px;display:flex;align-items:center;gap:10px;letter-spacing:-.2px}
.sec-title i{display:inline-block;width:3px;height:16px;border-radius:2px;background:linear-gradient(180deg,var(--blue),var(--purple))}
.legend{display:flex;gap:18px;margin-bottom:14px}
.li{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);font-weight:600}
.ld{width:10px;height:10px;border-radius:2px}
.chart-sc{overflow-x:auto}
.chart{display:flex;align-items:flex-end;justify-content:space-around;height:200px;gap:4px;padding:0 8px;min-width:360px}
.cg{display:flex;flex-direction:column;align-items:center;gap:7px;flex:1}
.bars{display:flex;gap:4px;align-items:flex-end;height:170px}
.bar{width:22px;border-radius:4px 4px 0 0;cursor:pointer;position:relative;transition:filter .2s}
.bar:hover{filter:brightness(1.3)}
.bar:hover::after{content:attr(data-v)"만";position:absolute;top:-24px;left:50%;transform:translateX(-50%);background:#1e293b;color:#f1f5f9;padding:2px 7px;border-radius:4px;font-size:10px;white-space:nowrap;border:1px solid #334155;pointer-events:none}
.bar-r{background:linear-gradient(180deg,#60a5fa,#1d4ed8)}
.bar-c{background:linear-gradient(180deg,#34d399,#065f46)}
.bar-p{background:linear-gradient(180deg,#c084fc,#6d28d9)}
.cl{font-size:11px;color:var(--muted);font-weight:600;text-align:center}
.cu{text-align:right;font-size:10px;color:#4b5563;margin-top:6px}
.final{background:linear-gradient(135deg,var(--blue-dark) 0%,#1a1040 50%,var(--green-dark) 100%);border:1px solid #2d3f5e;border-radius:12px;padding:32px;margin-bottom:20px;text-align:center}
.final-lbl{font-size:9px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:var(--blue);margin-bottom:14px}
.final-tx{font-size:15px;line-height:2;color:#cbd5e1;max-width:760px;margin:0 auto}
.rec{background:var(--green-dim);border:1px solid #0e3728;border-radius:12px;padding:24px}
.rec-lbl{font-size:9px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:var(--green);margin-bottom:10px}
.rec-tx{font-size:13.5px;line-height:1.95;color:#6ee7b7}
"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 인생 시나리오 리포트</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div class="hdr-row">
    <div class="hdr-title"><span>AI</span> 인생 시나리오 리포트</div>
    <div class="badges">{badges}</div>
  </div>
  <div class="insight">{_nl2br(summary.get("insight",""))}</div>
  <div class="conflict">{_e(summary.get("conflict",""))}</div>
</div>

<div class="cards-outer">
<div class="cards-row" id="cardsRow">
{cards_html}
  <div class="panel-wrap">
{panels_html}
  </div>
</div>
</div>

<div class="sec">
  <div class="sec-title"><i></i>수입 변화 시뮬레이션</div>
  <div class="legend">
    <div class="li"><div class="ld" style="background:#3b82f6"></div>현실형</div>
    <div class="li"><div class="ld" style="background:#10b981"></div>도전형</div>
    <div class="li"><div class="ld" style="background:#8b5cf6"></div>파격형</div>
  </div>
  <div class="chart-sc"><div class="chart" id="ch"></div></div>
  <div class="cu">단위: 만원 / 년</div>
</div>

<div class="final">
  <div class="final-lbl">AI 최종 메시지</div>
  <div class="final-tx">{_nl2br(final_msg)}</div>
</div>
<div class="rec">
  <div class="rec-lbl">AI 추천 이유 — {_e(rec_type)}</div>
  <div class="rec-tx">{_nl2br(rec.get("reason",""))}</div>
</div>

</div>
<script>
const lbs=['현재','1년','3년','5년','10년'];
const d={{r:{inc["r"]},c:{inc["c"]},p:{inc["p"]}}};
const mx={max_inc},ch=document.getElementById('ch');
lbs.forEach((lb,i)=>{{
  const g=document.createElement('div');g.className='cg';
  const bs=document.createElement('div');bs.className='bars';
  [['r','bar-r'],['c','bar-c'],['p','bar-p']].forEach(([k,c])=>{{
    const b=document.createElement('div');b.className=`bar ${{c}}`;
    b.style.height=Math.round(d[k][i]/mx*165)+'px';
    b.setAttribute('data-v',d[k][i].toLocaleString());
    bs.appendChild(b);
  }});
  const l=document.createElement('div');l.className='cl';l.textContent=lb;
  g.appendChild(bs);g.appendChild(l);ch.appendChild(g);
}});

let cur=null;
function pick(i){{
  const ps=document.querySelectorAll('.panel');
  const cs=document.querySelectorAll('.card');
  const bs=document.querySelectorAll('.sel-btn');
  if(cur===i){{
    ps[i].classList.remove('open');cs[i].classList.remove('active');
    bs[i].classList.remove('on');bs[i].textContent='이 시나리오 선택';cur=null;
    sendHeight();return;
  }}
  if(cur!==null){{
    ps[cur].classList.remove('open');cs[cur].classList.remove('active');
    bs[cur].classList.remove('on');bs[cur].textContent='이 시나리오 선택';
  }}
  ps[i].classList.add('open');cs[i].classList.add('active');
  bs[i].classList.add('on');bs[i].textContent='✔ 선택됨';cur=i;
  setTimeout(()=>{{
    ps[i].scrollIntoView({{behavior:'smooth',block:'nearest'}});
    sendHeight();
  }},200);
}}

function sendHeight(){{
  const h=document.documentElement.scrollHeight;
  window.parent.postMessage({{type:'streamlit:setFrameHeight',height:h}},'*');
}}
window.addEventListener('load',sendHeight);
new MutationObserver(sendHeight).observe(document.documentElement,{{subtree:true,childList:true,attributes:true}});
</script>
</body>
</html>"""


def render_input_page():
    st.title("AI 인생 시나리오 플래너")
    st.caption("15개 질문에 답하면 AI가 현실형·도전형·파격형 3가지 인생 시나리오를 분석해 드립니다.")

    col_load, col_save = st.columns([1, 1])
    with col_load:
        if st.button("저장된 정보 불러오기", use_container_width=True):
            profile = load_profile()
            if profile:
                st.session_state.inputs = profile
                st.success("프로필을 불러왔습니다.")
                st.rerun()
            else:
                st.warning("저장된 프로필이 없습니다.")

    st.divider()

    inputs = {}

    for q in QUESTIONS:
        key = q["key"]
        label = q["label"]
        saved = st.session_state.inputs.get(key)

        if q["type"] == "text":
            val = st.text_input(label, value=saved or "", key=f"input_{key}")
            st.caption(q["placeholder"])
            inputs[key] = val if val.strip() else "입력 없음"

        elif q["type"] == "slider":
            default = int(saved) if saved and str(saved).isdigit() else 5
            val = st.slider(label, min_value=1, max_value=10, value=default, key=f"input_{key}")
            inputs[key] = str(val)

        elif q["type"] == "select":
            options = q["options"]
            default_idx = options.index(saved) if saved in options else 0
            val = st.selectbox(label, options=options, index=default_idx, key=f"input_{key}")
            inputs[key] = val

        elif q["type"] == "income_select":
            options = q["options"]
            saved_sel = st.session_state.inputs.get("INCOME_SELECT", "직접 입력 안 함")
            default_idx = options.index(saved_sel) if saved_sel in options else 0
            sel = st.selectbox(label, options=options, index=default_idx, key="input_INCOME_SELECT")
            if sel == "직접 입력":
                saved_txt = st.session_state.inputs.get("INCOME_TEXT", "")
                txt = st.text_input(
                    "금액 직접 입력",
                    value=saved_txt,
                    placeholder="예) 연봉 6600만원, 월급 450만원",
                    key="input_INCOME_TEXT",
                )
                inputs["INCOME_SELECT"] = sel
                inputs["INCOME_TEXT"] = txt.strip()
            else:
                inputs["INCOME_SELECT"] = sel
                inputs["INCOME_TEXT"] = ""

        st.write("")

    st.divider()

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("내 정보 저장", use_container_width=True):
            save_profile(inputs)
            st.success("profile.json에 저장했습니다.")

    with col3:
        if st.button("시나리오 생성", type="primary", use_container_width=True):
            if not os.environ.get("GEMINI_API_KEY"):
                st.error(".env 파일에 GEMINI_API_KEY를 설정해 주세요.")
            else:
                with st.spinner("AI가 시나리오를 분석 중입니다... (30초~1분 소요)"):
                    try:
                        result = generate_scenarios(inputs)
                        st.session_state.inputs = inputs
                        st.session_state.result = result
                        st.session_state.page = "result"
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")


def render_result_page():
    if st.button("← 다시 입력하기"):
        st.session_state.page = "input"
        st.session_state.result = None
        st.rerun()

    html_content = build_result_html(st.session_state.result, st.session_state.inputs)
    components.html(html_content, height=3200, scrolling=False)

    st.divider()
    st.subheader("결과가 실제와 다른가요?")
    correction = st.text_area(
        "수정할 내용을 입력하세요",
        placeholder="예) 현재 연봉은 6,600만원입니다. 이를 반영해서 다시 작성해주세요.",
        height=100,
        key="correction_input",
    )
    if st.button("수정 반영하여 재생성", type="primary"):
        if not correction.strip():
            st.warning("수정할 내용을 입력해주세요.")
        else:
            with st.spinner("AI가 수정된 시나리오를 생성 중입니다... (30초~1분 소요)"):
                try:
                    result = generate_scenarios(st.session_state.inputs, correction)
                    st.session_state.result = result
                    st.rerun()
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")


def main():
    st.set_page_config(
        page_title="AI 인생 시나리오 플래너",
        page_icon="🧭",
        layout="wide"
    )
    init_session()

    if st.session_state.page == "input":
        render_input_page()
    else:
        render_result_page()


if __name__ == "__main__":
    main()
