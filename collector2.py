from datetime import datetime
import os
import random
import re
import time
from duckduckgo_search import DDGS
import feedparser
from google_play_scraper import Sort, reviews
import pandas as pd
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader

# -------------------------------------------------------------
# 0. 진짜 고객 VoC 판별 필터링 규칙 (노이즈 / 홍보글 / 쇼핑몰 스펙 제거)
# -------------------------------------------------------------
PROMO_PATTERNS = [
    # [커머스 / 배송 / 결제 / 가격 관련 광고 노이즈]
    r"delivery", r"shipping", r"hassle-free", r"returns?", r"cash on delivery",
    r"shop for", r"buy online", r"in stock", r"order now", r"price in", r"discount",
    r"naira", r"rand", r"dollars?", r"wholesale", r"best price", r"free delivery",
    r"nationwide delivery", r"collection", r"many ways to pay", r"money back",
    r"당일배송", r"무료배송", r"최저가", r"구매혜택", r"판매처", r"할인", r"특가",

    # [제조사 공식 PR / 제품 카탈로그 / 스펙 설명 문구]
    r"is designed for", r"designed to provide", r"high-quality replacement",
    r"seamless compatibility", r"official website", r"features an? ", r"leading provider",
    r"welcome to", r"overview", r"specifications?:", r"package includes?:",
    r"guaranteed quality", r"wide compatibility", r"genuine original", r"perfect replacement",
    r"소개합니다", r"제공합니다", r"특징:", r"공식 홈페이지", r"출시했습니다", r"완벽 호환"
]

EXPERIENCE_PATTERNS = [
    # [1인칭 사용자 화자 표현]
    r"\bi\b", r"\bmy\b", r"\bme\b", r"\bmine\b", r"\bwe\b",
    r"내가", r"저는", r"제가", r"우리", r"내 ", r"저희",

    # [구매 및 실제 사용 기간/시점 표현]
    r"bought", r"purchased", r"using", r"used", r"after [0-9]+",
    r"weeks?", r"months?", r"days?", r"update", r"stopped", r"broke",
    r"산 지", r"구입", r"구매한", r"쓰고 있", r"쓰다가", r"업데이트 후", r"교체",

    # [실제 결함 및 감정 표현]
    r"terrible", r"worst", r"frustrat", r"annoy", r"disappoint", r"hate",
    r"useless", r"garbage", r"trash", r"sucks?", r"fail", r"not work", r"broken",
    r"disconnect", r"load shedding", r"lag", r"freeze",
    r"짜증", r"불편", r"답답", r"최악", r"안 됨", r"고장", r"먹통", r"렉"
]


def is_genuine_voc(text):
  text_clean = str(text).lower()

  # 1) 홍보/광고/쇼핑몰 소개 문구가 포함되어 있으면 배제
  for pattern in PROMO_PATTERNS:
    if re.search(pattern, text_clean):
      return False

  # 2) 실제 사용 경험이나 주관적 평가 표현이 전혀 없으면 배제
  has_experience = any(re.search(p, text_clean) for p in EXPERIENCE_PATTERNS)
  if not has_experience:
    return False

  # 3) 너무 짧거나 본문이 빈약한 텍스트 배제
  if len(text_clean.strip()) < 25:
    return False

  return True


