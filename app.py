# -*- coding: utf-8 -*-
from collections import Counter
from datetime import datetime
import importlib
import io
import json
import os
import re
import time
import urllib.request
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

import translations as tr
# 모듈 캐시 즉시 갱신
importlib.reload(tr)

# -------------------------------------------------------------
# 0. 기본 환경 설정 & 경로 절대화 & 사내 보안 게이트 (v4.0)
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "voc_db.csv")

st.set_page_config(
    page_title="Global RCU VOC Intelligence v4.0",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

LANG_OPTIONS = {
    "🇰🇷 한국어 (Korean)": "ko",
    "🇺🇸 English": "en",
    "🇨🇳 简体中文 (Chinese)": "zh",
    "🇻🇳 Tiếng Việt (Vietnamese)": "vi",
    "🇹🇭 ภาษาไทย (Thai)": "th",
}

if "lang" not in st.session_state:
    st.session_state["lang"] = "ko"

selected_lang_label = st.sidebar.selectbox(
    "🌐 Language / 언어 선택",
    options=list(LANG_OPTIONS.keys()),
    index=list(LANG_OPTIONS.values()).index(st.session_state["lang"]),
    key="global_lang_selector_widget",
)
curr_lang = LANG_OPTIONS[selected_lang_label]
st.session_state["lang"] = curr_lang


def txt(key, **kwargs):
    s = tr.UI_TEXT.get(curr_lang, {}).get(key, tr.UI_TEXT["ko"].get(key, key))
    if kwargs:
        return s.format(**kwargs)
    return s


def get_cat_name(k):
    return tr.CATEGORIES.get(k, {}).get(curr_lang, k)


def get_dev_name(k):
    return tr.DEVICE_TYPES.get(k, {}).get(curr_lang, k)


def get_power_name(k):
    return tr.POWER_TYPES.get(k, {}).get(curr_lang, k)


def get_ui_name(k):
    return tr.UI_TYPES.get(k, {}).get(curr_lang, k)


def get_region_name(k):
    return tr.REGIONS.get(k, {}).get(curr_lang, k)


def get_col_name(k):
    return tr.TABLE_COLUMNS.get(k, {}).get(curr_lang, k)


def get_sentiment_name(k):
    return tr.SENTIMENTS.get(k, {}).get(curr_lang, k)


def get_action_sol(k):
    return tr.ACTION_RECOMMENDATIONS.get(k, {}).get(
        curr_lang, tr.ACTION_RECOMMENDATIONS.get(k, {}).get("ko", "")
    )


def get_secret_api_key():
    try:
        return st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def get_rcu_password():
    try:
        return st.secrets.get("RCU_PASSWORD", "rcu2026!")
    except Exception:
        return os.environ.get("RCU_PASSWORD", "rcu2026!")


RCU_PASSWORD = get_rcu_password()


def check_password():
    if st.session_state.get("password_correct", False):
        return True

    def password_entered():
        if st.session_state.get("password_input") == RCU_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title(txt("gate_title"))
        st.markdown(f"##### {txt('gate_sub')}")
        st.info(txt("gate_info"))

        st.text_input(
            txt("gate_input"),
            type="password",
            on_change=password_entered,
            key="password_input",
            placeholder=txt("gate_placeholder"),
        )

        if "password_correct" in st.session_state and not st.session_state.get(
            "password_correct"
        ):
            st.error(txt("gate_error"))

    return False


if not check_password():
    st.stop()

if st.sidebar.button(txt("logout"), help=txt("logout_help"), key="btn_logout_top"):
    st.session_state["password_correct"] = False
    st.rerun()

# -------------------------------------------------------------
# 1. 60개 브랜드 디렉터리 & 폼팩터 매핑
# -------------------------------------------------------------
BRAND_DIRECTORY = {
    # TV 제조사
    "Samsung": {"region": "Korea", "type": "TV 제조사", "power": "솔라셀/C타입 충전식", "ui": "미니멀 물리키"},
    "LG Electronics": {"region": "Korea", "type": "TV 제조사", "power": "건전지 교체형", "ui": "자이로/에어마우스"},
    "Sony": {"region": "Japan", "type": "TV 제조사", "power": "건전지 교체형", "ui": "백라이트 물리키"},
    "Panasonic": {"region": "Japan", "type": "TV 제조사", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "Sharp": {"region": "Japan", "type": "TV 제조사", "power": "건전지 교체형", "ui": "다버튼 핫키형"},
    "TCL": {"region": "Global", "type": "TV 제조사", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Hisense": {"region": "Global", "type": "TV 제조사", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Xiaomi": {"region": "ASIA", "type": "TV 제조사", "power": "건전지 교체형", "ui": "초미니멀 물리키"},
    "Vizio": {"region": "NA", "type": "TV 제조사", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Philips": {"region": "EU", "type": "TV 제조사", "power": "건전지 교체형", "ui": "양면/특수 물리키"},
    # 스트리밍 / 스마트 미디어
    "Apple": {"region": "Global", "type": "스트리밍/스마트 미디어", "power": "C타입 충전식", "ui": "터치 클릭패드"},
    "Amazon Fire TV": {"region": "Global", "type": "스트리밍/스마트 미디어", "power": "건전지 교체형", "ui": "백라이트 물리키"},
    "Google": {"region": "Global", "type": "스트리밍/스마트 미디어", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Roku": {"region": "NA", "type": "스트리밍/스마트 미디어", "power": "C타입 충전식", "ui": "이어폰잭/물리키"},
    "NVIDIA": {"region": "Global", "type": "스트리밍/스마트 미디어", "power": "건전지 교체형", "ui": "삼각기둥 백라이트"},
    "TiVo": {"region": "NA", "type": "스트리밍/스마트 미디어", "power": "건전지 교체형", "ui": "인체공학 피넛키"},
    "SofaBaton": {"region": "Global", "type": "스트리밍/스마트 미디어", "power": "C타입 충전식", "ui": "OLED스크린/휠"},
    # 방송통신사 (Telco/MSO)
    "Comcast": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "음성 특화 물리키"},
    "Charter": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "DirecTV": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "안드로이드 물리키"},
    "DISH Network": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "백라이트 물리키"},
    "Cox": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "음성 특화 물리키"},
    "Rogers": {"region": "NA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "음성 특화 물리키"},
    "Sky Group": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "터치/모션 백라이트"},
    "Vodafone": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "LGI (Virgin Media)": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "음성 특화 물리키"},
    "Canal+": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Orange": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Deutsche Telekom": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Telefonica": {"region": "EU", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "KT (지니TV)": {"region": "Korea", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "SKB (B tv)": {"region": "Korea", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "이어폰일체형 물리키"},
    "LGU+ (U+tv)": {"region": "Korea", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "이어폰일체형 물리키"},
    "MultiChoice (DStv)": {"region": "Africa", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "StarTimes": {"region": "Africa", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Canal+ Afrique": {"region": "Africa", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Tata Play": {"region": "ASIA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 핫키형"},
    "Airtel": {"region": "ASIA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "J:COM": {"region": "ASIA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "Hikari TV": {"region": "ASIA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 하이브리드"},
    "Foxtel": {"region": "ASIA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Claro": {"region": "SCA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    "Vrio Corp": {"region": "SCA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "다버튼 물리키"},
    "Televisa (izzi)": {"region": "SCA", "type": "방송통신사 (Telco/MSO)", "power": "건전지 교체형", "ui": "미니멀 물리키"},
    # 스마트홈 오토메이션
    "Control4": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "터치스크린/물리키"},
    "Crestron": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "터치스크린/물리키"},
    "Savant": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "고해상도 터치스크린"},
    "Josh.ai": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "AI음성/물리키"},
    "URC": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "터치스크린/물리키"},
    "RTI": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "대화면 터치스크린"},
    "Nice (ELAN)": {"region": "NA", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "터치스크린/인터콤"},
    "Basalte": {"region": "EU", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "명품 금속 터치"},
    "Logitech": {"region": "Global", "type": "스마트홈 오토메이션", "power": "크래들 무선충전식", "ui": "터치스크린/물리키"},
    "ADT": {"region": "NA", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "보안 키패드"},
    "Vivint": {"region": "NA", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "스마트 패널"},
    "Resideo": {"region": "NA", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "보안 키패드"},
    "Loxone": {"region": "EU", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "5터치 포인트"},
    "Somfy": {"region": "EU", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "모터 제어 휠"},
    "Cync (GE)": {"region": "NA", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "조명 디밍 버튼"},
    "Tuya": {"region": "Global", "type": "스마트홈 오토메이션", "power": "건전지 교체형", "ui": "스마트 허브 연동"},
}

BRAND_ALIASES = {
    "amazon": "Amazon Fire TV", "fire tv": "Amazon Fire TV", "google tv": "Google",
    "comcast (xfinity)": "Comcast", "xfinity": "Comcast", "spectrum": "Charter",
    "sky": "Sky Group", "virgin media": "LGI (Virgin Media)", "canal": "Canal+",
    "dt": "Deutsche Telekom", "telekom": "Deutsche Telekom", "vodafone tv": "Vodafone",
    "dstv": "MultiChoice (DStv)", "startimes": "StarTimes", "b tv": "SKB (B tv)",
    "skb": "SKB (B tv)", "지니tv": "KT (지니TV)", "kt": "KT (지니TV)", "u+tv": "LGU+ (U+tv)",
    "lgu+": "LGU+ (U+tv)", "lg": "LG Electronics", "samsung": "Samsung",
}


def normalize_brand(name):
    raw = str(name).strip()
    if raw in BRAND_DIRECTORY:
        return raw
    lower = raw.lower()
    if lower in BRAND_ALIASES:
        return BRAND_ALIASES[lower]
    for alias, canon in BRAND_ALIASES.items():
        if alias in lower:
            return canon
    for canon in BRAND_DIRECTORY:
        if canon.lower() in lower:
            return canon
    return raw

# -------------------------------------------------------------
# 2. 지역별 Champions 매트릭스 & 정밀 분류 엔진 (13대 카테고리)
# -------------------------------------------------------------
REGIONAL_TOP3 = {
    "한국 (KR)": {
        "TV 제조사": ["Samsung", "LG Electronics"],
        "방송통신사 (Telco/MSO)": ["KT (지니TV)", "SKB (B tv)", "LGU+ (U+tv)"],
    },
    "북미 (NA)": {
        "TV 제조사": ["Samsung", "Vizio", "TCL"],
        "스트리밍/스마트 미디어": ["Roku", "Amazon Fire TV", "Apple"],
        "방송통신사 (Telco/MSO)": ["Comcast", "Charter", "DirecTV"],
        "스마트홈 오토메이션": ["Control4", "Crestron", "Savant"],
    },
    "유럽 (EU)": {
        "TV 제조사": ["Samsung", "Philips", "LG Electronics"],
        "스트리밍/스마트 미디어": ["Amazon Fire TV", "Apple", "Google"],
        "방송통신사 (Telco/MSO)": ["Sky Group", "Vodafone", "Orange"],
        "스마트홈 오토메이션": ["Somfy", "Loxone", "Basalte"],
    },
    "아시아-태평양 (APAC)": {
        "TV 제조사": ["Sony", "Panasonic", "Sharp"],
        "스트리밍/스마트 미디어": ["Google", "Xiaomi", "Apple"],
        "방송통신사 (Telco/MSO)": ["Tata Play", "Airtel", "J:COM"],
        "스마트홈 오토메이션": ["Tuya", "SofaBaton", "Logitech"],
    },
    "아프리카 (Africa)": {
        "TV 제조사": ["Samsung", "Hisense", "LG Electronics"],
        "방송통신사 (Telco/MSO)": ["MultiChoice (DStv)", "StarTimes", "Canal+ Afrique"],
    },
}

KR_CHAMPIONS = sum(REGIONAL_TOP3["한국 (KR)"].values(), [])
NA_CHAMPIONS = sum(REGIONAL_TOP3["북미 (NA)"].values(), [])
EU_CHAMPIONS = sum(REGIONAL_TOP3["유럽 (EU)"].values(), [])
APAC_CHAMPIONS = sum(REGIONAL_TOP3["아시아-태평양 (APAC)"].values(), [])
AFRICA_CHAMPIONS = sum(REGIONAL_TOP3["아프리카 (Africa)"].values(), [])


