# -*- coding: utf-8 -*-
from datetime import datetime
import os
import random
import re
import time
from duckduckgo_search import DDGS
import feedparser
from google_play_scraper import Sort, reviews
import pandas as pd
from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader

# -------------------------------------------------------------
# 0. 경로 절대화 및 광고/쇼핑몰 노이즈 판별 필터링 규칙
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "voc_db.csv")

PROMO_PATTERNS = [
    r"delivery", r"shipping", r"hassle-free", r"returns?", r"cash on delivery",
    r"shop for", r"buy online", r"in stock", r"order now", r"price in", r"discount",
    r"naira", r"rand", r"dollars?", r"wholesale", r"best price", r"free delivery",
    r"nationwide delivery", r"collection", r"many ways to pay", r"money back",
    r"당일배송", r"무료배송", r"최저가", r"구매혜택", r"판매처", r"할인", r"특가",
    r"is designed for", r"designed to provide", r"high-quality replacement",
    r"seamless compatibility", r"official website", r"features an? ", r"leading provider",
    r"welcome to", r"overview", r"specifications?:", r"package includes?:",
    r"guaranteed quality", r"wide compatibility", r"genuine original", r"perfect replacement",
    r"소개합니다", r"제공합니다", r"특징:", r"공식 홈페이지", r"출시했습니다", r"완벽 호환",
]


def is_genuine_voc(text):
    text_clean = str(text).lower().strip()
    if len(text_clean) < 25:
        return False
    for pattern in PROMO_PATTERNS:
        if re.search(pattern, text_clean):
            return False
    return True