# -------------------------------------------------------------
# 1. 글로벌 핵심 타깃 RCU 모델 리스트 (유럽/아시아/아프리카/미주 전 권역)
# -------------------------------------------------------------
TARGET_RCU_LIST = [
    # [1] 글로벌 빅테크 / 스트리밍
    {
        "Brand": "Apple",
        "Device": "Apple TV Siri Remote (3rd Gen)",
        "Region": "Global",
    },
    {
        "Brand": "Google",
        "Device": "Chromecast with Google TV Voice Remote",
        "Region": "Global",
    },
    {
        "Brand": "Amazon Fire TV",
        "Device": "Alexa Voice Remote Pro",
        "Region": "Global",
    },
    {
        "Brand": "Amazon Fire TV",
        "Device": "Fire TV Stick 4K Max Remote",
        "Region": "Global",
    },
    {
        "Brand": "Roku",
        "Device": "Roku Voice Remote Pro (2nd Gen)",
        "Region": "NA",
    },
    {"Brand": "Roku", "Device": "Roku Simple Remote", "Region": "NA"},
    {"Brand": "NVIDIA", "Device": "NVIDIA Shield TV Remote", "Region": "Global"},
    {"Brand": "TiVo", "Device": "TiVo Stream 4K Remote", "Region": "NA"},
    # [2] 글로벌 TV 제조사
    {
        "Brand": "Samsung",
        "Device": "Samsung SolarCell Remote (TM2360E)",
        "Region": "Korea",
    },
    {
        "Brand": "Samsung",
        "Device": "Samsung Smart Control (BN59 Series)",
        "Region": "Korea",
    },
    {
        "Brand": "LG Electronics",
        "Device": "LG Magic Remote (MR23GN / MR24)",
        "Region": "Korea",
    },
    {
        "Brand": "LG Electronics",
        "Device": "LG Standard IR Remote",
        "Region": "Korea",
    },
    {
        "Brand": "Sony",
        "Device": "Sony Bravia Premium Backlit Remote",
        "Region": "Japan",
    },
    {"Brand": "Sony", "Device": "Sony Bravia Voice Remote", "Region": "Japan"},
    {
        "Brand": "Panasonic",
        "Device": "Panasonic Viera Voice Remote",
        "Region": "Japan",
    },
    {
        "Brand": "Panasonic",
        "Device": "Panasonic Fire TV Built-in Remote",
        "Region": "Japan",
    },
    {
        "Brand": "Sharp",
        "Device": "Sharp AQUOS Voice Remote Control",
        "Region": "Japan",
    },
    {"Brand": "Sharp", "Device": "Sharp Android TV Remote", "Region": "Japan"},
    {"Brand": "TCL", "Device": "TCL RC902V Voice Remote", "Region": "Global"},
    {
        "Brand": "Hisense",
        "Device": "Hisense ERF3A80 Voice Remote",
        "Region": "Global",
    },
    {
        "Brand": "Philips",
        "Device": "Philips Ambilight TV Remote",
        "Region": "EU",
    },
    {
        "Brand": "Xiaomi",
        "Device": "Xiaomi Mi TV Bluetooth Remote",
        "Region": "ASIA",
    },
    {"Brand": "Vizio", "Device": "Vizio SmartCast Voice Remote", "Region": "NA"},
    # [3] 유럽 전략 방송통신사
    {
        "Brand": "LGI (Virgin Media)",
        "Device": "Virgin TV 360 Voice Remote",
        "Region": "EU",
    },
    {
        "Brand": "LGI (Virgin Media)",
        "Device": "Liberty Global Horizon EOS Remote",
        "Region": "EU",
    },
    {"Brand": "Canal+", "Device": "Le Décodeur CANAL+ 4K Remote", "Region": "EU"},
    {"Brand": "Canal+", "Device": "Canal+ Voice Remote Control", "Region": "EU"},
    {
        "Brand": "Orange",
        "Device": "Orange Livebox TV UHD Remote",
        "Region": "EU",
    },
    {"Brand": "Orange", "Device": "Orange TV 4K Remote Control", "Region": "EU"},
    {
        "Brand": "Deutsche Telekom",
        "Device": "Deutsche Telekom MagentaTV One Remote",
        "Region": "EU",
    },
    {
        "Brand": "Deutsche Telekom",
        "Device": "MagentaTV Stick Voice Remote",
        "Region": "EU",
    },
    {
        "Brand": "Vodafone",
        "Device": "Vodafone GigaTV Home Voice Remote",
        "Region": "EU",
    },
    {"Brand": "Vodafone", "Device": "Vodafone TV UHD Remote", "Region": "EU"},
    {"Brand": "Sky Group", "Device": "Sky Q Voice Remote", "Region": "EU"},
    {"Brand": "Sky Group", "Device": "Sky Glass Motion Remote", "Region": "EU"},
    {"Brand": "Telefonica", "Device": "Movistar+ Voice Remote", "Region": "EU"},
    # [4] 아시아 핵심 방송통신사
    {
        "Brand": "KT (지니TV)",
        "Device": "KT Genie TV Smart Remote (지니TV 리모컨)",
        "Region": "Korea",
    },
    {
        "Brand": "SKB (B tv)",
        "Device": "SK Broadband B tv Smart Sound Remote (Btv 리모컨)",
        "Region": "Korea",
    },
    {
        "Brand": "LGU+ (U+tv)",
        "Device": "LG Uplus U+tv Earphone Remote (유플러스 리모컨)",
        "Region": "Korea",
    },
    {
        "Brand": "Tata Play",
        "Device": "Tata Play Binge+ Voice Remote",
        "Region": "ASIA",
    },
    {
        "Brand": "Airtel",
        "Device": "Airtel Xstream Box Voice Remote",
        "Region": "ASIA",
    },
    {"Brand": "J:COM", "Device": "J:COM LINK 4K Remote", "Region": "ASIA"},
    {
        "Brand": "Hikari TV",
        "Device": "Hikari Smart Voice Remote",
        "Region": "ASIA",
    },
    {
        "Brand": "Foxtel",
        "Device": "Foxtel Voice Remote (iQ5 / Hubbl)",
        "Region": "ASIA",
    },
    # [5] 아프리카 3대 Pay-TV & 위성 플랫폼
    {
        "Brand": "MultiChoice (DStv)",
        "Device": "DStv Explora Ultra Voice Remote",
        "Region": "Africa",
    },
    {
        "Brand": "MultiChoice (DStv)",
        "Device": "DStv Explora A9 Remote",
        "Region": "Africa",
    },
    {
        "Brand": "StarTimes",
        "Device": "StarTimes Digital TV Remote",
        "Region": "Africa",
    },
    {
        "Brand": "Canal+ Afrique",
        "Device": "Canal+ Afrique HD Decoder Remote",
        "Region": "Africa",
    },
    # [6] 북미/중남미 주요 방송통신사
    {"Brand": "Comcast", "Device": "Xfinity XR15 Voice Remote", "Region": "NA"},
    {"Brand": "Comcast", "Device": "Xfinity XR16 Flex Remote", "Region": "NA"},
    {"Brand": "Charter", "Device": "Spectrum Voice Remote", "Region": "NA"},
    {
        "Brand": "DirecTV",
        "Device": "DirecTV Stream Gemini Voice Remote",
        "Region": "NA",
    },
    {"Brand": "DISH Network", "Device": "DISH Voice Remote 54.0", "Region": "NA"},
    {"Brand": "Cox", "Device": "Cox Contour Voice Remote", "Region": "NA"},
    {"Brand": "Rogers", "Device": "Rogers Ignite Voice Remote", "Region": "NA"},
    {"Brand": "Claro", "Device": "Claro TV+ 4K Remote", "Region": "SCA"},
    {"Brand": "Vrio Corp", "Device": "DIRECTV GO / SKY Remote", "Region": "SCA"},
    {
        "Brand": "Televisa (izzi)",
        "Device": "izzi Smart Voice Remote",
        "Region": "SCA",
    },
    # [7] 스마트홈 / 통합 제어 리모컨
    {
        "Brand": "SofaBaton",
        "Device": "SofaBaton X1S Universal Remote",
        "Region": "Global",
    },
    {
        "Brand": "SofaBaton",
        "Device": "SofaBaton U2 Universal Remote",
        "Region": "Global",
    },
    {
        "Brand": "Control4",
        "Device": "Control4 Halo Touch Remote",
        "Region": "NA",
    },
    {"Brand": "Savant", "Device": "Savant Pro Remote X2", "Region": "NA"},
    {"Brand": "Crestron", "Device": "Crestron TSR-310 Remote", "Region": "NA"},
    {
        "Brand": "Logitech",
        "Device": "Logitech Harmony Companion",
        "Region": "Global",
    },
    {
        "Brand": "Josh.ai",
        "Device": "Josh Remote Handheld Controller",
        "Region": "NA",
    },
    {"Brand": "Basalte", "Device": "Basalte Miro Luxury Remote", "Region": "EU"},
    {"Brand": "Loxone", "Device": "Loxone Remote Air", "Region": "EU"},
    {"Brand": "Somfy", "Device": "Somfy Situo / Nina RTS Remote", "Region": "EU"},
    {"Brand": "Tuya", "Device": "Tuya Smart Universal IR Hub", "Region": "Global"},
]