def refine_category(text):
    t = str(text).lower()

    if any(w in t for w in ["gyro", "pointer", "cursor", "air mouse", "magic remote", "drift", "calibration", "touchpad", "포인터", "커서", "마우스", "자이로", "영점", "터치패드", "민감", "쏠림"]):
        return "모션/터치 센서 감도"

    if any(w in t for w in ["grip", "slippery", "ergonomic", "couch", "cushion", "slip", "too small", "too thin", "holding", "comfort", "그립", "미끄러", "미끄럼", "작아서", "얇아서", "소파", "손목", "불편", "잡기", "빠짐"]):
        return "그립감/인체공학 설계"

    if any(w in t for w in ["code", "program", "manual", "setup", "universal", "compatible", "compatibility", "stb", "등록", "호환", "호환성", "설명서", "코드", "설정", "세팅", "인식 안 됨"]):
        return "초기 등록/호환성 설정"

    if any(w in t for w in ["pair", "connect", "bluetooth", "wifi", "offline", "drop", "disconnect", "sync", "unpair", "network", "link", "lost", "load shedding", "synchro", "verbindung", "페어링", "연결", "블루투스"]):
        return "페어링/연결 끊김"

    if any(w in t for w in ["lag", "slow", "freeze", "stuck", "delay", "unresponsive", "hang", "epg", "latency", "buffering", "지연", "렉", "먹통", "느려", "멈춤", "반응"]):
        return "속도/지연/먹통"

    if any(w in t for w in ["volume", "mute", "cec", "hdmi", "turn on", "turn off", "soundbar", "receiver", "tv", "power", "handshake", "lautstärke", "볼륨", "소리", "전원", "외부입력"]):
        return "볼륨/TV연동(CEC)"

    if any(w in t for w in ["range", "line of sight", "distance", "angle", "ir ", "signal", "sensor", "aim", "reichweite", "수신", "거리", "각도", "정면", "적외선"]):
        return "신호범위/IR센서"

    if any(w in t for w in ["button", "layout", "press", "key", "click", "backlight", "chattering", "stiff", "눌러", "버튼", "키", "클릭", "더블클릭", "채터링", "백라이트", "씹힘", "함몰"]):
        return "버튼/UI 제어 불량"

    if any(w in t for w in ["battery", "charge", "drain", "solar", "recharge", "corrosion", "leak", "batterie", "akku", "pile", "배터리", "건전지", "충전", "방전", "광탈", "누액", "부식"]):
        return "배터리/전원"

    if any(w in t for w in ["voice", "mic", "alexa", "bixby", "siri", "assistant", "voix", "stimme", "음성", "마이크", "인식", "기가지니", "클로바"]):
        return "음성 인식/마이크"

    if any(w in t for w in ["cheap", "plastic", "break", "broke", "drop", "fall", "durability", "scratch", "깨짐", "파손", "마감", "부러", "내구성", "스크래치"]):
        return "내구성/하드웨어 퀄리티"

    if any(w in t for w in ["login", "sign in", "account", "update", "ad ", "ota", "brick", "업데이트", "계정", "광고"]):
        return "계정/업데이트/광고"

    if any(w in t for w in ["app", "hotkey", "shortcut", "finder", "raccourci", "핫키", "바로가기", "찾기", "비프음"]):
        return "단순 앱/기능 불만"

    return "기타/일반"


NOISE_FILTER_REGEX = re.compile(
    r"(?:공식\s*(?:기업\s*)?사이트|공식\s*홈페이지|공식\s*(?:직영\s*)?온라인샵|다이렉트샵|"
    r"\[kt\]\s*메인|\[마이페이지\]|고객센터|음성상담|채팅상담|보이스봇|"
    r"이용하시는\s*고객|혜택과\s*서비스|이벤트도\s*참여|되겠습니다|가능합니다|"
    r"주식회사|사업자등록|대표이사|개인정보처리|요금제\s*확인|상품서비스|"
    r"delivery|shipping|hassle-free|returns?|cash on delivery|"
    r"shop for|buy online|in stock|order now|price in|naira|rand|"
    r"nationwide delivery|collection|many ways to pay|money back|"
    r"is designed for|designed to provide|high-quality replacement|"
    r"seamless compatibility|official website|features an? |leading provider|"
    r"overview|specifications?:|package includes?:|replacement remote|aerial king)",
    re.IGNORECASE,
)


@st.cache_data(ttl=300)
def load_accumulated_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    try:
        df = pd.read_csv(DB_PATH, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(DB_PATH, encoding="utf-8")

    if not df.empty:
        df = df[~df["Review"].astype(str).str.contains(NOISE_FILTER_REGEX)].copy()
        df = df[df["Review"].astype(str).str.len() >= 25].copy()

        df["Brand"] = df["Brand"].apply(normalize_brand)
        df["Device_Type"] = df["Brand"].map(
            lambda b: BRAND_DIRECTORY.get(b, {}).get("type", "TV 제조사")
        )
        df["Region"] = df["Brand"].map(
            lambda b: BRAND_DIRECTORY.get(b, {}).get("region", "Global")
        )
        df["Power_Type"] = df["Brand"].map(
            lambda b: BRAND_DIRECTORY.get(b, {}).get("power", "건전지 교체형")
        )
        df["UI_Type"] = df["Brand"].map(
            lambda b: BRAND_DIRECTORY.get(b, {}).get("ui", "미니멀 물리키")
        )

        df["Category"] = df["Review"].apply(refine_category).fillna("기타/일반")
        df["Sentiment"] = df["Sentiment"].fillna("Negative")
        if "Source" not in df.columns:
            df["Source"] = "Web / Community"

        if "Collected_Date" in df.columns:
            cleaned_dates = (
                df["Collected_Date"]
                .astype(str)
                .str.strip()
                .str.extract(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})")[0]
                .str.replace(r"[./]", "-", regex=True)
            )
            df["Parsed_Date"] = pd.to_datetime(cleaned_dates, errors="coerce")
            df["Parsed_Date"] = df["Parsed_Date"].fillna(pd.Timestamp.now())
        else:
            df["Parsed_Date"] = pd.Timestamp.now()

    return df


df_all = load_accumulated_data()
if df_all.empty:
    st.warning(f"⚠️ '{DB_PATH}' is empty or missing.")
    st.stop()


# -------------------------------------------------------------
# Gemini AI 연동 엔진
# -------------------------------------------------------------
def analyze_voc_with_gemini(api_key, client_name, p_issue, s_issue, sample_reviews, lang="ko"):
    api_key = str(api_key).strip().strip('"').strip("'")
    if not api_key:
        return "⚠️ Gemini API Key가 입력되지 않았습니다."

    lang_names = {
        "ko": "Korean (한국어)",
        "en": "English",
        "zh": "Simplified Chinese (简体中文)",
        "vi": "Vietnamese (Tiếng Việt)",
        "th": "Thai (ภาษาไทย)"
    }
    target_lang_name = lang_names.get(lang, "Korean")
    reviews_formatted = "\n".join([f"- {r}" for r in sample_reviews])

    sum_title = tr.UI_TEXT.get(lang, {}).get("ai_summary_title", "고객 VoC 핵심 3줄 요약")
    rc_title = tr.UI_TEXT.get(lang, {}).get("ai_root_cause_title", "H/W & F/W 결함 근본 원인 (Root Cause) 분석")
    st_title = tr.UI_TEXT.get(lang, {}).get("ai_strategy_title", "B2B 수주전 기술 차별화 제언")

    prompt = f"""You are a distinguished Principal Remote Control Unit (RCU) Hardware/Firmware Architect and Telco B2B Solution Leader.
Analyze the following Voice of Customer (VoC) feedback for target client '{client_name}'.

- 1st Priority Defect: {p_issue}
- 2nd Priority Defect: {s_issue if s_issue else "None"}
- Field Customer Verbatim Reviews:
{reviews_formatted}

Generate an executive technical diagnosis strictly in {target_lang_name}.
Format the output into exactly three sections using Markdown:

### 📋 {sum_title}
(Provide 3 concise, impactful bullet points summarizing the actual user pain points. Keep each bullet under 60 characters.)

### 🔬 {rc_title}
(Provide 2-3 deep engineering root-cause diagnoses explaining the hardware/firmware bottlenecks, such as MCU wake-up jitter, BLE advertising/connection intervals, CEC handshake bus collisions, power management IC leakage, or metal dome debounce circuit timing. Keep each point under 110 characters.)

### 🎯 {st_title}
(Provide 2 concrete technical differentiation proposals to decisively win the B2B supply contract over competitors. Keep each point under 110 characters.)

Be concise, highly professional, and engineering-grade. Do not include introductory fluff."""

    non_text_keywords = ["tts", "audio", "embed", "image", "imagen", "robotics", "realtime", "live"]
    active_models = []
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(list_url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("models", []):
                m_name = m.get("name", "")
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    if not any(bad in m_name.lower() for bad in non_text_keywords):
                        active_models.append(m_name)
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            err_msg = err_data.get("error", {}).get("message", str(e))
        except Exception:
            err_msg = str(e)
        if e.code in (401, 403):
            return f"⚠️ Gemini API 인증/키 오류 ({err_msg})"
    except Exception:
        pass

    preferred_order = [
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-flash-latest",
        "models/gemini-1.5-pro",
        "models/gemini-pro"
    ]
    
    candidate_models = []
    for pref in preferred_order:
        if pref in active_models:
            candidate_models.append(pref)
    for m in active_models:
        if m not in candidate_models:
            candidate_models.append(m)

    if not candidate_models:
        candidate_models = preferred_order

    last_err = ""
    for model_full_name in candidate_models:
        clean_name = model_full_name if model_full_name.startswith("models/") else f"models/{model_full_name}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{clean_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500}
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            last_err = f"HTTP {e.code}: {msg}"
            if e.code in (401, 403):
                return f"⚠️ Gemini API 인증 오류 ({last_err})"
            continue
        except Exception as e:
            last_err = str(e)
            continue

    return f"⚠️ Gemini API 분석 실패: {last_err}"


# -------------------------------------------------------------
# PPTX 다국어 생성 엔진 (16:9 와이드 & 5개국어 100% 현지화)
# -------------------------------------------------------------
COLOR_NAVY_DARK     = RGBColor(15, 23, 42)    # #0F172A
COLOR_NAVY_SURFACE  = RGBColor(30, 41, 59)    # #1E293B
COLOR_BG_PAGE       = RGBColor(248, 250, 252) # #F8FAFC
COLOR_CARD_BG       = RGBColor(255, 255, 255) # #FFFFFF
COLOR_BORDER        = RGBColor(226, 232, 240) # #E2E8F0
COLOR_PRIMARY       = RGBColor(37, 99, 235)   # #2563EB Tech Blue
COLOR_PRIMARY_LIGHT = RGBColor(239, 246, 255) # #EFF6FF
COLOR_ACCENT_RED    = RGBColor(225, 29, 72)   # #E11D48
COLOR_ACCENT_ORANGE = RGBColor(234, 88, 12)   # #EA580C
COLOR_ACCENT_GREEN  = RGBColor(5, 150, 105)   # #059669
COLOR_TEXT_MAIN     = RGBColor(15, 23, 42)    # #0F172A
COLOR_TEXT_MUTED    = RGBColor(100, 116, 139) # #64748B
COLOR_TEXT_WHITE    = RGBColor(255, 255, 255)

FONT_FAMILY = "Malgun Gothic"


def set_slide_bg(slide, rgb_color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = rgb_color


def add_slide_header(slide, title_text, category_tag="RCU VOC INTELLIGENCE & B2B PROPOSAL", is_dark=False):
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.42), Inches(11.733), Inches(0.95))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_tag = tf.paragraphs[0]
    p_tag.text = category_tag.upper()
    p_tag.font.name = FONT_FAMILY
    p_tag.font.size = Pt(9.5)
    p_tag.font.bold = True
    p_tag.font.color.rgb = RGBColor(96, 165, 250) if is_dark else COLOR_PRIMARY
    p_tag.space_after = Pt(2)

    p_title = tf.add_paragraph()
    p_title.text = title_text
    p_title.font.name = FONT_FAMILY
    p_title.font.size = Pt(20)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_TEXT_WHITE if is_dark else COLOR_TEXT_MAIN


def add_card_container(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_BORDER, corner_radius_in=0.18):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()

    try:
        w_in = width.inches if hasattr(width, 'inches') else float(width) / 914400.0
        h_in = height.inches if hasattr(height, 'inches') else float(height) / 914400.0
        short_side = min(w_in, h_in)
        if short_side > 0:
            adj = corner_radius_in / short_side
            adj = min(max(adj, 0.02), 0.15)
            shape.adjustments[0] = adj
    except Exception:
        shape.adjustments[0] = 0.05
    return shape


