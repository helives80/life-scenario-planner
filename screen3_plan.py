import streamlit as st
import json
import os
import glob
import datetime

try:
    from google import genai as genai_v2
    from google.genai import types as gtypes
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False


CHECKLIST_SECTIONS = [
    ("이번 주 바로 할 것",   "this_week",     "week"),
    ("1개월 내 준비 사항",   "one_month",     "month"),
    ("3개월 내 이룰 것",     "three_months",  "3month"),
    ("반드시 갖춰야 할 것",  "must_prepare",  "prepare"),
    ("반드시 피해야 할 것",  "must_avoid",    "avoid"),
]

_SEC_ICON = {
    "this_week": "✅", "one_month": "📌",
    "three_months": "🎯", "must_prepare": "⭐", "must_avoid": "⚠️",
}

# ── 화면3 전용 CSS (스코프: .s3-* 커스텀 클래스만 사용) ─────────────────────
S3_CSS = """<style>
.s3-card{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;
  padding:18px 22px;margin:8px 0 18px;box-shadow:0 4px 20px rgba(0,0,0,.35)}
.s3-title{font-size:1rem;font-weight:700;color:#e8e8f0;
  display:flex;align-items:center;gap:8px;margin-bottom:10px}
.s3-sec-hdr{font-size:.95rem;font-weight:700;color:#e8e8f0;
  background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;
  padding:10px 16px;margin:14px 0 4px;display:flex;align-items:center;gap:8px}
.s3-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0}
.s3-stat{background:#16213e;border:1px solid #2a2a4a;border-radius:10px;
  padding:12px;text-align:center}
.s3-num{font-size:1.5rem;font-weight:800}
.s3-lbl{font-size:.72rem;color:#9090b0;margin-top:2px}
.s3-g{color:#2ecc71}.s3-y{color:#f59e0b}.s3-p{color:#a78bfa}
[data-testid="stProgress"]>div>div{
  background:linear-gradient(90deg,#7c6fcd,#3b82f6)!important;
  border-radius:99px!important}
.s3-smart-badges{display:flex;gap:8px;margin:2px 0 6px 28px;flex-wrap:wrap}
.s3-badge-metric{background:#0d2a1a;border:1px solid #1a4a2a;color:#4ade80;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:600}
.s3-badge-deadline{background:#0f0f2e;border:1px solid #2a2a5a;color:#a78bfa;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:600}
.s3-smart-tag{display:inline-block;background:#1a2235;border:1px solid #2a3a55;
  color:#60a5fa;padding:1px 7px;border-radius:4px;font-size:.7rem;margin-left:6px}
.s3-q-goal{background:linear-gradient(135deg,#1a1a3e,#0f2040);
  border-left:4px solid #6c63ff;border-radius:10px;
  padding:14px 18px;margin:4px 0 16px;font-size:1rem;font-weight:700;color:#e8e8f0}
.s3-badge-week{background:#3d0f0f;border:1px solid #7f1d1d;color:#fca5a5;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:700;margin-left:6px}
.s3-badge-month{background:#3d1f00;border:1px solid #7c2d12;color:#fdba74;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:700;margin-left:6px}
.s3-badge-3m{background:#052e16;border:1px solid #14532d;color:#86efac;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:700;margin-left:6px}
.s3-badge-res{background:#0c1a4a;border:1px solid #1e3a8a;color:#93c5fd;
  padding:2px 9px;border-radius:4px;font-size:.72rem;font-weight:700;margin-left:6px}
.s3-avoid-box{background:#1a0a0a;border:2px solid #7f1d1d;border-radius:10px;
  padding:12px 16px;margin:10px 0 4px;color:#fca5a5;font-size:.9rem}
.s3-res-item{color:#93c5fd;padding:3px 0 3px 8px;font-size:.9rem}
</style>"""

