from collections import Counter
from datetime import datetime, timedelta
import hashlib
import os
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------------
# 0. 기본 설정 & 사내 보안 게이트 (암호: rcu2026!)
# -------------------------------------------------------------
st.set_page_config(
    page_title="Global RCU VOC Intelligence v2.3",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

RCU_PASSWORD = "rcu2026!"


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
    st.title("🔒 Global RCU VOC Intelligence v2.3")
    st.markdown("##### 글로벌 60개사 RCU 인텔리전스 & B2B 수주 시스템")
    st.info("인가된 사내 실원 전용 보안 화면입니다. 접속 암호를 입력하세요.")

    st.text_input(
        "접속 비밀번호 (Access Code)",
        type="password",
        on_change=password_entered,
        key="password_input",
        placeholder="비밀번호 입력 후 Enter를 누르세요",
    )

    if "password_correct" in st.session_state and not st.session_state.get(
        "password_correct"
    ):
      st.error("❌ 비밀번호가 올바르지 않습니다.")

  return False


if not check_password():
  st.stop()

if st.sidebar.button(
    "🚪 로그아웃", help="세션을 종료하고 로그인 화면으로 돌아갑니다."
):
  st.session_state["password_correct"] = False
  st.rerun()

# -------------------------------------------------------------
# 1. 60개 브랜드 디렉터리 & 폼팩터 매핑 테이블 (아프리카 추가)
# -------------------------------------------------------------
BRAND_DIRECTORY = {
    # [TV 제조사]
    "Samsung": {
        "region": "Korea",
        "type": "TV 제조사",
        "power": "솔라셀/C타입 충전식",
        "ui": "미니멀 물리키",
    },
    "LG Electronics": {
        "region": "Korea",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "자이로/에어마우스",
    },
    "Sony": {
        "region": "Japan",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "백라이트 물리키",
    },
    "Panasonic": {
        "region": "Japan",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "Sharp": {
        "region": "Japan",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "다버튼 핫키형",
    },
    "TCL": {
        "region": "Global",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Hisense": {
        "region": "Global",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Xiaomi": {
        "region": "ASIA",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "초미니멀 물리키",
    },
    "Vizio": {
        "region": "NA",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Philips": {
        "region": "EU",
        "type": "TV 제조사",
        "power": "건전지 교체형",
        "ui": "양면/특수 물리키",
    },
    # [스트리밍 / 스마트 미디어]
    "Apple": {
        "region": "Global",
        "type": "스트리밍/스마트 미디어",
        "power": "C타입 충전식",
        "ui": "터치 클릭패드",
    },
    "Amazon Fire TV": {
        "region": "Global",
        "type": "스트리밍/스마트 미디어",
        "power": "건전지 교체형",
        "ui": "백라이트 물리키",
    },
    "Google": {
        "region": "Global",
        "type": "스트리밍/스마트 미디어",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Roku": {
        "region": "NA",
        "type": "스트리밍/스마트 미디어",
        "power": "C타입 충전식",
        "ui": "이어폰잭/물리키",
    },
    "NVIDIA": {
        "region": "Global",
        "type": "스트리밍/스마트 미디어",
        "power": "건전지 교체형",
        "ui": "삼각기둥 백라이트",
    },
    "TiVo": {
        "region": "NA",
        "type": "스트리밍/스마트 미디어",
        "power": "건전지 교체형",
        "ui": "인체공학 피넛키",
    },
    "SofaBaton": {
        "region": "Global",
        "type": "스트리밍/스마트 미디어",
        "power": "C타입 충전식",
        "ui": "OLED스크린/휠",
    },
    # [방송통신사 (Telco/MSO) - 아프리카 3대사 포함]
    "Comcast": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "음성 특화 물리키",
    },
    "Charter": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "DirecTV": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "안드로이드 물리키",
    },
    "DISH Network": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "백라이트 물리키",
    },
    "Cox": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "음성 특화 물리키",
    },
    "Rogers": {
        "region": "NA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "음성 특화 물리키",
    },
    "Sky Group": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "터치/모션 백라이트",
    },
    "Vodafone": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "LGI (Virgin Media)": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "음성 특화 물리키",
    },
    "Canal+": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Orange": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Deutsche Telekom": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Telefonica": {
        "region": "EU",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "KT (지니TV)": {
        "region": "Korea",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "SKB (B tv)": {
        "region": "Korea",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "이어폰일체형 물리키",
    },
    "LGU+ (U+tv)": {
        "region": "Korea",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "이어폰일체형 물리키",
    },
    "MultiChoice (DStv)": {
        "region": "Africa",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "StarTimes": {
        "region": "Africa",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Canal+ Afrique": {
        "region": "Africa",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Tata Play": {
        "region": "ASIA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 핫키형",
    },
    "Airtel": {
        "region": "ASIA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "J:COM": {
        "region": "ASIA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "Hikari TV": {
        "region": "ASIA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 하이브리드",
    },
    "Foxtel": {
        "region": "ASIA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Claro": {
        "region": "SCA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    "Vrio Corp": {
        "region": "SCA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "다버튼 물리키",
    },
    "Televisa (izzi)": {
        "region": "SCA",
        "type": "방송통신사 (Telco/MSO)",
        "power": "건전지 교체형",
        "ui": "미니멀 물리키",
    },
    # [스마트홈 오토메이션]
    "Control4": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "터치스크린/물리키",
    },
    "Crestron": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "터치스크린/물리키",
    },
    "Savant": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "고해상도 터치스크린",
    },
    "Josh.ai": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "AI음성/물리키",
    },
    "URC": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "터치스크린/물리키",
    },
    "RTI": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "대화면 터치스크린",
    },
    "Nice (ELAN)": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "터치스크린/인터콤",
    },
    "Basalte": {
        "region": "EU",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "명품 금속 터치",
    },
    "Logitech": {
        "region": "Global",
        "type": "스마트홈 오토메이션",
        "power": "크래들 무선충전식",
        "ui": "터치스크린/물리키",
    },
    "ADT": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "보안 키패드",
    },
    "Vivint": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "스마트 패널",
    },
    "Resideo": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "보안 키패드",
    },
    "Loxone": {
        "region": "EU",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "5터치 포인트",
    },
    "Somfy": {
        "region": "EU",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "모터 제어 휠",
    },
    "Cync (GE)": {
        "region": "NA",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "조명 디밍 버튼",
    },
    "Tuya": {
        "region": "Global",
        "type": "스마트홈 오토메이션",
        "power": "건전지 교체형",
        "ui": "스마트 허브 연동",
    },
}