def add_card_text_frame(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_BORDER, pad_h=0.25, pad_v=0.20, corner_radius_in=0.18):
    add_card_container(slide, left, top, width, height, bg_color, border_color, corner_radius_in=corner_radius_in)
    tb = slide.shapes.add_textbox(
        left + Inches(pad_h),
        top + Inches(pad_v),
        width - Inches(pad_h * 2),
        height - Inches(pad_v * 2)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    return tf


def parse_gemini_sections(text):
    sec_1, sec_2, sec_3 = [], [], []
    curr = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if "📋" in line or "요약" in line or "summary" in lower or "痛点" in line:
            curr = 1
            continue
        elif "🔬" in line or "root cause" in lower or "원인" in line or "根因" in line or "nguyên nhân" in lower or "สาเหตุ" in line:
            curr = 2
            continue
        elif "🎯" in line or "차별화" in line or "제언" in line or "strategy" in lower or "策略" in line or "đề xuất" in lower or "ข้อเสนอ" in line:
            curr = 3
            continue

        clean = line.lstrip("-*•# ").strip()
        if not clean:
            continue
        if curr == 1:
            sec_1.append(clean)
        elif curr == 2:
            sec_2.append(clean)
        elif curr == 3:
            sec_3.append(clean)
        else:
            sec_1.append(clean)

    if not sec_2 and not sec_3 and sec_1:
        n = len(sec_1)
        k1 = max(1, n // 3)
        k2 = max(2, (2 * n) // 3)
        sec_2 = sec_1[k1:k2]
        sec_3 = sec_1[k2:]
        sec_1 = sec_1[:k1]

    return sec_1, sec_2, sec_3


def create_pptx_deck(
    client_name, p_issue, s_issue, p_sol, s_sol, pitch, reviews, cat_counts=None, ai_analysis=None, roi_data=None, lang="ko"
):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    t_titles = {
        "ko": {
            "cover_tag": "GLOBAL RCU VOC INTELLIGENCE v4.0 | B2B STRATEGIC PROPOSAL",
            "deck_title": f"고객 VOC 분석 Insight에 기반한 {client_name} RCU 상품 제안서",
            "confidential": "사외비 (CONFIDENTIAL) - B2B 수주 심의용",
            "date": "작성일자", "target": "대상 고객사",
            "s1_tag": "VOICE OF CUSTOMER INTELLIGENCE",
            "s1_title": f"1. {client_name} 고객 핵심 불만 및 취약점 분석 (VoC Pain Points)",
            "rank1_badge": "🚨 1순위 핵심 결함", "rank2_badge": "⚠️ 2순위 핵심 결함",
            "reviews_header": "💬 현장 고객 대표 불만 원문 (Voice of Customer)",
            "chart_title": "정밀 기술 결함별 점유율 (Actionable Defect Distribution)",
            "chart_series": "불만 점유율", "others": "기타",
            "s2_tag": "R&D TECHNICAL ROADMAP",
            "s2_title": "2. 결함 원인별 차세대 H/W & F/W 기술 해결 솔루션",
            "sol_heading": "당사 차세대 H/W & F/W 엔지니어링 솔루션",
            "s2_fallback_title": "🛡️ 전수 품질 보증 및 신뢰성 검증 체계",
            "s2_fallback_body": "당사 표준 5단계 전수 검사 및 신뢰성 테스트 프로토콜이 기본 적용됩니다.",
            "s3_tag": "EXECUTIVE VALUE PROPOSITION",
            "s3_title": "3. 최고경영진(C-Level) 제안 및 기대효과 (Executive Pitch)",
            "exec_pitch_title": f"EXECUTIVE STRATEGIC PITCH FOR {client_name.upper()}",
            "p1_title": "📉 반품률 및 물류비 절감",
            "p1_sub": "• 연간 RCU 불량 반품률 65%+ 억제\n• 실물 교체 및 왕복 물류 OPEX 대폭 절감\n• H/W 내구성 강화로 제품 수명 주기 연장",
            "p2_title": "📞 CS 콜센터 인입률 차단",
            "p2_sub": "• 페어링/방전 관련 고객 문의 원천 차단\n• 고객센터 1건당 상담 처리 원가 절감\n• 초기 설치 단계 고객 자가 해결률 향상",
            "p3_title": "⭐ 가입자 NPS & 신뢰도 제고",
            "p3_sub": "• 응답 지연·먹통 없는 쾌적한 미디어 경험\n• 고객 이탈 방지 및 유료 서비스 만족도 증대\n• 차세대 프리미엄 RCU 브랜드 이미지 구축",
            "s4_tag": "FINANCIAL IMPACT & ROI SIMULATION",
            "s4_title": f"4. {client_name} 가입자 기반 연간 ROI & OPEX 비용 절감 추정치",
            "roi_card1_title": "💰 연간 총 OPEX 예상 절감액",
            "roi_card2_title": "📞 연간 CS 문의 인입 예방",
            "roi_card3_title": "📦 연간 불량 교체/반품 억제",
            "unit_cases": "건", "unit_units": "대",
            "roi_base_title": "📊 고객사 시뮬레이션 산출 기준 (Baseline)",
            "roi_p1": "적용 활성 가입자/단말 수량",
            "roi_p2": "고객사 연간 RCU CS 상담 인입률",
            "roi_p3": "고객센터 1건당 상담 처리 원가",
            "roi_p4": "연간 실물 교체/불량 반품률",
            "roi_p5": "단말 조달 원가 및 왕복 물류비",
            "roi_p6": "당사 차세대 H/W & F/W 결함 개선 목표",
            "roi_sav_title": "🎯 연간 세부 비용 절감 분석 (Annual Savings)",
            "roi_s1": "CS 상담 콜센터 비용 절감",
            "roi_s2": "실물 반품/교체 물류비 절감",
            "s5_tag": "AI DEEP ROOT CAUSE DIAGNOSIS",
            "s5_title": "5. Gemini AI 심층 결함 원인 (Root Cause) & 차별화 제언",
            "col1_title": "📋 고객 VoC 핵심 요약",
            "col2_title": "🔬 H/W & F/W Root Cause 진단",
            "col3_title": "🎯 B2B 수주전 기술 차별화 제언",
        },
        "en": {
            "cover_tag": "GLOBAL RCU VOC INTELLIGENCE v4.0 | B2B STRATEGIC PROPOSAL",
            "deck_title": f"RCU Product Proposal for {client_name} Based on Customer VoC Insights",
            "confidential": "CONFIDENTIAL & PROPRIETARY - Strictly for B2B Evaluation",
            "date": "Date", "target": "Target Client",
            "s1_tag": "VOICE OF CUSTOMER INTELLIGENCE",
            "s1_title": f"1. {client_name} Core Customer Pain Points & Defect Analysis",
            "rank1_badge": "🚨 Rank 1 Primary Defect", "rank2_badge": "⚠️ Rank 2 Secondary Defect",
            "reviews_header": "💬 Representative Field Customer Verbatim Reviews",
            "chart_title": "Actionable Defect Share Distribution",
            "chart_series": "Complaint Share", "others": "Others",
            "s2_tag": "R&D TECHNICAL ROADMAP",
            "s2_title": "2. Next-Gen H/W & F/W Engineering Countermeasures by Defect",
            "sol_heading": "Proprietary Next-Gen H/W & F/W Engineering Countermeasures",
            "s2_fallback_title": "🛡️ Total Quality & Reliability Assurance",
            "s2_fallback_body": "Standard 5-stage 100% inspection and reliability test protocols are applied by default.",
            "s3_tag": "EXECUTIVE VALUE PROPOSITION",
            "s3_title": "3. Executive Proposal & Strategic Value Drivers (Executive Pitch)",
            "exec_pitch_title": f"EXECUTIVE STRATEGIC PITCH FOR {client_name.upper()}",
            "p1_title": "📉 Lower Returns & Logistics OPEX",
            "p1_sub": "• 65%+ reduction in defect return rates\n• Substantial savings in replacement logistics\n• Extended lifecycle via robust industrial design",
            "p2_title": "📞 Drastic CS Call Reduction",
            "p2_sub": "• Eliminate pairing and battery drain inquiries\n• Decrease per-ticket customer support overhead\n• Maximize first-time setup self-service success",
            "p3_title": "⭐ Superior NPS & Retention",
            "p3_sub": "• Latency-free, premium navigation experience\n• Prevent subscriber churn and bolster loyalty\n• Position the brand as a top-tier media provider",
            "s4_tag": "FINANCIAL IMPACT & ROI SIMULATION",
            "s4_title": f"4. Estimated Annual OPEX Savings & Financial ROI for {client_name}",
            "roi_card1_title": "💰 Total Annual OPEX Saved",
            "roi_card2_title": "📞 Annual CS Calls Prevented",
            "roi_card3_title": "📦 Annual Hardware Swaps Avoided",
            "unit_cases": "Tickets", "unit_units": "Units",
            "roi_base_title": "📊 Simulation Baseline Parameters",
            "roi_p1": "Active Subscribers / Devices",
            "roi_p2": "Annual RCU CS Ticket Rate",
            "roi_p3": "Average Cost per CS Ticket",
            "roi_p4": "Annual Hardware Return/RMA Rate",
            "roi_p5": "Device Unit Cost + Roundtrip Logistics",
            "roi_p6": "Next-Gen H/W & F/W Defect Reduction Target",
            "roi_sav_title": "🎯 Annual Cost Savings Breakdown",
            "roi_s1": "CS Call Center Overhead Savings",
            "roi_s2": "Hardware RMA & Logistics Savings",
            "s5_tag": "AI DEEP ROOT CAUSE DIAGNOSIS",
            "s5_title": "5. Gemini AI Deep Defect Root Cause & Strategic Recommendations",
            "col1_title": "📋 Core VoC Pain Points",
            "col2_title": "🔬 H/W & F/W Root Cause Diagnosis",
            "col3_title": "🎯 B2B Differentiation Strategy",
        },
        "zh": {
            "cover_tag": "GLOBAL RCU VOC INTELLIGENCE v4.0 | B2B STRATEGIC PROPOSAL",
            "deck_title": f"基于客户 VoC 洞察的 {client_name} 遥控器产品方案建议书",
            "confidential": "机密 (CONFIDENTIAL) - 仅限商务竞标评估",
            "date": "编制日期", "target": "目标品牌",
            "s1_tag": "VOICE OF CUSTOMER INTELLIGENCE",
            "s1_title": f"1. {client_name} 客户核心痛点与缺陷深度分析 (VoC)",
            "rank1_badge": "🚨 第一核心缺陷", "rank2_badge": "⚠️ 第二核心缺陷",
            "reviews_header": "💬 现场典型用户痛点原声 (Verbatim VoC)",
            "chart_title": "可行动技术缺陷占比分布 (Actionable Defect Distribution)",
            "chart_series": "负面占比", "others": "其他",
            "s2_tag": "R&D TECHNICAL ROADMAP",
            "s2_title": "2. 针对缺陷根因的下一代软硬件核心技术方案",
            "sol_heading": "我方下一代软硬件一体化工程解决方案",
            "s2_fallback_title": "🛡️ 全流程品质保证与可靠性测试体系",
            "s2_fallback_body": "默认应用我方标准 5 阶段全检及高标准可靠性环境测试协议。",
            "s3_tag": "EXECUTIVE VALUE PROPOSITION",
            "s3_title": "3. 面向高管层的商务竞标价值主张与收益 (Executive Pitch)",
            "exec_pitch_title": f"EXECUTIVE STRATEGIC PITCH FOR {client_name.upper()}",
            "p1_title": "📉 大幅降低退货与物流成本",
            "p1_sub": "• 减少65%以上的遥控器故障退换货率\n• 显著节省售后换货往返物流运营支出\n• 增强硬件耐久度，延长整体产品生命周期",
            "p2_title": "📞 遏制呼叫中心客服接入率",
            "p2_sub": "• 从源头消除配对断连与电池耗电咨询\n• 降低每通客服工单处理综合成本\n• 提升用户初次开机配对自助成功率",
            "p3_title": "⭐ 提升净推荐值(NPS)与品牌美誉",
            "p3_sub": "• 无延迟、不卡顿的极致交互操控体验\n• 有效防范付费用户流失，增强品牌黏性\n• 确立行业领先的高端遥控器标杆品质",
            "s4_tag": "FINANCIAL IMPACT & ROI SIMULATION",
            "s4_title": f"4. {client_name} 基于在网用户的年度运营成本(OPEX)削减效益测算",
            "roi_card1_title": "💰 预计年度 OPEX 节省总额",
            "roi_card2_title": "📞 预计减少年度客服工单",
            "roi_card3_title": "📦 预计减少故障退换物流",
            "unit_cases": "单", "unit_units": "台",
            "roi_base_title": "📊 客户模拟测算基准参数 (Baseline)",
            "roi_p1": "适用在网用户/终端数量",
            "roi_p2": "年度遥控器相关客服工单率",
            "roi_p3": "每通客服工单综合处理成本",
            "roi_p4": "年度故障换货/退换率",
            "roi_p5": "终端硬件成本与往返物流费",
            "roi_p6": "下一代软硬件缺陷抑制目标",
            "roi_sav_title": "🎯 年度细分成本削减分析 (Annual Savings)",
            "roi_s1": "呼叫中心客服成本节省",
            "roi_s2": "售后换货与物流支出节省",
            "s5_tag": "AI DEEP ROOT CAUSE DIAGNOSIS",
            "s5_title": "5. Gemini AI 缺陷深层根因 (Root Cause) 与竞标差异化建议",
            "col1_title": "📋 客户核心痛点要约",
            "col2_title": "🔬 软硬件工程深层根因剖析",
            "col3_title": "🎯 B2B 竞标技术差异化建议",
        },
        "vi": {
            "cover_tag": "GLOBAL RCU VOC INTELLIGENCE v4.0 | B2B STRATEGIC PROPOSAL",
            "deck_title": f"Đề xuất sản phẩm điều khiển RCU cho {client_name} dựa trên phân tích VoC khách hàng",
            "confidential": "BẢO MẬT (CONFIDENTIAL) - Dành riêng cho đánh giá B2B",
            "date": "Ngày lập", "target": "Thương hiệu mục tiêu",
            "s1_tag": "VOICE OF CUSTOMER INTELLIGENCE",
            "s1_title": f"1. Điểm đau cốt lõi & Phân tích lỗi khách hàng {client_name} (VoC)",
            "rank1_badge": "🚨 Lỗi trọng yếu số 1", "rank2_badge": "⚠️ Lỗi trọng yếu số 2",
            "reviews_header": "💬 Trích dẫn khiếu nại thực tế từ khách hàng",
            "chart_title": "Phân bố tỷ lệ lỗi kỹ thuật trọng yếu",
            "chart_series": "Tỷ lệ lỗi", "others": "Khác",
            "s2_tag": "R&D TECHNICAL ROADMAP",
            "s2_title": "2. Giải pháp kỹ thuật H/W & F/W thế hệ mới theo nguyên nhân lỗi",
            "sol_heading": "Giải pháp kỹ thuật H/W & F/W thế hệ mới từ chúng tôi",
            "s2_fallback_title": "🛡️ Hệ thống Đảm bảo Chất lượng & Độ tin cậy Toàn diện",
            "s2_fallback_body": "Áp dụng mặc định quy trình kiểm tra 100% 5 bước tiêu chuẩn và thử nghiệm độ bền nghiêm ngặt.",
            "s3_tag": "EXECUTIVE VALUE PROPOSITION",
            "s3_title": "3. Đề xuất đàm phán lãnh đạo C-Level & Giá trị chiến lược",
            "exec_pitch_title": f"EXECUTIVE STRATEGIC PITCH FOR {client_name.upper()}",
            "p1_title": "📉 Giảm tỷ lệ đổi trả & Logistics",
            "p1_sub": "• Giảm hơn 65% tỷ lệ đổi trả do lỗi điều khiển\n• Tiết kiệm tối đa chi phí logistics đổi hàng\n• Nâng cao độ bền phần cứng, kéo dài tuổi thọ",
            "p2_title": "📞 Cắt giảm cuộc gọi đến tổng đài CS",
            "p2_sub": "• Loại bỏ thắc mắc về lỗi kết nối và hao pin\n• Giảm chi phí xử lý mỗi cuộc gọi hỗ trợ\n• Tăng tỷ lệ người dùng tự cài đặt thành công",
            "p3_title": "⭐ Nâng cao chỉ số NPS & Giữ chân thuê bao",
            "p3_sub": "• Trải nghiệm điều hướng mượt mà, không độ trễ\n• Ngăn ngừa rời mạng và giữ chân thuê bao VIP\n• Khẳng định hình ảnh thương hiệu cao cấp",
            "s4_tag": "FINANCIAL IMPACT & ROI SIMULATION",
            "s4_title": f"4. Ước tính Tiết Kiệm Chi Phí OPEX & ROI Hàng Năm cho {client_name}",
            "roi_card1_title": "💰 Tổng OPEX Tiết Kiệm Dự Kiến",
            "roi_card2_title": "📞 Số Cuộc Gọi CS Được Ngăn Ngừa",
            "roi_card3_title": "📦 Số Lượt Đổi Trả Được Cắt Giảm",
            "unit_cases": "Lượt", "unit_units": "Thiết bị",
            "roi_base_title": "📊 Thông số cơ sở mô phỏng (Baseline)",
            "roi_p1": "Số thuê bao/thiết bị đang hoạt động",
            "roi_p2": "Tỷ lệ gọi hỗ trợ CS hàng năm",
            "roi_p3": "Chi phí xử lý mỗi cuộc gọi CS",
            "roi_p4": "Tỷ lệ đổi trả phần cứng hàng năm",
            "roi_p5": "Giá thành thiết bị + Logistics hai chiều",
            "roi_p6": "Mục tiêu giảm lỗi H/W & F/W thế hệ mới",
            "roi_sav_title": "🎯 Phân tích tiết kiệm chi phí hàng năm",
            "roi_s1": "Tiết kiệm chi phí tổng đài CS",
            "roi_s2": "Tiết kiệm chi phí đổi trả & Logistics",
            "s5_tag": "AI DEEP ROOT CAUSE DIAGNOSIS",
            "s5_title": "5. Chẩn đoán lỗi gốc rễ (Root Cause) & Đề xuất từ Gemini AI",
            "col1_title": "📋 Tóm tắt điểm đau VoC",
            "col2_title": "🔬 Chẩn đoán gốc rễ H/W & F/W",
            "col3_title": "🎯 Đề xuất kỹ thuật tạo khác biệt B2B",
        },
        "th": {
            "cover_tag": "GLOBAL RCU VOC INTELLIGENCE v4.0 | B2B STRATEGIC PROPOSAL",
            "deck_title": f"ข้อเสนอผลิตภัณฑ์รีโมทคอนโทรลสำหรับ {client_name} โดยอิงข้อมูลเชิงลึก VoC ของลูกค้า",
            "confidential": "เอกสารลับ (CONFIDENTIAL) - สำหรับการประเมินโครงการ B2B",
            "date": "วันที่จัดทำ", "target": "แบรนด์เป้าหมาย",
            "s1_tag": "VOICE OF CUSTOMER INTELLIGENCE",
            "s1_title": f"1. การวิเคราะห์จุดบกพร่องและปัญหาสำคัญของผู้ใช้งาน {client_name} (VoC)",
            "rank1_badge": "🚨 ข้อบกพร่องวิกฤตอันดับ 1", "rank2_badge": "⚠️ ข้อบกพร่องวิกฤตอันดับ 2",
            "reviews_header": "💬 ข้อความสะท้อนปัญหาจริงจากผู้ใช้งาน",
            "chart_title": "สัดส่วนข้อบกพร่องทางเทคนิคที่สามารถแก้ไขได้",
            "chart_series": "สัดส่วนข้อร้องเรียน", "others": "อื่นๆ",
            "s2_tag": "R&D TECHNICAL ROADMAP",
            "s2_title": "2. โซลูชันวิศวกรรม H/W & F/W ยุคใหม่ตรงจุดตามสาเหตุข้อบกพร่อง",
            "sol_heading": "โซลูชันวิศวกรรม H/W & F/W รุ่นใหม่จากเรา",
            "s2_fallback_title": "🛡️ ระบบรับประกันคุณภาพและความน่าเชื่อถือครบวงจร",
            "s2_fallback_body": "ใช้โปรโตคอลการตรวจสอบคุณภาพ 5 ขั้นตอนมาตรฐานและการทดสอบความทนทานระดับสากล",
            "s3_tag": "EXECUTIVE VALUE PROPOSITION",
            "s3_title": "3. ข้อเสนอต่อผู้บริหารระดับสูง (C-Level) และผลประโยชน์เชิงกลยุทธ์",
            "exec_pitch_title": f"EXECUTIVE STRATEGIC PITCH FOR {client_name.upper()}",
            "p1_title": "📉 ลดอัตราการคืนสินค้าและค่าขนส่ง",
            "p1_sub": "• ลดอัตราการเคลมและคืนสินค้ามากกว่า 65%\n• ประหยัดค่าใช้จ่ายด้านโลจิสติกส์เปลี่ยนอุปกรณ์\n• เพิ่มความทนทานของ H/W ยืดอายุการใช้งาน",
            "p2_title": "📞 ตัดปัญหาการโทรเข้าศูนย์บริการลูกค้า",
            "p2_sub": "• ขจัดปัญหาข้อสงสัยเรื่องการจับคู่และแบตเตอรี่\n• ลดต้นทุนต่อสายในการให้บริการลูกค้า\n• เพิ่มอัตราความสำเร็จในการติดตั้งด้วยตนเอง",
            "p3_title": "⭐ เพิ่มคะแนน NPS และความภักดีต่อแบรนด์",
            "p3_sub": "• ประสบการณ์ควบคุมลื่นไหล ปราศจากความหน่วง\n• ป้องกันการยกเลิกบริการและเพิ่มความพึงพอใจ\n• สร้างภาพลักษณ์แบรนด์รีโมทระดับพรีเมียม",
            "s4_tag": "FINANCIAL IMPACT & ROI SIMULATION",
            "s4_title": f"4. ประมาณการผลตอบแทน ROI และการลดต้นทุน OPEX รายปีสำหรับ {client_name}",
            "roi_card1_title": "💰 ยอดรวม OPEX ที่ประหยัดได้ต่อปี",
            "roi_card2_title": "📞 ปริมาณการโทรเข้า CS ที่ลดลง",
            "roi_card3_title": "📦 การเปลี่ยน/คืนสินค้าที่ลดลง",
            "unit_cases": "สาย", "unit_units": "เครื่อง",
            "roi_base_title": "📊 เกณฑ์การคำนวณแบบจำลอง (Baseline)",
            "roi_p1": "จำนวนผู้ใช้งาน/อุปกรณ์ที่ใช้งานอยู่",
            "roi_p2": "อัตราการติดต่อศูนย์บริการต่อปี",
            "roi_p3": "ต้นทุนเฉลี่ยต่อการให้บริการ CS 1 ครั้ง",
            "roi_p4": "อัตราการคืน/เคลมอุปกรณ์ต่อปี",
            "roi_p5": "ต้นทุนอุปกรณ์ + ค่าขนส่งไปกลับ",
            "roi_p6": "เป้าหมายการลดข้อบกพร่อง H/W & F/W รุ่นใหม่",
            "roi_sav_title": "🎯 การวิเคราะห์การประหยัดต้นทุนรายปี (Annual Savings)",
            "roi_s1": "ประหยัดค่าใช้จ่ายศูนย์บริการลูกค้า (CS)",
            "roi_s2": "ประหยัดค่าเปลี่ยนอุปกรณ์และโลจิสติกส์",
            "s5_tag": "AI DEEP ROOT CAUSE DIAGNOSIS",
            "s5_title": "5. การวินิจฉัยสาเหตุเชิงลึก (Root Cause) และข้อเสนอเชิงกลยุทธ์โดย Gemini AI",
            "col1_title": "📋 สรุปประเด็นปัญหาสำคัญ (VoC)",
            "col2_title": "🔬 วินิจฉัยสาเหตุเชิงลึก H/W & F/W",
            "col3_title": "🎯 ข้อเสนอสร้างความแตกต่างเชิงเทคนิค B2B",
        },
    }
    L = t_titles.get(lang, t_titles["en"])
    today_date = datetime.now().strftime("%Y-%m-%d")

    # SLIDE 1: Cover
    slide1 = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide1, COLOR_NAVY_DARK)

    tag_box = slide1.shapes.add_textbox(Inches(0.8), Inches(1.1), Inches(11.733), Inches(0.5))
    p_t = tag_box.text_frame.paragraphs[0]
    p_t.text = L["cover_tag"]
    p_t.font.name = FONT_FAMILY
    p_t.font.size = Pt(11)
    p_t.font.bold = True
    p_t.font.color.rgb = RGBColor(96, 165, 250)

    title_box = slide1.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.733), Inches(2.6))
    tf1 = title_box.text_frame
    tf1.word_wrap = True
    p_title = tf1.paragraphs[0]
    p_title.text = L["deck_title"]
    p_title.font.name = FONT_FAMILY
    p_title.font.size = Pt(32)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_TEXT_WHITE

    tf_meta = add_card_text_frame(
        slide1, Inches(0.8), Inches(5.1), Inches(11.733), Inches(1.5),
        bg_color=COLOR_NAVY_SURFACE, border_color=RGBColor(51, 65, 85), pad_h=0.3, pad_v=0.25, corner_radius_in=0.18
    )
    p_m1 = tf_meta.paragraphs[0]
    p_m1.text = f"🎯 {L['target']}: {client_name}   |   📅 {L['date']}: {today_date}"
    p_m1.font.name = FONT_FAMILY
    p_m1.font.size = Pt(12)
    p_m1.font.bold = True
    p_m1.font.color.rgb = COLOR_TEXT_WHITE
    p_m1.space_after = Pt(6)

    p_m2 = tf_meta.add_paragraph()
    p_m2.text = f"🔒 {L['confidential']} · Global RCU Intelligence Platform v4.0"
    p_m2.font.name = FONT_FAMILY
    p_m2.font.size = Pt(10)
    p_m2.font.color.rgb = RGBColor(148, 163, 184)

    # SLIDE 2: VoC Pain Points & Native Vector Doughnut Chart
    slide2 = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide2, COLOR_BG_PAGE)
    add_slide_header(slide2, L["s1_title"], L["s1_tag"])

    tf_kpi1 = add_card_text_frame(
        slide2, Inches(0.8), Inches(1.5), Inches(5.6), Inches(1.2),
        bg_color=COLOR_CARD_BG, border_color=RGBColor(254, 202, 202), pad_h=0.25, pad_v=0.18, corner_radius_in=0.18
    )
    p = tf_kpi1.paragraphs[0]
    p.text = L["rank1_badge"]
    p.font.name = FONT_FAMILY
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_RED
    p.space_after = Pt(2)
    p = tf_kpi1.add_paragraph()
    p.text = str(p_issue)
    p.font.name = FONT_FAMILY
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN

    if s_issue:
        tf_kpi2 = add_card_text_frame(
            slide2, Inches(0.8), Inches(2.82), Inches(5.6), Inches(1.2),
            bg_color=COLOR_CARD_BG, border_color=RGBColor(254, 215, 170), pad_h=0.25, pad_v=0.18, corner_radius_in=0.18
        )
        p = tf_kpi2.paragraphs[0]
        p.text = L["rank2_badge"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT_ORANGE
        p.space_after = Pt(2)
        p = tf_kpi2.add_paragraph()
        p.text = str(s_issue)
        p.font.name = FONT_FAMILY
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = COLOR_TEXT_MAIN

    rev_top = Inches(4.14) if s_issue else Inches(2.82)
    rev_h = Inches(2.76) if s_issue else Inches(4.08)
    tf_rev = add_card_text_frame(
        slide2, Inches(0.8), rev_top, Inches(5.6), rev_h,
        pad_h=0.25, pad_v=0.18, corner_radius_in=0.18
    )
    p = tf_rev.paragraphs[0]
    p.text = L["reviews_header"]
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(6)

    for r in reviews[:3]:
        r_clean = str(r).replace('\n', ' ').strip()
        if len(r_clean) > 85:
            r_clean = r_clean[:82] + "..."
        p = tf_rev.add_paragraph()
        p.text = f'• "{r_clean}"'
        p.font.name = FONT_FAMILY
        p.font.size = Pt(9.5)
        p.font.italic = True
        p.font.color.rgb = RGBColor(71, 85, 105)
        p.space_after = Pt(4)

    add_card_container(slide2, Inches(6.8), Inches(1.5), Inches(5.733), Inches(5.4), corner_radius_in=0.18)
    title_chart_box = slide2.shapes.add_textbox(Inches(7.15), Inches(1.75), Inches(5.0), Inches(0.4))
    tf_ct = title_chart_box.text_frame
    tf_ct.margin_left = tf_ct.margin_top = tf_ct.margin_right = tf_ct.margin_bottom = 0
    p = tf_ct.paragraphs[0]
    p.text = L["chart_title"]
    p.font.name = FONT_FAMILY
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = COLOR_TEXT_MAIN

    if cat_counts is not None and not cat_counts.empty:
        valid_counts = cat_counts[cat_counts.index != "기타/일반"]
        if not valid_counts.empty:
            chart_data = CategoryChartData()
            top_cats = valid_counts.head(4)
            other_cnt = valid_counts.iloc[4:].sum() if len(valid_counts) > 4 else 0

            cat_labels = [tr.CATEGORIES.get(k, {}).get(lang, k) for k in top_cats.index]
            cat_vals = list(top_cats.values)
            if other_cnt > 0:
                cat_labels.append(L["others"])
                cat_vals.append(other_cnt)

            chart_data.categories = cat_labels
            chart_data.add_series(L["chart_series"], cat_vals)

            chart_shape = slide2.shapes.add_chart(
                XL_CHART_TYPE.DOUGHNUT, Inches(7.15), Inches(2.2), Inches(5.0), Inches(4.4), chart_data
            )
            chart = chart_shape.chart
            chart.has_legend = True
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.font.name = FONT_FAMILY
            chart.legend.font.size = Pt(8.5)
            chart.legend.include_in_layout = False

            plot = chart.plots[0]
            plot.has_data_labels = True
            plot.data_labels.font.name = FONT_FAMILY
            plot.data_labels.font.size = Pt(8.5)
            plot.data_labels.font.bold = True
            plot.data_labels.show_percentage = True
            plot.data_labels.show_value = False

    # SLIDE 3: R&D Solutions
    slide3 = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide3, COLOR_BG_PAGE)
    add_slide_header(slide3, L["s2_title"], L["s2_tag"])

    card_w = Inches(5.66)
    card_h = Inches(5.4)

    tf_sol1 = add_card_text_frame(
        slide3, Inches(0.8), Inches(1.5), card_w, card_h,
        pad_h=0.3, pad_v=0.25, corner_radius_in=0.18
    )
    p = tf_sol1.paragraphs[0]
    p.text = f"{L['rank1_badge']}: {p_issue}"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_RED
    p.space_after = Pt(10)

    p = tf_sol1.add_paragraph()
    p.text = f"🛠️ {L['sol_heading']}"
    p.font.name = FONT_FAMILY
    p.font.size = Pt(11.5)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_GREEN
    p.space_after = Pt(8)

    p_sol_clean = str(p_sol).strip()
    if p_sol_clean:
        p = tf_sol1.add_paragraph()
        p.text = p_sol_clean
        p.font.name = FONT_FAMILY
        p.font.size = Pt(10.5)
        p.font.color.rgb = COLOR_TEXT_MAIN
        p.space_after = Pt(6)

    tf_sol2 = add_card_text_frame(
        slide3, Inches(6.866), Inches(1.5), card_w, card_h,
        pad_h=0.3, pad_v=0.25, corner_radius_in=0.18
    )
    if s_issue:
        p = tf_sol2.paragraphs[0]
        p.text = f"{L['rank2_badge']}: {s_issue}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT_ORANGE
        p.space_after = Pt(10)

        p = tf_sol2.add_paragraph()
        p.text = f"🛠️ {L['sol_heading']}"
        p.font.name = FONT_FAMILY
        p.font.size = Pt(11.5)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT_GREEN
        p.space_after = Pt(8)

        s_sol_clean = str(s_sol).strip()
        if s_sol_clean:
            p = tf_sol2.add_paragraph()
            p.text = s_sol_clean
            p.font.name = FONT_FAMILY
            p.font.size = Pt(10.5)
            p.font.color.rgb = COLOR_TEXT_MAIN
    else:
        p = tf_sol2.paragraphs[0]
        p.text = L["s2_fallback_title"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY
        p.space_after = Pt(10)
        p = tf_sol2.add_paragraph()
        p.text = L["s2_fallback_body"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(10.5)
        p.font.color.rgb = COLOR_TEXT_MUTED

    # SLIDE 4: Executive Pitch
    slide4 = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide4, COLOR_BG_PAGE)
    add_slide_header(slide4, L["s3_title"], L["s3_tag"])

    tf_pitch = add_card_text_frame(
        slide4, Inches(0.8), Inches(1.5), Inches(11.733), Inches(2.3),
        bg_color=COLOR_PRIMARY_LIGHT, border_color=RGBColor(147, 197, 253),
        pad_h=0.35, pad_v=0.22, corner_radius_in=0.18
    )
    p = tf_pitch.paragraphs[0]
    p.text = L["exec_pitch_title"]
    p.font.name = FONT_FAMILY
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(6)

    p = tf_pitch.add_paragraph()
    p.text = f'"{pitch}"'
    p.font.name = FONT_FAMILY
    p.font.size = Pt(13.5)
    p.font.bold = True
    p.font.color.rgb = COLOR_NAVY_DARK

    pillar_w = Inches(3.64)
    pillar_gap = Inches(0.4)
    pillar_h = Inches(2.9)
    top_pillar = Inches(4.0)

    pillars = [
        {"title": L["p1_title"], "sub": L["p1_sub"]},
        {"title": L["p2_title"], "sub": L["p2_sub"]},
        {"title": L["p3_title"], "sub": L["p3_sub"]},
    ]

    for i, pil in enumerate(pillars):
        x = Inches(0.8) + i * (pillar_w + pillar_gap)
        tf_pil = add_card_text_frame(
            slide4, x, top_pillar, pillar_w, pillar_h,
            pad_h=0.25, pad_v=0.2, corner_radius_in=0.18
        )
        p = tf_pil.paragraphs[0]
        p.text = pil["title"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = COLOR_NAVY_DARK
        p.space_after = Pt(8)

        for line in pil["sub"].splitlines():
            p_line = tf_pil.add_paragraph()
            p_line.text = line.strip()
            p_line.font.name = FONT_FAMILY
            p_line.font.size = Pt(9.5)
            p_line.font.color.rgb = RGBColor(71, 85, 105)
            p_line.space_after = Pt(3)

    # SLIDE 5: Financial Impact & ROI Simulation
    if roi_data:
        slide_roi = prs.slides.add_slide(prs.slide_layouts[6])
        set_slide_bg(slide_roi, COLOR_BG_PAGE)
        add_slide_header(slide_roi, L["s4_title"], L["s4_tag"])

        kpi_configs = [
            {
                "val": f"${roi_data['saved_total_cost']:,.0f}",
                "lbl": L["roi_card1_title"],
                "color": COLOR_ACCENT_GREEN,
            },
            {
                "val": f"{roi_data['saved_cs_calls']:,} {L['unit_cases']}",
                "lbl": L["roi_card2_title"],
                "color": COLOR_PRIMARY,
            },
            {
                "val": f"{roi_data['saved_returns']:,} {L['unit_units']}",
                "lbl": L["roi_card3_title"],
                "color": COLOR_ACCENT_ORANGE,
            },
        ]
        card_w_roi = Inches(3.64)
        gap_roi = Inches(0.4)

        for i, kpi in enumerate(kpi_configs):
            x = Inches(0.8) + i * (card_w_roi + gap_roi)
            tf_k = add_card_text_frame(slide_roi, x, Inches(1.5), card_w_roi, Inches(1.3), pad_h=0.2, pad_v=0.15)
            p_v = tf_k.paragraphs[0]
            p_v.text = kpi["val"]
            p_v.font.name = FONT_FAMILY
            p_v.font.size = Pt(26)
            p_v.font.bold = True
            p_v.font.color.rgb = kpi["color"]
            p_v.alignment = PP_ALIGN.CENTER
            p_v.space_after = Pt(3)

            p_l = tf_k.add_paragraph()
            p_l.text = kpi["lbl"]
            p_l.font.name = FONT_FAMILY
            p_l.font.size = Pt(10.5)
            p_l.font.color.rgb = COLOR_TEXT_MUTED
            p_l.alignment = PP_ALIGN.CENTER

        tf_detail_l = add_card_text_frame(slide_roi, Inches(0.8), Inches(3.05), Inches(5.66), Inches(3.85), pad_h=0.3, pad_v=0.25)
        p = tf_detail_l.paragraphs[0]
        p.text = L["roi_base_title"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = COLOR_NAVY_DARK
        p.space_after = Pt(10)

        params_text = [
            f"• {L['roi_p1']}: {roi_data['sub_count']:,} {L['unit_units']}",
            f"• {L['roi_p2']}: {roi_data['cs_rate']:.1f}%",
            f"• {L['roi_p3']}: ${roi_data['cs_cost']:.2f}",
            f"• {L['roi_p4']}: {roi_data['return_rate']:.1f}%",
            f"• {L['roi_p5']}: ${roi_data['return_cost']:.2f}",
            f"• {L['roi_p6']}: -{roi_data['reduction_rate']}%",
        ]
        for pt in params_text:
            p = tf_detail_l.add_paragraph()
            p.text = pt
            p.font.name = FONT_FAMILY
            p.font.size = Pt(10)
            p.font.color.rgb = COLOR_TEXT_MAIN
            p.space_after = Pt(6)

        tf_detail_r = add_card_text_frame(slide_roi, Inches(6.866), Inches(3.05), Inches(5.66), Inches(3.85), pad_h=0.3, pad_v=0.25)
        p = tf_detail_r.paragraphs[0]
        p.text = L["roi_sav_title"]
        p.font.name = FONT_FAMILY
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY
        p.space_after = Pt(10)

        base_calls_int = int(roi_data["sub_count"] * roi_data["cs_rate"] / 100)
        base_rets_int = int(roi_data["sub_count"] * roi_data["return_rate"] / 100)

        if lang == "ko":
            calc_krw_eok = (roi_data["saved_total_cost"] * 1350.0) / 100000000.0
            calc_text = [
                f"1. {L['roi_s1']}: ${roi_data['saved_cs_cost']:,.0f} / 년",
                f"   (기존 {base_calls_int:,}건 중 {roi_data['saved_cs_calls']:,}건 예방)",
                "",
                f"2. {L['roi_s2']}: ${roi_data['saved_return_cost']:,.0f} / 년",
                f"   (기존 {base_rets_int:,}대 중 {roi_data['saved_returns']:,}대 반품 절감)",
                "",
                f"✨ 연간 총 ${roi_data['saved_total_cost']:,.0f} (한화 약 {calc_krw_eok:,.1f}억 원) OPEX 절감 달성",
            ]
        elif lang == "zh":
            calc_rmb_wan = (roi_data["saved_total_cost"] * 7.2) / 10000.0
            calc_text = [
                f"1. {L['roi_s1']}: ${roi_data['saved_cs_cost']:,.0f} / 年",
                f"   (原有 {base_calls_int:,} 单中预防 {roi_data['saved_cs_calls']:,} 单)",
                "",
                f"2. {L['roi_s2']}: ${roi_data['saved_return_cost']:,.0f} / 年",
                f"   (原有 {base_rets_int:,} 台中减少 {roi_data['saved_returns']:,} 台换货)",
                "",
                f"✨ 年度总计节省 ${roi_data['saved_total_cost']:,.0f} (约 {calc_rmb_wan:,.1f}万 人民币) OPEX 支出",
            ]
        else:
            calc_text = [
                f"1. {L['roi_s1']}: ${roi_data['saved_cs_cost']:,.0f} / yr",
                f"   ({roi_data['saved_cs_calls']:,} of {base_calls_int:,} {L['unit_cases']} prevented)",
                "",
                f"2. {L['roi_s2']}: ${roi_data['saved_return_cost']:,.0f} / yr",
                f"   ({roi_data['saved_returns']:,} of {base_rets_int:,} {L['unit_units']} avoided)",
                "",
                f"✨ Total Annual OPEX Savings: ${roi_data['saved_total_cost']:,.0f} (-{roi_data['reduction_rate']}% defect reduction)",
            ]

        for ct in calc_text:
            p = tf_detail_r.add_paragraph()
            p.text = ct
            p.font.name = FONT_FAMILY
            p.font.size = Pt(9.8) if not ct.startswith("✨") else Pt(10.5)
            p.font.bold = True if ct.startswith(("1.", "2.", "✨")) else False
            p.font.color.rgb = COLOR_ACCENT_GREEN if ct.startswith("✨") else COLOR_TEXT_MAIN
            p.space_after = Pt(4)

    # SLIDE 6: Gemini AI Root Cause
    if ai_analysis and not ai_analysis.startswith("⚠️"):
        slide_ai = prs.slides.add_slide(prs.slide_layouts[6])
        set_slide_bg(slide_ai, COLOR_BG_PAGE)
        add_slide_header(slide_ai, L["s5_title"], L["s5_tag"])

        s1_items, s2_items, s3_items = parse_gemini_sections(ai_analysis)

        ai_cols = [
            {"title": L["col1_title"], "color": COLOR_PRIMARY, "items": s1_items},
            {"title": L["col2_title"], "color": COLOR_ACCENT_RED, "items": s2_items},
            {"title": L["col3_title"], "color": COLOR_ACCENT_GREEN, "items": s3_items},
        ]

        col_w = Inches(3.64)
        col_gap = Inches(0.4)
        col_h = Inches(5.4)

        for i, acol in enumerate(ai_cols):
            x = Inches(0.8) + i * (col_w + col_gap)
            tf_col = add_card_text_frame(
                slide_ai, x, Inches(1.5), col_w, col_h,
                pad_h=0.25, pad_v=0.2, corner_radius_in=0.18
            )
            p = tf_col.paragraphs[0]
            p.text = acol["title"]
            p.font.name = FONT_FAMILY
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = acol["color"]
            p.space_after = Pt(10)

            items_to_show = acol["items"][:4] if acol["items"] else ["-"]
            for item in items_to_show:
                item_str = item.strip()
                if len(item_str) > 130:
                    item_str = item_str[:127] + "..."
                p = tf_col.add_paragraph()
                p.text = f"• {item_str}"
                p.font.name = FONT_FAMILY
                p.font.size = Pt(9.5)
                p.font.color.rgb = COLOR_TEXT_MAIN
                p.space_after = Pt(6)

    ppt_stream = io.BytesIO()
    prs.save(ppt_stream)
    ppt_stream.seek(0)
    return ppt_stream

# -------------------------------------------------------------
# 3. 사이드바 다차원 필터 패널 & API Key 설정
# -------------------------------------------------------------
st.sidebar.header(txt("sidebar_filter"))

if st.sidebar.button(txt("sync_btn"), key="btn_sync_collector"):
    with st.spinner("🔄 Syncing latest global VoC data... (~15-20s)"):
        try:
            import collector2
            importlib.reload(collector2)
            collector2.collect_advanced_voc(quick_mode=True)
            st.cache_data.clear()
            st.toast("✅ VoC database synced successfully!", icon="🚀")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"⚠️ Sync failed: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown(f"##### {txt('preset_title')}")

all_unique_brands = sorted(list(df_all["Brand"].unique()))
if "selected_brand_list" not in st.session_state:
    st.session_state["selected_brand_list"] = all_unique_brands

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button(txt("btn_kr")):
        st.session_state["selected_brand_list"] = [
            b for b in KR_CHAMPIONS if b in all_unique_brands
        ]
        st.rerun()
    if st.button(txt("btn_na")):
        st.session_state["selected_brand_list"] = [
            b for b in NA_CHAMPIONS if b in all_unique_brands
        ]
        st.rerun()
    if st.button(txt("btn_africa")):
        st.session_state["selected_brand_list"] = [
            b for b in AFRICA_CHAMPIONS if b in all_unique_brands
        ]
        st.rerun()

with col_btn2:
    if st.button(txt("btn_eu")):
        st.session_state["selected_brand_list"] = [
            b for b in EU_CHAMPIONS if b in all_unique_brands
        ]
        st.rerun()
    if st.button(txt("btn_apac")):
        st.session_state["selected_brand_list"] = [
            b for b in APAC_CHAMPIONS if b in all_unique_brands
        ]
        st.rerun()
    if st.button(txt("btn_all")):
        st.session_state["selected_brand_list"] = all_unique_brands
        st.rerun()

st.sidebar.markdown("---")

device_types = sorted(list(df_all["Device_Type"].dropna().unique()))
selected_types = st.sidebar.multiselect(
    txt("filter_dev"),
    options=device_types,
    default=device_types,
    format_func=get_dev_name,
)

brand_subset = df_all[df_all["Device_Type"].isin(selected_types)]["Brand"].unique()
available_brands = sorted(list(brand_subset))
valid_defaults = [
    b for b in st.session_state["selected_brand_list"] if b in available_brands
]
if not valid_defaults:
    valid_defaults = available_brands

selected_brands = st.sidebar.multiselect(
    txt("filter_brand"), options=available_brands, default=valid_defaults
)

with st.sidebar.expander(txt("filter_hw"), expanded=False):
    all_powers = sorted(list(df_all["Power_Type"].unique()))
    sel_powers = st.multiselect(
        txt("filter_power"),
        all_powers,
        default=all_powers,
        format_func=get_power_name,
    )

    all_uis = sorted(list(df_all["UI_Type"].unique()))
    sel_uis = st.multiselect(
        txt("filter_ui"),
        all_uis,
        default=all_uis,
        format_func=get_ui_name,
    )

selected_regions = st.sidebar.multiselect(
    txt("filter_region"),
    options=sorted(df_all["Region"].unique()),
    default=sorted(df_all["Region"].unique()),
    format_func=get_region_name,
)

available_cats_all = sorted(list(df_all["Category"].unique()))
pure_actionable_cats = [c for c in available_cats_all if c != "기타/일반"]

selected_cats = st.sidebar.multiselect(
    txt("filter_cat"),
    options=available_cats_all,
    default=pure_actionable_cats if pure_actionable_cats else available_cats_all,
    format_func=get_cat_name,
)

search_keyword = st.sidebar.text_input(
    txt("filter_kw"),
    placeholder=txt("kw_placeholder"),
)

with st.sidebar.expander("🤖 Gemini AI API Settings", expanded=False):
    saved_key = get_secret_api_key()
    user_api_key = st.text_input(
        txt("ai_key_input"),
        type="password",
        value=st.session_state.get("gemini_api_key", saved_key),
        placeholder="AIzaSy...",
        help=txt("ai_key_help"),
        key="gemini_key_input_box"
    )
    if user_api_key:
        st.session_state["gemini_api_key"] = user_api_key.strip()

# 1차 원문 필터링
filtered_df_raw = df_all[
    (df_all["Device_Type"].isin(selected_types))
    & (df_all["Brand"].isin(selected_brands))
    & (df_all["Power_Type"].isin(sel_powers))
    & (df_all["UI_Type"].isin(sel_uis))
    & (df_all["Region"].isin(selected_regions))
    & (df_all["Category"].isin(selected_cats))
]

if search_keyword.strip():
    filtered_df_raw = filtered_df_raw[
        filtered_df_raw["Review"]
        .astype(str)
        .str.contains(search_keyword.strip(), case=False, na=False)
    ]

# 분석 및 시각화용: '기타/일반'을 완전 배제한 정밀 기술 결함 데이터셋
filtered_df = filtered_df_raw[filtered_df_raw["Category"] != "기타/일반"].copy()
if filtered_df.empty:
    filtered_df = filtered_df_raw.copy()

# -------------------------------------------------------------
# 4. 상단 헤더 & 알림 배너
# -------------------------------------------------------------
st.title(txt("main_title"))
st.caption(txt("main_caption"))

if not filtered_df.empty:
    neg_only = filtered_df[filtered_df["Sentiment"] == "Negative"]
    top_3_cats = neg_only["Category"].value_counts().head(3)
    top_cat_names = [
        f"**{i+1}** {get_cat_name(cat)}" for i, cat in enumerate(top_3_cats.index)
    ]

    brand_neg_stats = (
        (filtered_df["Sentiment"] == "Negative")
        .groupby(filtered_df["Brand"])
        .mean()
        .reset_index(name="neg_rate")
    )
    brand_counts = filtered_df["Brand"].value_counts().reset_index()
    brand_counts.columns = ["Brand", "count"]
    brand_merged = pd.merge(brand_neg_stats, brand_counts, on="Brand")
    valid_brands = brand_merged[brand_merged["count"] >= 15].sort_values(
        by="neg_rate", ascending=False
    )
    highest_neg_brand = (
        valid_brands.iloc[0]["Brand"] if not valid_brands.empty else "-"
    )
    highest_neg_val = (
        f"{valid_brands.iloc[0]['neg_rate']*100:.1f}%"
        if not valid_brands.empty
        else "-"
    )

    b1, b2 = st.columns([2, 1])
    with b1:
        st.info(
            f"{txt('top3_alert')} {' | '.join(top_cat_names) if top_cat_names else '-'}"
        )
    with b2:
        st.warning(
            f"{txt('neg_alert')} **{highest_neg_brand}** ({txt('complaint_rate')} {highest_neg_val})"
        )

st.divider()

# -------------------------------------------------------------
# 5. 5대 탭 분할 구조
# -------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    txt("tab1"), txt("tab2"), txt("tab3"), txt("tab4"), txt("tab5")
])

# =============================================================
# TAB 1: 종합 모니터링 & 트렌드 + 인라인 드릴다운
# =============================================================
with tab1:
    total_cnt = len(filtered_df)
    neg_cnt = len(filtered_df[filtered_df["Sentiment"] == "Negative"])
    neg_ratio = (neg_cnt / total_cnt * 100) if total_cnt > 0 else 0
    top_cat_mode = filtered_df["Category"].mode()
    top_cat = get_cat_name(top_cat_mode.iloc[0]) if not top_cat_mode.empty else "-"

    if not filtered_df.empty:
        min_d = filtered_df["Parsed_Date"].min().strftime("%Y-%m-%d")
        max_d = filtered_df["Parsed_Date"].max().strftime("%Y-%m-%d")
        max_yw = filtered_df["Parsed_Date"].max().strftime("%Y-W%W")
        st.caption(txt("data_period_info", min_d=min_d, max_d=max_d, max_yw=max_yw))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(txt("m_actionable_cnt"), f"{total_cnt:,}")
    m2.metric(
        txt("m_neg_rate"),
        f"{neg_ratio:.1f}%",
        delta=f"{neg_cnt:,}",
        delta_color="inverse",
    )
    m3.metric(txt("m_top_issue"), top_cat)
    m4.metric(txt("m_brand_cnt"), f"{filtered_df['Brand'].nunique()}")

    st.write("")
    col_t1, col_t2 = st.columns(2)
    selected_slice = None

    def resolve_cat_example(cat):
        ex = tr.get_cat_example(cat, curr_lang)
        if ex and str(ex).strip() not in ["-", "", "None"]:
            return str(ex).strip()
        cat_revs = filtered_df[
            (filtered_df["Category"] == cat) & (filtered_df["Sentiment"] == "Negative")
        ]["Review"].dropna()
        if cat_revs.empty:
            cat_revs = filtered_df[filtered_df["Category"] == cat]["Review"].dropna()
        if not cat_revs.empty:
            sample_text = str(cat_revs.iloc[0]).replace("\n", " ").strip()
            sample_text = re.sub(r"^\[.*?\]\s*", "", sample_text)
            return sample_text[:65] + "..." if len(sample_text) > 65 else sample_text
        return "-"

    with col_t1:
        st.subheader(txt("chart_cat_dist"))
        if not filtered_df.empty:
            cat_counts = filtered_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            cat_counts["Category_Label"] = cat_counts["Category"].apply(get_cat_name)
            cat_counts["Description"] = cat_counts["Category"].map(lambda c: tr.get_cat_desc(c, curr_lang))
            cat_counts["Examples"] = cat_counts["Category"].apply(resolve_cat_example)

            hover_text_list = []
            for _, r in cat_counts.iterrows():
                c_lbl = r["Category_Label"]
                c_cnt = r["Count"]
                c_pct = (c_cnt / total_cnt * 100) if total_cnt > 0 else 0
                c_desc = r["Description"]
                c_ex = r["Examples"]

                ht = (
                    f"<b>{c_lbl}</b><br>"
                    f"{txt('share_label')}: <b>{c_pct:.1f}%</b> ({c_cnt:,}{txt('count_unit')})<br><br>"
                    f"📌 <b>{txt('lbl_definition')}:</b> {c_desc}<br>"
                    f"💬 <b>{txt('lbl_key_examples')}:</b> {c_ex}"
                )
                hover_text_list.append(ht)

            fig1 = go.Figure(
                data=[
                    go.Pie(
                        labels=cat_counts["Category_Label"],
                        values=cat_counts["Count"],
                        hole=0.4,
                        textinfo="percent",
                        hovertext=hover_text_list,
                        hovertemplate="%{hovertext}<extra></extra>",
                        customdata=cat_counts["Category"],
                        marker=dict(colors=px.colors.qualitative.Set3),
                    )
                ]
            )
            fig1.update_layout(
                margin=dict(t=20, b=20, l=10, r=10),
                legend=dict(orientation="v", x=1.05, y=0.5),
            )

            try:
                import inspect
                if "on_select" in inspect.signature(st.plotly_chart).parameters:
                    chart_event = st.plotly_chart(
                        fig1,
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="points",
                        key="pie_chart_cat_dist",
                    )
                    if (
                        chart_event
                        and isinstance(chart_event, dict)
                        and chart_event.get("selection")
                        and chart_event["selection"].get("points")
                    ):
                        p_idx = chart_event["selection"]["points"][0].get("point_index")
                        if p_idx is not None and 0 <= p_idx < len(cat_counts):
                            selected_slice = cat_counts.iloc[p_idx]["Category"]
                else:
                    st.plotly_chart(fig1, use_container_width=True)
            except Exception:
                st.plotly_chart(fig1, use_container_width=True)

    with col_t2:
        st.subheader(txt("chart_dev_dist"))
        if not filtered_df.empty:
            dev_df = filtered_df.copy()
            dev_df["Device_Type_Label"] = dev_df["Device_Type"].apply(get_dev_name)
            dev_df["Category_Label"] = dev_df["Category"].apply(get_cat_name)
            dev_cat = (
                dev_df.groupby(["Device_Type_Label", "Category_Label"])
                .size()
                .reset_index(name="건수")
            )
            fig2 = px.bar(
                dev_cat,
                x="Device_Type_Label",
                y="건수",
                color="Category_Label",
                barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Set3,
                labels={
                    "Device_Type_Label": txt("filter_dev"),
                    "건수": txt("count_unit"),
                    "Category_Label": txt("filter_cat"),
                },
            )
            fig2.update_layout(margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    # 인라인 심층 드릴다운 & 현장 VoC 원문 5선
    st.write("")
    st.markdown("---")
    st.subheader(txt("drilldown_title"))
    st.caption(txt("drilldown_caption"))

    if not filtered_df.empty:
        available_inspect_cats = sorted(list(filtered_df["Category"].unique()))

        if selected_slice and selected_slice in available_inspect_cats:
            st.session_state["inline_inspect_cat_select"] = selected_slice
            default_inspect_cat = selected_slice
        elif "inline_inspect_cat_select" in st.session_state and st.session_state["inline_inspect_cat_select"] in available_inspect_cats:
            default_inspect_cat = st.session_state["inline_inspect_cat_select"]
        elif "chosen_drilldown_cat" in st.session_state and st.session_state["chosen_drilldown_cat"] in available_inspect_cats:
            default_inspect_cat = st.session_state["chosen_drilldown_cat"]
        else:
            default_inspect_cat = (
                top_cat_mode.iloc[0]
                if (not top_cat_mode.empty and top_cat_mode.iloc[0] in available_inspect_cats)
                else available_inspect_cats[0]
            )

        inspect_cat = st.selectbox(
            txt("select_inspect_cat"),
            options=available_inspect_cats,
            index=available_inspect_cats.index(default_inspect_cat),
            format_func=get_cat_name,
            key="inline_inspect_cat_select",
        )
        st.session_state["chosen_drilldown_cat"] = inspect_cat

        col_dd1, col_dd2 = st.columns([1.1, 1.3])
        with col_dd1:
            st.markdown(f"##### {txt('cat_summary_card')}")
            cat_desc = tr.get_cat_desc(inspect_cat, curr_lang)
            cat_ex = resolve_cat_example(inspect_cat)
            cat_sol = get_action_sol(inspect_cat)
            cat_count_val = len(filtered_df[filtered_df["Category"] == inspect_cat])
            cat_ratio_val = (cat_count_val / total_cnt * 100) if total_cnt > 0 else 0

            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 18px; border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="font-size: 1.1em; font-weight: bold; color: #1f77b4; margin-bottom: 6px;">🏷️ {get_cat_name(inspect_cat)} <span style="font-size: 0.85em; color: #666;">({cat_count_val:,}{txt('count_unit')} · {cat_ratio_val:.1f}%)</span></div>
                    <div style="font-size: 0.92em; line-height: 1.5; margin-bottom: 8px;">📌 <b>{txt('lbl_definition')}:</b> {cat_desc}</div>
                    <div style="font-size: 0.92em; line-height: 1.5; color: #444;">💬 <b>{txt('lbl_key_examples')}:</b> {cat_ex}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.success(f"**🛠️ {txt('hw_fw_proposal')}**\n\n{cat_sol}")

        with col_dd2:
            st.markdown(f"##### {txt('cat_reviews_card')}")
            cat_reviews = filtered_df[
                (filtered_df["Category"] == inspect_cat)
                & (filtered_df["Sentiment"] == "Negative")
            ]["Review"].dropna()

            if cat_reviews.empty:
                cat_reviews = filtered_df[filtered_df["Category"] == inspect_cat]["Review"].dropna()

            if not cat_reviews.empty:
                sample_5_reviews = cat_reviews.head(5).tolist()
                for idx, rev_text in enumerate(sample_5_reviews):
                    st.markdown(
                        f"""
                        <div style="background-color: #ffffff; padding: 12px 16px; border-radius: 8px; border: 1px solid #e2e8f0; border-left: 4px solid #ef4444; margin-bottom: 8px; font-size: 0.92em; line-height: 1.5;">
                            <span style="color: #ef4444; font-weight: bold; margin-right: 6px;">#{idx+1}</span> "{rev_text}"
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info(txt("no_cat_reviews"))

    # 주차별 트렌드 라인 차트
    st.write("")
    st.markdown("---")
    
    col_tr_h, col_tr_sel = st.columns([1.5, 1])
    with col_tr_h:
        st.subheader(txt("chart_trend"))
    with col_tr_sel:
        trend_period_opt = st.radio(
            txt("period_filter_label"),
            options=["12w", "24w", "1y", "all"],
            format_func=lambda k: txt(f"period_{k}"),
            horizontal=True,
            index=1,
            label_visibility="collapsed",
            key="trend_period_selector_radio",
        )

    if not filtered_df.empty:
        trend_df = filtered_df.copy()
        max_dt = trend_df["Parsed_Date"].max()

        if trend_period_opt == "12w":
            trend_df = trend_df[trend_df["Parsed_Date"] >= (max_dt - pd.Timedelta(weeks=12))].copy()
        elif trend_period_opt == "24w":
            trend_df = trend_df[trend_df["Parsed_Date"] >= (max_dt - pd.Timedelta(weeks=24))].copy()
        elif trend_period_opt == "1y":
            trend_df = trend_df[trend_df["Parsed_Date"] >= (max_dt - pd.Timedelta(days=365))].copy()

        if trend_df.empty:
            trend_df = filtered_df.copy()

        trend_df["YearWeek"] = trend_df["Parsed_Date"].dt.strftime("%Y-W%W")
        trend_df["Category_Label"] = trend_df["Category"].apply(get_cat_name)

        weekly_trend = (
            trend_df.groupby(["YearWeek", "Category_Label"])
            .size()
            .reset_index(name="건수")
        )
        weekly_trend = weekly_trend.sort_values(by=["YearWeek", "Category_Label"], ascending=[True, True])

        fig_trend = px.line(
            weekly_trend,
            x="YearWeek",
            y="건수",
            color="Category_Label",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Set3,
            labels={
                "YearWeek": txt("week_unit"),
                "건수": txt("count_unit"),
                "Category_Label": txt("filter_cat"),
            },
        )
        
        fig_trend.update_layout(
            xaxis={
                "type": "category",
                "categoryorder": "category ascending"
            },
            margin=dict(t=20, b=20, l=10, r=10)
        )
        st.plotly_chart(fig_trend, use_container_width=True)

# =============================================================
# TAB 2: 브랜드 1:1 벤치마크
# =============================================================
with tab2:
    st.subheader(txt("t2_title"))
    st.caption(txt("t2_caption"))

    all_b = sorted(list(filtered_df["Brand"].dropna().unique()))
    if len(all_b) >= 2:
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            brand_a = st.selectbox(
                txt("brand_a_label"),
                all_b,
                index=all_b.index("Samsung") if "Samsung" in all_b else 0,
                key="brand_a_select",
            )
        with c_b2:
            cand_b = [b for b in all_b if b != brand_a]
            brand_b = st.selectbox(
                txt("brand_b_label"),
                cand_b,
                index=(
                    cand_b.index("MultiChoice (DStv)")
                    if "MultiChoice (DStv)" in cand_b
                    else 0
                ),
                key="brand_b_select",
            )

        df_a, df_b = filtered_df[filtered_df["Brand"] == brand_a], filtered_df[filtered_df["Brand"] == brand_b]
        a_cnt, b_cnt = len(df_a), len(df_b)
        a_neg_rate = (
            (len(df_a[df_a["Sentiment"] == "Negative"]) / a_cnt * 100)
            if a_cnt > 0
            else 0
        )
        b_neg_rate = (
            (len(df_b[df_b["Sentiment"] == "Negative"]) / b_cnt * 100)
            if b_cnt > 0
            else 0
        )

        k1, k2, km, k3, k4 = st.columns([2, 2, 1, 2, 2])
        k1.metric(f"[{brand_a}] {txt('m_actionable_cnt')}", f"{a_cnt:,}")
        k2.metric(f"[{brand_a}] {txt('m_neg_rate')}", f"{a_neg_rate:.1f}%")
        km.markdown(
            "<h3 style='text-align: center; color: gray;'>VS</h3>",
            unsafe_allow_html=True,
        )
        k3.metric(f"[{brand_b}] {txt('m_actionable_cnt')}", f"{b_cnt:,}")
        k4.metric(
            f"[{brand_b}] {txt('m_neg_rate')}",
            f"{b_neg_rate:.1f}%",
            delta=f"{b_neg_rate - a_neg_rate:+.1f}%p",
            delta_color="inverse",
        )

        df_ab = filtered_df[filtered_df["Brand"].isin([brand_a, brand_b])].copy()
        if not df_ab.empty:
            df_ab["Category_Label"] = df_ab["Category"].apply(get_cat_name)
            cat_ab = (
                df_ab.groupby(["Brand", "Category_Label"])
                .size()
                .reset_index(name="건수")
            )
            tot_ab = cat_ab.groupby("Brand")["건수"].transform("sum")
            cat_ab["비중(%)"] = (cat_ab["건수"] / tot_ab * 100).round(1)

            fig_comp = px.bar(
                cat_ab,
                x="Category_Label",
                y="비중(%)",
                color="Brand",
                barmode="group",
                color_discrete_sequence=["#1f77b4", "#ff7f0e"],
                labels={
                    "Category_Label": txt("filter_cat"),
                    "비중(%)": txt("ratio_unit"),
                },
            )
            fig_comp.update_layout(xaxis_tickangle=-30, margin=dict(t=20, b=20))
            st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown(f"#### {txt('rd_action_title')}")
        col_act_a, col_act_b = st.columns(2)
        with col_act_a:
            top_issue_a = df_a[df_a["Sentiment"] == "Negative"]["Category"].mode()
            act_cat_a = (
                top_issue_a.iloc[0] if not top_issue_a.empty else "배터리/전원"
            )
            rec_a = get_action_sol(act_cat_a)
            st.success(f"**[{brand_a}] {txt('core_weakness')}: {get_cat_name(act_cat_a)}**\n\n{txt('hw_fw_proposal')}\n- {rec_a}")

        with col_act_b:
            top_issue_b = df_b[df_b["Sentiment"] == "Negative"]["Category"].mode()
            act_cat_b = (
                top_issue_b.iloc[0] if not top_issue_b.empty else "배터리/전원"
            )
            rec_b = get_action_sol(act_cat_b)
            st.warning(f"**[{brand_b}] {txt('core_weakness')}: {get_cat_name(act_cat_b)}**\n\n{txt('hw_fw_proposal')}\n- {rec_b}")

# =============================================================
# TAB 3: 키워드 & 연관구
# =============================================================
with tab3:
    st.subheader(txt("t3_title"))
    col_t3_1, col_t3_2 = st.columns(2)
    neg_reviews = filtered_df[filtered_df["Sentiment"] == "Negative"][
        "Review"
    ].astype(str)
    stopwords = {
        "the", "and", "for", "with", "that", "this", "not", "but", "are",
        "was", "were", "remote", "control", "device", "tv", "app", "work",
        "works", "one", "all", "you", "can", "cant", "just", "very",
        "also", "from", "have", "리모컨", "작동", "사용", "제품", "진짜",
        "너무", "그냥", "다시", "ha", "va", "cua", "cho", "duoc",
        "thi", "khong", "cua", "la", "tai", "được", "không", "có",
        "การ", "และ", "ของ", "ที่", "ไม่", "ได้", "ใช้", "กับ"
    }
    single_words, bigram_phrases = [], []
    
    word_pattern = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
    
    for rev in neg_reviews:
        tokens = [
            w for w in word_pattern.findall(rev.lower())
            if w not in stopwords and len(w) > 2
        ]
        single_words.extend(tokens)
        for i in range(len(tokens) - 1):
            bigram_phrases.append(f"{tokens[i]} {tokens[i+1]}")

    with col_t3_1:
        st.markdown(f"##### {txt('top_keywords')}")
        if single_words:
            df_words = pd.DataFrame(
                Counter(single_words).most_common(10),
                columns=["Keyword", "Frequency"],
            )
            fig_words = px.bar(
                df_words,
                x="Frequency",
                y="Keyword",
                orientation="h",
                color="Frequency",
                color_continuous_scale="Reds",
            )
            fig_words.update_layout(
                yaxis={"autorange": "reversed"},
                margin=dict(t=20, b=20, l=10, r=10),
            )
            st.plotly_chart(fig_words, use_container_width=True)

    with col_t3_2:
        st.markdown(f"##### {txt('top_bigrams')}")
        if bigram_phrases:
            df_bigrams = pd.DataFrame(
                Counter(bigram_phrases).most_common(10),
                columns=["Bigram", "Frequency"],
            )
            fig_bigrams = px.bar(
                df_bigrams,
                x="Frequency",
                y="Bigram",
                orientation="h",
                color="Frequency",
                color_continuous_scale="Oranges",
            )
            fig_bigrams.update_layout(
                yaxis={"autorange": "reversed"},
                margin=dict(t=20, b=20, l=10, r=10),
            )
            st.plotly_chart(fig_bigrams, use_container_width=True)

# =============================================================
# TAB 4: 원문 DB & 다운로드
# =============================================================
with tab4:
    st.subheader(txt("t4_title"))
    display_cols = [
        c
        for c in [
            "Device_Type", "Power_Type", "UI_Type", "Region", "Brand",
            "Category", "Sentiment", "Source", "Review", "Collected_Date",
        ]
        if c in filtered_df_raw.columns
    ]

    table_df = filtered_df_raw[display_cols].copy()
    if "Device_Type" in table_df.columns:
        table_df["Device_Type"] = table_df["Device_Type"].apply(get_dev_name)
    if "Power_Type" in table_df.columns:
        table_df["Power_Type"] = table_df["Power_Type"].apply(get_power_name)
    if "UI_Type" in table_df.columns:
        table_df["UI_Type"] = table_df["UI_Type"].apply(get_ui_name)
    if "Region" in table_df.columns:
        table_df["Region"] = table_df["Region"].apply(get_region_name)
    if "Category" in table_df.columns:
        table_df["Category"] = table_df["Category"].apply(get_cat_name)
    if "Sentiment" in table_df.columns:
        table_df["Sentiment"] = table_df["Sentiment"].apply(get_sentiment_name)

    table_df = table_df.rename(columns={c: get_col_name(c) for c in display_cols})

    st.dataframe(table_df, use_container_width=True, height=500)
    today_date = datetime.now().strftime("%Y%m%d")

    csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=txt("btn_csv_down"),
        data=csv_bytes,
        file_name=f"rcu_voc_{curr_lang}_{today_date}.csv",
        mime="text/csv",
    )

# =============================================================
# TAB 5: B2B 수주 Pitch & ROI 시뮬레이터
# =============================================================
with tab5:
    st.subheader(txt("t5_title"))
    st.caption(txt("t5_caption"))

    all_pitch_brands = sorted(list(filtered_df["Brand"].dropna().unique()))
    target_client = st.selectbox(
        txt("target_client_label"),
        all_pitch_brands,
        index=(
            all_pitch_brands.index("KT (지니TV)")
            if "KT (지니TV)" in all_pitch_brands
            else 0
        ),
        key="pitch_target_client_select",
    )
    st.divider()

    client_df = filtered_df[filtered_df["Brand"] == target_client]
    client_neg = client_df[client_df["Sentiment"] == "Negative"]

    if client_neg.empty:
        st.info(txt("no_neg_voc", client=target_client))
    else:
        client_cat_counts = client_neg[client_neg["Category"] != "기타/일반"]["Category"].value_counts()
        if client_cat_counts.empty:
            client_cat_counts = client_neg["Category"].value_counts()

        top_issues = client_cat_counts.head(2)
        primary_issue_raw = top_issues.index[0]
        secondary_issue_raw = (
            top_issues.index[1] if len(top_issues) > 1 else None
        )

        primary_issue = get_cat_name(primary_issue_raw)
        secondary_issue = (
            get_cat_name(secondary_issue_raw) if secondary_issue_raw else None
        )

        col_p1, col_p2 = st.columns([1, 1.4])
        with col_p1:
            st.markdown(f"#### {txt('pain_point_title', client=target_client)}")
            st.error(
                f"**{txt('rank1_defect')}:** {primary_issue} ({txt('complaints_cnt', cnt=top_issues.iloc[0])})"
            )
            if secondary_issue:
                st.warning(
                    f"**{txt('rank2_defect')}:** {secondary_issue} ({txt('complaints_cnt', cnt=top_issues.iloc[1])})"
                )

            st.markdown(f"{txt('sample_reviews_title')}")
            valid_reviews = client_neg[
                ~client_neg["Review"].astype(str).str.contains(NOISE_FILTER_REGEX)
            ]["Review"]
            if valid_reviews.empty:
                valid_reviews = client_neg["Review"]
            sample_reviews = valid_reviews.dropna().head(3).tolist()
            for r in sample_reviews:
                st.caption(f"- {r}")

        with col_p2:
            st.markdown(f"#### {txt('rd_solution_title')}")
            sol_1 = get_action_sol(primary_issue_raw)
            st.success(f"✔️ **{txt('counter_sol', cat=primary_issue)}**\n\n{sol_1}")
            sol_2 = ""
            if secondary_issue_raw:
                sol_2 = get_action_sol(secondary_issue_raw)
                st.info(f"✔️ **{txt('counter_sol', cat=secondary_issue)}**\n\n{sol_2}")

        st.write("")
        st.markdown("---")
        st.markdown(f"#### {txt('pitch_title')}")

        dev_type = get_dev_name(
            BRAND_DIRECTORY.get(target_client, {}).get("type", "디바이스")
        )

        pitch_templates = {
            "ko": (
                f"현재 {target_client} 가입자들이 가장 큰 불편을 호소하고 있는"
                f" '{primary_issue}' 결함을 당사의 {dev_type} 특화 차세대 아키텍처로"
                " 완벽하게 해결하겠습니다. 단순한 납품 단가 절감이 아닌, 반품 및 CS"
                f" 콜센터 인입률을 원천 차단하여 {target_client}의 브랜드 신뢰도 제고와"
                " 운영 비용(OPEX)의 획기적 절감을 제안합니다."
            ),
            "en": (
                f"We will resolve the critical '{primary_issue}' defect"
                f" reported by {target_client} users with our next-generation"
                f" architecture tailored for {dev_type}. Beyond unit cost"
                " reductions, we propose eliminating return rates and customer"
                " support calls at the root, enhancing brand trust and"
                " drastically reducing OPEX."
            ),
            "zh": (
                f"我们将通过专为 {dev_type} 定制的下一代高可靠架构，彻底解决"
                f" {target_client} 用户当前反馈最强烈的 '{primary_issue}'"
                " 缺陷。不仅仅是降低元器件采购成本，更能从源头杜绝退货与售后呼叫中心成本，提升品牌美誉度并大幅降低运营支出"
                " (OPEX)。"
            ),
            "vi": (
                f"Chúng tôi sẽ giải quyết dứt điểm lỗi '{primary_issue}' mà"
                f" người dùng {target_client} đang phàn nàn nhiều nhất bằng kiến"
                f" trúc thế hệ mới dành riêng cho {dev_type}. Không chỉ giảm"
                " giá thành linh kiện, chúng tôi cam kết loại bỏ tỷ lệ đổi trả"
                " và cuộc gọi hỗ trợ kỹ thuật, nâng cao uy tín thương hiệu và"
                " tiết kiệm chi phí vận hành (OPEX)."
            ),
            "th": (
                f"เราพร้อมแก้ไขปัญหา '{primary_issue}' ที่ผู้ใช้งาน"
                f" {target_client} ร้องเรียนมากที่สุดด้วยสถาปัตยกรรมรุ่นใหม่ที่ออกแบบมาโดยเฉพาะสำหรับ"
                f" {dev_type} นอกเหนือจากการลดต้นทุนชิ้นส่วนแล้ว"
                " เรายังช่วยลดอัตราการเคลมสินค้าและภาระศูนย์บริการลูกค้าได้อย่างสิ้นเชิง"
                " เสริมสร้างความเชื่อมั่นต่อแบรนด์และลดค่าใช้จ่ายในการดำเนินงาน"
                " (OPEX) อย่างยั่งยืน"
            ),
        }
        final_pitch = pitch_templates.get(curr_lang, pitch_templates["en"])

        st.markdown(
            f"""
            <div style="background-color: #f8f9fa; padding: 22px; border-radius: 10px; border-left: 6px solid #1f77b4; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <span style="font-size: 0.9em; font-weight: bold; color: #1f77b4; text-transform: uppercase;">Executive Pitch for {target_client} ({curr_lang.upper()})</span>
                <p style="font-size: 1.15em; line-height: 1.65; color: #212529; margin-top: 8px; font-weight: 500;">
                    "{final_pitch}"
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ROI & OPEX 절감 시뮬레이터
        st.write("")
        st.markdown("---")
        st.markdown(f"#### {txt('sim_title', client=target_client)}")
        st.caption(txt("sim_caption"))

        with st.expander(txt("sim_expander"), expanded=True):
            col_sim1, col_sim2, col_sim3 = st.columns(3)
            with col_sim1:
                sub_count = st.number_input(
                    txt("sim_sub_count"),
                    min_value=0,
                    max_value=50000000,
                    value=1000000,
                    step=10000,
                    key="sim_sub_count"
                )
                reduction_rate = st.slider(
                    txt("sim_reduction_rate"),
                    min_value=0,
                    max_value=100,
                    value=65,
                    step=5,
                    key="sim_reduction_rate",
                    help=txt("sim_reduction_help")
                )

            with col_sim2:
                cs_rate = st.number_input(
                    txt("sim_cs_rate"),
                    min_value=0.0,
                    max_value=100.0,
                    value=4.5,
                    step=0.1,
                    key="sim_cs_rate"
                )
                cs_cost = st.number_input(
                    txt("sim_cs_cost"),
                    min_value=0.0,
                    max_value=5000.0,
                    value=4.5,
                    step=0.5,
                    key="sim_cs_cost"
                )

            with col_sim3:
                return_rate = st.number_input(
                    txt("sim_return_rate"),
                    min_value=0.0,
                    max_value=100.0,
                    value=1.2,
                    step=0.1,
                    key="sim_return_rate"
                )
                return_cost = st.number_input(
                    txt("sim_return_cost"),
                    min_value=0.0,
                    max_value=5000.0,
                    value=8.0,
                    step=0.5,
                    key="sim_return_cost"
                )

        base_cs_calls = sub_count * (cs_rate / 100.0)
        saved_cs_calls = int(base_cs_calls * (reduction_rate / 100.0))
        saved_cs_cost = saved_cs_calls * cs_cost

        base_returns = sub_count * (return_rate / 100.0)
        saved_returns = int(base_returns * (reduction_rate / 100.0))
        saved_return_cost = saved_returns * return_cost

        saved_total_cost = saved_cs_cost + saved_return_cost

        roi_data_dict = {
            "sub_count": sub_count,
            "cs_rate": cs_rate,
            "cs_cost": cs_cost,
            "return_rate": return_rate,
            "return_cost": return_cost,
            "reduction_rate": reduction_rate,
            "saved_cs_calls": saved_cs_calls,
            "saved_cs_cost": saved_cs_cost,
            "saved_returns": saved_returns,
            "saved_return_cost": saved_return_cost,
            "saved_total_cost": saved_total_cost,
        }

        if curr_lang == "ko":
            cost_delta = f"약 {(saved_total_cost * 1350.0) / 100000000.0:,.1f}억 원 / 년"
            cs_delta = f"-{reduction_rate}% 감축"
            return_delta = f"-{reduction_rate}% 반품 절감"
        elif curr_lang == "zh":
            cost_delta = f"约 {saved_total_cost * 7.2 / 10000:,.1f}万 人民币 / 年"
            cs_delta = f"-{reduction_rate}% 减少"
            return_delta = f"-{reduction_rate}% 换货削减"
        else:
            cost_delta = f"~${saved_total_cost/1000000:,.2f}M / Year" if saved_total_cost >= 1000000 else f"~${saved_total_cost:,.0f} / Year"
            cs_delta = f"-{reduction_rate}% Reduction"
            return_delta = f"-{reduction_rate}% Reduced Swaps"

        col_roi1, col_roi2, col_roi3 = st.columns(3)
        col_roi1.metric(
            txt("sim_kpi_total"),
            f"${saved_total_cost:,.0f}",
            delta=cost_delta,
        )
        col_roi2.metric(
            txt("sim_kpi_cs"),
            f"{saved_cs_calls:,} {txt('sim_unit_calls')}",
            delta=cs_delta,
        )
        col_roi3.metric(
            txt("sim_kpi_return"),
            f"{saved_returns:,} {txt('sim_unit_devices')}",
            delta=return_delta,
        )

        st.write("")
        st.markdown("---")

        # Gemini AI VoC 심층 진단 & 결함 원인(Root Cause) 섹션
        st.subheader(txt("ai_section_title"))
        ai_session_key = f"ai_insight_{target_client}_{curr_lang}"

        active_api_key = st.session_state.get(
            "gemini_api_key",
            get_secret_api_key()
        )

        col_ai_btn, col_ai_info = st.columns([1, 2.5])
        with col_ai_btn:
            trigger_ai = st.button(txt("ai_btn"), type="primary", key="btn_trigger_gemini_ai")

        if trigger_ai:
            if not active_api_key:
                st.warning(txt("ai_key_missing"))
            else:
                with st.spinner(txt("ai_loading")):
                    ai_result = analyze_voc_with_gemini(
                        active_api_key,
                        target_client,
                        primary_issue,
                        secondary_issue,
                        sample_reviews,
                        lang=curr_lang
                    )
                    st.session_state[ai_session_key] = ai_result

        current_ai_text = st.session_state.get(ai_session_key, None)
        if current_ai_text:
            st.markdown(
                """
                <div style="background-color: #f0f7ff; padding: 24px; border-radius: 12px; border: 1.5px solid #90caf9; margin-top: 15px; margin-bottom: 20px;">
                """,
                unsafe_allow_html=True
            )
            st.markdown(current_ai_text)
            st.markdown("</div>", unsafe_allow_html=True)

        st.write("")
        ppt_file = create_pptx_deck(
            target_client,
            primary_issue,
            secondary_issue,
            sol_1,
            sol_2,
            final_pitch,
            sample_reviews,
            cat_counts=client_cat_counts,
            ai_analysis=current_ai_text,
            roi_data=roi_data_dict,
            lang=curr_lang,
        )
        st.download_button(
            label=txt("btn_pptx_down_v4", client=target_client),
            data=ppt_file,
            file_name=f"B2B_Pitch_{target_client.replace('/', '_')}_{curr_lang}_v4.0_{today_date}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key="btn_download_pptx_report",
        )