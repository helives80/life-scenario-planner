import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import os
import html as _html
import datetime
import urllib.request
from dotenv import load_dotenv
import screen3_plan
import screen4_career

load_dotenv()

SCREEN3_ENABLED = True

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

COMPARE_SYSTEM_PROMPT = """
당신은 AI 인생 시나리오 비교 분석 엔진입니다.
과거에 저장된 시나리오 데이터와 현재 입력값을 비교하여 사용자의 변화를 분석합니다.

응답은 반드시 단일 JSON 객체 하나만 반환합니다. 코드펜스·설명·공백 줄바꿈 외 어떤 문자도 추가 금지.

분석 지침:
1. changes: Q2(만족도), Q5(저축), Q6(가족지지), Q3(버틸 기간) 등 핵심 항목과 텍스트 항목 변화를 분석합니다.
   direction은 "up"(긍정적 변화), "down"(부정적 변화), "same"(변화 없음), "changed"(내용 변경) 중 하나.
2. recommendation_change: 과거 AI 추천 타입과 현재 입력값 기준으로 추천할 타입을 분석합니다.
   after_type은 반드시 현실형/도전형/파격형 중 하나.
3. checklist: 과거 추천 시나리오의 next_steps 항목들이 현재 입력값 변화를 근거로 달성됐을 가능성을 평가합니다.
   likely_done은 true(달성 가능성 높음) 또는 false(미달성 가능성 높음).
4. overall_analysis: 3~4문장. 핵심 변화를 요약하고 현재 상황에서 다음 방향을 구체적으로 제시합니다.
"""

COMPARE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label":     {"type": "string"},
                    "before":    {"type": "string"},
                    "after":     {"type": "string"},
                    "direction": {"type": "string"},
                    "comment":   {"type": "string"},
                },
                "required": ["label", "before", "after", "direction", "comment"],
            },
        },
        "recommendation_change": {
            "type": "object",
            "properties": {
                "before_type": {"type": "string"},
                "after_type":  {"type": "string"},
                "analysis":    {"type": "string"},
            },
            "required": ["before_type", "after_type", "analysis"],
        },
        "checklist": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item":        {"type": "string"},
                    "category":    {"type": "string"},
                    "likely_done": {"type": "boolean"},
                    "reason":      {"type": "string"},
                },
                "required": ["item", "category", "likely_done", "reason"],
            },
        },
        "overall_analysis": {"type": "string"},
    },
    "required": ["changes", "recommendation_change", "checklist", "overall_analysis"],
}

PROFILE_PATH = "profile.json"

# ── 다크/라이트 테마 공통 CSS 변수 ────────────────────────────────────────────
_THEME_DARK_CSS = """<style>
:root{
  --bg:#0d1117;--surface:#161b27;--card:#1a1a2e;--card2:#16213e;
  --border:#2a2a4a;--text:#e8e8f0;--text2:#a0a0c0;--text3:#6060a0;
  --accent:#6c63ff;--blue:#4a7fff;--green:#2ecc71;--red:#e74c3c;
  --purple:#9b59b6;--shadow:0 4px 20px rgba(0,0,0,.35);
  --radius:12px;--radius-sm:8px;
}
</style>"""

_THEME_LIGHT_CSS = """<style>
:root{
  --bg:#f8f9ff;--surface:#ffffff;--card:#ffffff;--card2:#f0f2ff;
  --border:#dde0f0;--text:#1a1a2e;--text2:#4a4a7a;--text3:#9090b0;
  --accent:#6c63ff;--blue:#2255cc;--green:#1a7a45;--red:#dc2626;
  --purple:#5b21b6;--shadow:0 2px 12px rgba(0,0,0,.08);
  --radius:12px;--radius-sm:8px;
}
/* ── 앱 전체 배경 ── */
.stApp,[data-testid="stAppViewContainer"]{background-color:#f8f9ff!important}
/* ── 상단 헤더 ── */
[data-testid="stHeader"]{background-color:#f8f9ff!important;border-bottom:1px solid #dde0f0!important}
[data-testid="stHeader"] *{color:#1a1a2e!important}
[data-testid="stToolbar"] *{color:#1a1a2e!important}
[data-testid="stDecoration"]{background:none!important}
/* ── 사이드바 ── */
section[data-testid="stSidebar"]{background-color:#eef0fa!important}
section[data-testid="stSidebar"] *{color:#1a1a2e!important}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#1a1a2e!important}
/* ── 기본 텍스트·마크다운 ── */
.stApp p,.stApp span,.stApp label,.stApp div{color:#1a1a2e}
[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] *{color:#1a1a2e!important}
h1,h2,h3,h4,h5,h6{color:#1a1a2e!important}
/* ── 체크박스 ── */
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] span{color:#1a1a2e!important}
/* ── 버튼 ── */
button[kind="secondary"],button[kind="secondaryFormSubmit"]{
  background-color:#ffffff!important;color:#1a1a2e!important;border-color:#dde0f0!important}
button[kind="primary"]{color:#ffffff!important}
/* ── 입력 필드 ── */
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{
  background-color:#ffffff!important;color:#1a1a2e!important;border-color:#dde0f0!important}
[data-testid="stTextInput"] label,[data-testid="stTextArea"] label{color:#1a1a2e!important}
/* ── expander ── */
[data-testid="stExpander"]{background-color:#ffffff!important;border-color:#dde0f0!important}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:#1a1a2e!important}
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] *{color:#1a1a2e!important}
/* ── 알림 박스 ── */
[data-testid="stInfo"]{background-color:#eff6ff!important}
[data-testid="stInfo"] *{color:#1e40af!important}
[data-testid="stWarning"]{background-color:#fffbeb!important}
[data-testid="stWarning"] *{color:#92400e!important}
[data-testid="stSuccess"]{background-color:#f0fdf4!important}
[data-testid="stSuccess"] *{color:#166534!important}
[data-testid="stError"]{background-color:#fef2f2!important}
[data-testid="stError"] *{color:#991b1b!important}
/* ── caption/subtext ── */
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:#4a4a7a!important}
/* ── 구분선 ── */
hr{border-color:#dde0f0!important}
/* ── 메트릭 ── */
[data-testid="stMetric"] label,[data-testid="stMetric"] [data-testid="stMetricLabel"]{color:#4a4a7a!important}
[data-testid="stMetric"] [data-testid="stMetricValue"]{color:#1a1a2e!important}
/* ── select box ── */
[data-testid="stSelectbox"] label{color:#1a1a2e!important}
[data-baseweb="select"] [data-testid="stMarkdownContainer"] *{color:#1a1a2e!important}
/* ── chat ── */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] *{color:#1a1a2e!important}
[data-testid="stChatInputContainer"]{background-color:#ffffff!important;border-color:#dde0f0!important}
</style>"""


def apply_theme() -> None:
    """st.session_state.theme 값에 따라 공통 CSS 변수를 Streamlit에 주입한다."""
    try:
        theme = st.session_state.get("theme", "dark")
        st.markdown(_THEME_LIGHT_CSS if theme == "light" else _THEME_DARK_CSS,
                    unsafe_allow_html=True)
    except Exception:
        pass


def render_theme_toggle() -> None:
    """사이드바에 다크/라이트 모드 토글을 렌더링한다. 위치 이동 시 이 함수만 재배치."""
    theme = st.session_state.get("theme", "dark")
    is_dark = (theme == "dark")
    with st.sidebar:
        new_is_dark = st.toggle(
            "🌙 다크 모드" if is_dark else "☀️ 라이트 모드",
            value=is_dark,
            key="theme_sidebar_toggle",
        )
        if new_is_dark != is_dark:
            st.session_state.theme = "dark" if new_is_dark else "light"
            st.rerun()


# ── Google 로그인 (임시 비활성화) ────────────────────────────────────────────
# 아래 플래그를 True 로 바꾸면 로그인 기능이 다시 활성화됩니다.
_LOGIN_ENABLED = False


def _safe_get_user_info() -> dict:
    """st.user 에서 사용자 정보를 안전하게 dict 로 반환. 실패 시 빈 dict."""
    # ── 로그인 비활성화 중 ──────────────────────────────────────────────────
    if not _LOGIN_ENABLED:
        return {"is_logged_in": True, "name": "", "email": "", "picture": ""}
    # ── 활성화 시 아래 코드 사용 ────────────────────────────────────────────
    try:
        return {
            "is_logged_in": bool(st.user.is_logged_in),
            "name":         st.user.get("name", "")    or "",
            "email":        st.user.get("email", "")   or "",
            "picture":      st.user.get("picture", "") or "",
        }
    except Exception:
        return {"is_logged_in": False, "name": "", "email": "", "picture": ""}


