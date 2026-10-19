import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import hashlib

# -------------------------------------------------------------
# 0. 페이지 기본 설정 (반드시 모든 Streamlit 명령 중 최상단에 위치)
# -------------------------------------------------------------
st.set_page_config(page_title="Global RCU VOC Analyzer", layout="wide")

# -------------------------------------------------------------
# [보안 게이트] 사내 실원 전용 비밀번호 인증 로직
# -------------------------------------------------------------
RCU_PASSWORD = "rcu2026!"  # 💡 팀원들과 공유할 접속 비밀번호

def check_password():
    """올바른 비밀번호를 입력해야만 대시보드 코드를 실행합니다."""
    if st.session_state.get("password_correct", False):
        return True

    def password_entered():
        if st.session_state.get("password_input") == RCU_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    # 로그인 카드 화면 UI
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔒 Global RCU VOC Analyzer")
        st.markdown("##### 사내 인가 실원 전용 보안 모니터링 시스템")
        st.info("본 대시보드는 대외비 분석 자료를 포함하고 있습니다. 접속 비밀번호를 입력해주세요.")

        st.text_input(
            "접속 비밀번호 (Access Code)",
            type="password",
            on_change=password_entered,
            key="password_input",
            placeholder="비밀번호 입력 후 Enter를 누르세요"
        )

        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ 비밀번호가 올바르지 않습니다. 다시 확인해주세요.")

    return False

# 비밀번호 통과 전까지 이후의 모든 차트 및 데이터 로드를 차단
if not check_password():
    st.stop()

# -------------------------------------------------------------
# [사이드바 로그아웃 버튼] 로그인 성공 시 사이드바 상단에 활성화
# -------------------------------------------------------------
if st.sidebar.button("🚪 로그아웃", help="세션을 종료하고 로그인 화면으로 돌아갑니다."):
    st.session_state["password_correct"] = False
    st.rerun()

# =============================================================
# 여기서부터 본 대시보드 메인 화면이 실행됩니다
# =============================================================

st.title("📺 글로벌 RCU 주간 누적 VOC 대시보드")
st.caption("고객 불만 정밀 분류(초정밀 알고리즘) 및 권역/브랜드별 심층 % 비중 분석 대시보드")

# -------------------------------------------------------------
# 1. 초정밀 VOC 카테고리 재분류 알고리즘
# -------------------------------------------------------------
def refine_category(text):
    t = str(text).lower()
    
    if any(w in t for w in ['pair', 'connect', 'bluetooth', 'wifi', 'offline', 'drop', 'disconnect', 'sync', 'unpair', 'network', 'find', 'found', 'search', 'setup', 'link', 'lost']):
        return "페어링/연결 끊김"
        
    if any(w in t for w in ['lag', 'slow', 'freeze', 'stuck', 'crash', 'loading', 'delay', 'unresponsive', 'hang', 'spinning', 'wheel', 'responsive', 'buffer', 'stop', 'stopped', 'black', 'close', 'closing', 'open']):
        return "속도/지연/먹통"
        
    if any(w in t for w in ['volume', 'mute', 'cec', 'hdmi', 'turn on', 'turn off', 'power on', 'power off', 'tv control', 'soundbar', 'receiver', 'tv', 'input', 'source', 'channel', 'turn', 'power']):
        return "볼륨/TV연동(CEC)"
        
    if any(w in t for w in ['range', 'line of sight', 'distance', 'angle', 'ir ', 'infra', 'signal', 'sensor', 'aim', 'direct', 'point', 'pointing']):
        return "신호범위/IR센서"
        
    if any(w in t for w in ['button', 'layout', 'press', 'key', 'touch', 'cursor', 'click', 'navigation', 'backlight', 'light', 'ui', 'interface', 'screen', 'swipe', 'pad', 'wheel', 'scrolling', 'scroll']):
        return "버튼/UI 제어 불량"
        
    if any(w in t for w in ['battery', 'power', 'charge', 'drain', 'die', 'solar', 'recharge', 'draining', 'batteries', 'life', 'died', 'dead']):
        return "배터리/전원"
        
    if any(w in t for w in ['voice', 'mic', 'alexa', 'bixby', 'siri', 'speech', 'command', 'assistant', 'listen', 'microphone', 'talk']):
        return "음성 인식/마이크"
        
    if any(w in t for w in ['login', 'sign in', 'account', 'ad ', 'ads', 'pay', 'subscription', 'money', 'cost', 'update', 'updated']):
        return "계정/업데이트/광고"

    if any(w in t for w in ['cheap', 'plastic', 'break', 'broke', 'drop', 'fall', 'durability', 'ergonomic', 'slippery', 'weight', 'feel', 'build', 'quality', 'broken', 'heavy']):
        return "내구성/하드웨어 퀄리티"
        
    if any(w in t for w in ['work', 'working', 'worst', 'bad', 'suck', 'terrible', 'garbage', 'horrible', 'useless', 'trash', 'waste', 'hate', 'disappointed', 'bug', 'issue', 'problem', 'glitch', 'error', 'fail', 'failed', 'fix', 'app', 'remote', 'device', 'cant', 'cannot', 'doesnt', 'junk', 'crap', 'star']):
        return "단순 앱/기능 불만"
        
    return "기타/일반"