BRAND_ALIASES = {
    "amazon": "Amazon Fire TV",
    "amazon fire": "Amazon Fire TV",
    "fire tv": "Amazon Fire TV",
    "firetv": "Amazon Fire TV",
    "google tv": "Google",
    "chromecast": "Google",
    "comcast (xfinity)": "Comcast",
    "xfinity": "Comcast",
    "spectrum": "Charter",
    "charter (spectrum)": "Charter",
    "sky": "Sky Group",
    "sky q": "Sky Group",
    "sky glass": "Sky Group",
    "virgin media": "LGI (Virgin Media)",
    "lgi": "LGI (Virgin Media)",
    "liberty global": "LGI (Virgin Media)",
    "canal": "Canal+",
    "canal plus": "Canal+",
    "canal+": "Canal+",
    "dt": "Deutsche Telekom",
    "telekom": "Deutsche Telekom",
    "magentatv": "Deutsche Telekom",
    "vodafone tv": "Vodafone",
    "orange tv": "Orange",
    "livebox": "Orange",
    # 아프리카 얼라이언스
    "dstv": "MultiChoice (DStv)",
    "multichoice": "MultiChoice (DStv)",
    "startimes": "StarTimes",
    "star times": "StarTimes",
    "canal afrique": "Canal+ Afrique",
    "canal+ afrique": "Canal+ Afrique",
    "b tv": "SKB (B tv)",
    "skb": "SKB (B tv)",
    "sk broadband": "SKB (B tv)",
    "지니tv": "KT (지니TV)",
    "지니 tv": "KT (지니TV)",
    "kt": "KT (지니TV)",
    "u+tv": "LGU+ (U+tv)",
    "lgu+": "LGU+ (U+tv)",
    "lg uplus": "LGU+ (U+tv)",
    "lg": "LG Electronics",
    "lg elec": "LG Electronics",
    "samsung electronics": "Samsung",
    "bravia": "Sony",
    "sony bravia": "Sony",
    "panasonic viera": "Panasonic",
    "sharp aquos": "Sharp",
    "tcl tv": "TCL",
    "hisense tv": "Hisense",
    "control 4": "Control4",
    "josh": "Josh.ai",
    "josh ai": "Josh.ai",
    "elan": "Nice (ELAN)",
    "harmony": "Logitech",
    "ge cync": "Cync (GE)",
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
# 2. 지역별(Region) x 4대 영역 강자 (Top 3) 매트릭스 (한국 및 아프리카 포함)
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
        "방송통신사 (Telco/MSO)": [
            "MultiChoice (DStv)",
            "StarTimes",
            "Canal+ Afrique",
        ],
    },
}

KR_CHAMPIONS = sum(REGIONAL_TOP3["한국 (KR)"].values(), [])
NA_CHAMPIONS = sum(REGIONAL_TOP3["북미 (NA)"].values(), [])
EU_CHAMPIONS = sum(REGIONAL_TOP3["유럽 (EU)"].values(), [])
APAC_CHAMPIONS = sum(REGIONAL_TOP3["아시아-태평양 (APAC)"].values(), [])
AFRICA_CHAMPIONS = sum(REGIONAL_TOP3["아프리카 (Africa)"].values(), [])

# -------------------------------------------------------------
# 3. R&D 액션 아이템 & B2B 수주 Pitch 제안서 DB
# -------------------------------------------------------------
ACTION_RECOMMENDATIONS = {
    "볼륨/TV연동(CEC)": (
        "Dual-Path CEC/IR 하이브리드 엔진 적용 (CEC 미응답 시 0.05초 내 IR 자동"
        " 백업 송출) 및 아프리카/유럽/글로벌 로컬 AV 기기 12,000+ 클라우드 코드"
        " 매핑 DB 탑재"
    ),
    "페어링/연결 끊김": (
        "BLE 광고(Advertising) 인터벌 최적화, 순환정전(Load Shedding) 복구 시 자동"
        " 재연결 타임아웃 1.5초 이내 단축 및 99.9% 무중단 리트라이 알고리즘 개선"
    ),
    "속도/지연/먹통": (
        "RCU MCU 딥슬립 웨이크업 지연을 45ms 이하로 단축하고 OS단 키 입력 이벤트"
        " 버퍼 큐(Queue) 확장"
    ),
    "버튼/UI 제어 불량": (
        "100만 회 수명 보증 메탈 돔(Metal Dome) 스위치 적용, 모래먼지 방진"
        " 실링(Dust-proof Sealing) 및 35ms 하드웨어 디바운스 회로 튜닝"
    ),
    "신호범위/IR센서": (
        "IR LED 송출 지향각 광각화(Wide-angle Lens) 및 RF/BLE 송신 출력(Tx"
        " Power) +3dBm 부스팅 설계"
    ),
    "배터리/전원": (
        "저가 배터리 누액 방지용 안티-코로전(Anti-corrosion) 도금 단자 적용 및"
        " 스마트 센서 융합 백라이트 누수 차단 (배터리 수명 12개월 이상 보장)"
    ),
    "음성 인식/마이크": (
        "거실 TV 사운드 간섭을 90% 차단하는 마이크 독립 음향 챔버(Chamber) 설계"
        " 및 다국어 주변 소음 제거(ENC) 칩셋 탑재"
    ),
    "내구성/하드웨어 퀄리티": (
        "EU 친환경 규제 대응 PCR(재활용 수지) 85% 적용 충격 흡수 리브(Rib)"
        " 구조 보강 및 RCA 500회 내마모 UV 코팅 키캡 인쇄"
    ),
    "단순 앱/기능 불만": (
        "사용자 커스텀 리매핑(User Programmable Key) 지원 및 스마트 EPG 채널"
        " 탐색 제스처 UI/UX 탑재"
    ),
    "계정/업데이트/광고": (
        "원격 OTA 펌웨어 무중단 듀얼 뱅크(Dual-bank) 롤백 프로세스 구축으로 벽돌"
        " 현상 원천 방지"
    ),
}