# ── 화면3 라이트 모드 override (screen4 방식과 동일) ───────────────────────────
S3_CSS_LIGHT_OVERRIDE = """<style>
.s3-card{background:#ffffff!important;border-color:#dde0f0!important;
  box-shadow:0 2px 8px rgba(0,0,0,.08)!important}
.s3-title{color:#1a1a2e!important}
.s3-sec-hdr{color:#1a1a2e!important;background:#f0f2ff!important;border-color:#dde0f0!important}
.s3-stat{background:#f0f2ff!important;border-color:#dde0f0!important}
.s3-lbl{color:#606080!important}
.s3-g{color:#1a7a45!important}
.s3-y{color:#b45309!important}
.s3-p{color:#5b21b6!important}
.s3-q-goal{background:linear-gradient(135deg,#eff0ff,#e8eeff)!important;
  border-left-color:#6c63ff!important;color:#1a1a2e!important}
.s3-avoid-box{background:#fff0f0!important;border-color:#dc2626!important;color:#7f1d1d!important}
.s3-res-item{color:#1e40af!important}
.s3-smart-tag{background:#eff0ff!important;border-color:#c7d2fe!important;color:#3730a3!important}
.s3-badge-metric{background:#f0fdf4!important;border-color:#86efac!important;color:#166534!important}
.s3-badge-deadline{background:#faf5ff!important;border-color:#d8b4fe!important;color:#6b21a8!important}
.s3-badge-week{background:#fff0f0!important;border-color:#fca5a5!important;color:#991b1b!important}
.s3-badge-month{background:#fff7ed!important;border-color:#fdba74!important;color:#9a3412!important}
.s3-badge-3m{background:#f0fdf4!important;border-color:#86efac!important;color:#166534!important}
.s3-badge-res{background:#eff6ff!important;border-color:#93c5fd!important;color:#1e40af!important}
</style>"""

# ── AI 평가 프롬프트 / 스키마 ────────────────────────────────────────────────

EVAL_SYSTEM_PROMPT = """
당신은 AI 인생 시나리오 실행 코치입니다.
사용자의 원본 입력값, 선택한 시나리오, 현재까지 완료한 실행 항목을 받아
아래 JSON 한 개만 반환합니다. 코드펜스·설명·주석 등 JSON 외 어떤 문자도 금지.

반환 JSON 스키마:
{
  "evaluation": {
    "execution": "A~F 등급과 한 줄 평가 (예: B — 이번 주 2개 중 1개 완료, 속도 양호)",
    "speed":     "A~F 등급과 한 줄 평가",
    "direction": "A~F 등급과 한 줄 평가"
  },
  "message": "Q8 두려움과 Q13 고민을 직접 인용한 2~3문장 평가 메시지",
  "suggestions": ["조정 제안 1", "조정 제안 2"],
  "encouragement": "입력값을 반영한 1~2문장 격려 메시지"
}

evaluation.execution: 완료된 항목 비율과 항목 구체성을 기준으로 평가.
evaluation.speed: 완료 속도(예상 대비 진척도)를 기준으로 평가.
evaluation.direction: 선택 시나리오의 목표(Q10)와 현재 행동의 정렬도 평가.
message: Q8(두려움)·Q13(고민)을 반드시 큰따옴표로 직접 인용.
suggestions: 미완료 항목 중 우선순위가 높은 것 2개 제안.
encouragement: Q10(목표)·Q11(버킷리스트) 중 하나를 직접 인용.
"""

EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "evaluation": {
            "type": "object",
            "properties": {
                "execution": {"type": "string"},
                "speed":     {"type": "string"},
                "direction": {"type": "string"},
            },
            "required": ["execution", "speed", "direction"],
        },
        "message":       {"type": "string"},
        "suggestions":   {"type": "array", "items": {"type": "string"}},
        "encouragement": {"type": "string"},
    },
    "required": ["evaluation", "message", "suggestions", "encouragement"],
}

# ── 화면3 SMART 실행계획 변환 프롬프트/스키마 ───────────────────────────────

SMART_NS_SYSTEM_PROMPT = """
당신은 실행 코치입니다. 화면2(시나리오 카드)의 next_steps 를 받아
더 구체적인 SMART 실행 액션으로 변환한 JSON 한 개만 반환합니다.
코드펜스·설명·주석 등 JSON 외 어떤 문자도 금지.

변환 규칙:
1. 각 항목을 SMART(구체·측정가능·달성가능·관련성·시한) 형식으로 재작성.
2. task: 무엇을, 얼마나, 어떻게 할지 1문장으로 기술.
3. metric: 완료를 판단하는 측정 지표 (횟수·금액·완료 여부 등) 1개.
4. deadline: 이 항목을 마쳐야 할 요일·날짜·주차 등 구체적 시한.
5. 사용자 입력값(직업·기술·자금·가족·두려움) 중 최소 1개를 task 에 직접 인용.
6. "열심히", "꾸준히" 같은 추상어 금지.
7. 각 섹션의 항목 개수는 원본과 반드시 동일하게 유지.
8. must_prepare·must_avoid 는 더 구체적인 단문으로 재작성(단순 문자열).
"""

_SMART_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "task":     {"type": "string"},
        "metric":   {"type": "string"},
        "deadline": {"type": "string"},
    },
    "required": ["task", "metric", "deadline"],
}

