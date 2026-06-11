import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_gemini_api_key() -> str:
    """st.secrets → .env(환경변수) 순서로 GEMINI_API_KEY를 로드.
    양쪽 모두 없으면 st.error + st.stop()으로 앱을 중단한다."""
    # 1순위: Streamlit Cloud Secrets
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    # 2순위: 로컬 .env / 시스템 환경변수
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key

    # 키 없음 → 안내 후 중단
    st.error(
        "**GEMINI_API_KEY가 설정되지 않았습니다.**\n\n"
        "- **로컬 개발**: 프로젝트 루트 `.env` 파일에 `GEMINI_API_KEY=your_key` 를 추가하세요.\n"
        "- **Streamlit Cloud**: App settings → Secrets 에 "
        "`GEMINI_API_KEY = \"your_key\"` 를 추가하세요."
    )
    st.stop()