TARGET_RCU_LIST = [
    {"Brand": "Apple", "Device": "Apple TV Siri Remote (3rd Gen)", "Region": "Global"},
    {"Brand": "Google", "Device": "Chromecast with Google TV Voice Remote", "Region": "Global"},
    {"Brand": "Amazon Fire TV", "Device": "Alexa Voice Remote Pro", "Region": "Global"},
    {"Brand": "Amazon Fire TV", "Device": "Fire TV Stick 4K Max Remote", "Region": "Global"},
    {"Brand": "Roku", "Device": "Roku Voice Remote Pro (2nd Gen)", "Region": "NA"},
    {"Brand": "Roku", "Device": "Roku Simple Remote", "Region": "NA"},
    {"Brand": "NVIDIA", "Device": "NVIDIA Shield TV Remote", "Region": "Global"},
    {"Brand": "TiVo", "Device": "TiVo Stream 4K Remote", "Region": "NA"},
    {"Brand": "Samsung", "Device": "Samsung SolarCell Remote (TM2360E)", "Region": "Korea"},
    {"Brand": "Samsung", "Device": "Samsung Smart Control (BN59 Series)", "Region": "Korea"},
    {"Brand": "LG Electronics", "Device": "LG Magic Remote (MR23GN / MR24)", "Region": "Korea"},
    {"Brand": "LG Electronics", "Device": "LG Standard IR Remote", "Region": "Korea"},
    {"Brand": "Sony", "Device": "Sony Bravia Premium Backlit Remote", "Region": "Japan"},
    {"Brand": "Sony", "Device": "Sony Bravia Voice Remote", "Region": "Japan"},
    {"Brand": "Panasonic", "Device": "Panasonic Viera Voice Remote", "Region": "Japan"},
    {"Brand": "Sharp", "Device": "Sharp AQUOS Voice Remote Control", "Region": "Japan"},
    {"Brand": "TCL", "Device": "TCL RC902V Voice Remote", "Region": "Global"},
    {"Brand": "Hisense", "Device": "Hisense ERF3A80 Voice Remote", "Region": "Global"},
    {"Brand": "Philips", "Device": "Philips Ambilight TV Remote", "Region": "EU"},
    {"Brand": "Xiaomi", "Device": "Xiaomi Mi TV Bluetooth Remote", "Region": "ASIA"},
    {"Brand": "Vizio", "Device": "Vizio SmartCast Voice Remote", "Region": "NA"},
    {"Brand": "LGI (Virgin Media)", "Device": "Virgin TV 360 Voice Remote", "Region": "EU"},
    {"Brand": "Canal+", "Device": "Le Décodeur CANAL+ 4K Remote", "Region": "EU"},
    {"Brand": "Orange", "Device": "Orange Livebox TV UHD Remote", "Region": "EU"},
    {"Brand": "Deutsche Telekom", "Device": "Deutsche Telekom MagentaTV One Remote", "Region": "EU"},
    {"Brand": "Vodafone", "Device": "Vodafone GigaTV Home Voice Remote", "Region": "EU"},
    {"Brand": "Sky Group", "Device": "Sky Q Voice Remote", "Region": "EU"},
    {"Brand": "Telefonica", "Device": "Movistar+ Voice Remote", "Region": "EU"},
    {"Brand": "KT (지니TV)", "Device": "KT Genie TV Smart Remote (지니TV 리모컨)", "Region": "Korea"},
    {"Brand": "SKB (B tv)", "Device": "SK Broadband B tv Smart Sound Remote (Btv 리모컨)", "Region": "Korea"},
    {"Brand": "LGU+ (U+tv)", "Device": "LG Uplus U+tv Earphone Remote (유플러스 리모컨)", "Region": "Korea"},
    {"Brand": "Tata Play", "Device": "Tata Play Binge+ Voice Remote", "Region": "ASIA"},
    {"Brand": "Airtel", "Device": "Airtel Xstream Box Voice Remote", "Region": "ASIA"},
    {"Brand": "J:COM", "Device": "J:COM LINK 4K Remote", "Region": "ASIA"},
    {"Brand": "MultiChoice (DStv)", "Device": "DStv Explora Ultra Voice Remote", "Region": "Africa"},
    {"Brand": "StarTimes", "Device": "StarTimes Digital TV Remote", "Region": "Africa"},
    {"Brand": "Canal+ Afrique", "Device": "Canal+ Afrique HD Decoder Remote", "Region": "Africa"},
    {"Brand": "Comcast", "Device": "Xfinity XR15 Voice Remote", "Region": "NA"},
    {"Brand": "Charter", "Device": "Spectrum Voice Remote", "Region": "NA"},
    {"Brand": "DirecTV", "Device": "DirecTV Stream Gemini Voice Remote", "Region": "NA"},
    {"Brand": "SofaBaton", "Device": "SofaBaton X1S Universal Remote", "Region": "Global"},
    {"Brand": "Control4", "Device": "Control4 Halo Touch Remote", "Region": "NA"},
    {"Brand": "Savant", "Device": "Savant Pro Remote X2", "Region": "NA"},
]


def get_localized_queries(device, brand, region):
    queries = [f'"{device}" review "problem" OR "issue" OR "not working"']
    if brand in ["KT (지니TV)", "SKB (B tv)", "LGU+ (U+tv)"] or (
        region == "Korea" and brand in ["Samsung", "LG Electronics"]
    ):
        queries.append(f'"{device}" 리모컨 먹통 OR 고장 OR "연결 안됨" OR "배터리"')
    elif brand in ["Sharp", "Panasonic", "Sony", "J:COM"]:
        queries.append(f'"{device}" リモコン "反応しない" OR 故障 OR ペアリング OR 電池')
    elif brand in ["Canal+", "Orange"]:
        queries.append(f'"{device}" télécommande "problème" OR panne OR synchro OR pile')
    elif brand in ["Deutsche Telekom", "Vodafone"]:
        queries.append(f'"{device}" Fernbedienung "funktioniert nicht" OR defekt OR Batterien')
    elif brand in ["MultiChoice (DStv)", "StarTimes"]:
        queries.append(f'"{device}" remote "load shedding" OR "battery leak"')
    else:
        queries.append(f'"{device}" remote "button click" OR "battery drain" OR "disconnect"')
    return queries