SMART_NS_SCHEMA = {
    "type": "object",
    "properties": {
        "this_week":    {"type": "array", "items": _SMART_ITEM_SCHEMA},
        "one_month":    {"type": "array", "items": _SMART_ITEM_SCHEMA},
        "three_months": {"type": "array", "items": _SMART_ITEM_SCHEMA},
        "must_prepare": {"type": "array", "items": {"type": "string"}},
        "must_avoid":   {"type": "array", "items": {"type": "string"}},
    },
    "required": ["this_week", "one_month", "three_months", "must_prepare", "must_avoid"],
}

# ── 화면3 분기별 실행계획 프롬프트/스키마 ───────────────────────────────────

QUARTERLY_PLAN_SYSTEM_PROMPT = """당신은 커리어 코치입니다.
사용자가 선택한 시나리오를 실제로 실행하기 위한
구체적인 분기별 실행 계획을 작성해주세요.

각 분기(Q1~Q4)마다:
- 분기 핵심 목표 1개 (측정 가능한 수치 포함)
- 이번 주 바로 할 것 2개 (오늘 당장 실행 가능한 행동)
- 이번 달 완료 항목 3개 (구체적 행동 + 예상 소요 시간)
- 3개월 내 달성 목표 2개 (검증 가능한 결과물)
- 필요한 자원·도구 2개 (비용·시간 포함)
- 이 분기에 반드시 피해야 할 것 1개

사용자 직업·기술·두려움·연봉을 모두 반영해서
현실적이고 구체적으로 작성하세요.
코드펜스·설명·주석 등 JSON 외 어떤 문자도 금지."""

_Q_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "quarter":          {"type": "string"},
        "main_goal":        {"type": "string"},
        "this_week":        {"type": "array", "items": {"type": "string"}},
        "this_month":       {"type": "array", "items": {"type": "string"}},
        "three_month_goal": {"type": "array", "items": {"type": "string"}},
        "resources":        {"type": "array", "items": {"type": "string"}},
        "avoid":            {"type": "string"},
    },
    "required": ["quarter", "main_goal", "this_week", "this_month",
                 "three_month_goal", "resources", "avoid"],
}

QUARTERLY_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "quarters": {"type": "array", "items": _Q_ITEM_SCHEMA},
    },
    "required": ["quarters"],
}

# ── 체크리스트 저장/불러오기 ─────────────────────────────────────────────────

def cleanup_old_checklists(days: int = 30):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for f in glob.glob("checklist_*.json"):
        try:
            if datetime.datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:
                os.remove(f)
        except Exception:
            pass


def load_latest_checklist(scenario_type: str) -> dict:
    files = sorted(glob.glob(f"checklist_{scenario_type}_*.json"), reverse=True)
    if not files:
        return {}
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_checklist(scenario_type: str, checks: dict, scenario: dict = None):
    today = datetime.date.today().strftime("%Y%m%d")
    path = f"checklist_{scenario_type}_{today}.json"
    data = {
        "date": datetime.date.today().isoformat(),
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "scenario_type": scenario_type,
        "selected_scenario": scenario or {},
        "checks": checks,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"체크리스트 저장 중 오류가 발생했습니다: {e}")


