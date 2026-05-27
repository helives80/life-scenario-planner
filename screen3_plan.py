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


def _get_client():
    return genai_v2.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

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
    # 시나리오 전환 시 채팅 초기화
    st.session_state.coach_chat = []
    st.session_state.coach_error = None
    st.session_state.coach_pending_msg = None

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
    response = _get_client().models.generate_content(
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
        item
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
        item
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

    response = _get_client().models.generate_content(
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
                k: st.session_state.get(k, False)
                for section_label, ns_key, key_prefix in CHECKLIST_SECTIONS
                for idx in range(50)
                for k in [f"check_{key_prefix}_{idx}"]
                if k in st.session_state
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

    # ── 체크리스트
    all_checks: dict = {}

    for section_label, ns_key, key_prefix in CHECKLIST_SECTIONS:
        items = ns.get(ns_key, [])
        if not items:
            continue
        icon = _SEC_ICON.get(ns_key, "📋")
        st.markdown(f'<p class="s3-sec-hdr">{icon} {section_label}</p>', unsafe_allow_html=True)
        checked_count = 0
        for idx, item in enumerate(items):
            ck_key = f"check_{key_prefix}_{idx}"
            checked = st.checkbox(item, key=ck_key)
            all_checks[ck_key] = checked
            if checked:
                checked_count += 1
        total = len(items)
        pct = int(checked_count / total * 100) if total else 0
        st.progress(pct / 100, text=f"완료율 {pct}% ({checked_count}/{total})")
        st.write("")

    # ── 전체 달성률 대시보드
    total_done = sum(1 for v in all_checks.values() if v)
    total_items = len(all_checks)
    pct_all = int(total_done / total_items * 100) if total_items else 0
    remaining = total_items - total_done
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

    # ── AI 코치 메시지
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