def collect_advanced_voc(quick_mode=True):
    """
    quick_mode=True : 대시보드 웹 UI 버튼 클릭 시 타임아웃 방지를 위한 고속 최신 수집 (~20초)
    quick_mode=False: 터미널/GitHub Actions 정기 배치 실행용 전체 심층 수집
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    if os.path.exists(DB_PATH):
        try:
            old_df = pd.read_csv(DB_PATH, encoding="utf-8-sig")
        except Exception:
            old_df = pd.read_csv(DB_PATH, encoding="utf-8")
        existing_reviews = set(old_df["Review"].astype(str).str.strip())
        print(f"📂 기존 DB 로드 완료: 총 {len(old_df):,}건 (기존 등록 리뷰 {len(existing_reviews):,}개)")
    else:
        old_df = pd.DataFrame(columns=["Collected_Date", "Source", "Brand", "Sentiment", "Review"])
        existing_reviews = set()

    new_data = []

    play_count = 60 if quick_mode else 400
    yt_limit = 20 if quick_mode else 60
    ddg_targets = TARGET_RCU_LIST[:8] if quick_mode else TARGET_RCU_LIST[:25]

    # -------------------------------------------------------------
    # 1. Google Play Store (실제 고객 작성일 rev['at'] 반영)
    # -------------------------------------------------------------
    playstore_apps = {
        "com.kt.otn": ("KT (지니TV)", "지니 TV 모바일", "kr", "ko"),
        "com.skb.btvmobile": ("SKB (B tv)", "모바일 B tv", "kr", "ko"),
        "uplus.tv.remote": ("LGU+ (U+tv)", "U+tv 리모컨", "kr", "ko"),
        "jp.co.sharp.aquos.remocon": ("Sharp", "AQUOS Remote Player", "jp", "ja"),
        "com.panasonic.pavc.viera.nremote3": ("Panasonic", "TV Remote 3", "jp", "ja"),
        "com.tatasky.hd": ("Tata Play", "Tata Play Mobile", "in", "en"),
        "airtel.myself.amigo": ("Airtel", "Airtel Xstream", "in", "en"),
        "fr.canal.android.canal": ("Canal+", "myCANAL", "fr", "fr"),
        "com.orange.owtv": ("Orange", "Orange TV", "fr", "fr"),
        "de.telekom.magentatv.atv": ("Deutsche Telekom", "MagentaTV", "de", "de"),
        "com.vodafone.vodafonetv": ("Vodafone", "Vodafone TV", "de", "de"),
        "com.virginmedia.tvanywhere": ("LGI (Virgin Media)", "Virgin TV Go", "gb", "en"),
        "com.bskyb.skyq": ("Sky Group", "Sky Q Remote App", "gb", "en"),
        "com.multichoice.mydstv": ("MultiChoice (DStv)", "MyDStv", "za", "en"),
        "com.control4.os3": ("Control4", "Control4 OS3", "us", "en"),
        "com.samsung.android.oneconnect": ("Samsung", "SmartThings", "us", "en"),
        "com.lgeha.nuts": ("LG Electronics", "LG ThinQ", "us", "en"),
        "com.tcl.magiconnect": ("TCL", "TCL MagiConnect", "us", "en"),
        "com.google.android.videos": ("Google", "Google TV", "us", "en"),
        "com.amazon.storm.lightning.client.aosp": ("Amazon Fire TV", "Fire TV App", "us", "en"),
    }

    print(f"\n[1/4] 📱 Google Play Store 최신 리뷰 수집 중 ({'고속 모드' if quick_mode else '전체 모드'})...")
    for app_id, (brand, app_name, country_code, lang_code) in playstore_apps.items():
        try:
            res, _ = reviews(
                app_id,
                lang=lang_code,
                country=country_code,
                sort=Sort.NEWEST,
                count=play_count,
            )
            added_count = 0
            for rev in res:
                text = rev.get("content", "").strip()
                review_full = f"[{app_name}] {text[:350]}"
                if len(text) < 15 or review_full in existing_reviews:
                    continue

                rev_date_obj = rev.get("at")
                if isinstance(rev_date_obj, datetime):
                    actual_date_str = rev_date_obj.strftime("%Y-%m-%d")
                else:
                    actual_date_str = today_str

                existing_reviews.add(review_full)
                sentiment = "Positive" if rev.get("score", 1) >= 4 else "Negative"

                new_data.append({
                    "Collected_Date": actual_date_str,
                    "Source": f"Google Play ({country_code.upper()})",
                    "Brand": brand,
                    "Sentiment": sentiment,
                    "Review": review_full,
                })
                added_count += 1
            if added_count > 0:
                print(f"  - [{country_code.upper()}] {brand} ({app_name}): 신규 {added_count}건 추가")
        except Exception:
            continue

    # -------------------------------------------------------------
    # 2. YouTube 최신 리뷰 댓글 수집
    # -------------------------------------------------------------
    print("\n[2/4] 🎬 YouTube 최신 실시간 리뷰 댓글 수집 중...")
    try:
        downloader = YoutubeCommentDownloader()
        youtube_videos = [
            ("LGI (Virgin Media)", "https://www.youtube.com/watch?v=k4u0bH9V_dI"),
            ("Canal+", "https://www.youtube.com/watch?v=0kFvW7rS4s4"),
            ("Deutsche Telekom", "https://www.youtube.com/watch?v=wXW5Z4Qz8Wk"),
            ("Samsung", "https://www.youtube.com/watch?v=1F_U7f0oXgQ"),
            ("LG Electronics", "https://www.youtube.com/watch?v=vV1r3k7Y2hA"),
            ("Sony", "https://www.youtube.com/watch?v=x2e1l9_z_pM"),
            ("Tata Play", "https://www.youtube.com/watch?v=n8-6h2gqJg8"),
            ("MultiChoice (DStv)", "https://www.youtube.com/watch?v=Yf9pYQGq5Q4"),
            ("Apple", "https://www.youtube.com/watch?v=r0vVqP2_p8U"),
            ("Amazon Fire TV", "https://www.youtube.com/watch?v=9L8K2p6J0lU"),
        ]

        multilingual_keywords = [
            "remote", "button", "work", "issue", "battery", "pair", "bad", "click", "lag",
            "리모컨", "연결", "먹통", "배터리", "リモコン", "反応", "故障", "電池",
            "télécommande", "synchro", "panne", "Fernbedienung", "defekt", "load shedding",
        ]

        for brand, url in youtube_videos:
            try:
                comments = downloader.get_comments_from_url(url, sort_by=SORT_BY_RECENT)
                count = 0
                for comment in comments:
                    if count >= yt_limit:
                        break
                    text = comment.get("text", "").strip()
                    if len(text) < 15 or text in existing_reviews:
                        continue

                    t_lower = text.lower()
                    if not any(k.lower() in t_lower for k in multilingual_keywords):
                        continue

                    existing_reviews.add(text)
                    positive_indicators = ["love", "great", "good", "best", "awesome", "좋아", "gut"]
                    sentiment = "Positive" if any(w in t_lower for w in positive_indicators) else "Negative"

                    new_data.append({
                        "Collected_Date": today_str,
                        "Source": "YouTube Community",
                        "Brand": brand,
                        "Sentiment": sentiment,
                        "Review": text[:350],
                    })
                    count += 1
                if count > 0:
                    print(f"  - {brand} 영상 최신 댓글: 신규 {count}건 추가")
            except Exception:
                continue
    except Exception:
        pass

    # -------------------------------------------------------------
    # 3. Reddit 권역별 최신 RSS 수집
    # -------------------------------------------------------------
    print("\n[3/4] 💬 Reddit 포럼 최신 글 수집 중...")
    reddit_targets = [
        ("VirginMedia", "LGI (Virgin Media)"),
        ("canalplus", "Canal+"),
        ("telekom", "Deutsche Telekom"),
        ("korea", "KT (지니TV)"),
        ("DStv", "MultiChoice (DStv)"),
        ("samsung", "Samsung"),
        ("LGOLED", "LG Electronics"),
        ("bravia", "Sony"),
        ("Roku", "Roku"),
        ("firetv", "Amazon Fire TV"),
        ("appletv", "Apple"),
    ]

    for sub, brand in reddit_targets:
        try:
            feed = feedparser.parse(f"https://www.reddit.com/r/{sub}/new.rss")
            count = 0
            for entry in feed.entries:
                text = f"{entry.title} {entry.get('summary', '')}".strip()
                if len(text) < 20 or text in existing_reviews:
                    continue

                t_lower = text.lower()
                if not any(w in t_lower for w in ["remote", "control", "button", "battery", "lag", "pairing", "리모컨"]):
                    continue

                entry_date_str = today_str
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        entry_date_str = datetime(*entry.published_parsed[:3]).strftime("%Y-%m-%d")
                    except Exception:
                        entry_date_str = today_str

                existing_reviews.add(text)
                sentiment = "Positive" if any(w in t_lower for w in ["love", "great", "fixed", "good"]) else "Negative"

                new_data.append({
                    "Collected_Date": entry_date_str,
                    "Source": f"Reddit (r/{sub})",
                    "Brand": brand,
                    "Sentiment": sentiment,
                    "Review": text[:350],
                })
                count += 1
            if count > 0:
                print(f"  - r/{sub} ({brand}): 신규 {count}건 추가")
        except Exception:
            continue

    # -------------------------------------------------------------
    # 4. DuckDuckGo (최근 1개월 내 등록 글 우선 수집)
    # -------------------------------------------------------------
    print("\n[4/4] 🌐 웹/포럼 실시간 VoC 수집 (최근 등록 글 우선 검색)...")
    try:
        with DDGS() as ddgs:
            for idx, item in enumerate(ddg_targets, 1):
                brand = item["Brand"]
                device = item["Device"]
                region = item["Region"]
                dev_count = 0

                localized_queries = get_localized_queries(device, brand, region)
                for query in localized_queries:
                    if dev_count >= 5:
                        break
                    try:
                        results = list(ddgs.text(query, max_results=5, timelimit="m"))
                        for res in results:
                            body = res.get("body", "").strip()
                            if len(body) < 30 or body in existing_reviews:
                                continue
                            if not is_genuine_voc(body):
                                continue

                            existing_reviews.add(body)
                            new_data.append({
                                "Collected_Date": today_str,
                                "Source": f"Web Forum ({region})",
                                "Brand": brand,
                                "Sentiment": "Negative",
                                "Review": f"[{device}] {body[:350]}",
                            })
                            dev_count += 1
                        time.sleep(random.uniform(0.3, 0.7))
                    except Exception:
                        time.sleep(0.4)
                        continue
                if dev_count > 0:
                    print(f"  - [{idx}] [{region}] {device}: 신규 {dev_count}건 추가")
    except Exception as e:
        print(f"  ⚠️ DuckDuckGo 수집 중단: {e}")

    # -------------------------------------------------------------
    # 5. 데이터 병합 & 저장
    # -------------------------------------------------------------
    if not new_data:
        print("\nℹ️ 새로 수집된 신규 리뷰가 없습니다. (모든 소스에서 중복 제외 후 신규 0건)")
        return

    new_df = pd.DataFrame(new_data)
    combined_df = (
        pd.concat([old_df, new_df], ignore_index=True)
        .drop_duplicates(subset=["Review"], keep="first")
        .reset_index(drop=True)
    )

    combined_df.to_csv(DB_PATH, index=False, encoding="utf-8-sig")
    print(f"\n🎉 [수집 완료] 신규 {len(new_data):,}건 수집 완료! 총 누적: {len(combined_df):,}건")

    parsed_temp = pd.to_datetime(combined_df["Collected_Date"].astype(str).str.slice(0, 10), errors="coerce").dropna()
    if not parsed_temp.empty:
        print(f"📅 현재 DB 날짜 범위: {parsed_temp.min().strftime('%Y-%m-%d')} ~ {parsed_temp.max().strftime('%Y-%m-%d')}")
        print(f"📊 최신 주차: {parsed_temp.dt.strftime('%Y-W%W').max()}")


if __name__ == "__main__":
    collect_advanced_voc(quick_mode=False)