# -------------------------------------------------------------
# 2. 지역별 언어 맞춤 검색 쿼리 생성기
# -------------------------------------------------------------
def get_localized_queries(device, brand, region):
  queries = [f'"{device}" review "problem" OR "issue" OR "not working"']

  # 1. 한국 (KR)
  if brand in ["KT (지니TV)", "SKB (B tv)", "LGU+ (U+tv)"] or (
      region == "Korea" and brand in ["Samsung", "LG Electronics"]
  ):
    queries.append(f'"{device}" 리모컨 먹통 OR 고장 OR "연결 안됨" OR "배터리"')

  # 2. 일본 (JP)
  elif brand in ["Sharp", "Panasonic", "Sony", "J:COM", "Hikari TV"]:
    queries.append(f'"{device}" リモコン "反応しない" OR 故障 OR ペアリング OR 電池')

  # 3. 프랑스 / 서유럽 (FR/EU)
  elif brand in ["Canal+", "Orange"]:
    queries.append(
        f'"{device}" télécommande "problème" OR panne OR synchro OR pile'
    )

  # 4. 독일 / 중유럽 (DE/EU)
  elif brand in ["Deutsche Telekom", "Vodafone"]:
    queries.append(
        f'"{device}" Fernbedienung "funktioniert nicht" OR defekt OR Batterien'
    )

  # 5. 영국 / 유럽 전문 포럼 (UK/EU)
  elif brand in ["LGI (Virgin Media)", "Sky Group", "Philips"]:
    queries.append(
        f'site:avforums.com "{device}" "remote" OR "battery drain" OR CEC'
    )

  # 6. 인도 / 아시아태평양 (IN/APAC)
  elif brand in ["Tata Play", "Airtel"]:
    queries.append(
        f'"{device}" remote "pairing failed" OR "hang" OR complaint OR "battery"'
    )

  # 7. 아프리카 (Africa)
  elif brand in ["MultiChoice (DStv)", "StarTimes", "Canal+ Afrique"]:
    queries.append(
        f'"{device}" remote "load shedding" OR "takealot" OR "battery leak"'
    )

  # 8. 북미 및 글로벌 공통
  else:
    queries.append(
        f'"{device}" remote "button click" OR "battery drain" OR "disconnect"'
    )

  return queries