VIP_PITCH_DB = {
    "Samsung": (
        "글로벌 1위 TV 리더십에 걸맞은 차세대 친환경 솔루션입니다. 솔라셀 충전 효율"
        " 30% 개선 및 미니멀 키 배열에서의 오입력을 방지하는 스마트 햅틱 피드백을"
        " 제안합니다."
    ),
    "LG Electronics": (
        "매직 리모컨 고유의 자이로 에어마우스 포인터 튐 현상을 억제하는 AI 모션"
        " 필터링 펌웨어와 100만 회 내마모 휠 엔코더 하드웨어를 제안합니다."
    ),
    "Apple": (
        "Siri Remote의 정밀 터치 클릭패드 스크롤 관성(Inertia)을 튜닝하고, 차가운"
        " 알루미늄 그립감을 보완하는 인체공학 에지 곡면 가공 아키텍처를"
        " 제안합니다."
    ),
    "Amazon Fire TV": (
        "Alexa Voice Remote Pro의 모션 백라이트 누설 전류를 70% 차단하여 건전지"
        " 수명을 1년 이상으로 연장하고, 주변 TV 노이즈 간섭을 제거한 빔포밍"
        " 마이크를 제안합니다."
    ),
    "Comcast": (
        "북미 최대 가입자 기반의 Xfinity Voice Remote 전원·볼륨 CEC 불일치를"
        " 0.05초 만에 IR로 보정하는 Dual-Path 엔진을 통해 CS 콜센터 인입률 30%"
        " 감축을 보장합니다."
    ),
    "Sky Group": (
        "Sky Glass / Sky Q의 프리미엄 유럽 표준에 맞춘 감성 모션 조명 제어와"
        " 다국적 홈시어터 환경에서의 초저지연 음성 탐색 최적화를 제안합니다."
    ),
    "Control4": (
        "Halo Touch 리모컨의 3.2인치 터치스크린 레이턴시를 45ms 이하로 단축하고,"
        " 절전 복귀 시 5GHz Wi-Fi 재연결 타임아웃을 1초대로 단축하는 고신뢰성"
        " 칩셋을 제안합니다."
    ),
    "Crestron": (
        "초고가 럭셔리 주거 환경에 걸맞은 TSR-310 전용 초저전력 무선 게이트웨이"
        " 프로토콜 튜닝 및 크래들 접촉 무결성을 보장하는 무선 충전 모듈을"
        " 제안합니다."
    ),
    "LGI (Virgin Media)": (
        "LGI 가입자가 겪는 핵심 스트레스인 'TV 볼륨 싱크 불량(CEC)'과 '잦은"
        " 배터리 방전'을 지능형 RCU로 해결하여 셋톱 교체 없는 CS 콜센터 인입률"
        " 30% 감축을 약속합니다."
    ),
    "Canal+": (
        "프리미엄 4K UHD 콘텐츠에 부합하는 명품 마감과 영화 감상 몰입을 방해하지"
        " 않는 무소음(Whisper-quiet) 실리콘 댐퍼 버튼을 제안합니다."
    ),
    "Orange": (
        "Orange 2030 탄소중립에 부합하는 해양 폐플라스틱(PCR) 85% 적용 및 낙하"
        " 파손율 제로(Zero-Return)를 달성한 고강성 에코 모듈형 리모컨을"
        " 제안합니다."
    ),
    "Deutsche Telekom": (
        "MagentaTV의 방대한 EPG와 클라우드 스트리밍을 단 1프레임의 렉도 없이"
        " 탐색하는 초저지연(45ms) 안드로이드 TV 엔진을 제안합니다."
    ),
    "Vodafone": (
        "유럽 각국의 파편화된 중소 로컬 TV와 사운드바를 단 한 번의 페어링으로"
        " 완벽 제어하는 12,000+ 글로벌 AV 호환 DB 탑재형 RCU를 제안합니다."
    ),
    # [아프리카 3대사 VIP Pitch]
    "MultiChoice (DStv)": (
        "아프리카 전역의 잦은 순환정전(Load Shedding) 복구 시에도 페어링이 즉각"
        " 유지되는 비휘발성 NVM 메모리 펌웨어와 모래먼지 고착을 방지하는 실링"
        " 구조를 적용하여, CS 콜센터 인입률 35% 감축 및 가입자 이탈 방지를"
        " 보장합니다."
    ),
    "StarTimes": (
        "아프리카 현지의 고온다습 기후와 저품질 건전지 누액에 대응하는"
        " 안티-코로전(Anti-Corrosion) 특수 방청 도금 단자 및 초저전력(대기전류"
        " 3μA) 펌웨어를 적용하여, 현지 가입자에게 압도적인 배터리 수명과 가성비"
        " 신뢰성을 제공합니다."
    ),
    "Canal+ Afrique": (
        "프랑스어권 서아프리카 위성 방송 가입자를 위해 사막 모래먼지 유입을 100%"
        " 차단하는 방진 멤브레인 키패드와 아프리카 현지 구형 CRT/평판 TV 99%"
        " 호환성을 보장하는 고출력 IR/BLE 하이브리드 RCU를 제안합니다."
    ),
}

CATEGORY_META = {
    "볼륨/TV연동(CEC)": {
        "def": "TV 본체, 사운드바, 셋톱박스 간 HDMI-CEC 및 IR 코드 연동 이슈",
        "example": "사운드바 볼륨 조절 불가, 외부입력 전환 싱크 풀림",
    },
    "페어링/연결 끊김": {
        "def": "블루투스/RF/Wi-Fi 통신 연결 실패 및 간헐적 끊김 현상",
        "example": "절전 모드 후 재페어링 필요, 정전 후 연결 끊김",
    },
    "속도/지연/먹통": {
        "def": "버튼 입력 후 지연(인풋랙) 및 시스템 멈춤(Freezing)",
        "example": "1~2초 반응 딜레이, 연속 입력 시 먹통",
    },
    "버튼/UI 제어 불량": {
        "def": (
            "물리 키감, 중복 입력(채터링/더블클릭), 먼지 유입으로 인한 키 뻑뻑함"
        ),
        "example": "방향키 두 번 연속 입력, 모래먼지 끼임",
    },
    "신호범위/IR센서": {
        "def": "무선 신호 도달 거리 한계 및 송수신 지향각(각도) 제한",
        "example": "정면 조준 시에만 동작, 3m 이상 거리 인식 불가",
    },
    "배터리/전원": {
        "def": "배터리 누액 부식, 비정상적 방전 속도, 백라이트 누수",
        "example": "단자 부식 방전, 새 배터리 2주 만에 방전",
    },
    "음성 인식/마이크": {
        "def": "음성 인식률 저하 및 마이크 센서 소음 간섭",
        "example": "음성 호출 실패, TV 사운드 오인식",
    },
    "계정/업데이트/광고": {
        "def": "펌웨어 업데이트 오류, 계정 연동 강제, UI 내 광고 거부감",
        "example": "업데이트 중 벽돌 현상, 강제 로그인 요구",
    },
    "내구성/하드웨어 퀄리티": {
        "def": "케이스 마감, 낙하 파손, 버튼 인쇄 지워짐, 하우징 유격",
        "example": "가벼운 낙하에 배터리 커버 파손, 키 각인 마모",
    },
    "단순 앱/기능 불만": {
        "def": "전용 핫키 커스텀 불가 및 OS 기능 정책 불만",
        "example": "원치 않는 앱 바로가기 오작동, 리모컨 찾기 비프음 미달",
    },
    "기타/일반": {
        "def": "단순 불만 표현, 배송/패키징 등 전반적인 만족도 이슈",
        "example": "전반적인 품질 실망, 포장 파손",
    },
}