def render_login_page() -> None:
    """로그인 전용 페이지 — Streamlit 내장 OIDC(st.login) 방식."""
    # ── 로그인 비활성화 중: 이 함수는 호출되지 않음 ─────────────────────────
    # authlib 설치 여부 사전 확인
    # try:
    #     from streamlit.auth_util import is_authlib_installed
    #     if not is_authlib_installed():
    #         st.error(
    #             "설정 오류: `authlib>=1.3.2` 패키지가 설치되지 않았습니다. "
    #             "requirements.txt에 `authlib>=1.3.2`를 추가하고 재배포해주세요."
    #         )
    #         st.stop()
    # except Exception:
    #     pass

    st.markdown(
        """
        <style>
        @keyframes hbf{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
        .login-wrap{display:flex;flex-direction:column;align-items:center;
          justify-content:center;min-height:65vh;gap:20px;text-align:center;
          padding:0 24px}
        .login-icon{font-size:3.2rem;animation:hbf 4s ease-in-out infinite}
        .login-title{font-size:1.7rem;font-weight:800;margin:0;
          background:linear-gradient(135deg,#a0a8ff,#7ef8c8);
          -webkit-background-clip:text;-webkit-text-fill-color:transparent;
          background-clip:text}
        .login-sub{color:#9090b0;font-size:.95rem;margin:0}
        </style>
        <div class="login-wrap">
          <div class="login-icon">🧭</div>
          <div class="login-title">AI 인생 시나리오 플래너</div>
          <div class="login-sub">Google 계정으로 로그인하여 나만의 시나리오를 시작하세요</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1, 1])
    with col:
        try:
            st.login("google")
        except Exception as _e:
            st.error(f"로그인 버튼 초기화 오류: {_e}")
    st.stop()


def render_user_sidebar() -> None:
    """사이드바에 사용자 프로필 + 로그아웃 버튼 표시."""
    # ── 로그인 비활성화 중: 사이드바 사용자 정보 표시 안 함 ─────────────────
    if not _LOGIN_ENABLED:
        return
    # ── 활성화 시 아래 코드 사용 ────────────────────────────────────────────
    user = _safe_get_user_info()
    if not user["is_logged_in"]:
        return
    name    = user["name"]
    email   = user["email"]
    picture = user["picture"]
    try:
        with st.sidebar:
            if picture:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;padding:10px 0 4px">'
                    f'  <img src="{_e(picture)}" width="36" height="36"'
                    f'       style="border-radius:50%;border:2px solid rgba(160,168,255,.4)">'
                    f'  <div>'
                    f'    <div style="font-size:.85rem;font-weight:700;color:#fff">{_e(name)}</div>'
                    f'    <div style="font-size:.72rem;color:#9090b0">{_e(email)}</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(email or "로그인됨")
            try:
                st.logout()
            except Exception:
                if st.button("로그아웃", use_container_width=True, key="sidebar_logout_fallback"):
                    st.rerun()
            st.divider()
    except Exception:
        pass


# ── 화면0 시각 상수 ───────────────────────────────────────────────────────────
_HOME_PAGE_CSS = """<style>
.home-brand{display:flex;flex-direction:column;align-items:center;
  margin:28px auto 22px;gap:10px;text-align:center}
.home-brand-icon{width:66px;height:66px;
  filter:drop-shadow(0 0 16px rgba(100,120,255,.4));
  animation:hbf 4s ease-in-out infinite}
@keyframes hbf{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
.home-brand h1{font-size:clamp(1.3rem,4vw,1.6rem);font-weight:800;
  letter-spacing:-.5px;margin:0;
  background:linear-gradient(135deg,#a0a8ff 0%,#7ef8c8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.home-brand p{font-size:.9rem;color:#9090b0;margin:0}
/* 상태2 결과 카드 */
.home-card-result{background:linear-gradient(135deg,#0e3f74,#0a2d55);
  border:1px solid rgba(30,127,212,.35);border-radius:16px;
  padding:18px 20px 14px;margin-bottom:4px}
.home-cr-top{display:flex;justify-content:space-between;
  align-items:flex-start;gap:10px}
.home-cr-badge{display:inline-flex;align-items:center;gap:5px;
  font-size:.68rem;font-weight:600;
  background:rgba(30,127,212,.25);border:1px solid rgba(30,127,212,.35);
  border-radius:30px;padding:3px 10px;color:#7ec8ff;margin-bottom:6px}
.home-cr-name{font-size:1rem;font-weight:800;color:#fff;line-height:1.3}
.home-cr-date{font-size:.72rem;color:rgba(255,255,255,.45);
  text-align:right;flex-shrink:0;padding-top:2px}
/* 상태3 진행 카드 */
.home-card-progress{background:linear-gradient(135deg,#2a1e5c,#1f1848);
  border:1px solid rgba(107,98,212,.35);border-radius:16px;
  padding:18px 20px 14px;margin-bottom:4px}
.home-cp-top{display:flex;justify-content:space-between;
  align-items:center;gap:10px}
.home-cp-name{font-size:1rem;font-weight:800;color:#fff}
.home-cp-todo{display:inline-flex;align-items:center;gap:4px;
  font-size:.7rem;font-weight:700;
  background:rgba(255,180,80,.12);border:1px solid rgba(255,180,80,.22);
  border-radius:30px;padding:3px 9px;color:#ffb450;flex-shrink:0}
.home-cp-meta{display:flex;justify-content:space-between;
  font-size:.73rem;color:rgba(255,255,255,.5);margin:8px 0 4px}
.home-cp-pct{font-weight:700;color:#c3b8ff}
.home-cp-bg{height:7px;background:rgba(255,255,255,.1);
  border-radius:99px;overflow:hidden}
.home-cp-fill{height:100%;
  background:linear-gradient(90deg,#534AB7,#9b8fff);
  border-radius:99px;transition:width 1.2s cubic-bezier(.22,1,.36,1)}
/* Streamlit 버튼 오버라이드 */
[data-testid="stButton"]>button{
  border-radius:18px!important;padding:18px 22px!important;
  font-size:.97rem!important;font-weight:700!important;
  min-height:66px!important;width:100%!important;
  transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s!important;
  letter-spacing:-.2px!important;text-align:left!important}
[data-testid="stButton"]>button:hover:not([disabled]){
  transform:translateY(-4px)!important}
[data-testid="stButton"]>button[kind="primary"]{
  background:linear-gradient(135deg,#0F6E56,#0d5c47)!important;
  border:1px solid rgba(19,149,122,.35)!important;color:#fff!important}
[data-testid="stButton"]>button[kind="primary"]:hover{
  box-shadow:0 10px 30px rgba(15,110,86,.5)!important}
[data-testid="stButton"]>button[kind="secondary"]{
  background:linear-gradient(135deg,#534AB7,#423b96)!important;
  border:1px solid rgba(107,98,212,.35)!important;color:#fff!important}
[data-testid="stButton"]>button[kind="secondary"]:hover{
  box-shadow:0 10px 30px rgba(83,74,183,.5)!important}
[data-testid="stButton"]>button[disabled]{
  background:rgba(37,37,64,.8)!important;
  border:1px solid rgba(255,255,255,.06)!important;
  color:#5a5a7a!important;cursor:not-allowed!important;
  transform:none!important;box-shadow:none!important}
</style>"""

_COMPASS_SVG = (
    '<svg class="home-brand-icon" viewBox="0 0 72 72" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="36" cy="36" r="34" stroke="url(#hcg1)" stroke-width="2.5"/>'
    '<circle cx="36" cy="36" r="26" stroke="url(#hcg2)" stroke-width="1.2" stroke-dasharray="3 3"/>'
    '<polygon points="36,10 40,36 36,30 32,36" fill="url(#hcg3)"/>'
    '<polygon points="36,62 32,36 36,42 40,36" fill="#4a4a6a"/>'
    '<circle cx="36" cy="36" r="4" fill="url(#hcg3)"/>'
    '<line x1="36" y1="4" x2="36" y2="12" stroke="rgba(160,168,255,0.4)" stroke-width="2" stroke-linecap="round"/>'
    '<line x1="36" y1="60" x2="36" y2="68" stroke="rgba(160,168,255,0.2)" stroke-width="1.5" stroke-linecap="round"/>'
    '<line x1="4" y1="36" x2="12" y2="36" stroke="rgba(160,168,255,0.2)" stroke-width="1.5" stroke-linecap="round"/>'
    '<line x1="60" y1="36" x2="68" y2="36" stroke="rgba(160,168,255,0.2)" stroke-width="1.5" stroke-linecap="round"/>'
    '<circle cx="18" cy="18" r="1.5" fill="#a0a8ff" opacity=".7"/>'
    '<circle cx="54" cy="15" r="1" fill="#7ef8c8" opacity=".6"/>'
    '<circle cx="58" cy="52" r="1.2" fill="#a0a8ff" opacity=".5"/>'
    '<defs>'
    '<linearGradient id="hcg1" x1="0" y1="0" x2="72" y2="72" gradientUnits="userSpaceOnUse">'
    '<stop offset="0%" stop-color="#a0a8ff"/><stop offset="100%" stop-color="#7ef8c8"/>'
    '</linearGradient>'
    '<linearGradient id="hcg2" x1="0" y1="0" x2="72" y2="72" gradientUnits="userSpaceOnUse">'
    '<stop offset="0%" stop-color="#a0a8ff" stop-opacity=".5"/>'
    '<stop offset="100%" stop-color="#7ef8c8" stop-opacity=".5"/>'
    '</linearGradient>'
    '<linearGradient id="hcg3" x1="36" y1="10" x2="36" y2="36" gradientUnits="userSpaceOnUse">'
    '<stop offset="0%" stop-color="#7ef8c8"/><stop offset="100%" stop-color="#a0a8ff"/>'
    '</linearGradient>'
    '</defs></svg>'
)

Q3_OPTIONS = ["3개월 미만", "6개월", "1년", "1년 이상"]
Q5_OPTIONS = ["없음", "50만 미만", "50~150만", "150만 이상"]
Q6_OPTIONS = ["강하게 반대", "중립", "지지", "적극 응원"]
INCOME_OPTIONS = [
    "선택",
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
AGE_OPTIONS    = ["20대 초반", "20대 후반", "30대 초반", "30대 후반", "40대 초반", "40대 후반", "50대 초반", "50대 후반", "60대 이상"]
GENDER_OPTIONS = ["남성", "여성", "선택 안 함"]
TIME_OPTIONS   = ["1시간 미만", "1~2시간", "2~3시간", "3시간 이상"]

SECTIONS = [
    {
        "title": "현재 상황",
        "desc": "지금 어디에 있나요? 현재 직업·재정·환경을 파악합니다",
        "questions": [
            {"id": "job",           "label": "현재 직업·역할",        "type": "text",         "placeholder": "예) 중소기업 영업부장 15년차, 프리랜서 디자이너"},
            {"id": "satisfaction",  "label": "현 상황 만족도",         "type": "slider"},
            {"id": "endurance",     "label": "버틸 수 있는 기간",      "type": "select",       "options": Q3_OPTIONS},
            {"id": "saving",        "label": "매달 저축 가능 금액",    "type": "select",       "options": Q5_OPTIONS},
            {"id": "family_support","label": "가족의 지지 여부",       "type": "select",       "options": Q6_OPTIONS},
        ],
    },
    {
        "title": "내 자산·역량",
        "desc": "무엇을 가지고 있나요? 활용 가능한 기술과 자원을 확인합니다",
        "questions": [
            {"id": "age",       "label": "연령대",                    "type": "select",        "options": AGE_OPTIONS},
            {"id": "gender",    "label": "성별",                      "type": "select",        "options": GENDER_OPTIONS},
            {"id": "skill",     "label": "돈 받고 팔 수 있는 기술",   "type": "text",          "placeholder": "예) 영업·협상 경험, 엑셀 분석, 콘텐츠 기획"},
            {"id": "income",    "label": "현재 연봉 또는 월급",       "type": "income_select", "options": INCOME_OPTIONS},
            {"id": "free_time", "label": "하루 평균 여유시간",        "type": "select",        "options": TIME_OPTIONS},
        ],
    },
    {
        "title": "가치관·두려움",
        "desc": "무엇이 중요한가요? 포기할 수 없는 것과 두려움을 솔직하게 적어주세요",
        "questions": [
            {"id": "priority",  "label": "절대 포기할 수 없는 것", "type": "text", "placeholder": "예) 가족과의 저녁 시간, 주말 취미 생활, 건강 관리"},
            {"id": "fear",      "label": "가장 두려운 것",         "type": "text", "placeholder": "예) 50대에 직장 잃는 것, 노후 준비 없이 나이 드는 것"},
            {"id": "rolemodel", "label": "롤모델·닮고 싶은 삶",    "type": "text", "placeholder": "예) 자기 회사 차린 선배, 자유롭게 일하는 프리랜서 지인"},
        ],
    },
    {
        "title": "미래 비전",
        "desc": "어디로 가고 싶나요? 10년 후 모습과 인생에서 반드시 이룰 것을 적어주세요",
        "questions": [
            {"id": "goal",       "label": "10년 후 목표",              "type": "textarea", "placeholder": "예) 내 회사 운영, 안정적인 부업 수입 월 300만"},
            {"id": "bucketlist", "label": "죽기 전 반드시 하고 싶은 일", "type": "text",  "placeholder": "예) 세계여행, 책 한 권 출판, 자녀 결혼 다 시키기"},
        ],
    },
    {
        "title": "변화·행동",
        "desc": "무엇을 바꿀 건가요? 현재 고민과 지금 당장 실행 가능한 것을 적어주세요",
        "questions": [
            {"id": "change_5y",  "label": "5년 전과 달라진 점",    "type": "textarea", "placeholder": "예) 이직 2번 했음, 아이가 생겼음, 부모님 간병 시작"},
            {"id": "worry",      "label": "현재 가장 큰 고민",     "type": "textarea", "placeholder": "예) 지금 직장 계속 다닐지 이직할지 모르겠다"},
            {"id": "changeable", "label": "지금 바꿀 수 있는 것",  "type": "text",     "placeholder": "예) 퇴근 후 유튜브 2시간을 자기계발로 바꾸기"},
        ],
    },
]

QUESTIONS = [q for s in SECTIONS for q in s["questions"]]

ID_TO_Q = {
    "job": 1, "satisfaction": 2, "endurance": 3, "skill": 4,
    "saving": 5, "family_support": 6, "priority": 7, "fear": 8,
    "rolemodel": 9, "goal": 10, "bucketlist": 11, "change_5y": 12,
    "worry": 13, "changeable": 14,
}

OLD_KEY_MIGRATION = {
    "Q1": "job", "Q2": "satisfaction", "Q3": "endurance", "Q4": "skill",
    "Q5": "saving", "Q6": "family_support", "Q7": "priority", "Q8": "fear",
    "Q9": "rolemodel", "Q10": "goal", "Q11": "bucketlist", "Q12": "change_5y",
    "Q13": "worry", "Q14": "changeable",
    "AGE": "age", "GENDER": "gender", "TIME": "free_time",
}


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


def _inputs_to_q_lines(inputs: dict) -> list:
    """inputs dict(id 기반 또는 구형 Q번호 기반) → Q1~Q15 형식 라인 목록."""
    lines = []
    for id_key, q_num in sorted(ID_TO_Q.items(), key=lambda x: x[1]):
        value = inputs.get(id_key, inputs.get(f"Q{q_num}", "입력 없음"))
        lines.append(f"Q{q_num}: {value}")
        if q_num == 1:
            income_sel = inputs.get("INCOME_SELECT", "선택")
            income_txt = inputs.get("INCOME_TEXT", "")
            if income_sel == "직접 입력" and income_txt:
                lines.append(f"현재 소득: {income_txt}")
            elif income_sel not in ("선택", "직접 입력", ""):
                lines.append(f"현재 소득: {income_sel}")
    lines.append("Q15: 입력 없음")
    for id_key, old_key, label in [
        ("age", "AGE", "연령대"), ("gender", "GENDER", "성별"),
        ("free_time", "TIME", "하루 평균 여유시간"),
    ]:
        val = inputs.get(id_key, inputs.get(old_key, ""))
        if val:
            lines.append(f"{label}: {val}")
    return lines


def build_user_message(inputs: dict, correction: str = "") -> str:
    msg = "\n".join(_inputs_to_q_lines(inputs))
    if correction and correction.strip():
        msg += (
            "\n\n===수정 요청===\n"
            "사용자가 아래 내용이 실제와 다르다고 합니다.\n"
            "반드시 반영해서 시나리오를 다시 작성해주세요:\n"
            + correction.strip()
        )
    return msg


def generate_scenarios(inputs: dict, correction: str = "") -> dict:
    model = get_model()
    if model is None:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    user_message = build_user_message(inputs, correction)
    response = model.generate_content(user_message)
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI 응답을 파싱할 수 없습니다 (JSON 오류). 잠시 후 다시 시도해 주세요.\n상세: {e}") from e


def save_profile(inputs: dict):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(inputs, f, ensure_ascii=False, indent=2)


def load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(inputs: dict, result: dict) -> str:
    today = datetime.date.today().strftime("%Y%m%d")
    base = f"history_{today}"
    path = f"{base}.json"
    counter = 2
    while os.path.exists(path):
        path = f"{base}_{counter}.json"
        counter += 1
    selected = st.session_state.get("selected_scenario") or {}
    data = {
        "date": datetime.date.today().isoformat(),
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "inputs": inputs,
        "result": result,
        "selected_scenario": selected,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def list_history() -> list:
    import glob
    files = sorted(glob.glob("history_*.json"), reverse=True)
    items = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            saved_at = data.get("saved_at", data.get("date", ""))[:16].replace("T", " ")
            inp = data.get("inputs", {})
            q1 = inp.get("job", inp.get("Q1", ""))
            label = f"{saved_at}  |  {q1[:25]}" if q1 else saved_at
            items.append({"filename": f, "label": label, "data": data})
        except Exception:
            continue
    return items


def get_user_status() -> int:
    """저장 파일 유무로 사용자 상태를 판단한다.
    1: 신규  2: 설문완료·플랜미시작  3: 플랜진행중
    """
    import glob as _glob
    try:
        has_history   = bool(_glob.glob("history_*.json"))
        # screen3 은 checklist_{시나리오유형}_{날짜}.json 으로 저장
        has_checklist = bool(_glob.glob("checklist_*.json"))
        if has_history and has_checklist:
            return 3
        if has_history:
            return 2
        return 1
    except Exception:
        return 1


def _load_latest_history() -> dict:
    """최신 history_*.json 데이터 반환. 실패 시 빈 dict."""
    import glob as _glob
    try:
        files = sorted(_glob.glob("history_*.json"), reverse=True)
        if not files:
            return {}
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_latest_career_checklist() -> dict:
    """최신 checklist_*.json (화면3 저장) 데이터 반환. 실패 시 빈 dict."""
    import glob as _glob
    try:
        files = sorted(_glob.glob("checklist_*.json"), reverse=True)
        if not files:
            return {}
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_compare_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=COMPARE_RESPONSE_SCHEMA,
        temperature=0.7,
    )
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=COMPARE_SYSTEM_PROMPT,
        generation_config=generation_config,
    )


def build_compare_message(old_data: dict, new_inputs: dict) -> str:
    old_inputs = old_data.get("inputs", {})
    old_result = old_data.get("result", {})
    old_date = old_data.get("saved_at", old_data.get("date", ""))[:10]
    old_rec = old_result.get("recommendation", {})
    old_rec_type = old_rec.get("type", "")
    old_scenarios = old_result.get("scenarios", [])
    old_rec_sc = next((s for s in old_scenarios if s.get("type") == old_rec_type), {})
    old_ns = old_rec_sc.get("next_steps", {})

    lines = [f"=== 과거 입력값 ({old_date}) ==="]
    lines.extend(_inputs_to_q_lines(old_inputs))

    lines.append("")
    lines.append(f"=== 과거 AI 추천 ({old_rec_type}) ===")
    lines.append(old_rec.get("reason", ""))

    lines.append("")
    lines.append("=== 과거 추천 시나리오 next_steps ===")
    for ns_key, ns_label in [
        ("this_week", "이번 주"), ("one_month", "1개월 내"),
        ("three_months", "3개월 내"), ("must_prepare", "반드시 갖춰야 할 것"),
        ("must_avoid", "반드시 피해야 할 것"),
    ]:
        items = old_ns.get(ns_key, [])
        if items:
            lines.append(f"{ns_label}: {' / '.join(items)}")
    coach = old_ns.get("coach_message", "")
    if coach:
        lines.append(f"AI 코치 메시지: {coach}")

    lines.append("")
    lines.append("=== 현재 입력값 ===")
    lines.extend(_inputs_to_q_lines(new_inputs))

    return "\n".join(lines)


def generate_comparison(old_data: dict, new_inputs: dict) -> dict:
    model = get_compare_model()
    if model is None:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    msg = build_compare_message(old_data, new_inputs)
    response = model.generate_content(msg)
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI 응답을 파싱할 수 없습니다 (JSON 오류). 잠시 후 다시 시도해 주세요.\n상세: {e}") from e


def get_korean_font_path():
    """한국어 TTF/TTC 폰트 경로 반환. 없으면 다운로드 시도, 실패 시 None."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "fonts", "NanumGothic.ttf"),
        "/Library/Fonts/NanumGothic.ttf",
        os.path.expanduser("~/Library/Fonts/NanumGothic.ttf"),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/local/share/fonts/NanumGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        # macOS 시스템 폰트
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    cache = os.path.join(base, "fonts", "NanumGothic.ttf")
    if os.path.exists(cache):
        return cache
    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        urllib.request.urlretrieve(url, cache)
        if os.path.getsize(cache) > 10000:
            return cache
    except Exception:
        pass
    return None


def generate_pdf(result: dict, inputs: dict, screen3_data: dict = None, screen4_data: dict = None, scope: str = "full") -> bytes:
    """Gemini 결과를 fpdf2로 PDF 변환. 한국어 폰트 자동 적용."""
    from fpdf import FPDF

    font_path = get_korean_font_path()
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(20, 20, 20)

    use_kr = False
    if font_path:
        try:
            pdf.add_font("KR", fname=font_path)
            pdf.add_font("KR", style="B", fname=font_path)
            use_kr = True
        except Exception:
            pass

    def sf(size=10):
        pdf.set_font("KR" if use_kr else "Helvetica", size=size)

    def sfb(size=10):
        if use_kr:
            try:
                pdf.set_font("KR", style="B", size=size)
            except Exception:
                pdf.set_font("KR", size=size)
        else:
            pdf.set_font("Helvetica", style="B", size=size)

    def wl(text, size=10, bold=False, color=(30, 30, 30), lh=6):
        (sfb if bold else sf)(size)
        pdf.set_text_color(*color)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, lh, str(text) if text else "")
        pdf.set_text_color(30, 30, 30)

    def section(title, color=(59, 130, 246)):
        pdf.ln(5)
        sfb(12)
        pdf.set_text_color(*color)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*color)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.set_draw_color(0, 0, 0)
        pdf.ln(4)
        pdf.set_text_color(30, 30, 30)

    summary   = result.get("summary", {})
    scenarios = result.get("scenarios", [])
    rec       = result.get("recommendation", {})
    rec_type  = rec.get("type", "")
    final_msg = result.get("final_message", "")
    color_rgb = {"blue": (59, 130, 246), "green": (16, 185, 129), "purple": (139, 92, 246)}

    if scope == "screen4_only":
        # ── 화면4 전용 표지
        pdf.add_page()
        sfb(20)
        pdf.set_text_color(108, 99, 255)
        pdf.cell(0, 12, "3년 후 커리어 설계 리포트", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(2)
        sf(10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, datetime.date.today().strftime("%Y년 %m월 %d일"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(8)
        pdf.set_text_color(30, 30, 30)
    else:
        # ── 표지 + 요약
        pdf.add_page()
        sfb(20)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 12, "AI 인생 시나리오 리포트", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(2)
        sf(10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, datetime.date.today().strftime("%Y년 %m월 %d일"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(8)

        section("입력 정보 요약")
        for key, label in [("job","직업·역할"),("satisfaction","현 상황 만족도"),("age","연령대"),("gender","성별"),("free_time","하루 평균 여유시간")]:
            val = inputs.get(key, "")
            if val and val != "입력 없음":
                suffix = "/10" if key == "Q2" else ""
                wl(f"  {label}: {val}{suffix}")
        income_sel = inputs.get("INCOME_SELECT", "")
        income_txt = inputs.get("INCOME_TEXT", "")
        if income_sel == "직접 입력" and income_txt:
            wl(f"  현재 소득: {income_txt}")
        elif income_sel not in ("선택", "직접 입력", "", None):
            wl(f"  현재 소득: {income_sel}")

        section("핵심 인사이트")
        wl(summary.get("insight", ""), lh=7)
        pdf.ln(2)
        wl(f"핵심 갈등: {summary.get('conflict','')}", color=(160, 90, 0), lh=7)

    # ── 시나리오별 페이지 (scope=="full" 일 때만)
    for sc in scenarios if scope == "full" else []:
        pdf.add_page()
        sc_type = sc.get("type", "")
        c_rgb   = color_rgb.get(sc.get("color", "blue"), (60, 60, 60))
        is_rec  = sc_type == rec_type

        sfb(14)
        pdf.set_text_color(*c_rgb)
        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 9, f"시나리오  {sc_type}{'  ★ AI 추천' if is_rec else ''}")
        sfb(13)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 8, sc.get("title", ""))
        pdf.ln(2)
        wl(sc.get("description", ""), lh=7)
        pdf.ln(3)

        sfb(10); pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, "마일스톤", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
        ms = sc.get("milestones", {})
        for yr, lbl in [("1y","1년"),("3y","3년"),("5y","5년"),("10y","10년")]:
            wl(f"  {lbl}: {ms.get(yr,'')}", lh=6)
        pdf.ln(3)

        sfb(10); pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, "두려움 분석", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(70, 70, 100)
        sf(9); pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, sc.get("fear_response", ""))
        pdf.set_text_color(30, 30, 30); pdf.ln(2)

        trf = sc.get("tradeoff", {})
        sf(10)
        pdf.set_text_color(0, 130, 80)
        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"▲ 얻는 것: {trf.get('gain','')}")
        pdf.set_text_color(180, 60, 0)
        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"▼ 잃는 것: {trf.get('lose','')}")
        pdf.set_text_color(30, 30, 30)

        ns = sc.get("next_steps", {})
        if ns:
            pdf.ln(6)
            sfb(13); pdf.set_text_color(*c_rgb)
            rec_mark = " (AI 추천)" if is_rec else ""
            pdf.cell(0, 8, f"실행 계획{rec_mark}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); pdf.ln(2)
            for ns_title, ns_key in [
                ("이번 주 바로 할 것","this_week"),
                ("1개월 내 준비 사항","one_month"),
                ("3개월 내 이룰 것","three_months"),
                ("반드시 갖춰야 할 것","must_prepare"),
                ("반드시 피해야 할 것","must_avoid"),
            ]:
                items = ns.get(ns_key, [])
                if items:
                    sfb(10); pdf.set_text_color(80, 80, 80)
                    pdf.cell(0, 7, ns_title, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(30, 30, 30); sf(10)
                    for it in items:
                        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  • {it}")
                    pdf.ln(2)
            coach = ns.get("coach_message", "")
            if coach:
                sfb(10); pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 7, "AI 코치 한 마디", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(60, 60, 100); sf(10)
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, coach)

    # ── 마지막 페이지: 추천 이유 + 최종 메시지 (scope=="full" 일 때만)
    if scope == "full":
        pdf.add_page()
        section("AI 추천 이유", color=(16, 185, 129))
        sfb(11); pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 7, f"추천 시나리오: {rec_type}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30); sf(10)
        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 7, rec.get("reason", ""))

        section("AI 최종 메시지")
        sf(10); pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 7, final_msg)

    # ── 화면3 실행 계획 페이지 (screen3_data 있을 때만)
    if screen3_data:
        sc3 = screen3_data.get("scenario", {})
        checks = screen3_data.get("checks", {})
        ns3 = sc3.get("next_steps", {})
        ev = screen3_data.get("eval_result")

        pdf.add_page()
        section("실행 계획 체크리스트", color=(139, 92, 246))
        sfb(11); pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 7, f"선택 시나리오: {sc3.get('type','')} — {sc3.get('title','')}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30); pdf.ln(3)

        sec_map = [
            ("이번 주 바로 할 것", "this_week",    "week"),
            ("1개월 내 준비 사항", "one_month",    "month"),
            ("3개월 내 이룰 것",   "three_months", "3month"),
            ("반드시 갖춰야 할 것", "must_prepare", "prepare"),
            ("반드시 피해야 할 것", "must_avoid",   "avoid"),
        ]
        for sec_lbl, ns_key, key_pfx in sec_map:
            items = ns3.get(ns_key, [])
            if not items:
                continue
            sfb(10); pdf.set_text_color(100, 100, 120)
            pdf.cell(0, 7, sec_lbl, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); sf(9)
            for idx, item in enumerate(items):
                mark = "✅" if checks.get(f"check_{key_pfx}_{idx}", False) else "⬜"
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 6, f"  {mark} {item}")
            pdf.ln(2)

        if ev:
            pdf.ln(4)
            section("AI 실행 평가", color=(139, 92, 246))
            ev_inner = ev.get("evaluation", {})
            for lbl, key in [("실행력", "execution"), ("속도", "speed"), ("방향성", "direction")]:
                wl(f"  {lbl}: {ev_inner.get(key, '-')}", lh=6)
            pdf.ln(2)
            wl("AI 평가 메시지:", bold=True)
            sf(9); pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 6, ev.get("message", ""))

    # ── 화면4 커리어 설계 페이지 (screen4_data 있을 때만)
    if screen4_data:
        pdf.add_page()
        section("3년 후 커리어 설계 계획", color=(108, 99, 255))

        goal_role   = screen4_data.get("goal_role", "")
        goal_income = screen4_data.get("goal_income", "")
        goal_skills = screen4_data.get("goal_skills", "")
        if goal_role:
            wl(f"  목표 직책·역할: {goal_role}")
        if goal_income:
            wl(f"  목표 연 수입: {goal_income}")
        if goal_skills:
            wl(f"  핵심 보유 예정 기술: {goal_skills[:200]}")
        pdf.ln(3)

        gap = screen4_data.get("gap_result", {})
        req_skills  = gap.get("required_skills", [])
        pref_skills = gap.get("preferred_skills", [])
        have        = gap.get("have", [])
        lack        = gap.get("lack", [])
        gap_comment = gap.get("gap_comment", "")

        if req_skills:
            sfb(10); pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, "요구 역량 TOP 5", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); sf(9)
            for s in req_skills:
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  • {s}")
            pdf.ln(2)
        if pref_skills:
            sfb(10); pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, "우대사항 TOP 5", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); sf(9)
            for s in pref_skills:
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  • {s}")
            pdf.ln(2)

        if have or lack:
            sfb(10); pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, "갭 분석", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); sf(9)
            if have:
                pdf.set_text_color(0, 130, 80)
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, "현재 보유:")
                pdf.set_text_color(30, 30, 30)
                for s in have:
                    pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  ✅ {s}")
            if lack:
                pdf.set_text_color(180, 60, 0)
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, "부족한 것:")
                pdf.set_text_color(30, 30, 30)
                for s in lack:
                    pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  ❌ {s}")
            if gap_comment:
                pdf.ln(2); sf(9); pdf.set_text_color(70, 70, 120)
                pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"💡 {gap_comment}")
                pdf.set_text_color(30, 30, 30)
            pdf.ln(3)

        roadmap = screen4_data.get("roadmap", {})
        if roadmap:
            sfb(10); pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, "3년 로드맵", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30); sf(9)
            for yr_key, yr_label in [("y1", "1년차"), ("y2", "2년차"), ("y3", "3년차")]:
                tasks = roadmap.get(yr_key, [])
                if tasks:
                    sfb(9); pdf.set_text_color(60, 60, 160)
                    pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"{yr_label}:")
                    pdf.set_text_color(30, 30, 30); sf(9)
                    for t in tasks:
                        pdf.set_x(pdf.l_margin); pdf.multi_cell(pdf.epw, 6, f"  • {t}")
            pdf.ln(3)

        monthly_plan = screen4_data.get("monthly_plan", [])
        checks       = screen4_data.get("checks", {})
        if monthly_plan:
            pdf.add_page()
            section("월별 실행 계획 체크현황 (36개월)", color=(108, 99, 255))
            sf(9)
            for p in monthly_plan[:36]:
                month   = p.get("month", "?")
                task    = p.get("task", "").strip()
                if not task:
                    continue
                done = checks.get(f"s4_check_{month}", False)
                mark = "✅" if done else "⬜"
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(pdf.epw, 6, f"  {mark} {month}개월차: {task}")

    return bytes(pdf.output())


def init_session():
    if "inputs" not in st.session_state:
        st.session_state.inputs = {}
    if "result" not in st.session_state:
        st.session_state.result = None
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "compare_mode" not in st.session_state:
        st.session_state.compare_mode = False
    if "compare_result" not in st.session_state:
        st.session_state.compare_result = None
    if "compare_old_data" not in st.session_state:
        st.session_state.compare_old_data = None
    if "selected_scenario" not in st.session_state:
        st.session_state.selected_scenario = None
    if "eval_result" not in st.session_state:
        st.session_state.eval_result = None
    if "coach_chat" not in st.session_state:
        st.session_state.coach_chat = []
    if "coach_error" not in st.session_state:
        st.session_state.coach_error = None
    if "coach_pending_msg" not in st.session_state:
        st.session_state.coach_pending_msg = None
    if "career_result" not in st.session_state:
        st.session_state.career_result = None
    if "career_grounding_used" not in st.session_state:
        st.session_state.career_grounding_used = False


def _e(s):
    return _html.escape(str(s) if s is not None else "")


def _nl2br(s):
    return _e(s).replace("\n", "<br>")


def _li(lst):
    return "".join(f"<li>{_e(x)}</li>" for x in (lst or []))


def build_result_html(result: dict, inputs: dict, theme: str = "dark") -> str:
    summary      = result.get("summary", {})
    scenarios    = result.get("scenarios", [])
    rec          = result.get("recommendation", {})
    final_msg    = result.get("final_message", "")
    rec_type     = rec.get("type", "")

    COLOR_CLS  = {"blue": "r", "green": "c", "purple": "p"}
    COLOR_VAR  = {"blue": "blue", "green": "green", "purple": "purple"}

    # ── badges
    badges = ""
    if inputs.get("job") not in (None, "입력 없음"):
        badges += f'<div class="bdg">직업 <b>{_e(inputs["job"])}</b></div>'
    if inputs.get("satisfaction") not in (None, "입력 없음"):
        badges += f'<div class="bdg">만족도 <b>{_e(inputs["satisfaction"])} / 10</b></div>'
    if inputs.get("endurance") not in (None, "입력 없음"):
        badges += f'<div class="bdg">버틸 수 있는 기간 <b>{_e(inputs["endurance"])}</b></div>'
    if inputs.get("family_support") not in (None, "입력 없음"):
        badges += f'<div class="bdg">가족 지지 <b>{_e(inputs["family_support"])}</b></div>'

    # ── cards + panels (card-wrap 단위로 합쳐서 세로 스택)
    cards_html = ""
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

        ns = sc.get("next_steps", {})
        cards_html += f"""
  <div class="card-wrap">
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
      <div class="card-actions">
        <button class="toggle-btn" id="toggle-{i}" onclick="togglePanel({i})">▼ 실행 계획 보기</button>
      </div>
    </div>
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
    </div>
  </div>"""

    # ── chart data
    max_inc = max(max(inc["r"]), max(inc["c"]), max(inc["p"]), 1)

    DARK_VARS = """:root{
  --bg:#0d1117;--surface:#161b27;--border:#1f2a3c;--text:#e2e8f0;--muted:#8892a4;
  --blue:#3b82f6;--blue-dark:#1e3a5f;--blue-dim:#0f1e33;
  --green:#10b981;--green-dark:#0d3d2a;--green-dim:#081e14;
  --purple:#8b5cf6;--purple-dark:#2d1b5e;--purple-dim:#16102e;
}"""
    LIGHT_VARS = """:root{
  --bg:#F8F9FA;--surface:#FFFFFF;--border:#E2E8F0;--text:#222222;--muted:#64748B;
  --blue:#1A5FA8;--blue-dark:#DBEAFE;--blue-dim:#EFF6FF;
  --green:#0D6B52;--green-dark:#D1FAE5;--green-dim:#ECFDF5;
  --purple:#5043B0;--purple-dark:#EDE9FE;--purple-dim:#F5F3FF;
}"""
    LIGHT_OVERRIDES = """
.hdr-title{color:#1e293b}
.bdg{background:#F1F5F9;border-color:#E2E8F0}
.bdg b{color:#1e293b}
.insight{background:#F8FAFC;color:#475569}
.conflict{background:#FFFBEB;border-color:#FDE68A;color:#92400E}
.conflict::before{color:#92400E}
.card-r{background:var(--blue-dim);border-color:#BFDBFE}
.card-c{background:var(--green-dim);border-color:#A7F3D0}
.card-p{background:var(--purple-dim);border-color:#DDD6FE}
.card-title{color:#1e293b}
.card-desc{color:#475569}
.tl-tx{color:#475569}
.tl-row::before{box-shadow:0 0 0 2px #F8F9FA}
.fear-tx{color:#475569}
.trf-g{background:#F0FDF4;border-color:#BBF7D0;color:#065F46}
.trf-g::before{color:#0D6B52}
.trf-l{background:#FFF7ED;border-color:#FED7AA;color:#9A3412}
.trf-l::before{color:#C2410C}
.toggle-btn{border-color:#E2E8F0;color:#64748B}
.toggle-btn:hover{background:#F1F5F9;color:#1e293b}
.panel-r .panel-inner{background:#F0F7FF;border-color:#BFDBFE}
.panel-c .panel-inner{background:#F0FDF8;border-color:#A7F3D0}
.panel-p .panel-inner{background:#F8F5FF;border-color:#DDD6FE}
.pb li{color:#475569}
.avoid-wrap{background:#FFF5F5;border-color:#FECACA}
.avoid-wrap li{color:#9B1C1C}
.panel-r .coach{background:#F0F7FF;border-color:#BFDBFE}
.panel-c .coach{background:#F0FDF8;border-color:#A7F3D0}
.panel-p .coach{background:#F8F5FF;border-color:#DDD6FE}
.coach-tx{color:#334155}
.sec{background:var(--surface);border-color:var(--border)}
.sec-title{color:#1e293b}
.bar:hover::after{background:#F1F5F9;color:#1e293b;border-color:#CBD5E1}
.final{background:linear-gradient(135deg,#EFF6FF 0%,#F5F3FF 50%,#ECFDF5 100%);border-color:#BFDBFE}
.final-tx{color:#334155}
.rec{background:var(--green-dim);border-color:#A7F3D0}
.rec-tx{color:#065F46}
.cu{color:#94A3B8}
"""
    CSS_VARS   = LIGHT_VARS   if theme == "light" else DARK_VARS
    CSS_EXTRA  = LIGHT_OVERRIDES if theme == "light" else ""

    CSS = CSS_VARS + """
*{box-sizing:border-box;margin:0;padding:0}
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
.cards-row{display:flex;flex-direction:column;gap:0}
@media(max-width:767px){.cards-row{gap:0}}
.card-wrap{border-bottom:1px solid var(--border);padding-bottom:28px;margin-bottom:28px}
.card-wrap:last-child{border-bottom:none;margin-bottom:0}
.card{border-radius:12px;padding:28px 32px;display:flex;flex-direction:column;gap:14px;transition:transform .2s,box-shadow .2s;cursor:default;position:relative;overflow:hidden}
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
.type-lbl{font-size:13px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--c);background:var(--cd);border:1px solid var(--ct);padding:3px 10px;border-radius:4px}
.ai-bdg{background:#8a6914;border:1px solid #b8960c;color:#fde68a;font-size:13px;font-weight:800;padding:3px 10px;border-radius:4px;letter-spacing:.3px}
.card-title{font-size:26px;font-weight:800;color:#f1f5f9;letter-spacing:-.3px}
.card-desc{font-size:16px;line-height:1.8;color:#94a3b8}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{background:var(--cd);color:var(--c);border:1px solid var(--ct);border-radius:4px;padding:3px 11px;font-size:13px;font-weight:700;letter-spacing:.3px}
.tl-hd{font-size:9px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.tl{display:flex;flex-direction:column;gap:1px;position:relative;padding-left:20px}
.tl::before{content:"";position:absolute;left:4px;top:6px;bottom:6px;width:1px;background:linear-gradient(to bottom,var(--c),transparent)}
.tl-row{display:flex;gap:8px;align-items:flex-start;padding:4px 0;position:relative}
.tl-row::before{content:"";position:absolute;left:-16px;top:9px;width:7px;height:7px;border-radius:50%;background:var(--c);box-shadow:0 0 0 2px var(--bg)}
.tl-yr{font-size:10px;font-weight:800;color:var(--c);min-width:26px;padding-top:1px}
.tl-tx{font-size:15px;color:#94a3b8;line-height:1.6}
.fear{background:var(--cd);border-left:3px solid var(--c);border-radius:0 8px 8px 0;padding:10px 14px}
.fear-hd{font-size:9px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--c);margin-bottom:5px}
.fear-tx{font-size:12px;line-height:1.75;color:#94a3b8;font-style:italic}
.trf{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.trf-box{padding:9px 11px;border-radius:7px;font-size:12px;line-height:1.65}
.trf-g{background:#041d10;border:1px solid #0d3d22;color:#6ee7b7}
.trf-g::before{content:"▲ 얻는 것\A";white-space:pre;font-size:9px;font-weight:800;letter-spacing:.5px;color:#10b981;text-transform:uppercase}
.trf-l{background:#1a0a00;border:1px solid #3d1a00;color:#fdba74}
.trf-l::before{content:"▼ 잃는 것\A";white-space:pre;font-size:9px;font-weight:800;letter-spacing:.5px;color:#f97316;text-transform:uppercase}
.card-actions{display:flex;gap:8px;margin-top:auto}
.toggle-btn{flex:1;padding:11px;border:1px solid var(--border);background:transparent;color:var(--muted);border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s;letter-spacing:.3px}
.toggle-btn:hover{background:#1e293b;color:#f1f5f9}
.toggle-btn.open{border-color:var(--c);color:var(--c)}
.sel-btn{flex:1;padding:11px;border:1px solid var(--c);background:transparent;color:var(--c);border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s;letter-spacing:.3px}
.sel-btn:hover,.sel-btn.on{background:var(--c);color:#0d1117}
.panel{overflow:hidden;max-height:0;transition:max-height .6s cubic-bezier(.4,0,.2,1),opacity .4s;opacity:0}
.panel.open{max-height:9000px;opacity:1;overflow:visible}
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
""" + CSS_EXTRA

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
  const cs=document.querySelectorAll('.card');
  const bs=document.querySelectorAll('.sel-btn');
  if(cur===i){{
    cs[i].classList.remove('active');
    bs[i].classList.remove('on');bs[i].textContent='이 시나리오 선택';
    cur=null;return;
  }}
  if(cur!==null){{
    cs[cur].classList.remove('active');
    bs[cur].classList.remove('on');bs[cur].textContent='이 시나리오 선택';
  }}
  cs[i].classList.add('active');
  bs[i].classList.add('on');bs[i].textContent='✔ 선택됨';
  cur=i;
}}

function togglePanel(i){{
  const p=document.getElementById('panel-'+i);
  const btn=document.getElementById('toggle-'+i);
  if(!p||!btn)return;
  const isOpen=p.classList.contains('open');
  if(isOpen){{
    p.classList.remove('open');
    btn.classList.remove('open');
    btn.textContent='▼ 실행 계획 보기';
  }}else{{
    p.classList.add('open');
    btn.classList.add('open');
    btn.textContent='▲ 접기';
  }}
  sendHeight();
  setTimeout(sendHeight,650);
  setTimeout(sendHeight,1000);
}}

function sendHeight(){{
  requestAnimationFrame(function(){{
    var h=Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight,
      document.body.offsetHeight
    );
    window.parent.postMessage({{type:'streamlit:setFrameHeight',height:h}},'*');
  }});
}}
window.addEventListener('load',function(){{setTimeout(sendHeight,100);}});
if(window.ResizeObserver){{
  new ResizeObserver(sendHeight).observe(document.body);
}}
new MutationObserver(sendHeight).observe(document.documentElement,{{subtree:true,childList:true,attributes:true}});