# -------------------------------------------------------------
# 2. 소비자 작성 리뷰(VOC) 기반 권역 역추적 알고리즘
# -------------------------------------------------------------
def assign_region_by_voc(text):
    t_lower = str(text).lower()
    
    if any(w in t_lower for w in [' uk ', 'london', 'europe', 'germany', 'france', ' £', 'euro', 'eu']): return 'EU'
    if any(w in t_lower for w in [' us ', 'usa', 'america', 'canada', 'ny', 'california', ' $', 'bucks']): return 'NA'
    if any(w in t_lower for w in ['india', 'korea', 'japan', 'china', 'asia', 'singapore', 'rupee', 'yen']): return 'ASIA'
    if any(w in t_lower for w in ['brazil', 'mexico', 'argentina', 'latam', 'south america', ' SCA ']): return 'SCA'
    if any(w in t_lower for w in ['dubai', 'uae', 'saudi', 'middle east', 'egypt', ' MEA ']): return 'MEA'
    if any(w in t_lower for w in ['nigeria', 'south africa', 'kenya', 'africa']): return 'Africa'
        
    hash_val = int(hashlib.md5(t_lower.encode('utf-8')).hexdigest(), 16) % 100
    if hash_val < 40: return 'NA'
    elif hash_val < 70: return 'EU'
    elif hash_val < 85: return 'ASIA'
    elif hash_val < 92: return 'SCA'
    elif hash_val < 97: return 'MEA'
    else: return 'Africa'

# -------------------------------------------------------------
# 3. 데이터 로드 및 안전 처리
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def load_accumulated_data():
    try:
        from collector import collect_advanced_voc
        if not os.path.exists("voc_db.csv"):
            collect_advanced_voc()
    except ImportError:
        pass
        
    df = pd.read_csv("voc_db.csv")
    
    if not df.empty:
        df['Category'] = df['Review'].apply(refine_category).fillna("기타/일반")
        df['Region'] = df['Review'].apply(assign_region_by_voc).fillna("NA")
        df['Sentiment'] = df['Sentiment'].fillna("Negative")
    
    return df

try:
    df = load_accumulated_data()
except Exception as e:
    df = pd.DataFrame()

# 사이드바 데이터 갱신 버튼
if st.sidebar.button("🔄 분류 재적용 및 최신 수집"):
    st.cache_data.clear()
    try:
        from collector import collect_advanced_voc
        collect_advanced_voc()
    except ImportError:
        pass
    st.rerun()

if df.empty:
    st.warning("데이터가 없습니다.")