def refine_category(text):
  t = str(text).lower()
  if any(
      w in t
      for w in [
          "pair",
          "connect",
          "bluetooth",
          "wifi",
          "offline",
          "drop",
          "disconnect",
          "sync",
          "unpair",
          "network",
          "link",
          "lost",
          "load shedding",
          "synchro",
          "verbindung",
          "페어링",
          "연결",
      ]
  ):
    return "페어링/연결 끊김"
  if any(
      w in t
      for w in [
          "lag",
          "slow",
          "freeze",
          "stuck",
          "delay",
          "unresponsive",
          "hang",
          "epg",
          "verzögerung",
          "langsam",
          "지연",
          "렉",
          "먹통",
          "느려",
          "멈춤",
      ]
  ):
    return "속도/지연/먹통"
  if any(
      w in t
      for w in [
          "volume",
          "mute",
          "cec",
          "hdmi",
          "turn on",
          "turn off",
          "soundbar",
          "receiver",
          "tv",
          "power",
          "handshake",
          "lautstärke",
          "볼륨",
          "소리",
          "전원",
          "외부입력",
      ]
  ):
    return "볼륨/TV연동(CEC)"
  if any(
      w in t
      for w in [
          "range",
          "line of sight",
          "distance",
          "angle",
          "ir ",
          "signal",
          "sensor",
          "aim",
          "reichweite",
          "수신",
          "거리",
          "각도",
          "정면",
      ]
  ):
    return "신호범위/IR센서"
  if any(
      w in t
      for w in [
          "button",
          "layout",
          "press",
          "key",
          "touch",
          "click",
          "backlight",
          "ui",
          "screen",
          "dust",
          "sand",
          "stiff",
          "taste",
          "drücken",
          "bouton",
          "버튼",
          "키",
          "터치",
          "클릭",
          "더블클릭",
          "채터링",
          "백라이트",
      ]
  ):
    return "버튼/UI 제어 불량"
  if any(
      w in t
      for w in [
          "battery",
          "power",
          "charge",
          "drain",
          "solar",
          "recharge",
          "corrosion",
          "leak",
          "batterie",
          "akku",
          "pile",
          "배터리",
          "건전지",
          "충전",
          "방전",
          "광탈",
          "누액",
          "부식",
      ]
  ):
    return "배터리/전원"
  if any(
      w in t
      for w in [
          "voice",
          "mic",
          "alexa",
          "bixby",
          "siri",
          "assistant",
          "voix",
          "stimme",
          "음성",
          "마이크",
          "인식",
          "기가지니",
          "클로바",
      ]
  ):
    return "음성 인식/마이크"
  if any(
      w in t
      for w in [
          "cheap",
          "plastic",
          "break",
          "broke",
          "drop",
          "fall",
          "durability",
          "cassé",
          "kaputt",
          "깨짐",
          "파손",
          "마감",
          "부러",
          "내구성",
      ]
  ):
    return "내구성/하드웨어 퀄리티"
  if any(
      w in t
      for w in [
          "login",
          "sign in",
          "account",
          "update",
          "ad ",
          "mise à jour",
          "업데이트",
          "계정",
          "광고",
      ]
  ):
    return "계정/업데이트/광고"
  if any(
      w in t
      for w in [
          "app",
          "hotkey",
          "shortcut",
          "finder",
          "raccourci",
          "핫키",
          "바로가기",
          "찾기",
          "비프음",
      ]
  ):
    return "단순 앱/기능 불만"
  return "기타/일반"


# -------------------------------------------------------------
# 4. 데이터 로드 및 전처리 (노이즈 자동 차단 가드레일 탑재)
# -------------------------------------------------------------
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
  if not os.path.exists("voc_db.csv"):
    try:
      from collector2 import collect_advanced_voc

      collect_advanced_voc()
    except Exception:
      pass

  if not os.path.exists("voc_db.csv"):
    return pd.DataFrame()

  try:
    df = pd.read_csv("voc_db.csv", encoding="utf-8-sig")
  except Exception:
    df = pd.read_csv("voc_db.csv", encoding="utf-8")

  if not df.empty:
    # [핵심 가드레일] 화면 로딩 시 회사 소개글/광고성/단순스펙 행 원천 차단
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
      df["Parsed_Date"] = pd.to_datetime(
          df["Collected_Date"].str.slice(0, 10), errors="coerce"
      )
      df["Parsed_Date"] = df["Parsed_Date"].fillna(pd.Timestamp.now())
    else:
      df["Parsed_Date"] = pd.Timestamp.now()

  return df


df = load_accumulated_data()

if df.empty:
  st.warning(
      "⚠️ 'voc_db.csv' 파일이 비어 있거나 모든 데이터가 노이즈 필터링되었습니다."
  )
  st.stop()

# -------------------------------------------------------------
# 5. 사이드바 다차원 필터 패널 (한국 및 아프리카 포함 프리셋)
# -------------------------------------------------------------
st.sidebar.header("🔍 통합 필터 패널")

if st.sidebar.button("🔄 최신 수집 & 분류 동기화"):
  st.cache_data.clear()
  try:
    from collector2 import collect_advanced_voc

    collect_advanced_voc()
  except Exception:
    pass
  st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### ⚡ 지역별 핵심 강자 (Top 3) 프리셋")

all_unique_brands = sorted(list(df["Brand"].unique()))
if "selected_brand_list" not in st.session_state:
  st.session_state["selected_brand_list"] = all_unique_brands

# 권역별 원클릭 버튼 그리드
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
  if st.button("🇰🇷 한국 (5개사)", help="국내 TV 양사 및 통신 3사 일괄 선택"):
    st.session_state["selected_brand_list"] = [
        b for b in KR_CHAMPIONS if b in all_unique_brands
    ]
    st.rerun()
  if st.button("🇺🇸 북미 (12개사)", help="북미 4대 영역별 Top 3 (총 12개사)"):
    st.session_state["selected_brand_list"] = [
        b for b in NA_CHAMPIONS if b in all_unique_brands
    ]
    st.rerun()
  if st.button(
      "🌍 아프리카 (6개사)", help="아프리카 3대 Pay-TV 및 주요 TV (총 6개사)"
  ):
    st.session_state["selected_brand_list"] = [
        b for b in AFRICA_CHAMPIONS if b in all_unique_brands
    ]
    st.rerun()

with col_btn2:
  if st.button("🇪🇺 유럽 (12개사)", help="유럽 4대 영역별 Top 3 (총 12개사)"):
    st.session_state["selected_brand_list"] = [
        b for b in EU_CHAMPIONS if b in all_unique_brands
    ]
    st.rerun()
  if st.button(
      "🌏 아태 (12개사)", help="일본·인도 등 APAC 4대 영역별 Top 3 (총 12개사)"
  ):
    st.session_state["selected_brand_list"] = [
        b for b in APAC_CHAMPIONS if b in all_unique_brands
    ]
    st.rerun()
  if st.button("🔄 전체 60개사", help="모든 브랜드 필터 복원"):
    st.session_state["selected_brand_list"] = all_unique_brands
    st.rerun()