def save_quarterly_plan(scenario_type: str, plan_data: dict):
    """분기별 실행계획을 checklist_구체화_*.json으로 저장."""
    today = datetime.date.today().strftime("%Y%m%d")
    path = f"checklist_구체화_{today}_{scenario_type}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.date.today().isoformat(),
                "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "scenario_type": scenario_type,
                "plan": plan_data,
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _call_quarterly_plan_api(inputs: dict, scenario: dict) -> dict:
    """분기별(Q1~Q4) 구체 실행계획을 Gemini로 생성."""
    if not _GENAI_OK:
        return {}

    lines = ["=== 사용자 정보 ==="]
    for id_key, label in [
        ("job", "직업"), ("skill", "기술"), ("saving", "자금"),
        ("fear", "두려움"), ("goal", "목표"), ("satisfaction", "만족도"),
        ("family_support", "가족지지"),
    ]:
        val = inputs.get(id_key, "")
        if val and val != "입력 없음":
            lines.append(f"  {label}: {val}")
    inc_sel = inputs.get("INCOME_SELECT", "")
    inc_txt = inputs.get("INCOME_TEXT", "")
    if inc_sel == "직접 입력" and inc_txt:
        lines.append(f"  현재 소득: {inc_txt}")
    elif inc_sel not in ("선택", "직접 입력", "", None):
        lines.append(f"  현재 소득: {inc_sel}")

    lines += [
        "",
        f"=== 선택 시나리오: {scenario.get('type', '')} — {scenario.get('title', '')} ===",
        scenario.get("description", ""),
    ]

    client = genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="\n".join(lines),
        config=gtypes.GenerateContentConfig(
            system_instruction=QUARTERLY_PLAN_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=QUARTERLY_PLAN_SCHEMA,
            temperature=0.7,
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _render_quarter_card(qdata: dict, q_idx: int, all_checks: dict):
    """분기 카드 한 개를 렌더링하고 all_checks에 체크박스 상태를 기록."""
    q_label      = qdata.get("quarter", f"Q{q_idx + 1}")
    main_goal    = qdata.get("main_goal", "")
    this_week    = qdata.get("this_week", [])
    this_month   = qdata.get("this_month", [])
    three_m_goal = qdata.get("three_month_goal", [])
    resources    = qdata.get("resources", [])
    avoid        = qdata.get("avoid", "")

    with st.expander(f"**{q_label}** — {main_goal}", expanded=(q_idx == 0)):
        st.markdown(
            f'<div class="s3-q-goal">🎯 {main_goal}</div>',
            unsafe_allow_html=True,
        )

        if this_week:
            st.markdown(
                '<p class="s3-sec-hdr">✅ 이번 주 바로 할 것'
                ' <span class="s3-badge-week">이번 주</span></p>',
                unsafe_allow_html=True,
            )
            for i, item in enumerate(this_week):
                ck_key = f"qplan_{q_idx}_week_{i}"
                all_checks[ck_key] = st.checkbox(item, key=ck_key)

        if this_month:
            st.markdown(
                '<p class="s3-sec-hdr">📌 이번 달 완료 항목'
                ' <span class="s3-badge-month">이번 달</span></p>',
                unsafe_allow_html=True,
            )
            for i, item in enumerate(this_month):
                ck_key = f"qplan_{q_idx}_month_{i}"
                all_checks[ck_key] = st.checkbox(item, key=ck_key)

        if three_m_goal:
            st.markdown(
                '<p class="s3-sec-hdr">🎯 3개월 내 달성 목표'
                ' <span class="s3-badge-3m">3개월 목표</span></p>',
                unsafe_allow_html=True,
            )
            for i, item in enumerate(three_m_goal):
                ck_key = f"qplan_{q_idx}_3m_{i}"
                all_checks[ck_key] = st.checkbox(item, key=ck_key)

        if resources:
            st.markdown(
                '<p class="s3-sec-hdr">⭐ 필요 자원·도구'
                ' <span class="s3-badge-res">필요 자원</span></p>',
                unsafe_allow_html=True,
            )
            for item in resources:
                st.markdown(
                    f'<div class="s3-res-item">• {item}</div>',
                    unsafe_allow_html=True,
                )

        if avoid:
            st.markdown(
                f'<div class="s3-avoid-box">⚠️ <strong>이 분기 반드시 피할 것:</strong> {avoid}</div>',
                unsafe_allow_html=True,
            )

        # 분기별 완료율
        q_keys   = [k for k in all_checks if k.startswith(f"qplan_{q_idx}_week_")
                    or k.startswith(f"qplan_{q_idx}_month_")
                    or k.startswith(f"qplan_{q_idx}_3m_")]
        q_done   = sum(1 for k in q_keys if all_checks.get(k))
        q_total  = len(q_keys)
        if q_total:
            pct = int(q_done / q_total * 100)
            st.progress(pct / 100, text=f"완료율 {pct}% ({q_done}/{q_total})")


def _item_text(item) -> str:
    """dict 또는 str 항목에서 표시 텍스트를 추출한다."""
    if isinstance(item, dict):
        return item.get("task", "")
    return str(item)


def _call_smart_ns_api(inputs: dict, scenario: dict, original_ns: dict) -> dict:
    """화면2 next_steps 를 SMART 실행 액션으로 변환. 실패 시 빈 dict 반환."""
    if not _GENAI_OK:
        return {}

    lines = ["=== 사용자 입력값 ==="]
    for id_key, label in [
        ("job", "직업"), ("satisfaction", "만족도"), ("skill", "기술"),
        ("saving", "자금"), ("family_support", "가족지지"),
        ("fear", "두려움"), ("goal", "목표"),
    ]:
        val = inputs.get(id_key, "")
        if val and val != "입력 없음":
            lines.append(f"  {label}: {val}")

    lines += [
        "",
        f"=== 선택 시나리오: {scenario.get('type', '')} — {scenario.get('title', '')} ===",
        "",
        "=== 원본 next_steps (변환 대상) ===",
    ]
    for _, ns_key, _ in CHECKLIST_SECTIONS:
        items = original_ns.get(ns_key, [])
        if items:
            lines.append(f"[{ns_key}]")
            for it in items:
                lines.append(f"  - {_item_text(it)}")

    client = genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="\n".join(lines),
        config=gtypes.GenerateContentConfig(
            system_instruction=SMART_NS_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=SMART_NS_SCHEMA,
            temperature=0.6,
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _init_checks(scenario_type: str, ns: dict):
    """시나리오가 바뀔 때만 체크 상태와 채팅 히스토리를 초기화."""
    if st.session_state.get("checklist_scenario_type") == scenario_type:
        return
    st.session_state.checklist_scenario_type = scenario_type
    loaded = load_latest_checklist(scenario_type).get("checks", {})
    for _, ns_key, key_prefix in CHECKLIST_SECTIONS:
        for idx in range(len(ns.get(ns_key, []))):
            ck_key = f"check_{key_prefix}_{idx}"
            st.session_state[ck_key] = loaded.get(ck_key, False)
    # 시나리오 전환 시 채팅 + SMART ns 캐시 초기화
    st.session_state.coach_chat = []
    st.session_state.coach_error = None
    st.session_state.coach_pending_msg = None
    for _k in ("s3_smart_ns", "s3_smart_ns_type", "s3_smart_ns_failed", "s3_smart_ns_err",
               "s3_qplan", "s3_qplan_type", "s3_qplan_failed", "s3_qplan_err"):
        st.session_state.pop(_k, None)

# ── AI 평가 ──────────────────────────────────────────────────────────────────

def _build_eval_prompt(inputs: dict, scenario: dict, completed_items: list) -> str:
    id_to_q = {
        "job": "Q1(직업)", "satisfaction": "Q2(만족도)", "endurance": "Q3(버틸기간)",
        "skill": "Q4(기술)", "saving": "Q5(저축)", "family_support": "Q6(가족지지)",
        "priority": "Q7(포기불가)", "fear": "Q8(두려움)", "rolemodel": "Q9(롤모델)",
        "goal": "Q10(목표)", "bucketlist": "Q11(버킷리스트)", "change_5y": "Q12(5년전)",
        "worry": "Q13(고민)", "changeable": "Q14(바꿀수있는것)",
    }
    lines = ["=== 원본 입력값 ==="]
    for id_key, label in id_to_q.items():
        val = inputs.get(id_key, "입력 없음")
        lines.append(f"{label}: {val}")
    inc_sel = inputs.get("INCOME_SELECT", "")
    inc_txt = inputs.get("INCOME_TEXT", "")
    if inc_sel == "직접 입력" and inc_txt:
        lines.append(f"소득: {inc_txt}")
    elif inc_sel not in ("직접 입력 안 함", "직접 입력", ""):
        lines.append(f"소득: {inc_sel}")

    lines += [
        "",
        f"=== 선택 시나리오: {scenario.get('type', '')} — {scenario.get('title', '')} ===",
        scenario.get("description", ""),
        "",
        "=== 완료한 실행 항목 ===",
    ]
    if completed_items:
        lines += [f"  ✅ {item}" for item in completed_items]
    else:
        lines.append("  (아직 완료한 항목 없음)")

    return "\n".join(lines)


def _call_eval_api(prompt_text: str) -> dict:
    if not _GENAI_OK:
        raise RuntimeError("google-genai SDK를 불러오지 못했습니다.")
    client = genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_text,
        config=gtypes.GenerateContentConfig(
            system_instruction=EVAL_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EVAL_SCHEMA,
            temperature=0.7,
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _render_eval(eval_data: dict):
    ev = eval_data.get("evaluation", {})
    grade_color = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "E": "🔴", "F": "🔴"}

    st.markdown("#### 실행 평가")
    col1, col2, col3 = st.columns(3)
    for col, (label, key) in zip(
        [col1, col2, col3],
        [("실행력", "execution"), ("속도", "speed"), ("방향성", "direction")],
    ):
        val = ev.get(key, "")
        grade = val[0].upper() if val else "?"
        icon = grade_color.get(grade, "⚪")
        with col:
            st.metric(label=f"{icon} {label}", value=grade)
            st.caption(val[2:].strip() if len(val) > 2 else val)

    st.markdown("#### AI 평가 메시지")
    st.info(eval_data.get("message", ""))

    suggestions = eval_data.get("suggestions", [])
    if suggestions:
        st.markdown("#### 조정 제안")
        for s in suggestions:
            st.markdown(f"- {s}")

    enc = eval_data.get("encouragement", "")
    if enc:
        st.success(enc)


def _render_ai_evaluation(inputs: dict, scenario: dict, ns: dict, all_checks: dict):
    st.divider()
    st.markdown("### AI 중간 평가")

    if not _GENAI_OK:
        st.error("google-genai SDK가 설치되지 않았습니다. `pip install google-genai --upgrade`를 실행하세요.")
        return
    if not os.environ.get("GEMINI_API_KEY", ""):
        st.warning("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    completed_items = [
        _item_text(item)
        for _, ns_key, key_prefix in CHECKLIST_SECTIONS
        for idx, item in enumerate(ns.get(ns_key, []))
        if all_checks.get(f"check_{key_prefix}_{idx}", False)
    ]
    total_checks = sum(len(ns.get(s[1], [])) for s in CHECKLIST_SECTIONS)
    pct_overall = int(len(completed_items) / total_checks * 100) if total_checks else 0

    if pct_overall >= 70:
        st.info(f"전체 완료율 **{pct_overall}%** 달성! AI 평가를 받아보세요.")

    col_btn, col_clear = st.columns([3, 1])
    with col_btn:
        run_eval = st.button("🤖 AI 평가 받기", type="primary", use_container_width=True)
    with col_clear:
        if st.button("결과 지우기", use_container_width=True):
            st.session_state.eval_result = None
            st.rerun()

    if run_eval:
        with st.spinner("AI가 실행 상황을 평가 중입니다... (20~40초 소요)"):
            try:
                eval_data = _call_eval_api(
                    _build_eval_prompt(inputs, scenario, completed_items)
                )
                st.session_state.eval_result = eval_data
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"AI 응답을 파싱하지 못했습니다: {e}")
                with st.expander("원본 응답 보기"):
                    st.text(getattr(e, "doc", ""))
                if st.button("재시도", key="retry_json"):
                    st.rerun()
            except Exception as e:
                st.error(f"AI 평가 호출 중 오류가 발생했습니다: {e}")
                if st.button("재시도", key="retry_api"):
                    st.rerun()

    if st.session_state.get("eval_result"):
        _render_eval(st.session_state.eval_result)

# ── AI 코치 채팅 ──────────────────────────────────────────────────────────────

def _build_coach_system_prompt(inputs: dict, all_checks: dict, ns: dict, scenario: dict) -> str:
    id_to_label = {
        "job": "직업", "satisfaction": "만족도", "endurance": "버틸기간",
        "skill": "기술", "saving": "저축", "family_support": "가족지지",
        "priority": "포기불가", "fear": "두려움(Q8)", "rolemodel": "롤모델",
        "goal": "목표(Q10)", "bucketlist": "버킷리스트", "change_5y": "5년전변화",
        "worry": "고민(Q13)", "changeable": "바꿀수있는것",
    }
    lines = [
        "당신은 인생 코치입니다. 사용자의 15개 입력값과 현재 실행 현황을 알고 있습니다.",
        "직설적이지만 따뜻한 코치 톤으로 한국어 존댓말로 답변하세요.",
        "막연한 격려나 클리셰('열심히 하세요', '할 수 있습니다') 대신 입력값을 직접 인용해 구체적으로 답변하세요.",
        "",
        "[15개 입력값 요약]",
    ]
    for id_key, label in id_to_label.items():
        val = inputs.get(id_key, "")
        if val and val != "입력 없음":
            lines.append(f"  {label}: {val}")
    inc_sel = inputs.get("INCOME_SELECT", "")
    inc_txt = inputs.get("INCOME_TEXT", "")
    if inc_sel == "직접 입력" and inc_txt:
        lines.append(f"  소득: {inc_txt}")
    elif inc_sel not in ("직접 입력 안 함", "직접 입력", ""):
        lines.append(f"  소득: {inc_sel}")

    lines += [
        "",
        f"[선택 시나리오: {scenario.get('type', '')} — {scenario.get('title', '')}]",
        "",
        "[체크 완료 항목 요약]",
    ]
    completed = [
        _item_text(item)
        for _, ns_key, key_prefix in CHECKLIST_SECTIONS
        for idx, item in enumerate(ns.get(ns_key, []))
        if all_checks.get(f"check_{key_prefix}_{idx}", False)
    ]
    if completed:
        lines += [f"  ✅ {item}" for item in completed]
    else:
        lines.append("  (아직 완료 항목 없음)")

    return "\n".join(lines)


def _call_coach_api(system_prompt: str, history: list, user_msg: str) -> str:
    if not _GENAI_OK:
        raise RuntimeError("google-genai SDK를 불러오지 못했습니다.")

    contents = [
        gtypes.Content(
            role="user" if msg["role"] == "user" else "model",
            parts=[gtypes.Part(text=msg["content"])],
        )
        for msg in history
    ]
    contents.append(
        gtypes.Content(role="user", parts=[gtypes.Part(text=user_msg)])
    )

    client = genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
        ),
    )
    return response.text