</script>
</body>
</html>"""


def render_compare_page():
    comp = st.session_state.compare_result
    old_data = st.session_state.compare_old_data

    if st.button("← 입력 화면으로"):
        st.session_state.page = "input"
        st.session_state.compare_result = None
        st.session_state.compare_old_data = None
        st.rerun()

    old_date = old_data.get("saved_at", old_data.get("date", ""))[:16].replace("T", " ")
    st.title("📊 시나리오 비교 분석")
    st.caption(f"과거 기록 ({old_date}) vs 현재 입력값")
    st.divider()

    # 항목별 변화
    st.subheader("항목별 변화")
    changes = comp.get("changes", [])
    dir_icon = {"up": "📈", "down": "📉", "changed": "🔄", "same": "➖"}
    for ch in changes:
        icon = dir_icon.get(ch.get("direction", "same"), "🔄")
        col1, col2, col3 = st.columns([2, 3, 5])
        with col1:
            st.markdown(f"**{ch.get('label', '')}**")
        with col2:
            st.markdown(f"{icon} `{ch.get('before', '')}` → `{ch.get('after', '')}`")
        with col3:
            st.caption(ch.get("comment", ""))
    st.divider()

    # 추천 시나리오 변화
    st.subheader("AI 추천 시나리오 변화")
    rec_ch = comp.get("recommendation_change", {})
    col1, col2 = st.columns(2)
    type_color = {"현실형": "🔵", "도전형": "🟢", "파격형": "🟣"}
    with col1:
        bt = rec_ch.get("before_type", "")
        st.metric("과거 추천", f"{type_color.get(bt, '')} {bt}")
    with col2:
        at = rec_ch.get("after_type", "")
        st.metric("현재 추천 (예측)", f"{type_color.get(at, '')} {at}")
    st.info(rec_ch.get("analysis", ""))
    st.divider()

    # 과거 next steps 달성 여부 체크리스트
    st.subheader("과거 Next Steps 달성 여부 체크리스트")
    checklist = comp.get("checklist", [])
    if checklist:
        for item in checklist:
            done = item.get("likely_done", False)
            icon = "✅" if done else "⬜"
            cat = item.get("category", "")
            st.markdown(f"{icon} **{item.get('item', '')}**" + (f"  <sub>({cat})</sub>" if cat else ""), unsafe_allow_html=True)
            st.caption(item.get("reason", ""))
    else:
        st.caption("체크리스트 항목이 없습니다.")
    st.divider()

    # AI 종합 분석
    st.subheader("AI 종합 분석")
    st.write(comp.get("overall_analysis", ""))


def _migrate_profile(profile: dict) -> dict:
    """구형(Q1-Q15/AGE/GENDER/TIME 키) 프로필을 id 기반 키로 변환."""
    migrated = {}
    for old_key, new_key in OLD_KEY_MIGRATION.items():
        if old_key in profile:
            migrated[new_key] = profile[old_key]
    for k in ("INCOME_SELECT", "INCOME_TEXT"):
        if k in profile:
            migrated[k] = profile[k]
    for q in QUESTIONS:
        id_key = q["id"]
        if id_key in profile and id_key not in migrated:
            migrated[id_key] = profile[id_key]
    return migrated


def _render_question(q: dict, inputs: dict) -> None:
    """단일 질문 위젯을 렌더링하고 inputs 딕셔너리를 채운다."""
    qid  = q["id"]
    wkey = f"input_{qid}"
    saved = st.session_state.inputs.get(qid)

    if q["type"] == "text":
        if wkey not in st.session_state:
            st.session_state[wkey] = "" if (not saved or saved == "입력 없음") else saved
        val = st.text_input(q["label"], placeholder=q.get("placeholder", ""), key=wkey)
        inputs[qid] = val.strip() if val.strip() else "입력 없음"

    elif q["type"] == "textarea":
        if wkey not in st.session_state:
            st.session_state[wkey] = "" if (not saved or saved == "입력 없음") else saved
        val = st.text_area(q["label"], placeholder=q.get("placeholder", ""), height=80, key=wkey)
        inputs[qid] = val.strip() if val.strip() else "입력 없음"

    elif q["type"] == "slider":
        default = int(saved) if saved and str(saved).isdigit() else 5
        if wkey not in st.session_state:
            st.session_state[wkey] = default
        val = st.slider(q["label"], min_value=1, max_value=10, key=wkey)
        st.caption(f"현재 선택: **{val} / 10**")
        inputs[qid] = str(val)

    elif q["type"] == "select":
        options = q["options"]
        if wkey not in st.session_state:
            st.session_state[wkey] = saved if saved in options else options[0]
        val = st.selectbox(q["label"], options=options, key=wkey)
        inputs[qid] = val

    elif q["type"] == "income_select":
        options = q["options"]
        saved_sel = st.session_state.inputs.get("INCOME_SELECT", "선택")
        if "input_INCOME_SELECT" not in st.session_state:
            st.session_state["input_INCOME_SELECT"] = saved_sel if saved_sel in options else "선택"
        sel = st.selectbox(q["label"], options=options, key="input_INCOME_SELECT")
        if sel == "직접 입력":
            saved_txt = st.session_state.inputs.get("INCOME_TEXT", "")
            if "input_INCOME_TEXT" not in st.session_state:
                st.session_state["input_INCOME_TEXT"] = saved_txt
            txt = st.text_input(
                "금액 직접 입력",
                placeholder="예) 연봉 5000만원, 월급 350만원",
                key="input_INCOME_TEXT",
            )
            inputs["INCOME_SELECT"] = sel
            inputs["INCOME_TEXT"] = txt.strip()
        else:
            inputs["INCOME_SELECT"] = sel
            inputs["INCOME_TEXT"] = ""


def _restore_session_from_history(hist: dict):
    """history 데이터를 session_state에 복원해 화면2·3이 정상 동작하게 한다."""
    result    = hist.get("result", {})
    inputs    = hist.get("inputs", {})
    scenarios = result.get("scenarios", [])
    # 저장된 selected_scenario 우선 사용, 없으면 AI 추천 시나리오 fallback
    saved_sel = hist.get("selected_scenario", {})
    saved_type = saved_sel.get("type", "")
    if saved_type and any(s.get("type") == saved_type for s in scenarios):
        selected = next(s for s in scenarios if s.get("type") == saved_type)
    else:
        rec_type = result.get("recommendation", {}).get("type", "")
        selected = next((s for s in scenarios if s.get("type") == rec_type),
                        scenarios[0] if scenarios else {})
    st.session_state.result            = result
    st.session_state.inputs            = inputs
    st.session_state.selected_scenario = selected


def _build_status_section_html(status: int, hist_data: dict, checklist_data: dict) -> str:
    """상태(1/2/3)에 맞는 {{STATUS_SECTION}} 치환용 HTML 블록 반환."""
    result    = hist_data.get("result", {})
    scenarios = result.get("scenarios", [])
    # 우선순위: 체크리스트 저장값(화면3 저장) > history 저장값 > AI 추천
    saved_sel      = checklist_data.get("selected_scenario") or hist_data.get("selected_scenario", {})
    saved_sel_type = (saved_sel or {}).get("type", "") or checklist_data.get("scenario_type", "")
    if saved_sel_type and any(s.get("type") == saved_sel_type for s in scenarios):
        display_sc = next(s for s in scenarios if s.get("type") == saved_sel_type)
        display_type = saved_sel_type
    else:
        rec          = result.get("recommendation", {})
        display_type = rec.get("type", "")
        display_sc   = next((s for s in scenarios if s.get("type") == display_type), {})
    sc_title     = display_sc.get("title", "")
    saved_at     = (hist_data.get("saved_at", hist_data.get("date", "")) or "")[:10]
    display_date = saved_at.replace("-", ".") or "—"
    TYPE_EMOJI   = {"현실형": "🔵", "도전형": "🟢", "파격형": "🟣"}
    emoji        = TYPE_EMOJI.get(display_type, "⭐")
    scenario_display = _e(f"{emoji} {display_type} — {sc_title}") if display_type else "—"
    rec_type     = display_type

    _checks_dict  = checklist_data.get("checks", {})
    _total        = max(len(_checks_dict), 1)
    checked_count = sum(1 for v in _checks_dict.values() if v)
    pct_int       = int(checked_count / _total * 100)
    unchecked_y1  = sum(1 for k, v in _checks_dict.items() if k.startswith("check_week_") and not v)

    if status == 1:
        return """
  <button class="plan-btn btn-locked" onclick="toast('🔒','먼저 인생 시나리오를 설계해주세요')">
    <span class="b-icon">📋</span>
    <span class="b-text">
      <span class="b-label">목표 달성 플랜 <span class="lock-tag">🔒 잠김</span></span>
      <span class="b-desc">선택한 시나리오 실행 현황 + AI 코칭</span>
    </span>
  </button>"""
    elif status == 2:
        return f"""
  <div class="card-result">
    <div class="cr-top">
      <div>
        <div class="cr-badge">📊 내 시나리오 결과</div>
        <div class="cr-name">{scenario_display}</div>
      </div>
      <div class="cr-date">분석일<br><strong>{_e(display_date)}</strong></div>
    </div>
    <div class="cr-actions">
      <button class="cr-btn cr-btn-outline" onclick="toast('📄','결과 화면으로 이동합니다')">결과 다시 보기</button>
      <button class="cr-btn cr-btn-fill" onclick="toast('🚀','목표달성플랜으로 이동합니다')">목표달성플랜 시작하기 →</button>
    </div>
  </div>"""
    else:
        return f"""
  <div class="card-progress">
    <div class="cp-top">
      <div class="cp-name">{scenario_display}</div>
      <div class="cp-todo">⚠️ 미완료 {unchecked_y1}개</div>
    </div>
    <div class="cp-bar-wrap">
      <div class="cp-bar-meta"><span>전체 진행률</span><span class="cp-pct">{pct_int}%</span></div>
      <div class="cp-bar"><div class="cp-fill" id="cpFill" data-pct="{pct_int}"></div></div>
    </div>
    <button class="cp-continue" onclick="toast('📋','플랜 진행 화면으로 이동합니다')">이어서 진행하기 →</button>
  </div>"""


def build_home_html(status: int, hist_data: dict, checklist_data: dict, theme: str = "dark") -> str:
    """screen0.html을 읽어 {{STATUS_SECTION}} 플레이스홀더를 상태별 HTML로 치환해 반환."""
    html_path = os.path.join(os.path.dirname(__file__), "screen0.html")
    if not os.path.exists(html_path):
        return ""

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    status_section = _build_status_section_html(status, hist_data, checklist_data)
    html_content = html_content.replace("{{STATUS_SECTION}}", status_section)

    return html_content


def _render_home_status_card(status: int, hist_data: dict, checklist_data: dict) -> None:
    """상태2·3의 시각 정보 카드를 st.markdown으로 렌더링 (클릭 없음)."""
    result    = hist_data.get("result", {})
    scenarios = result.get("scenarios", [])
    # 우선순위: 체크리스트 저장값(화면3 저장) > history 저장값 > AI 추천
    saved_sel      = checklist_data.get("selected_scenario") or hist_data.get("selected_scenario", {})
    saved_sel_type = (saved_sel or {}).get("type", "") or checklist_data.get("scenario_type", "")
    if saved_sel_type and any(s.get("type") == saved_sel_type for s in scenarios):
        display_sc   = next(s for s in scenarios if s.get("type") == saved_sel_type)
        display_type = saved_sel_type
    else:
        rec          = result.get("recommendation", {})
        display_type = rec.get("type", "")
        display_sc   = next((s for s in scenarios if s.get("type") == display_type), {})
    sc_title   = display_sc.get("title", "")
    TYPE_EMOJI = {"현실형": "🔵", "도전형": "🟢", "파격형": "🟣"}
    emoji      = TYPE_EMOJI.get(display_type, "⭐")
    sc_disp    = _e(f"{emoji} {display_type} — {sc_title}") if display_type else "—"

    if status == 2:
        saved_at     = (hist_data.get("saved_at", hist_data.get("date", "")) or "")[:10]
        display_date = saved_at.replace("-", ".") or "—"
        st.markdown(
            f'<div class="home-card-result">'
            f'  <div class="home-cr-top">'
            f'    <div>'
            f'      <div class="home-cr-badge">📊 내 시나리오 결과</div>'
            f'      <div class="home-cr-name">{sc_disp}</div>'
            f'    </div>'
            f'    <div class="home-cr-date">분석일<br><strong>{_e(display_date)}</strong></div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:  # status == 3
        _cd       = checklist_data.get("checks", {})
        _tot      = max(len(_cd), 1)
        checked   = sum(1 for v in _cd.values() if v)
        pct       = int(checked / _tot * 100)
        unchecked = sum(1 for k, v in _cd.items() if k.startswith("check_week_") and not v)
        st.markdown(
            f'<div class="home-card-progress">'
            f'  <div class="home-cp-top">'
            f'    <div class="home-cp-name">{sc_disp}</div>'
            f'    <div class="home-cp-todo">⚠️ 미완료 {unchecked}개</div>'
            f'  </div>'
            f'  <div>'
            f'    <div class="home-cp-meta">'
            f'      <span>전체 진행률</span>'
            f'      <span class="home-cp-pct">{pct}%</span>'
            f'    </div>'
            f'    <div class="home-cp-bg">'
            f'      <div class="home-cp-fill" style="width:{pct}%"></div>'
            f'    </div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_home_nav_buttons(status: int, hist_data: dict) -> None:
    """상태별 네이티브 네비게이션 버튼."""
    # ── 버튼 1: 인생 시나리오 시작 (항상) ───────────────────────────────────
    if st.button(
        "🎯  인생 시나리오 시작",
        type="primary",
        use_container_width=True,
        key="hn_start",
    ):
        st.session_state.page = "input"
        st.rerun()

    st.write("")

    # ── 버튼 2: 상태별 중간 영역 ────────────────────────────────────────────
    if status == 1:
        st.button(
            "🔒  목표 달성 플랜  (잠김)",
            disabled=True,
            use_container_width=True,
            key="hn_plan_locked",
        )

    elif status == 2:
        if st.button(
            "📊  결과 다시 보기",
            use_container_width=True,
            type="secondary",
            key="hn_result",
        ):
            _restore_session_from_history(hist_data)
            st.session_state.page = "result"
            st.rerun()
        if st.button(
            "▶  목표달성플랜 시작하기",
            use_container_width=True,
            type="secondary",
            key="hn_plan",
        ):
            _restore_session_from_history(hist_data)
            st.session_state.page = "plan"
            st.rerun()

    else:  # status == 3
        if st.button(
            "▶  이어서 진행하기 →",
            use_container_width=True,
            type="secondary",
            key="hn_continue",
        ):
            _restore_session_from_history(hist_data)
            st.session_state.page = "plan"
            st.rerun()

    st.write("")

    # ── 버튼 3: 커리어 설계 (항상) ──────────────────────────────────────────
    if st.button(
        "💼  3년 후 커리어 설계",
        use_container_width=True,
        type="secondary",
        key="hn_career",
    ):
        st.session_state["s4_prev_page"] = "home"
        st.session_state.page = "career"
        st.rerun()


def render_home_page():
    status         = get_user_status()
    hist_data      = _load_latest_history() if status >= 2 else {}
    checklist_data = _load_latest_career_checklist() if status >= 3 else {}

    # ── CSS 주입 ─────────────────────────────────────────────────────────────
    st.markdown(_HOME_PAGE_CSS, unsafe_allow_html=True)

    # ── 브랜드 헤더 ──────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="home-brand">'
        f'  {_COMPASS_SVG}'
        f'  <h1>AI 인생 시나리오 플래너</h1>'
        f'  <p>당신의 다음 10년을 설계하세요</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── 중앙 컬럼 레이아웃 ───────────────────────────────────────────────────
    _, col, _ = st.columns([1, 2, 1])
    with col:
        # 상태 정보 카드 (status 2, 3)
        if status >= 2:
            _render_home_status_card(status, hist_data, checklist_data)
            st.write("")

        # 네이티브 버튼
        _render_home_nav_buttons(status, hist_data)

        # ── 초기화 버튼 ──────────────────────────────────────────────────
        st.write("")
        st.write("")
        with st.expander("⚙️ 데이터 초기화"):
            st.warning(
                "초기화하면 저장된 모든 데이터(설문, 시나리오 결과, 실행 계획)가 삭제됩니다.\n\n"
                "이 작업은 되돌릴 수 없습니다."
            )
            confirmed = st.checkbox(
                "위 내용을 확인했으며, 모든 데이터를 삭제합니다.",
                key="reset_confirm_check",
            )
            if confirmed:
                if st.button(
                    "초기화 실행",
                    type="primary",
                    use_container_width=True,
                    key="hn_reset_exec",
                ):
                    import glob as _greset
                    for _pat in [
                        "profile.json",
                        "history_*.json",
                        "checklist_*.json",
                        "result_*.json",
                        "career_save_*.json",
                    ]:
                        for _f in _greset.glob(_pat):
                            try:
                                os.remove(_f)
                            except Exception:
                                pass
                    # session_state 초기화
                    for _k in list(st.session_state.keys()):
                        try:
                            del st.session_state[_k]
                        except Exception:
                            pass
                    st.session_state.page = "home"
                    st.rerun()


def render_input_page():
    if st.button("← 홈으로", key="input_home"):
        st.session_state.page = "home"
        st.rerun()

    st.title("AI 인생 시나리오 플래너")
    st.caption("18개 질문에 답하면 AI가 현실형·도전형·파격형 3가지 인생 시나리오를 분석해 드립니다.")

    col_load, col_compare = st.columns([1, 1])
    with col_load:
        if st.button("저장된 정보 불러오기", use_container_width=True):
            raw_profile = load_profile()
            if raw_profile:
                profile = _migrate_profile(raw_profile)
                st.session_state.inputs = profile
                for q in QUESTIONS:
                    qid = q["id"]
                    wkey = f"input_{qid}"
                    if q["type"] in ("text", "textarea"):
                        raw = profile.get(qid, "")
                        st.session_state[wkey] = "" if raw == "입력 없음" else (raw or "")
                    elif q["type"] == "slider":
                        raw = profile.get(qid, "5")
                        st.session_state[wkey] = int(raw) if str(raw).isdigit() else 5
                    elif q["type"] == "select":
                        options = q["options"]
                        raw = profile.get(qid, options[0])
                        st.session_state[wkey] = raw if raw in options else options[0]
                    elif q["type"] == "income_select":
                        options = q["options"]
                        raw_sel = profile.get("INCOME_SELECT", "선택")
                        st.session_state["input_INCOME_SELECT"] = raw_sel if raw_sel in options else "선택"
                        st.session_state["input_INCOME_TEXT"] = profile.get("INCOME_TEXT", "")
                st.success("프로필을 불러왔습니다.")
                st.rerun()
            else:
                st.warning("저장된 프로필이 없습니다.")

    with col_compare:
        if st.button("📊 과거 결과와 비교", use_container_width=True):
            st.session_state.compare_mode = not st.session_state.compare_mode
            st.rerun()

    if st.session_state.compare_mode:
        with st.container(border=True):
            st.markdown("**과거 결과 선택**")
            history_items = list_history()
            if not history_items:
                st.warning("저장된 과거 기록이 없습니다. 결과 화면에서 '이 결과 저장' 버튼을 눌러 기록을 남기세요.")
                if st.button("닫기", key="close_compare"):
                    st.session_state.compare_mode = False
                    st.rerun()
            else:
                options = {item["label"]: item for item in history_items}
                selected_label = st.selectbox("비교할 과거 기록 선택", list(options.keys()), key="compare_select")
                if st.button("비교 분석 시작", type="primary", use_container_width=True, key="compare_start"):
                    selected_data = options[selected_label]["data"]
                    cur_inputs = st.session_state.inputs
                    if not any(cur_inputs.get(k) for k in ("job", "satisfaction", "endurance", "skill", "saving")):
                        st.warning("먼저 현재 입력값을 작성해 주세요.")
                    else:
                        with st.spinner("AI가 비교 분석 중입니다... (30초~1분 소요)"):
                            try:
                                comp_result = generate_comparison(selected_data, cur_inputs)
                                st.session_state.compare_result = comp_result
                                st.session_state.compare_old_data = selected_data
                                st.session_state.compare_mode = False
                                st.session_state.page = "compare"
                                st.rerun()
                            except Exception as e:
                                st.error(f"비교 분석 오류: {e}")

    inputs = {}

    for sec in SECTIONS:
        st.divider()
        st.subheader(sec["title"])
        st.caption(sec["desc"])
        for q in sec["questions"]:
            _render_question(q, inputs)
            st.write("")

    st.divider()

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("내 정보 저장", use_container_width=True):
            save_profile(inputs)
            st.success("저장 완료")

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
    # PDF 미리 생성 (버튼 렌더링에 필요)
    pdf_bytes = None
    try:
        pdf_bytes = generate_pdf(st.session_state.result, st.session_state.inputs)
    except Exception:
        pass

    # ── 페이지 제목 ──────────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:36px;font-weight:900;letter-spacing:-.5px;'
        'margin:0 0 12px;color:#f1f5f9">인생 시나리오</p>',
        unsafe_allow_html=True,
    )

    col_home, col_back, col_save_hist, col_pdf = st.columns([2, 3, 2, 2])
    with col_home:
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with col_back:
        if st.button("← 다시 입력하기", use_container_width=True):
            st.session_state.page = "input"
            st.session_state.result = None
            st.rerun()
    with col_save_hist:
        if st.button("💾 이 결과 저장", use_container_width=True):
            try:
                save_history(st.session_state.inputs, st.session_state.result)
                st.success("저장 완료")
            except Exception as e:
                st.error(f"저장 실패: {e}")
    with col_pdf:
        if pdf_bytes:
            fname = f"scenario_report_{datetime.date.today().strftime('%Y%m%d')}.pdf"
            st.download_button(
                label="📄 PDF로 저장",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )
    st.divider()
    _result = st.session_state.result
    _rec_type = _result.get("recommendation", {}).get("type", "")
    _scenarios = _result.get("scenarios", [])
    if _scenarios:
        _TYPE_EMOJI  = {"현실형": "🔵", "도전형": "🟢", "파격형": "🟣"}
        _TYPE_COLOR  = {"현실형": "#3b82f6", "도전형": "#10b981", "파격형": "#8b5cf6"}
        st.markdown("##### ▶ 실행할 시나리오를 선택하세요")
        # AI 추천 버튼: 해당 시나리오 색상 테두리 강조 CSS 주입
        _rec_color = _TYPE_COLOR.get(_rec_type, "#10b981")
        st.markdown(
            f'<style>[data-testid="stButton"] button[data-testid="baseButton-secondary"]'
            f'[kind="secondary"]{{}} '
            f'div[data-testid="column"]:has(button[aria-label*="{_rec_type}"]) button'
            f'{{border:2px solid {_rec_color}!important;'
            f'background:rgba({",".join(str(int(_rec_color.lstrip("#")[i:i+2],16)) for i in (0,2,4))},0.12)!important;'
            f'color:#f1f5f9!important}}</style>',
            unsafe_allow_html=True,
        )
        _plan_cols = st.columns(len(_scenarios))
        for _plan_col, _sc in zip(_plan_cols, _scenarios):
            with _plan_col:
                _sc_type = _sc.get("type", "")
                _is_rec  = (_sc_type == _rec_type)
                _emoji   = _TYPE_EMOJI.get(_sc_type, "")
                _label   = f"{_emoji} {_sc_type}"
                if st.button(
                    _label,
                    help=_sc.get("title", ""),
                    use_container_width=True,
                    type="secondary",
                    key=f"go_plan_{_sc_type}",
                ):
                    st.session_state.selected_scenario = _sc
                    st.session_state.page = "plan"
                    st.rerun()
                if _is_rec:
                    st.caption("⭐ AI 추천")
                st.caption(_sc.get("title", ""))

    theme = st.session_state.get("theme", "dark")
    html_content = build_result_html(st.session_state.result, st.session_state.inputs, theme)
    components.html(html_content, height=200, scrolling=False)

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
    apply_theme()
    render_theme_toggle()

    # ── 로그인 체크 (Streamlit 내장 OIDC) ────────────────────────────────────
    if not _safe_get_user_info()["is_logged_in"]:
        render_login_page()

    render_user_sidebar()

    if st.session_state.page == "home":
        render_home_page()
    elif st.session_state.page == "input":
        render_input_page()
    elif st.session_state.page == "compare":
        render_compare_page()
    elif st.session_state.page == "plan":
        if SCREEN3_ENABLED:
            screen3_plan.render()
        else:
            st.warning("화면3 점검 중입니다.")
            if st.button("← 결과로 돌아가기"):
                st.session_state.page = "result"
                st.rerun()
    elif st.session_state.page == "career":
        screen4_career.render(pdf_fn=generate_pdf)
    elif st.session_state.page == "result":
        render_result_page()
    else:
        st.session_state.page = "home"
        st.rerun()


if __name__ == "__main__":
    main()