# 세부 핀포인트 선택 콤보박스 (각 영역 Top 3)
detail_presets = {
    "선택 안 함 (전체 유지)": None,
    "🇰🇷 한국 TV (Samsung, LG)": REGIONAL_TOP3["한국 (KR)"]["TV 제조사"],
    "🇰🇷 한국 통신 3사 (KT, SKB, LGU+)": REGIONAL_TOP3["한국 (KR)"][
        "방송통신사 (Telco/MSO)"
    ],
    "🇺🇸 북미 TV Top 3 (Samsung, Vizio, TCL)": REGIONAL_TOP3["북미 (NA)"][
        "TV 제조사"
    ],
    "🇺🇸 북미 스트리밍 Top 3 (Roku, Amazon, Apple)": REGIONAL_TOP3["북미 (NA)"][
        "스트리밍/스마트 미디어"
    ],
    "🇺🇸 북미 통신사 Top 3 (Comcast, Charter, DirecTV)": REGIONAL_TOP3[
        "북미 (NA)"
    ]["방송통신사 (Telco/MSO)"],
    "🇺🇸 북미 스마트홈 Top 3 (Control4, Crestron, Savant)": REGIONAL_TOP3[
        "북미 (NA)"
    ]["스마트홈 오토메이션"],
    "🇪🇺 유럽 TV Top 3 (Samsung, Philips, LG)": REGIONAL_TOP3["유럽 (EU)"][
        "TV 제조사"
    ],
    "🇪🇺 유럽 스트리밍 Top 3 (Amazon, Apple, Google)": REGIONAL_TOP3["유럽 (EU)"][
        "스트리밍/스마트 미디어"
    ],
    "🇪🇺 유럽 통신사 Top 3 (Sky Group, Vodafone, Orange)": REGIONAL_TOP3[
        "유럽 (EU)"
    ]["방송통신사 (Telco/MSO)"],
    "🇪🇺 유럽 스마트홈 Top 3 (Somfy, Loxone, Basalte)": REGIONAL_TOP3[
        "유럽 (EU)"
    ]["스마트홈 오토메이션"],
    "🌏 아태 TV Top 3 (Sony, Panasonic, Sharp)": REGIONAL_TOP3[
        "아시아-태평양 (APAC)"
    ]["TV 제조사"],
    "🌏 아태 스트리밍 Top 3 (Google, Xiaomi, Apple)": REGIONAL_TOP3[
        "아시아-태평양 (APAC)"
    ]["스트리밍/스마트 미디어"],
    "🌏 아태 통신사 Top 3 (Tata Play, Airtel, J:COM)": REGIONAL_TOP3[
        "아시아-태평양 (APAC)"
    ]["방송통신사 (Telco/MSO)"],
    "🌏 아태 스마트홈 Top 3 (Tuya, SofaBaton, Logitech)": REGIONAL_TOP3[
        "아시아-태평양 (APAC)"
    ]["스마트홈 오토메이션"],
    "🌍 아프리카 TV (Samsung, Hisense, LG)": REGIONAL_TOP3[
        "아프리카 (Africa)"
    ]["TV 제조사"],
    "🌍 아프리카 통신사 (DStv, StarTimes, Canal+)": REGIONAL_TOP3[
        "아프리카 (Africa)"
    ]["방송통신사 (Telco/MSO)"],
}

st.sidebar.caption("📍 특정 지역의 특정 영역만 핀포인트 선택:")
sub_col1, sub_col2 = st.sidebar.columns([3, 1])
target_sub = sub_col1.selectbox(
    "세부 강자 선택",
    options=list(detail_presets.keys()),
    label_visibility="collapsed",
)
if sub_col2.button("적용"):
  if detail_presets[target_sub]:
    st.session_state["selected_brand_list"] = [
        b for b in detail_presets[target_sub] if b in all_unique_brands
    ]
  else:
    st.session_state["selected_brand_list"] = all_unique_brands
  st.rerun()

st.sidebar.markdown("---")

device_types = sorted(list(df["Device_Type"].dropna().unique()))
selected_types = st.sidebar.multiselect(
    "기기 분류 (Device Type)", options=device_types, default=device_types
)

brand_subset = df[df["Device_Type"].isin(selected_types)]["Brand"].unique()
available_brands = sorted(list(brand_subset))

valid_defaults = [
    b for b in st.session_state["selected_brand_list"] if b in available_brands
]
if not valid_defaults:
  valid_defaults = available_brands

selected_brands = st.sidebar.multiselect(
    "브랜드 선택", options=available_brands, default=valid_defaults
)

with st.sidebar.expander("⚙️ 하드웨어 폼팩터 세부 필터", expanded=False):
  all_powers = sorted(list(df["Power_Type"].unique()))
  sel_powers = st.multiselect("전원 방식", all_powers, default=all_powers)

  all_uis = sorted(list(df["UI_Type"].unique()))
  sel_uis = st.multiselect("입력 인터페이스", all_uis, default=all_uis)

selected_regions = st.sidebar.multiselect(
    "VOC 발생 권역 (Region)",
    options=sorted(df["Region"].unique()),
    default=sorted(df["Region"].unique()),
)

selected_cats = st.sidebar.multiselect(
    "이슈 카테고리",
    options=sorted(df["Category"].unique()),
    default=sorted(df["Category"].unique()),
)

search_keyword = st.sidebar.text_input(
    "💬 본문 키워드 검색",
    placeholder="예: 터치, 페어링, CEC, 배터리, load shedding",
)

# 필터링 적용
filtered_df = df[
    (df["Device_Type"].isin(selected_types))
    & (df["Brand"].isin(selected_brands))
    & (df["Power_Type"].isin(sel_powers))
    & (df["UI_Type"].isin(sel_uis))
    & (df["Region"].isin(selected_regions))
    & (df["Category"].isin(selected_cats))
]

if search_keyword.strip():
  filtered_df = filtered_df[
      filtered_df["Review"]
      .astype(str)
      .str.contains(search_keyword.strip(), case=False, na=False)
  ]

# -------------------------------------------------------------
# 6. 상단 헤더 & 알림 배너
# -------------------------------------------------------------
st.title("📺 글로벌 RCU 고객 VOC 인텔리전스 대시보드 v2.3")
st.caption(
    "글로벌 60개사 (TV OEM · OTT 스트리밍 · 글로벌 Telco/MSO · 스마트홈"
    " 오토메이션) 통합 분석 & B2B 수주 시스템"
)

if not filtered_df.empty:
  neg_only = filtered_df[filtered_df["Sentiment"] == "Negative"]
  top_3_cats = neg_only["Category"].value_counts().head(3)
  top_cat_names = [f"**{i+1}위** {cat}" for i, cat in enumerate(top_3_cats.index)]

  brand_neg_stats = (
      filtered_df.groupby("Brand")
      .apply(lambda x: (x["Sentiment"] == "Negative").mean())
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
        f"🚨 **핵심 고객 불만 TOP 3:** "
        f"{' | '.join(top_cat_names) if top_cat_names else '데이터 없음'}"
    )
  with b2:
    st.warning(
        f"⚠️ **부정 VOC 집중 모니터링:** "
        f"**{highest_neg_brand}** (불만율 {highest_neg_val})"
    )

