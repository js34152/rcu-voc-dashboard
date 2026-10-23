import os
import re
import pandas as pd

# 전 브랜드 공통 노이즈 정규식 (국문/영문 공식 홍보, 고객센터, 쇼핑몰 정책)
NOISE_REGEX = re.compile(
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


def clean_database():
  file_path = "voc_db.csv"
  if not os.path.exists(file_path):
    print("❌ 'voc_db.csv' 파일이 존재하지 않습니다.")
    return

  try:
    df = pd.read_csv(file_path, encoding="utf-8-sig")
  except Exception:
    df = pd.read_csv(file_path, encoding="utf-8")

  initial_cnt = len(df)
  print(f"📊 정제 전 전체 데이터: {initial_cnt:,}건")

  # 1) 기업 홍보 및 쇼핑몰 정책 문구 행 제거
  df_clean = df[~df["Review"].astype(str).str.contains(NOISE_REGEX)].copy()

  # 2) 본문 길이가 너무 짧은(25자 미만) 단순 단어 나열 행 제거
  df_clean = df_clean[df_clean["Review"].astype(str).str.len() >= 25]

  removed_cnt = initial_cnt - len(df_clean)

  # 덮어쓰기 저장 (UTF-8-BOM)
  df_clean.to_csv(file_path, index=False, encoding="utf-8-sig")
  print(f"🧹 제거된 전체 브랜드 홍보/광고 노이즈: {removed_cnt:,}건")
  print(f"🎉 순수 VoC 보존 완료: {len(df_clean):,}건")


if __name__ == "__main__":
  clean_database()