def _render_chat(inputs: dict, scenario: dict, ns: dict, all_checks: dict):
    st.divider()
    st.markdown("### AI 코치 채팅")

    if not _GENAI_OK:
        st.error("google-genai SDK가 설치되지 않았습니다. `pip install google-genai --upgrade`를 실행하세요.")
        return
    if not os.environ.get("GEMINI_API_KEY", ""):
        st.warning("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    # 이전 대화 히스토리 표시
    for msg in st.session_state.coach_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 이전 호출 실패 시 에러 + 재전송 버튼
    if st.session_state.get("coach_error"):
        with st.chat_message("assistant"):
            st.error(st.session_state.coach_error)
        if st.button("재전송", key="chat_retry"):
            pending = st.session_state.get("coach_pending_msg", "")
            if pending:
                st.session_state.coach_error = None
                try:
                    sys_prompt = _build_coach_system_prompt(inputs, all_checks, ns, scenario)
                    resp_text = _call_coach_api(
                        sys_prompt, st.session_state.coach_chat[:-1], pending
                    )
                    st.session_state.coach_chat.append({"role": "assistant", "content": resp_text})
                    st.session_state.coach_pending_msg = None
                except Exception as e:
                    st.session_state.coach_error = f"재전송 중 오류가 발생했습니다: {e}"
            st.rerun()

    # 새 메시지 입력
    if user_input := st.chat_input("코치에게 질문하거나 고민을 털어놓으세요..."):
        st.session_state.coach_chat.append({"role": "user", "content": user_input})
        st.session_state.coach_pending_msg = user_input
        st.session_state.coach_error = None

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("코치가 답변 중입니다..."):
                try:
                    sys_prompt = _build_coach_system_prompt(inputs, all_checks, ns, scenario)
                    resp_text = _call_coach_api(
                        sys_prompt,
                        st.session_state.coach_chat[:-1],  # 현재 메시지 제외한 히스토리
                        user_input,
                    )
                    st.markdown(resp_text)
                    st.session_state.coach_chat.append({"role": "assistant", "content": resp_text})
                    st.session_state.coach_pending_msg = None
                except Exception as e:
                    err_msg = f"코치 응답 중 오류가 발생했습니다: {e}"
                    st.error(err_msg)
                    st.session_state.coach_error = err_msg

# ── render() ─────────────────────────────────────────────────────────────────

def render():
    cleanup_old_checklists(days=30)
    st.markdown(S3_CSS, unsafe_allow_html=True)
    if st.session_state.get("theme", "dark") == "light":
        st.markdown(S3_CSS_LIGHT_OVERRIDE, unsafe_allow_html=True)

    st.title("실행 계획")

    col_home, col_back, col_save = st.columns([1, 1, 1])
    with col_home:
        if st.button("🏠 홈으로", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with col_back:
        if st.button("← 결과로 돌아가기", use_container_width=True):
            st.session_state.page = "result"
            st.rerun()
    with col_save:
        if st.button("💾 저장하기", use_container_width=True, key="s3_save_btn"):
            _s3_scenario = st.session_state.get("selected_scenario") or {}
            _s3_type     = _s3_scenario.get("type", "")
            _s3_checks   = {
                k: v for k, v in st.session_state.items()
                if isinstance(v, bool) and (k.startswith("qplan_") or k.startswith("check_"))
            }
            if _s3_type and _s3_checks:
                save_checklist(_s3_type, _s3_checks, scenario=_s3_scenario)
                st.success("저장 완료")
            elif not _s3_type:
                st.warning("선택된 시나리오가 없어 저장할 수 없습니다.")

    scenario = st.session_state.get("selected_scenario")
    if not scenario:
        st.warning("선택된 시나리오가 없습니다. 결과 화면에서 '▶ 지금 바로 실행하기'를 눌러주세요.")
        return

    scenario_type = scenario.get("type", "")
    ns = scenario.get("next_steps", {})
    inputs = st.session_state.get("inputs", {})

    _init_checks(scenario_type, ns)

    st.subheader(f"시나리오: {scenario_type} — {scenario.get('title', '')}")
    st.caption(scenario.get("description", ""))
    st.divider()

    # ── 분기별 실행계획 생성/캐시 ────────────────────────────────────────────
    _cached_qtype = st.session_state.get("s3_qplan_type", "")
    _cached_qplan = st.session_state.get("s3_qplan")
    _qplan_failed = st.session_state.get("s3_qplan_failed", False)

    if _cached_qtype != scenario_type or not _cached_qplan:
        if not _qplan_failed and _GENAI_OK and os.environ.get("GEMINI_API_KEY", ""):
            with st.spinner("AI가 분기별 실행 계획을 작성 중입니다... (15~40초)"):
                try:
                    _new_qplan = _call_quarterly_plan_api(inputs, scenario)
                    if _new_qplan:
                        st.session_state["s3_qplan_type"] = scenario_type
                        st.session_state["s3_qplan"] = _new_qplan
                        st.session_state["s3_qplan_failed"] = False
                        save_quarterly_plan(scenario_type, _new_qplan)
                        st.rerun()
                except Exception as _qe:
                    st.session_state["s3_qplan_failed"] = True
                    st.session_state["s3_qplan_err"] = str(_qe)

    _qplan = (
        st.session_state.get("s3_qplan")
        if st.session_state.get("s3_qplan_type") == scenario_type
        else None
    )

    if st.session_state.get("s3_qplan_failed"):
        _c1, _c2 = st.columns([4, 1])
        with _c1:
            st.warning("분기별 실행 계획 생성에 실패했습니다. 기본 계획을 표시합니다.")
        with _c2:
            if st.button("🔄 재시도", key="s3_qplan_retry"):
                for _k in ("s3_qplan", "s3_qplan_type", "s3_qplan_failed", "s3_qplan_err"):
                    st.session_state.pop(_k, None)
                st.rerun()
    elif _qplan:
        st.caption("📅 AI가 선택한 시나리오를 기반으로 분기별(Q1~Q4) 구체 실행 계획을 작성했습니다.")

    # ── 분기 카드 or 기본 체크리스트(fallback)
    all_checks: dict = {}

    if _qplan:
        quarters = _qplan.get("quarters", [])
        for q_idx, qdata in enumerate(quarters):
            _render_quarter_card(qdata, q_idx, all_checks)
    else:
        # fallback: 화면2 next_steps 기반 기본 체크리스트
        for section_label, ns_key, key_prefix in CHECKLIST_SECTIONS:
            orig_items = ns.get(ns_key, [])
            if not orig_items:
                continue
            icon = _SEC_ICON.get(ns_key, "📋")
            st.markdown(
                f'<p class="s3-sec-hdr">{icon} {section_label}</p>',
                unsafe_allow_html=True,
            )
            checked_count = 0
            for idx, item in enumerate(orig_items):
                ck_key = f"check_{key_prefix}_{idx}"
                task_text = _item_text(item)
                checked = st.checkbox(task_text, key=ck_key)
                all_checks[ck_key] = checked
                if checked:
                    checked_count += 1
            total = len(orig_items)
            pct = int(checked_count / total * 100) if total else 0
            st.progress(pct / 100, text=f"완료율 {pct}% ({checked_count}/{total})")
            st.write("")

    # ── 전체 달성률 대시보드
    total_done  = sum(1 for v in all_checks.values() if v)
    total_items = len(all_checks)
    pct_all     = int(total_done / total_items * 100) if total_items else 0
    remaining   = total_items - total_done
    st.markdown(f"""<div class="s3-card">
<div class="s3-title">📊 전체 달성률</div>
<div class="s3-stats">
  <div class="s3-stat"><div class="s3-num s3-g">{total_done}</div><div class="s3-lbl">✅ 완료 항목</div></div>
  <div class="s3-stat"><div class="s3-num s3-y">{remaining}</div><div class="s3-lbl">📋 남은 항목</div></div>
  <div class="s3-stat"><div class="s3-num s3-p">{pct_all}%</div><div class="s3-lbl">달성률</div></div>
</div>
</div>""", unsafe_allow_html=True)

    # ── PDF 다운로드 버튼 (전체 리포트 + 체크리스트 포함)
    if st.session_state.get("result"):
        pdf_bytes_s3 = None
        try:
            import app as _app
            screen3_data = {
                "scenario": scenario,
                "checks": all_checks,
                "eval_result": st.session_state.get("eval_result"),
            }
            pdf_bytes_s3 = _app.generate_pdf(
                st.session_state.result,
                st.session_state.get("inputs", {}),
                screen3_data=screen3_data,
            )
        except Exception:
            pass
        if pdf_bytes_s3:
            st.download_button(
                label="📥 전체 리포트 PDF 저장",
                data=pdf_bytes_s3,
                file_name=f"scenario_plan_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # ── AI 코치 메시지 (원본 시나리오 coach_message)
    coach = ns.get("coach_message", "")
    if coach:
        st.divider()
        st.markdown("#### AI 코치 한 마디")
        st.info(coach)

    # ── 체크 상태 자동 저장 (rerun마다 갱신)
    if all_checks:
        save_checklist(scenario_type, all_checks, scenario=scenario)

    # ── AI 중간 평가
    _render_ai_evaluation(inputs, scenario, ns, all_checks)

    # ── AI 코치 채팅
    _render_chat(inputs, scenario, ns, all_checks)