st.divider()

# -------------------------------------------------------------
# 7. 5대 탭(Tab) 화면 분할 구조
# -------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 종합 모니터링 & 트렌드",
    "⚔️ 브랜드 1:1 벤치마크 & R&D 액션",
    "🔍 이슈 & 키워드/연관구 심층 분석",
    "📋 원문 DB 및 리포트 다운로드",
    "💼 B2B 수주 & 임원 보고용 Pitch",
])

# =============================================================
# TAB 1: 종합 모니터링 & 시계열 트렌드
# =============================================================
with tab1:
  total_cnt = len(filtered_df)
  neg_cnt = len(filtered_df[filtered_df["Sentiment"] == "Negative"])
  neg_ratio = (neg_cnt / total_cnt * 100) if total_cnt > 0 else 0
  top_cat_mode = filtered_df["Category"].mode()
  top_cat = top_cat_mode.iloc[0] if not top_cat_mode.empty else "-"

  m1, m2, m3, m4 = st.columns(4)
  m1.metric("분석 VOC 총 건수", f"{total_cnt:,}건")
  m2.metric(
      "전체 불만(부정) 비율",
      f"{neg_ratio:.1f}%",
      delta=f"{neg_cnt:,}건",
      delta_color="inverse",
  )
  m3.metric("최다 발생 이슈", top_cat)
  m4.metric("분석 브랜드 수", f"{filtered_df['Brand'].nunique()}개사")

  st.write("")

  col_t1, col_t2 = st.columns(2)
  with col_t1:
    st.subheader("📊 정밀 이슈 카테고리 분포")
    if not filtered_df.empty:
      cat_counts = filtered_df["Category"].value_counts().reset_index()
      cat_counts.columns = ["Category", "Count"]
      cat_counts["Def"] = cat_counts["Category"].map(
          lambda x: CATEGORY_META.get(x, {}).get("def", "정의 정보 없음")
      )
      cat_counts["Example"] = cat_counts["Category"].map(
          lambda x: CATEGORY_META.get(x, {}).get("example", "사례 정보 없음")
      )
      cat_counts["Tooltip"] = cat_counts.apply(
          lambda r: (
              f"📌 <b>정의:</b> {r['Def']}<br>💬 <b>주요 사례:</b> {r['Example']}"
          ),
          axis=1,
      )

      fig1 = go.Figure(
          data=[
              go.Pie(
                  labels=cat_counts["Category"],
                  values=cat_counts["Count"],
                  hole=0.4,
                  customdata=cat_counts["Tooltip"],
                  hovertemplate=(
                      "<b>%{label}</b><br>비중: <b>%{percent}</b>"
                      " (%{value:,}건)<br><br>%{customdata}<extra></extra>"
                  ),
                  textinfo="percent",
                  marker=dict(colors=px.colors.qualitative.Set3),
              )
          ]
      )
      fig1.update_layout(
          margin=dict(t=20, b=20, l=10, r=10),
          legend=dict(orientation="v", x=1.05, y=0.5, font=dict(size=11)),
      )
      st.plotly_chart(fig1, use_container_width=True)

  with col_t2:
    st.subheader("🌐 4대 기기 분류(Device Type)별 불만 분포")
    if not filtered_df.empty:
      dev_cat = (
          filtered_df.groupby(["Device_Type", "Category"])
          .size()
          .reset_index(name="건수")
      )
      dev_tot = dev_cat.groupby("Device_Type")["건수"].transform("sum")
      dev_cat["비중(%)"] = (dev_cat["건수"] / dev_tot * 100).round(1)

      fig2 = px.bar(
          dev_cat,
          x="Device_Type",
          y="건수",
          color="Category",
          barmode="stack",
          color_discrete_sequence=px.colors.qualitative.Set3,
          hover_data={"건수": ":,d", "비중(%)": ":.1f%"},
      )
      fig2.update_layout(margin=dict(t=20, b=20, l=10, r=10))
      st.plotly_chart(fig2, use_container_width=True)

  st.write("")
  st.subheader("📈 주간별 VOC 발생 추이 및 이슈 모니터링")
  if not filtered_df.empty:
    trend_df = filtered_df.copy()
    trend_df["YearWeek"] = trend_df["Parsed_Date"].dt.strftime("%Y-W%W")
    weekly_trend = (
        trend_df.groupby(["YearWeek", "Category"])
        .size()
        .reset_index(name="건수")
    )

    fig_trend = px.line(
        weekly_trend,
        x="YearWeek",
        y="건수",
        color="Category",
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig_trend.update_layout(
        xaxis_title="수집 주차 (Year-Week)",
        yaxis_title="발생 건수",
        margin=dict(t=20, b=20, l=10, r=10),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# =============================================================
# TAB 2: 브랜드 1:1 벤치마크 & R&D 액션 아이템
# =============================================================
with tab2:
  st.subheader("⚔️ 글로벌 브랜드 맞춤 1:1 비교 벤치마크")
  st.caption(
      "경쟁사 대비 특정 브랜드의 불만 격차를 대조하고, R&D 개선 액션 아이템을"
      " 도출합니다."
  )

  all_b = sorted(list(df["Brand"].dropna().unique()))
  if len(all_b) >= 2:
    c_b1, c_b2 = st.columns(2)
    with c_b1:
      brand_a = st.selectbox(
          "비교 기준 브랜드 (Brand A)",
          all_b,
          index=all_b.index("Samsung") if "Samsung" in all_b else 0,
      )
    with c_b2:
      cand_b = [b for b in all_b if b != brand_a]
      brand_b = st.selectbox(
          "비교 대상 브랜드 (Brand B)",
          cand_b,
          index=(
              cand_b.index("MultiChoice (DStv)")
              if "MultiChoice (DStv)" in cand_b
              else 0
          ),
      )

    df_a, df_b = df[df["Brand"] == brand_a], df[df["Brand"] == brand_b]
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
    k1.metric(f"[{brand_a}] 분석 건수", f"{a_cnt:,}건")
    k2.metric(f"[{brand_a}] 불만 비율", f"{a_neg_rate:.1f}%")
    km.markdown(
        "<h3 style='text-align: center; color: gray;'>VS</h3>",
        unsafe_allow_html=True,
    )
    k3.metric(f"[{brand_b}] 분석 건수", f"{b_cnt:,}건")
    k4.metric(
        f"[{brand_b}] 불만 비율",
        f"{b_neg_rate:.1f}%",
        delta=f"{b_neg_rate - a_neg_rate:+.1f}%p",
        delta_color="inverse",
    )

    df_ab = df[df["Brand"].isin([brand_a, brand_b])]
    if not df_ab.empty:
      cat_ab = (
          df_ab.groupby(["Brand", "Category"]).size().reset_index(name="건수")
      )
      tot_ab = cat_ab.groupby("Brand")["건수"].transform("sum")
      cat_ab["비중(%)"] = (cat_ab["건수"] / tot_ab * 100).round(1)

      fig_comp = px.bar(
          cat_ab,
          x="Category",
          y="비중(%)",
          color="Brand",
          barmode="group",
          title=f"📊 [{brand_a}] vs [{brand_b}] 카테고리별 불만 비중(%) 비교",
          color_discrete_sequence=["#1f77b4", "#ff7f0e"],
          hover_data={"비중(%)": ":.1f%", "건수": ":,d"},
      )
      fig_comp.update_layout(xaxis_tickangle=-30, margin=dict(t=40, b=20))
      st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("#### 💡 R&D 개발 / 기획팀 우선 개선 권고안 (Action Items)")
    col_act_a, col_act_b = st.columns(2)

    with col_act_a:
      top_issue_a = (
          df_a[df_a["Sentiment"] == "Negative"]["Category"].mode()
      )
      act_cat_a = top_issue_a.iloc[0] if not top_issue_a.empty else "기타/일반"
      rec_a = ACTION_RECOMMENDATIONS.get(
          act_cat_a, "품질 신뢰성 지속 모니터링 필요"
      )
      st.success(
          f"**[{brand_a}] 핵심 취약점: {act_cat_a}**\n\n📌 **차기 하드웨어/FW"
          f" 개선 제언:**\n- {rec_a}"
      )

    with col_act_b:
      top_issue_b = (
          df_b[df_b["Sentiment"] == "Negative"]["Category"].mode()
      )
      act_cat_b = top_issue_b.iloc[0] if not top_issue_b.empty else "기타/일반"
      rec_b = ACTION_RECOMMENDATIONS.get(
          act_cat_b, "품질 신뢰성 지속 모니터링 필요"
      )
      st.warning(
          f"**[{brand_b}] 핵심 취약점: {act_cat_b}**\n\n📌 **차기 하드웨어/FW"
          f" 개선 제언:**\n- {rec_b}"
      )

    st.write("")
    st.markdown("##### 💬 양사 대표 부정 VOC 원문 대조")
    col_ra, col_rb = st.columns(2)
    with col_ra:
      st.markdown(f"**[{brand_a}] 최근 주요 불만 리뷰**")
      for i, r in enumerate(
          df_a[df_a["Sentiment"] == "Negative"]["Review"].dropna().head(3), 1
      ):
        st.caption(f"{i}. {r}")
    with col_rb:
      st.markdown(f"**[{brand_b}] 최근 주요 불만 리뷰**")
      for i, r in enumerate(
          df_b[df_b["Sentiment"] == "Negative"]["Review"].dropna().head(3), 1
      ):
        st.caption(f"{i}. {r}")

# =============================================================
# TAB 3: 이슈 & 키워드/연관구(Bigram) 심층 분석
# =============================================================
with tab3:
  st.subheader("🔍 부정 VOC 핵심 키워드 & 2단어 연관구(Bigram) 분석")

  col_t3_1, col_t3_2 = st.columns(2)

  neg_reviews = filtered_df[filtered_df["Sentiment"] == "Negative"][
      "Review"
  ].astype(str)
  stopwords = {
      "the",
      "and",
      "for",
      "with",
      "that",
      "this",
      "not",
      "but",
      "are",
      "was",
      "were",
      "remote",
      "control",
      "device",
      "tv",
      "app",
      "work",
      "works",
      "one",
      "all",
      "you",
      "can",
      "cant",
      "just",
      "very",
      "also",
      "from",
      "have",
      "리모컨",
      "작동",
      "사용",
      "제품",
      "진짜",
      "너무",
      "그냥",
      "다시",
  }

  single_words = []
  bigram_phrases = []

  for rev in neg_reviews:
    tokens = [
        w
        for w in re.findall(r"[a-zA-Z가-힣]{2,}", rev.lower())
        if w not in stopwords and len(w) > 2
    ]
    single_words.extend(tokens)
    for i in range(len(tokens) - 1):
      bigram_phrases.append(f"{tokens[i]} {tokens[i+1]}")

  with col_t3_1:
    st.markdown("##### 🔥 부정 VOC 핵심 빈출 단어 TOP 10")
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
          yaxis={"autorange": "reversed"}, margin=dict(t=20, b=20, l=10, r=10)
      )
      st.plotly_chart(fig_words, use_container_width=True)

  with col_t3_2:
    st.markdown("##### 🧩 핵심 결함 연관구 (Bigram TOP 10)")
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
          yaxis={"autorange": "reversed"}, margin=dict(t=20, b=20, l=10, r=10)
      )
      st.plotly_chart(fig_bigrams, use_container_width=True)

  st.write("")
  col_t3_3, col_t3_4 = st.columns(2)
  with col_t3_3:
    st.markdown("##### 🔋 전원 방식(Power Type)별 주요 불만 유형")
    if not filtered_df.empty:
      p_cat = (
          filtered_df.groupby(["Power_Type", "Category"])
          .size()
          .reset_index(name="건수")
      )
      p_tot = p_cat.groupby("Power_Type")["건수"].transform("sum")
      p_cat["비중(%)"] = (p_cat["건수"] / p_tot * 100).round(1)

      fig_p = px.bar(
          p_cat,
          x="Power_Type",
          y="건수",
          color="Category",
          barmode="stack",
          color_discrete_sequence=px.colors.qualitative.Pastel,
          hover_data={"건수": ":,d", "비중(%)": ":.1f%"},
      )
      fig_p.update_layout(margin=dict(t=20, b=20, l=10, r=10))
      st.plotly_chart(fig_p, use_container_width=True)

  with col_t3_4:
    st.markdown("##### 🏷️ 브랜드별 최다 불만 항목")
    if not filtered_df.empty:
      b_cat = (
          filtered_df.groupby(["Brand", "Category"])
          .size()
          .reset_index(name="건수")
      )
      b_tot = b_cat.groupby("Brand")["건수"].transform("sum")
      b_cat["비중(%)"] = (b_cat["건수"] / b_tot * 100).round(1)

      fig_b = px.bar(
          b_cat,
          x="Brand",
          y="건수",
          color="Category",
          barmode="stack",
          color_discrete_sequence=px.colors.qualitative.Set3,
          hover_data={"건수": ":,d", "비중(%)": ":.1f%"},
      )
      fig_b.update_layout(xaxis_tickangle=-45, margin=dict(t=20, b=20))
      st.plotly_chart(fig_b, use_container_width=True)

