# -*- coding: utf-8 -*-
import os
import re
import pandas as pd

# 어디서 실행하든 항상 같은 폴더의 voc_db.csv를 찾도록 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "voc_db.csv")

# 전 브랜드 공통 광고/쇼핑몰/제조사 소개글 블랙리스트 정규식 (다국어 리뷰 보존)
NOISE_REGEX = re.compile(
    r"(?:공식\s*(?:기업\s*)?사이트|공식\s*홈페이지|공식\s*(?:직영\s*)?온라인샵|다이렉트샵|"
    r"\[kt\]\s*메인|\[마이페이지\]|고객센터|음성상담|채팅상담|보이스봇|"
    r"이용하시는\s*고객|혜택과\s*서비스|이벤트도\s*참여|되겠습니다|가능합니다|"
    r"주식회사|사업자등록|대표이사|개인정보처리|요금제\s*확인|상품서비스|"
    r"당일배송|무료배송|최저가|구매혜택|판매처|할인|특가|소개합니다|제공합니다|특징:|출시했습니다|"
    r"delivery|shipping|hassle-free|returns?|cash on delivery|discount|dollars?|wholesale|best price|free delivery|"
    r"shop for|buy online|in stock|order now|price in|naira|rand|"
    r"nationwide delivery|collection|many ways to pay|money back|"
    r"is designed for|designed to provide|high-quality replacement|"
    r"seamless compatibility|official website|features an? |leading provider|"
    r"welcome to|overview|specifications?:|package includes?:|replacement remote|aerial king|"
    r"guaranteed quality|wide compatibility|genuine original)",
    re.IGNORECASE,
)


def clean_database():
    if not os.path.exists(DB_PATH):
        print("❌ 'voc_db.csv' 파일이 존재하지 않습니다.")
        return

    try:
        df = pd.read_csv(DB_PATH, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(DB_PATH, encoding="utf-8")

    initial_cnt = len(df)
    print(f"📊 정제 전 전체 데이터: {initial_cnt:,}건")

    # 1) 빈 값(NaN) 제거 및 앞뒤 공백 정리
    df_clean = df.dropna(subset=["Review"]).copy()
    df_clean["Review"] = df_clean["Review"].astype(str).str.strip()

    # 2) 기업 홍보 및 쇼핑몰 광고 문구 행 제거
    df_clean = df_clean[~df_clean["Review"].str.contains(NOISE_REGEX)].copy()

    # 3) 본문 길이가 너무 짧은(25자 미만) 행 제거
    df_clean = df_clean[df_clean["Review"].str.len() >= 25].copy()

    # 4) 완전히 똑같은 중복 리뷰 제거
    df_clean = df_clean.drop_duplicates(subset=["Review"], keep="first").reset_index(drop=True)

    removed_cnt = initial_cnt - len(df_clean)

    # 영구 덮어쓰기 저장 (UTF-8-BOM)
    df_clean.to_csv(DB_PATH, index=False, encoding="utf-8-sig")
    print(f"🧹 제거된 홍보/광고/중복 노이즈: {removed_cnt:,}건")
    print(f"🎉 순수 글로벌 VoC 보존 완료: {len(df_clean):,}건 ('voc_db.csv' 갱신 완료)")


if __name__ == "__main__":
    clean_database()