def collect_advanced_voc():
  today_str = datetime.now().strftime("%Y-%m-%d")
  db_file = "voc_db.csv"

  if os.path.exists(db_file):
    try:
      old_df = pd.read_csv(db_file, encoding="utf-8-sig")
    except Exception:
      old_df = pd.read_csv(db_file, encoding="utf-8")
    existing_reviews = set(old_df["Review"].astype(str).str.strip())
  else:
    old_df = pd.DataFrame(
        columns=["Collected_Date", "Source", "Brand", "Sentiment", "Review"]
    )
    existing_reviews = set()

  new_data = []

  # -------------------------------------------------------------
  # 1. Google Play Store 대량 수집 (국가 코드 및 언어별 타깃팅)
  # -------------------------------------------------------------
  playstore_apps = {
      # [한국]
      "com.kt.otn": ("KT (지니TV)", "지니 TV 모바일", "kr", "ko"),
      "com.skb.btvmobile": ("SKB (B tv)", "모바일 B tv", "kr", "ko"),
      "uplus.tv.remote": ("LGU+ (U+tv)", "U+tv 리모컨", "kr", "ko"),
      # [일본]
      "jp.co.sharp.aquos.remocon": (
          "Sharp",
          "AQUOS Remote Player",
          "jp",
          "ja",
      ),
      "com.panasonic.pavc.viera.nremote3": (
          "Panasonic",
          "TV Remote 3",
          "jp",
          "ja",
      ),
      # [인도]
      "com.tatasky.hd": ("Tata Play", "Tata Play Mobile", "in", "en"),
      "airtel.myself.amigo": ("Airtel", "Airtel Xstream", "in", "en"),
      # [유럽]
      "fr.canal.android.canal": ("Canal+", "myCANAL", "fr", "fr"),
      "com.orange.owtv": ("Orange", "Orange TV", "fr", "fr"),
      "de.telekom.magentatv.atv": (
          "Deutsche Telekom",
          "MagentaTV",
          "de",
          "de",
      ),
      "com.vodafone.vodafonetv": ("Vodafone", "Vodafone TV", "de", "de"),
      "com.virginmedia.tvanywhere": (
          "LGI (Virgin Media)",
          "Virgin TV Go",
          "gb",
          "en",
      ),
      "com.bskyb.skyq": ("Sky Group", "Sky Q Remote App", "gb", "en"),
      # [아프리카]
      "com.multichoice.mydstv": (
          "MultiChoice (DStv)",
          "MyDStv",
          "za",
          "en",
      ),
      "com.star.mobile.video": ("StarTimes", "StarTimes ON", "za", "en"),
      # [글로벌 / 북미]
      "com.control4.os3": ("Control4", "Control4 OS3", "us", "en"),
      "com.savanttech.savantpro": ("Savant", "Savant Pro", "us", "en"),
      "ai.josh.app": ("Josh.ai", "Josh.ai", "us", "en"),
      "com.samsung.android.oneconnect": (
          "Samsung",
          "SmartThings",
          "us",
          "en",
      ),
      "com.lgeha.nuts": ("LG Electronics", "LG ThinQ", "us", "en"),
      "com.tcl.magiconnect": ("TCL", "TCL MagiConnect", "us", "en"),
      "com.google.android.videos": ("Google", "Google TV", "us", "en"),
      "com.xfinity.remote": ("Comcast", "Xfinity Remote", "us", "en"),
      "com.amazon.storm.lightning.client.aosp": (
          "Amazon Fire TV",
          "Fire TV App",
          "us",
          "en",
      ),
  }

  print(
      "\n[1/4] 📱 Google Play Store 지역별(유럽·아시아·아프리카·북미) 정밀"
      " 수집 중..."
  )
  for (
      app_id,
      (brand, app_name, country_code, lang_code),
  ) in playstore_apps.items():
    try:
      res, _ = reviews(
          app_id,
          lang=lang_code,
          country=country_code,
          sort=Sort.NEWEST,
          count=300,
      )
      added_count = 0
      for rev in res:
        text = rev.get("content", "").strip()
        review_full = f"[{app_name}] {text[:350]}"
        if len(text) < 15 or review_full in existing_reviews:
          continue

        existing_reviews.add(review_full)
        sentiment = "Positive" if rev["score"] >= 4 else "Negative"

        new_data.append({
            "Collected_Date": today_str,
            "Source": f"Google Play ({country_code.upper()})",
            "Brand": brand,
            "Sentiment": sentiment,
            "Review": review_full,
        })
        added_count += 1
      print(
          f"  - [{country_code.upper()}] {brand} ({app_name}): 신규"
          f" {added_count}건 추가"
      )
    except Exception:
      continue

  # -------------------------------------------------------------
  # 2. YouTube 권역별 리뷰 영상 댓글 수집
  # -------------------------------------------------------------
  print("\n[2/4] 🎬 YouTube 권역별 실사용 리뷰 댓글 파싱 중...")
  try:
    downloader = YoutubeCommentDownloader()
    youtube_videos = [
        # 유럽
        ("LGI (Virgin Media)", "https://www.youtube.com/watch?v=k4u0bH9V_dI"),
        ("Canal+", "https://www.youtube.com/watch?v=0kFvW7rS4s4"),
        ("Deutsche Telekom", "https://www.youtube.com/watch?v=wXW5Z4Qz8Wk"),
        ("Orange", "https://www.youtube.com/watch?v=u6Gv1y6s5xU"),
        ("Vodafone", "https://www.youtube.com/watch?v=E_P9Zz3q9g8"),
        # 아시아
        ("Samsung", "https://www.youtube.com/watch?v=1F_U7f0oXgQ"),
        ("LG Electronics", "https://www.youtube.com/watch?v=vV1r3k7Y2hA"),
        ("Sony", "https://www.youtube.com/watch?v=x2e1l9_z_pM"),
        ("Tata Play", "https://www.youtube.com/watch?v=n8-6h2gqJg8"),
        # 아프리카
        ("MultiChoice (DStv)", "https://www.youtube.com/watch?v=Yf9pYQGq5Q4"),
        ("StarTimes", "https://www.youtube.com/watch?v=UqQ_xNnF1c8"),
        # 글로벌 / 북미
        ("Apple", "https://www.youtube.com/watch?v=r0vVqP2_p8U"),
        ("Amazon Fire TV", "https://www.youtube.com/watch?v=9L8K2p6J0lU"),
        ("Control4", "https://www.youtube.com/watch?v=gA_b78Y4jQc"),
        ("Savant", "https://www.youtube.com/watch?v=F070Vb20Ym8"),
    ]

    multilingual_keywords = [
        "remote",
        "button",
        "work",
        "issue",
        "battery",
        "pair",
        "bad",
        "click",
        "lag",
        "리모컨",
        "연결",
        "먹통",
        "배터리",
        "リモコン",
        "反応",
        "故障",
        "電池",
        "télécommande",
        "synchro",
        "panne",
        "Fernbedienung",
        "defekt",
        "drücken",
        "load shedding",
        "explora",
        "decoder",
    ]

    for brand, url in youtube_videos:
      try:
        comments = downloader.get_comments_from_url(url, sort_by=SORT_BY_POPULAR)
        count = 0
        for comment in comments:
          if count >= 80:
            break
          text = comment.get("text", "").strip()
          if len(text) < 15 or text in existing_reviews:
            continue

          t_lower = text.lower()
          if not any(k.lower() in t_lower for k in multilingual_keywords):
            continue

          existing_reviews.add(text)
          positive_indicators = [
              "love",
              "great",
              "good",
              "best",
              "awesome",
              "좋아",
              "parfait",
              "gut",
              "最高",
          ]
          sentiment = (
              "Positive"
              if any(w in t_lower for w in positive_indicators)
              else "Negative"
          )

          new_data.append({
              "Collected_Date": today_str,
              "Source": "YouTube Community",
              "Brand": brand,
              "Sentiment": sentiment,
              "Review": text[:350],
          })
          count += 1
        print(f"  - {brand} 영상 댓글: 신규 {count}건 추가")
      except Exception:
        continue
  except Exception:
    pass

  # -------------------------------------------------------------
  # 3. Reddit 권역별 서브레딧 수집
  # -------------------------------------------------------------
  print("\n[3/4] 💬 Reddit 유럽·아시아·아프리카 포럼 수집 중...")
  reddit_targets = [
      ("VirginMedia", "LGI (Virgin Media)"),
      ("canalplus", "Canal+"),
      ("telekom", "Deutsche Telekom"),
      ("vodafone", "Vodafone"),
      ("orange", "Orange"),
      ("AVForums", "Sky Group"),
      ("korea", "KT (지니TV)"),
      ("japanlife", "Sony"),
      ("IndiaTech", "Tata Play"),
      ("DStv", "MultiChoice (DStv)"),
      ("southafrica", "MultiChoice (DStv)"),
      ("Control4", "Control4"),
      ("savant", "Savant"),
      ("Joshai", "Josh.ai"),
      ("samsung", "Samsung"),
      ("LGOLED", "LG Electronics"),
      ("tcltvs", "TCL"),
      ("Panasonic", "Panasonic"),
      ("bravia", "Sony"),
      ("Roku", "Roku"),
      ("firetv", "Amazon Fire TV"),
      ("appletv", "Apple"),
      ("ShieldAndroidTV", "NVIDIA"),
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
        if not any(
            w in t_lower
            for w in [
                "remote",
                "control",
                "app",
                "button",
                "issue",
                "cec",
                "battery",
                "lag",
                "pairing",
                "decoder",
                "리모컨",
                "télécommande",
            ]
        ):
          continue

        existing_reviews.add(text)
        sentiment = (
            "Positive"
            if any(w in t_lower for w in ["love", "great", "fixed", "good"])
            else "Negative"
        )

        new_data.append({
            "Collected_Date": today_str,
            "Source": f"Reddit (r/{sub})",
            "Brand": brand,
            "Sentiment": sentiment,
            "Review": text[:350],
        })
        count += 1
      print(f"  - r/{sub} ({brand}): 신규 {count}건 추가")
    except Exception:
      continue

  # -------------------------------------------------------------
  # 4. DuckDuckGo 다국어 웹 검색 (💡 순수 고객 VoC 실시간 필터 적용)
  # -------------------------------------------------------------
  print(
      f"\n[4/4] 🌐 다국어 맞춤 웹/포럼 심층 수집 및 순수 VoC 필터링 (총"
      f" {len(TARGET_RCU_LIST)}개 모델)..."
  )

  with DDGS() as ddgs:
    for idx, item in enumerate(TARGET_RCU_LIST, 1):
      brand = item["Brand"]
      device = item["Device"]
      region = item["Region"]
      dev_count = 0

      max_fetch = (
          10
          if region in ["EU", "Africa", "Korea"]
          or brand in ["Sony", "Sharp", "Tata Play"]
          else 6
      )
      localized_queries = get_localized_queries(device, brand, region)

      for query in localized_queries:
        if dev_count >= max_fetch:
          break
        try:
          results = list(ddgs.text(query, max_results=6))
          for res in results:
            body = res.get("body", "").strip()

            # 1차 중복 검사
            if len(body) < 30 or body in existing_reviews:
              continue

            # 💡 [핵심] 회사 소개/쇼핑몰 광고/단순 스펙 글 실시간 차단
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

          time.sleep(random.uniform(0.4, 0.8))
        except Exception:
          time.sleep(0.8)
          continue

      print(
          f"  - [{idx}/{len(TARGET_RCU_LIST)}] [{region}] {device}: 신규"
          f" {dev_count}건 (광고/소개글 배제 완료)"
      )

  # -------------------------------------------------------------
  # 5. 데이터 병합, 중복 제거 및 CSV 저장
  # -------------------------------------------------------------
  if not new_data:
    print("\nℹ️ 새로 수집된 신규 리뷰가 없습니다. 기존 데이터를 유지합니다.")
    return

  new_df = pd.DataFrame(new_data)
  combined_df = (
      pd.concat([old_df, new_df], ignore_index=True)
      .drop_duplicates(subset=["Review"], keep="first")
      .reset_index(drop=True)
  )

  combined_df.to_csv(db_file, index=False, encoding="utf-8-sig")
  print(
      f"\n🎉 [수집 완료] 신규 {len(new_data):,}건 수집 완료! 총 누적:"
      f" {len(combined_df):,}건이 voc_db.csv에 UTF-8-BOM으로 저장되었습니다."
  )


if __name__ == "__main__":
  collect_advanced_voc()