# =============================================================
# TAB 4: 원문 DB 및 엑셀 다운로드 (BOM 인코딩 보정)
# =============================================================
with tab4:
  st.subheader("📋 정밀 분류된 글로벌 60개사 VOC 원문 DB")
  display_cols = [
      c
      for c in [
          "Device_Type",
          "Power_Type",
          "UI_Type",
          "Region",
          "Brand",
          "Category",
          "Sentiment",
          "Source",
          "Review",
          "Collected_Date",
      ]
      if c in filtered_df.columns
  ]
  st.dataframe(filtered_df[display_cols], use_container_width=True, height=500)

  today_date = datetime.now().strftime("%Y%m%d")
  csv_bytes = filtered_df.to_csv(index=False).encode("utf-8-sig")

  down_c1, down_c2 = st.columns([1, 3])
  with down_c1:
    st.download_button(
        label="📥 필터링된 VOC 데이터 CSV 다운로드",
        data=csv_bytes,
        file_name=f"rcu_voc_global_v23_{today_date}.csv",
        mime="text/csv",
    )
  with down_c2:
    st.info(
        f"총 **{len(filtered_df):,}건**의 데이터가 Excel에서 깨지지 않는"
        f" UTF-8-BOM 포맷(`rcu_voc_global_v23_{today_date}.csv`)으로"
        " 다운로드됩니다."
    )

