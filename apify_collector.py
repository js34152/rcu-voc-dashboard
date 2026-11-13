# -*- coding: utf-8 -*-
from datetime import datetime
import os
from apify_client import ApifyClient
import pandas as pd

# -------------------------------------------------------------
# 1. 보안 설정: 코드에 직접 적지 않고 PC 환경변수(또는 GitHub Secrets)에서 자동 로드
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "voc_db.csv")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()

# -------------------------------------------------------------
# 2. 404 오류 없는 아마존 공식 활성 링크
# -------------------------------------------------------------
TARGET_RCUS = [
    {
        "Brand": "Amazon Fire TV",
        "Device": "Alexa Voice Remote Pro",
        "url": "https://www.amazon.com/dp/B09N3ZNHTY",
    },
    {
        "Brand": "Roku",
        "Device": "Roku Voice Remote Pro",
        "url": "https://www.amazon.com/dp/B0916RDGMD",
    },
    {
        "Brand": "Apple",
        "Device": "Apple TV Siri Remote",
        "url": "https://www.amazon.com/dp/B0933D3CT6",
    },
    {
        "Brand": "Google",
        "Device": "Chromecast Voice Remote",
        "url": "https://www.amazon.com/dp/B097ZBC26C",
    },
    {
        "Brand": "SofaBaton",
        "Device": "SofaBaton U2 Universal Remote",
        "url": "https://www.amazon.com/dp/B0B4WC9N43",
    },
    {
        "Brand": "Samsung",
        "Device": "Samsung Smart Remote Replacement",
        "url": "https://www.amazon.com/dp/B08V8BNNVR",
    },
    {
        "Brand": "LG Electronics",
        "Device": "LG Magic Remote Replacement",
        "url": "https://www.amazon.com/dp/B0BTD8G59B",
    },
]


def parse_amazon_date(raw_date, fallback_str):
    if not raw_date:
        return fallback_str
    text = str(raw_date).strip()
    if " on " in text:
        text = text.split(" on ")[-1].strip()
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return parsed.strftime("%Y-%m-%d")
    return fallback_str


def collect_amazon_reviews():
    if not APIFY_TOKEN:
        print("❌ 오류: APIFY_TOKEN 환경변수가 설정되지 않았습니다.")
        print("💡 터미널에서 setx APIFY_TOKEN \"본인토큰\" 실행 후 VS Code를 재시작하세요.")
        return

    client = ApifyClient(APIFY_TOKEN)
    today_str = datetime.now().strftime("%Y-%m-%d")

    if os.path.exists(DB_PATH):
        try:
            df_existing = pd.read_csv(DB_PATH, encoding="utf-8-sig")
        except Exception:
            df_existing = pd.read_csv(DB_PATH, encoding="utf-8")
        existing_reviews = set(df_existing["Review"].astype(str).str.strip())
    else:
        df_existing = pd.DataFrame(
            columns=["Collected_Date", "Source", "Brand", "Sentiment", "Review"]
        )
        existing_reviews = set()

    new_records = []
    print(f"🚀 [아마존 자동 수집 시작] 총 {len(TARGET_RCUS)}개 모델 수집 진행...")

    for idx, item in enumerate(TARGET_RCUS, 1):
        brand = item["Brand"]
        device = item["Device"]
        url = item["url"]

        print(f"\n[{idx}/{len(TARGET_RCUS)}] {brand} - '{device}' 크롤링 중...")

        run_input = {
            "productUrls": [{"url": url}],
            "maxReviews": 10,
            "sort": "recent",
            "filterByRatings": ["allStars"],
        }

        try:
            run = client.actor("junglee/amazon-reviews-scraper").call(
                run_input=run_input
            )

            dataset_id = getattr(run, "default_dataset_id", None) or (
                run.get("defaultDatasetId") if isinstance(run, dict) else None
            )

            dataset_items = client.dataset(dataset_id).list_items().items
            added_count = 0

            for rev in dataset_items:
                desc = rev.get("reviewDescription", "") or rev.get("reviewText", "")
                title = rev.get("reviewTitle", "")

                if not desc and not title:
                    continue

                full_text = f"[{device}] {title}. {desc}".strip()

                if len(full_text) < 15 or full_text in existing_reviews:
                    continue

                rating = rev.get("ratingScore", 1)
                sentiment = "Positive" if rating >= 4 else "Negative"
                actual_date = parse_amazon_date(rev.get("date"), today_str)

                existing_reviews.add(full_text)
                new_records.append({
                    "Collected_Date": actual_date,
                    "Source": "Amazon (Apify Verified)",
                    "Brand": brand,
                    "Sentiment": sentiment,
                    "Review": full_text[:400],
                })
                added_count += 1

            print(f"  - {brand}: 신규 {added_count}건 수집 완료")
        except Exception as e:
            print(f"  - {brand} 처리 중 오류: {e}")

    if new_records:
        df_new = pd.DataFrame(new_records)
        df_combined = (
            pd.concat([df_existing, df_new], ignore_index=True)
            .drop_duplicates(subset=["Review"], keep="first")
            .reset_index(drop=True)
        )
        df_combined.to_csv(DB_PATH, index=False, encoding="utf-8-sig")
        print(
            f"\n🎉 [완료] 신규 리뷰 {len(new_records):,}건이 voc_db.csv에 누적"
            f" 저장되었습니다! (총 {len(df_combined):,}건)"
        )
    else:
        print("\nℹ️ 새로 수집된 신규 리뷰가 없거나 기존 데이터와 중복되었습니다.")


if __name__ == "__main__":
    collect_amazon_reviews()