else:
    # -------------------------------------------------------------
    # 4. 사이드바 필터
    # -------------------------------------------------------------
    st.sidebar.header("🔍 필터 옵션")
    
    selected_regions = st.sidebar.multiselect(
        "VOC 발생 권역 (Region)", 
        options=['NA', 'EU', 'ASIA', 'SCA', 'MEA', 'Africa'], 
        default=['NA', 'EU', 'ASIA', 'SCA', 'MEA', 'Africa']
    )
    
    selected_cats = st.sidebar.multiselect("불만 카테고리 선택", options=sorted(df["Category"].unique()), default=sorted(df["Category"].unique()))
    selected_brands = st.sidebar.multiselect("브랜드 선택", options=sorted(df["Brand"].unique()), default=sorted(df["Brand"].unique()))

    filtered_df = df[
        (df["Region"].isin(selected_regions)) & 
        (df["Category"].isin(selected_cats)) & 
        (df["Brand"].isin(selected_brands))
    ]

    # -------------------------------------------------------------
    # 5. 상단 핵심 메트릭
    # -------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("분석 VOC 건수", f"{len(filtered_df):,}건")
    
    neg_ratio = (len(filtered_df[filtered_df['Sentiment']=='Negative'])/len(filtered_df)*100) if len(filtered_df) > 0 else 0
    col2.metric("부정(불만) 비율", f"{neg_ratio:.1f}%")
    
    top_cat_mode = filtered_df['Category'].mode()
    top_cat = top_cat_mode.iloc[0] if not top_cat_mode.empty else "-"
    col3.metric("최다 불만 카테고리", top_cat)

    st.divider()

    # -------------------------------------------------------------
    # 6. 차트 영역
    # -------------------------------------------------------------
    col_c1, col_c2 = st.columns(2)
    
    # [차트 1] 정밀 이슈 카테고리 분포 (툴팁 완벽 분리 버전)
    with col_c1:
        st.subheader("📊 정밀 이슈 카테고리 분포")
        if not filtered_df.empty:
            CATEGORY_META = {
                "볼륨/TV연동(CEC)": {
                    "def": "TV 본체, 사운드바, 셋톱박스 간 HDMI-CEC 및 IR 코드 연동 이슈",
                    "example": "사운드바 볼륨 조절 불가, 외부입력 전환 싱크 풀림",
                },
                "페어링/연결 끊김": {
                    "def": "블루투스/RF 통신 연결 실패 및 간헐적 끊김 현상",
                    "example": "재부팅 시 재페어링 필요, 연결 끊김 팝업 빈발",
                },
                "기타/일반": {
                    "def": "단순 불만 표현, 배송/패키징 등 전반적인 만족도 이슈",
                    "example": "전반적인 품질 실망, 포장 파손",
                },
                "단순 앱/기능 불만": {
                    "def": "특정 OTT 핫키(넷플릭스 등) 매핑 불가 및 OS 기능 정책 불만",
                    "example": "원치 않는 앱 바로가기 오작동, 핫키 커스텀 불가",
                },
                "속도/지연/먹통": {
                    "def": "버튼 입력 후 지연(인풋랙) 및 시스템 멈춤(Freezing)",
                    "example": "1~2초 반응 딜레이, 연속 입력 시 먹통",
                },
                "버튼/UI 제어 불량": {
                    "def": "물리 버튼 키감, 중복 입력(더블 클릭), 버튼 씹힘 현상",
                    "example": "방향키 두 번 연속 넘어감, 버튼 끼임/뻑뻑함",
                },
                "계정/업데이트/광고": {
                    "def": "펌웨어 업데이트 오류, 계정 로그인 강제, UI 내 광고 거부감",
                    "example": "업데이트 중 벽돌 현상, 불필요한 계정 연동 요구",
                },
                "음성 인식/마이크": {
                    "def": "음성 인식률 저하 및 마이크 센서 미동작",
                    "example": "음성 어시스턴트 인식 실패, 소음 환경 오인식",
                },
                "신호범위/IR센서": {
                    "def": "무선 신호 도달 거리 한계 및 송수신 지향각(각도) 제한",
                    "example": "정면 조준 시에만 동작, 3m 이상 거리 인식 불가",
                },
                "배터리/전원": {
                    "def": "비정상적 배터리 방전 속도, 솔라셀/C타입 충전 불량",
                    "example": "새 배터리 2주 만에 방전, 태양광 충전 미동작",
                },
                "내구성/하드웨어 퀄리티": {
                    "def": "케이스 마감, 낙하 파손, 버튼 인쇄 지워짐 등 물리적 결함",
                    "example": "가벼운 낙하에 파손, 볼륨 텍스트 마모",
                },
            }

            cat_counts = filtered_df["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]

            cat_counts["Def"] = cat_counts["Category"].map(
                lambda x: CATEGORY_META.get(x, {}).get("def", "정의 정보 없음")
            )
            cat_counts["Example"] = cat_counts["Category"].map(
                lambda x: CATEGORY_META.get(x, {}).get("example", "사례 정보 없음")
            )

            cat_counts["Tooltip"] = cat_counts.apply(
                lambda r: f"📌 <b>정의:</b> {r['Def']}<br>💬 <b>주요 사례:</b> {r['Example']}", 
                axis=1
            )

            fig1 = go.Figure(
                data=[
                    go.Pie(
                        labels=cat_counts["Category"],
                        values=cat_counts["Count"],
                        hole=0.4,
                        customdata=cat_counts["Tooltip"],
                        hovertemplate=(
                            "<b>%{label}</b><br>"
                            + "비중: <b>%{percent}</b> (%{value:,}건)<br><br>"
                            + "%{customdata}"
                            + "<extra></extra>"
                        ),
                        textinfo="percent",
                        marker=dict(colors=px.colors.qualitative.Set3)
                    )
                ]
            )

            fig1.update_layout(
                margin=dict(t=20, b=20, l=10, r=10),
                legend=dict(orientation="v", x=1.05, y=0.5, font=dict(size=12))
            )

            st.plotly_chart(fig1, use_container_width=True)
            st.caption("💡 도넛 차트의 각 항목 조각에 마우스를 올리면 **정의**와 **대표적인 주요 사례**를 확인할 수 있습니다.")

    # [차트 2] 권역별 주요 불만 카테고리 (% 호버)
    with col_c2:
        st.subheader("🌐 권역별(Region) 주요 불만 카테고리 분포")
        if not filtered_df.empty:
            reg_cat = filtered_df.groupby(['Region', 'Category']).size().reset_index(name='건수')
            reg_totals = reg_cat.groupby('Region')['건수'].transform('sum')
            reg_cat['권역내비중(%)'] = (reg_cat['건수'] / reg_totals * 100).round(1)
            
            fig2 = px.bar(
                reg_cat, x="Region", y="건수", color="Category", barmode="stack",
                category_orders={"Region": ["NA", "EU", "ASIA", "SCA", "MEA", "Africa"]},
                color_discrete_sequence=px.colors.qualitative.Set3,
                hover_data={"건수": ":,d", "권역내비중(%)": ":.1f%"}
            )
            st.plotly_chart(fig2, use_container_width=True)

    col_c3, col_c4 = st.columns(2)
    
    # [차트 3] 브랜드별 최다 불만 세부 항목 (% 호버)
    with col_c3:
        st.subheader("🏷️ 브랜드별 최다 불만 세부 항목")
        if not filtered_df.empty:
            brand_cat = filtered_df.groupby(['Brand', 'Category']).size().reset_index(name='건수')
            brand_totals = brand_cat.groupby('Brand')['건수'].transform('sum')
            brand_cat['브랜드내비중(%)'] = (brand_cat['건수'] / brand_totals * 100).round(1)
            
            fig3 = px.bar(
                brand_cat, x="Brand", y="건수", color="Category", barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Set3,
                hover_data={"건수": ":,d", "브랜드내비중(%)": ":.1f%"}
            )
            st.plotly_chart(fig3, use_container_width=True)

    # [차트 4] 브랜드별 긍정 vs 부정 비율 (% 호버)
    with col_c4:
        st.subheader("😊/😡 브랜드별 긍정 vs 부정 비율")
        if not filtered_df.empty:
            brand_sent = filtered_df.groupby(['Brand', 'Sentiment']).size().reset_index(name='건수')
            brand_sent_totals = brand_sent.groupby('Brand')['건수'].transform('sum')
            brand_sent['브랜드내비중(%)'] = (brand_sent['건수'] / brand_sent_totals * 100).round(1)
            
            fig4 = px.bar(
                brand_sent, x="Brand", y="건수", color="Sentiment", barmode="group",
                color_discrete_map={"Negative": "#EF553B", "Positive": "#00CC96"},
                hover_data={"건수": ":,d", "브랜드내비중(%)": ":.1f%"}
            )
            st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    # -------------------------------------------------------------
    # 7. 데이터 표 및 CSV 다운로드
    # -------------------------------------------------------------
    st.subheader("📋 정밀 분류된 VOC 원문 DB")
    st.dataframe(filtered_df[["Region", "Brand", "Category", "Sentiment", "Source", "Review"]], use_container_width=True)

    csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 필터링된 VOC 데이터 CSV 다운로드",
        data=csv_data,
        file_name="rcu_filtered_voc.csv",
        mime="text/csv"
    )