# =============================================================
# TAB 5: B2B 수주 & 임원 보고용 Pitch 제안서 (1-Page 다운로드 탑재)
# =============================================================
with tab5:
  st.subheader("💼 B2B 기술 영업 & 사업 수주 맞춤 Pitch 제안서")
  st.caption(
      "60개 전체 고객사 대상: 선택한 고객사의 실제 VoC 취약점을 정밀 분석하여,"
      " 당사의 해결 솔루션과 임원 보고용 맞춤 Pitch를 자동 도출합니다."
  )

  all_pitch_brands = sorted(list(df["Brand"].dropna().unique()))
  target_client = st.selectbox(
      "🎯 제안 대상 고객사 선택 (Target Client)",
      all_pitch_brands,
      index=(
          all_pitch_brands.index("KT (지니TV)")
          if "KT (지니TV)" in all_pitch_brands
          else 0
      ),
  )

  st.divider()

  client_df = df[df["Brand"] == target_client]
  client_neg = client_df[client_df["Sentiment"] == "Negative"]

  if client_neg.empty:
    st.info(
        f"'{target_client}'의 부정 VOC 데이터가 충분하지 않아 Pitch 제안서를"
        " 생성할 수 없습니다."
    )
  else:
    top_issues = client_neg["Category"].value_counts().head(2)
    primary_issue = top_issues.index[0]
    secondary_issue = top_issues.index[1] if len(top_issues) > 1 else None

    col_p1, col_p2 = st.columns([1, 1.4])

    with col_p1:
      st.markdown(f"#### 🚨 1. {target_client} 핵심 취약점 (VoC Pain Points)")
      st.error(
          f"**1순위 결함 지수:** {primary_issue} ({top_issues.iloc[0]}건 불만"
          " 접수)"
      )
      if secondary_issue:
        st.warning(
            f"**2순위 결함 지수:** {secondary_issue} ({top_issues.iloc[1]}건 불만"
            " 접수)"
        )

      st.markdown("💬 **현장 고객 대표 불만 원문:**")

      # [노이즈 2중 차단 가드레일] 순수 고객 VoC 우선 추출
      valid_reviews = client_neg[
          ~client_neg["Review"].astype(str).str.contains(NOISE_FILTER_REGEX)
      ]["Review"]
      if valid_reviews.empty:
        valid_reviews = client_neg["Review"]
      sample_reviews = valid_reviews.dropna().head(3).tolist()

      for r in sample_reviews:
        st.caption(f"- {r}")

    with col_p2:
      st.markdown("#### 🛠️ 2. 당사 R&D 기술 해결 솔루션 (Technical Action)")
      sol_1 = ACTION_RECOMMENDATIONS.get(
          primary_issue,
          "해당 카테고리 전담 품질 신뢰성 모니터링 및 펌웨어 리팩토링",
      )
      st.success(f"✔️ **[{primary_issue}] 대응 솔루션:**\n\n{sol_1}")

      if secondary_issue:
        sol_2 = ACTION_RECOMMENDATIONS.get(
            secondary_issue, "차세대 하드웨어 스펙 보강 및 회로 최적화"
        )
        st.info(f"✔️ **[{secondary_issue}] 대응 솔루션:**\n\n{sol_2}")

    st.write("")
    st.markdown("---")

    st.markdown("#### 🎤 3. 임원 보고 / B2B 수주 맞춤 Pitch 스크립트")

    if target_client in VIP_PITCH_DB:
      final_pitch = VIP_PITCH_DB[target_client]
    else:
      dev_type = BRAND_DIRECTORY.get(target_client, {}).get("type", "디바이스")
      final_pitch = (
          f"현재 {target_client} 가입자들이 가장 큰 불편을 호소하고 있는"
          f" '{primary_issue}' 결함을 당사의 {dev_type} 특화 차세대 아키텍처로"
          " 완벽하게 해결하겠습니다. 단순한 납품 단가 절감이 아닌, 반품 및 CS"
          f" 콜센터 인입률을 원천 차단하여 {target_client}의 브랜드 신뢰도 제고와"
          " 운영 비용(OPEX)의 획기적 절감을 제안합니다."
      )

    st.markdown(
        f"""
            <div style="background-color: #f8f9fa; padding: 22px; border-radius: 10px; border-left: 6px solid #1f77b4; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <span style="font-size: 0.9em; font-weight: bold; color: #1f77b4; text-transform: uppercase;">Executive Pitch for {target_client}</span>
                <p style="font-size: 1.15em; line-height: 1.65; color: #212529; margin-top: 8px; font-weight: 500;">
                    "{final_pitch}"
                </p>
            </div>
            """,
        unsafe_allow_html=True,
    )

    st.write("")
    pitch_summary_text = (
        f"""# [B2B Pitch Proposal] {target_client} RCU Quality & UX Improvement
- Date: {datetime.now().strftime("%Y-%m-%d")}
- Target Brand: {target_client} ({BRAND_DIRECTORY.get(target_client, {}).get("type", "OEM")})

## 1. Core VoC Vulnerabilities
- Primary Issue: {primary_issue} ({top_issues.iloc[0]} reports)
{f"- Secondary Issue: {secondary_issue} ({top_issues.iloc[1]} reports)" if secondary_issue else ""}

## 2. Technical Solutions & Action Items
- Solution 1 ({primary_issue}): {sol_1}
{f"- Solution 2 ({secondary_issue}): {sol_2}" if secondary_issue else ""}

## 3. Executive Sales Pitch
"{final_pitch}"

## 4. Voice of Customer (Sample Quotes)
"""
        + "\n".join([f"- {q}" for q in sample_reviews])
    )

    st.download_button(
        label=f"📄 [{target_client}] 1-Page 수주 제안서 내보내기 (.md)",
        data=pitch_summary_text.encode("utf-8-sig"),
        file_name=f"B2B_Pitch_{target_client}_{today_date}.md",
        mime="text/markdown",
    )
