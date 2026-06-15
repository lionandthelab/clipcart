## 0. 목표

이 프로젝트의 목표는 생활문제 해결형 affiliate 숏폼 사업을 최대한 자동화하는 것이다.

운영자는 플랫폼 가입, affiliate 계정 생성, TopView 영상 생성, 최종 승인만 담당한다.

AI Agent는 아래 작업을 담당한다.

1. 인터넷에서 판매 가능성이 높은 생활문제 해결형 상품을 찾는다.
2. 상품을 점수화한다.
3. 운영자에게 TopView 입력용 제품 링크만 넘긴다.
4. 운영자가 TopView로 만든 영상을 업로드 폴더에 넣으면, 플랫폼별 문구를 만들고 예약/게시한다.
5. 게시 후 성과를 수집한다.
6. 성과가 좋은 상품과 포맷을 기준으로 다음 상품 탐색 루프를 반복한다.

핵심 원칙:

* AI가 임의로 상품을 구매하거나 결제하지 않는다.
* AI가 플랫폼 약관을 우회하지 않는다.
* 업로드는 공식 API 또는 허용된 스케줄러만 사용한다.
* 건강, 의료, 금융, 다이어트, 유아 안전, 전기 안전, 식품, 화장품 효능 주장은 제외한다.
* affiliate 관계는 모든 게시물에 명확히 고지한다.
* 사람의 승인 없이는 신규 상품을 게시하지 않는다.
* 사람의 승인 없이는 과장 문구, 효능 주장, 비교 우위 주장을 확정하지 않는다.

### 플랫폼·규제 제약

* YouTube: Data API로 업로드 가능 ([Upload a Video | YouTube Data API](https://developers.google.com/youtube/v3/guides/uploading_a_video))
* Instagram: Meta Content Publishing API로 Reels 게시 가능
* TikTok: Content Posting API의 Direct Post 흐름 사용
* 각 플랫폼 OAuth, 권한, 앱 심사, 계정 조건은 별도로 맞춰야 한다.
* affiliate/협찬성 콘텐츠는 광고·수수료 관계를 명확히 고지해야 한다. 국내 운영이면 공정위 추천·보증 광고 고지 리스크도 같이 봐야 한다. ([KFTC Influencer Marketing Handbook](https://www.kimchang.com/en/insights/detail.kc?idx=21962&sch_section=4))

---

## 0.5 멀티 머신 운영 · 동기화 (실전 런북, 2026-06-12)

> 실제 구현·운영 규칙의 **권위 문서는 루트 `CLAUDE.md`** 다. 아래 4장 이하의 개념 스펙과 충돌하면 CLAUDE.md/코드를 따른다.
> 이 절은 **여러 머신(예: Windows + macOS)에서 같은 채널을 중복·충돌 없이 돌리기 위한** 운영 런북이다.

### 단일 진실원천 = git 저장소
- **git 추적(모든 머신 공유):** 코드 `src/`, 스케줄 스크립트 `scripts/`, 폰트 `assets/`(Black Han Sans), **게시 원장 `data/*.json`(history/posts/products/niche_state…)**.
- **git 미추적(머신마다 따로 준비):** `.env`(키/비밀), `.venv/`, `tools/ffmpeg/`, `outbox/`, `logs/`.

### 새 머신 셋업 순서
1. `git clone` → `python -m venv .venv` → `.venv`에서 `pip install -e .`
2. `.env` 준비(steward-lab .env에서 복사). 필수 키: `COUPANG_ACCESS_KEY/COUPANG_SECRET_KEY/COUPANG_SUB_ID`, `ALIEXPRESS_APP_KEY/ALIEXPRESS_APP_SECRET/ALIEXPRESS_TRACKING_ID`, `YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN`, `TYPECAST_API_KEY`, `PEXELS_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`(Kling), `ELEVENLABS_API_KEY`(선택). META/TIKTOK/PINTEREST는 해당 게시 시.
3. ffmpeg: `tools/ffmpeg` 없으면 `imageio-ffmpeg` 폴백이 자동 사용됨.
4. 스케줄 등록(**OS 레벨이라 git에 없음 → 머신마다 직접 등록**):
   - **Windows 작업 스케줄러:** `ClipcartDaily`(쿠팡, 매일 07:20 → `scripts/daily_task.ps1`), `ClipcartAli`(알리, 매일 13:00 1회 → `scripts/ali_daily.ps1`). 작업 인자는 `-NoProfile -ExecutionPolicy Bypass -File "<절대경로>\scripts\xxx.ps1"`(앞 공백/끝 백슬래시 금지 — 깨지면 즉시 실패).
   - **macOS launchd:** `com.clipcart.ali-daily`(알리, 6시간 00/06/12/18 → `scripts/ali_daily.sh`, `~/Library/LaunchAgents`).
5. ⚠️ **스크립트 내 절대경로를 자기 머신에 맞게 수정**: `daily_task.ps1`/`ali_daily.ps1`는 `c:\Users\ikess\...`, `ali_daily.sh`는 `/Users/mac/...`로 하드코딩돼 있다. 새 머신은 자기 프로젝트 경로로 바꿔야 동작한다.

### 머신 간 중복 방지 = `data/history.json` + git 동기화 (핵심)
- **`data/history.json`**(append-only)이 dedup 권위 원장. 차단 키: 쿠팡상품ID / 알리상품ID / 정규화 상품명(타 판매자 동일상품 포함) / 니치 키워드 갭(`CLIPCART_KEYWORD_GAP_DAYS`, 기본 10일).
- **모든 스케줄 스크립트는** ① 실행 **전 `git pull --rebase --autostash`**(다른 머신 게시분을 history에 반영 → 같은 상품/니치 회피) ② 게시 **후 `data` commit → pull → push**(이번 게시분을 다른 머신에 공유). 충돌 시 `git rebase --abort`로 저장소를 깨끗이 유지(다음 실행에서 재동기화).
- 결과: 각 머신이 상대 게시분을 보고 중복을 피한다. **양쪽 머신이 자주 pull/push할수록 안전.**

### 주의 / 한계
- history.json은 pretty JSON 배열이라 **두 머신이 거의 동시에 게시하면 rebase 충돌** 가능. 스케줄 시각을 겹치지 않게 둘 것(현재 Windows 07:20·13:00 / Mac 00·06·12·18). 충돌이 잦아지면 **JSONL(레코드=한 줄) 전환**이 근본 해결책.
- 충돌로 push가 막히면 게시분은 로컬에만 남는다 → 수동 `git pull --rebase` 후 history.json의 **양쪽 항목을 모두 살려** 머지하고 push.
- `*.sh`는 `.gitattributes`로 LF 고정(Windows에서 저장돼도 macOS 셸이 깨지지 않게).
- 의무 고지는 **확정형만** 인정("…수수료를 제공받습니다"), 소스별 분기(쿠팡/알리). `compliance.py`가 하드게이트 + `sanitize_text`로 생성 문구의 금지어 정화. (아래 4.3의 옛 '받을 수 있습니다' 표현은 공정위 2024-12 개정으로 **폐기**.)

---

## 0.6 링크 퍼널 · 전환 측정 (실전 런북, 2026-06-15)

> 조회수가 아니라 **클릭·구매**가 목표(CLAUDE.md §14). 이 절은 "영상 → 링크 → 구매" 퍼널을 어떻게 잇고 측정하는지의 권위 런북이다.

### 단일 링크 퍼널 = bio 페이지

- **bio 페이지**가 모든 제품 링크의 단일 모음. 공개 URL: **`https://lionandthelab.github.io/clipcart/bio/`** (GitHub Pages, master `/docs`에서 서빙).
- **운영자 필수 1회 작업:** YouTube 채널 '링크'(프로필)에 위 URL을 등록. 영상 CTA가 "프로필 링크"를 가리키므로 이게 없으면 퍼널이 끊긴다. `.env`의 `LINK_IN_BIO_URL`도 같은 값.
- 생성기: `src/clipcart/bio/page.py` (`clipcart bio`). 현재 **실공개 중인** YouTube 영상의 제품만 최신순으로 — '오늘의 제품' 강조 + 카테고리 그룹 + (알리) 할인율·판매량·만족도. 쿠팡은 검색 API가 평점/리뷰를 안 줘서 가격만.

### CTA 컨벤션 (영상 설명문)

- 설명문 템플릿: **`data/format_profile.json`의 `description_template`**. 순서: ① 훅 → ② **의무 고지(공정위: 첫 부분, 250자 이내)** → ③ 직접 제품링크(상품별 subId) → ④ bio/프로필 링크 → 추천대상/장점/단점 → 해시태그.
- **"고정 댓글" 의존 금지.** YouTube Data API는 댓글 핀을 지원하지 않아(`daily.py` manual_steps, 수동) AUTO 모드에서 누락되면 막다른 길이 된다. 링크 유도는 **직접 링크 + 프로필(bio)** 로만.
- in-video 자막/내레이션 CTA는 영상 엔진(`src/clipcart/video/**`, 외부 머지 대기)이라 머지 후 동일 방향으로 정렬.

### 자동 동기화 (앞으로 만들 때마다 자동 반영)

- 스케줄러(`scripts/daily_task.ps1`, `scripts/ali_daily.sh`)가 **매 게시 후** `clipcart metrics`(실공개 상태 정정) → `clipcart bio`(페이지 재생성) → `git add data docs/bio` → commit/pull/push 한다. **신규 업로드·운영자 삭제가 bio에 자동 반영**된다.
- 수동 동기화도 동일: `clipcart bio` (삭제·비공개 영상은 자동 제외).

### 측정 (subId)

- 정산은 계정 trackingCode 기준, **subId는 리포트 분류용 자유값**(`coupang.py` `make_sub_id`, 2026-06-12 실측). 영상별 `salrimshorts{상품ID}`, bio는 `bio{상품ID}`로 분리 측정. 알리는 subId 미지원.
- 확인: `clipcart analyze` (소스·훅·카테고리·subId 귀속 집계).
- **2026-06-15 진단:** 30일간 영상/bio per-product subId 클릭 0(딥링크의 `subid=` 임베드는 정상 검증 → 측정 버그 아닌 실제 미클릭). 빈 subId 매출은 채널 외 유입(레거시·운영자 본인 쿠팡 사용). → 조회→클릭이 병목. CTA를 bio로 통일한 효과는 영상 subId에 클릭이 잡히기 시작하는지로 확인.

### 과거 영상 백필

- 설명문 템플릿을 바꾸면 **이미 올라간 영상**은 옛 설명문 그대로다. 맞추려면:
  `python scripts/retrofit_descriptions.py --live` (제목·태그 보존, description만 현재 템플릿으로, 게시 전 컴플라이언스 게이트 동일 적용. dry-run은 플래그 없이 실행).

자세한 배경·진단은 [docs/conversion-funnel.md](docs/conversion-funnel.md).

---

## 1. 사업 컨셉

### 브랜드명

살림해결소

### 포지셔닝

생활 속 불편함을 줄이는 문제 해결형 제품을 짧게 소개하는 숏폼 affiliate 채널.

### 타깃

* 자취생
* 신혼부부
* 1~2인 가구
* 반려동물 가구
* 정리/청소에 시간을 쓰기 싫은 사람
* 주방, 욕실, 세탁, 수납 문제를 빠르게 해결하고 싶은 사람

### 초기 카테고리

1. 주방 문제 해결템
2. 청소 문제 해결템
3. 정리/수납 문제 해결템
4. 욕실 문제 해결템
5. 세탁/건조 문제 해결템
6. 반려동물 털/냄새 관리템

### 제외 카테고리

아래 카테고리는 초기 운영에서 제외한다.

* 건강기능식품
* 의약품
* 의료기기
* 다이어트 제품
* 화장품 효능 중심 제품
* 유아 안전용품
* 전기 안전 리스크가 큰 제품
* 고가 가전
* 식품
* 주류
* 담배/니코틴
* 성인용품
* 투자/금융 상품
* 효과 입증이 어려운 미신성 제품
* 과장 표현 없이는 팔기 어려운 제품

---

## 2. 전체 자동화 구조

```text
Product Research Agent
  ↓
Product Scoring Agent
  ↓
Compliance Filter Agent
  ↓
Human Approval Gate 1: 상품 승인
  ↓
TopView Handoff Agent
  ↓
Human Task: TopView 영상 생성
  ↓
Video Intake Agent
  ↓
Caption & Disclosure Agent
  ↓
Human Approval Gate 2: 업로드 승인
  ↓
Publishing Agent
  ↓
Analytics Agent
  ↓
Learning Loop Agent
  ↓
Product Research Agent
```

---

## 3. Human-in-the-loop 플로우

이 프로젝트는 완전 자동 게시가 아니라 승인 기반 자동화로 운영한다.

### Gate 1: 상품 승인

AI가 상품 후보를 찾고 점수화한 뒤, 운영자에게 아래 형식으로만 제안한다.

```json
{
  "date": "YYYY-MM-DD",
  "batch_id": "batch_001",
  "products": [
    {
      "product_id": "P001",
      "product_name": "창틀 틈새 청소 브러시",
      "category": "청소",
      "product_url": "https://...",
      "affiliate_url": "https://...",
      "price": 8900,
      "reason": "문제 장면과 해결 장면이 명확함",
      "risk": "곰팡이 제거 효과 과장 금지",
      "score": 87,
      "recommended_angle": "물티슈로 창틀 닦는 불편함 해결"
    }
  ]
}
```

운영자는 아래 중 하나로 응답한다.

```text
APPROVE P001, P003, P007
REJECT P002, P004
REVISE P005: 가격 2만원 이하 대체품 찾아줘
```

AI는 `APPROVE` 된 상품만 TopView 제작 대상으로 넘긴다.

### Gate 2: TopView 영상 생성

AI는 승인된 상품에 대해 운영자에게 TopView 작업용 정보만 제공한다.

```json
{
  "product_id": "P001",
  "product_url": "https://...",
  "affiliate_url": "https://...",
  "topview_prompt": "...",
  "must_show": [
    "문제 장면",
    "제품 사용 장면",
    "결과 장면",
    "단점 1개"
  ],
  "must_not_say": [
    "완벽 제거",
    "무조건",
    "100%",
    "평생 해결"
  ]
}
```

운영자는 TopView에서 영상을 만든 뒤 아래 위치에 파일을 넣는다.

```text
/inbox/videos/P001.mp4
```

또는 아래 메타데이터를 업데이트한다.

```json
{
  "product_id": "P001",
  "video_path": "/inbox/videos/P001.mp4",
  "status": "VIDEO_READY"
}
```

### Gate 3: 업로드 승인

AI는 영상 파일을 감지하면 업로드 전 패키지를 만든다.

```json
{
  "product_id": "P001",
  "platforms": ["youtube_shorts", "instagram_reels", "tiktok"],
  "title": "창틀 청소 아직도 물티슈로 하세요?",
  "caption": "...",
  "hashtags": ["#청소템", "#생활꿀템", "#살림템"],
  "disclosure": "이 콘텐츠에는 affiliate 링크가 포함되어 있으며, 구매 시 일정 수수료를 받을 수 있습니다.",
  "pinned_comment": "제품 링크는 프로필에 정리해뒀습니다. affiliate 링크가 포함되어 있습니다.",
  "affiliate_url": "https://...",
  "risk_check": "PASS"
}
```

운영자는 아래 중 하나로 응답한다.

```text
PUBLISH P001
SCHEDULE P001 2026-06-10 19:30
REVISE P001: 제목을 덜 광고스럽게 바꿔
REJECT P001
```

AI는 `PUBLISH` 또는 `SCHEDULE` 명령이 있어야 게시한다.

### Gate 4: 성과 기반 루프 승인

AI는 매일 성과를 정리한다.

```json
{
  "date": "YYYY-MM-DD",
  "winners": [
    {
      "product_id": "P001",
      "reason": "프로필 클릭률 높음",
      "next_action": "같은 카테고리 유사 상품 10개 탐색"
    }
  ],
  "losers": [
    {
      "product_id": "P004",
      "reason": "조회수 대비 클릭 없음",
      "next_action": "중단"
    }
  ]
}
```

운영자는 아래 중 하나로 응답한다.

```text
LOOP APPROVE
LOOP PAUSE
LOOP ONLY 청소템
LOOP EXCLUDE 욕실템
```

`LOOP APPROVE` 없이는 신규 루프를 게시 단계까지 진행하지 않는다.

---

## 4. Agent 역할

## 4.1 Product Research Agent

### 역할

인터넷에서 생활문제 해결형 affiliate 상품 후보를 찾는다.

### 입력

```json
{
  "target_country": "KR",
  "categories": ["주방", "청소", "정리수납", "욕실"],
  "price_min": 3000,
  "price_max": 30000,
  "max_products": 30
}
```

### 검색 대상

* 쿠팡
* 네이버쇼핑
* Amazon
* AliExpress
* TikTok Shop
* YouTube Shopping 가능 상품
* 쇼핑몰 베스트셀러
* 리뷰 기반 커뮤니티
* 생활꿀템 관련 숏폼 트렌드
* 검색 자동완성
* 리뷰 많은 상품 목록

### 찾을 상품 조건

좋은 후보:

* 문제 장면이 3초 안에 보인다.
* 사용 전/후 차이가 크다.
* 가격이 낮다.
* 설명 없이 영상으로 이해된다.
* 충동구매 가능성이 있다.
* 리뷰 수가 많다.
* 평점이 안정적이다.
* 단점이 치명적이지 않다.
* affiliate 링크 생성이 가능하다.

나쁜 후보:

* 효과를 과장해야 팔린다.
* Before/After를 만들기 어렵다.
* 리뷰에 불량, 파손, 냄새, 배송 문제가 많다.
* 너무 흔한 바이럴템이다.
* 가격이 높다.
* 영상 소재가 지루하다.
* 규제 리스크가 있다.

### 출력

```json
{
  "product_id": "P001",
  "product_name": "",
  "category": "",
  "source": "",
  "product_url": "",
  "affiliate_url": "",
  "price": null,
  "rating": null,
  "review_count": null,
  "problem_statement": "",
  "video_angle": "",
  "before_scene": "",
  "after_scene": "",
  "main_benefit": "",
  "known_downside": "",
  "risk_notes": "",
  "raw_research_notes": ""
}
```

---

## 4.2 Product Scoring Agent

### 역할

상품 후보를 점수화한다.

### 점수 기준

```text
총점 =
문제 강도 30점
+ 영상화 용이성 25점
+ 충동구매성 20점
+ 리뷰 신뢰도 15점
+ 가격 적합성 10점
- 클레임 위험 20점
- 규제 위험 100점
```

### 세부 기준

문제 강도:

* 5점: 누구나 즉시 공감하는 불편함
* 4점: 특정 생활 패턴에서 자주 발생
* 3점: 있으면 좋지만 절박하지 않음
* 2점: 문제 인식이 약함
* 1점: 문제 자체가 애매함

영상화 용이성:

* 5점: Before/After가 명확함
* 4점: 사용 장면이 쉽게 보임
* 3점: 설명이 조금 필요함
* 2점: 화면만으로 이해 어려움
* 1점: 영상 소재로 부적합

충동구매성:

* 5점: 1만원대 이하, 바로 구매 가능
* 4점: 2만원대, 고민 적음
* 3점: 3만원대, 약간 고민
* 2점: 5만원 이상
* 1점: 고가

리뷰 신뢰도:

* 5점: 리뷰 많고 평점 안정적
* 4점: 리뷰 충분, 불만 적음
* 3점: 리뷰 보통
* 2점: 리뷰 적음
* 1점: 리뷰 불안정

클레임 위험:

* 5점: 불량/효과 논란 많음
* 4점: 품질 편차 큼
* 3점: 보통
* 2점: 낮음
* 1점: 매우 낮음

규제 위험:

* 의료, 건강, 식품, 다이어트, 유아 안전, 화장품 효능, 전기 안전 관련 주장이 필요하면 즉시 제외한다.

### 출력

```json
{
  "product_id": "",
  "score": 0,
  "score_breakdown": {
    "problem_strength": 0,
    "video_ease": 0,
    "impulse_buy": 0,
    "review_trust": 0,
    "price_fit": 0,
    "claim_risk": 0,
    "regulatory_risk": 0
  },
  "decision": "APPROVE_CANDIDATE | REJECT",
  "reason": "",
  "human_review_required": true
}
```

---

## 4.3 Compliance Filter Agent

### 역할

상품, 대본, 캡션, 자막, 고정댓글에서 위험 표현을 제거한다.

### 금지 표현

아래 표현은 쓰지 않는다.

```text
무조건
100%
완벽
평생
최고
압도적
효과 보장
냄새 완전 제거
곰팡이 완전 제거
세균 박멸
살균
항균
의사 추천
전문가 인증
공식 인증
아이에게 안전
반려동물에게 완전 안전
전기세 절감 보장
```

### 필수 고지

모든 게시물 설명 또는 고정댓글에 아래 문장을 포함한다.

```text
이 콘텐츠에는 affiliate 링크가 포함되어 있으며, 구매 시 일정 수수료를 받을 수 있습니다.
```

짧은 자막에는 아래 문장을 사용한다.

```text
affiliate 링크 포함
```

### 출력

```json
{
  "risk_check": "PASS | FAIL",
  "issues": [],
  "safe_caption": "",
  "safe_title": "",
  "safe_pinned_comment": "",
  "required_disclosure": ""
}
```

---

## 4.4 TopView Handoff Agent

### 역할

운영자가 TopView에서 영상을 만들 수 있도록 제품 링크와 영상 제작 지시문을 제공한다.

### 출력 형식

```json
{
  "product_id": "",
  "product_name": "",
  "product_url": "",
  "affiliate_url": "",
  "topview_prompt_ko": "",
  "topview_prompt_en": "",
  "video_structure": {
    "0-3s": "",
    "4-8s": "",
    "9-20s": "",
    "21-26s": "",
    "27-30s": ""
  },
  "must_include": [],
  "must_avoid": [],
  "disclosure_text": ""
}
```

### TopView 기본 프롬프트

```text
30초 세로형 숏폼 제품 영상 생성.

스타일:
- 실제 집에서 쓰는 느낌
- 빠른 템포
- 과장 없는 설명
- 문제 해결 중심
- Before/After 구조
- 한국어 자막
- 한국어 자연스러운 내레이션
- 마지막에 단점 1개 포함
- affiliate 고지 포함

구성:
0~3초: 생활 속 불편한 문제 장면
4~8초: 제품 등장
9~20초: 제품 사용 장면
21~26초: 결과 장면
27~30초: 단점 1개와 CTA

CTA:
제품 링크는 프로필에 정리해뒀습니다.

고지:
affiliate 링크가 포함되어 있습니다.
```

---

## 4.5 Video Intake Agent

### 역할

운영자가 만든 TopView 영상을 수집하고, 게시 가능 상태인지 확인한다.

### 입력 위치

```text
/inbox/videos
```

### 파일명 규칙

```text
{product_id}.mp4
```

예시:

```text
P001.mp4
```

### 검수 항목

* 세로 영상인지 확인
* 길이가 15~45초인지 확인
* 제품명 또는 상품 맥락이 맞는지 확인
* 금지 표현이 영상 자막에 없는지 확인
* affiliate 고지가 포함되어 있는지 확인
* 플랫폼별 업로드 가능 용량인지 확인
* 저작권 위험 음악이 있는지 확인

### 출력

```json
{
  "product_id": "",
  "video_path": "",
  "status": "VIDEO_READY | NEEDS_REVISION | REJECTED",
  "issues": []
}
```

---

## 4.6 Caption & Disclosure Agent

### 역할

플랫폼별 제목, 설명, 해시태그, 고정댓글을 만든다.

### YouTube Shorts 출력

```json
{
  "title": "",
  "description": "",
  "tags": [],
  "paid_promotion": true,
  "disclosure": ""
}
```

### Instagram Reels 출력

```json
{
  "caption": "",
  "hashtags": [],
  "branded_content_required": true,
  "disclosure": ""
}
```

### TikTok 출력

```json
{
  "caption": "",
  "hashtags": [],
  "disclosure": ""
}
```

### 문구 원칙

* 제품명보다 문제를 먼저 말한다.
* 과장하지 않는다.
* 단점 1개를 포함한다.
* 댓글 유도는 자연스럽게 한다.
* 링크는 프로필 또는 허용된 쇼핑 링크로 유도한다.
* affiliate 고지는 숨기지 않는다.

---

## 4.7 Publishing Agent

### 역할

운영자가 승인한 콘텐츠를 플랫폼에 게시하거나 예약한다.

### 게시 조건

아래 조건이 모두 참이어야 한다.

```json
{
  "human_approved_product": true,
  "video_ready": true,
  "compliance_pass": true,
  "human_publish_approved": true,
  "affiliate_disclosure_present": true
}
```

### 금지

* 사람 승인 없이 게시 금지
* 플랫폼 API 약관 우회 금지
* 비공식 브라우저 자동화로 로그인/게시 금지
* 댓글 도배 금지
* 동일 영상 대량 반복 게시 금지
* 고지 없는 affiliate 링크 게시 금지

### 게시 후 기록

```json
{
  "product_id": "",
  "platform": "",
  "post_id": "",
  "post_url": "",
  "published_at": "",
  "caption": "",
  "status": "PUBLISHED"
}
```

---

## 4.8 Analytics Agent

### 역할

게시 성과를 수집하고 다음 루프를 위한 판단 자료를 만든다.

### 수집 지표

```text
조회수
좋아요
댓글
저장
공유
프로필 클릭
링크 클릭
구매 수
수익
CTR
CVR
영상 지속률
댓글 내 구매 신호
```

### 구매 신호 댓글

아래 표현이 있으면 구매 신호로 분류한다.

```text
어디서 사요
제품명 뭐예요
링크 주세요
가격 얼마예요
써본 사람?
이거 괜찮나요
```

### 출력

```json
{
  "date": "",
  "summary": "",
  "top_products": [],
  "top_categories": [],
  "bad_products": [],
  "recommended_next_actions": []
}
```

---

## 4.9 Learning Loop Agent

### 역할

성과 데이터를 바탕으로 다음 상품 탐색 방향을 정한다.

### 루프 규칙

* 클릭이 높은 상품군은 유사 상품을 10개 더 찾는다.
* 조회수만 높고 클릭이 낮으면 포맷은 유지하되 상품군은 재검토한다.
* 댓글 구매 신호가 있으면 같은 문제군을 확장한다.
* 구매가 발생한 상품은 다른 각도로 영상 3개를 추가 제안한다.
* 불만 댓글이 많은 상품은 즉시 중단한다.

### 출력

```json
{
  "loop_decision": "EXPAND | PAUSE | KILL | RETEST",
  "reason": "",
  "next_research_query": "",
  "human_approval_required": true
}
```

---

## 5. 데이터 구조

### products.json

```json
{
  "product_id": "P001",
  "created_at": "YYYY-MM-DD",
  "status": "CANDIDATE",
  "product_name": "",
  "category": "",
  "product_url": "",
  "affiliate_url": "",
  "price": 0,
  "rating": 0,
  "review_count": 0,
  "score": 0,
  "risk_status": "PASS",
  "human_approval": "PENDING"
}
```

### videos.json

```json
{
  "video_id": "V001",
  "product_id": "P001",
  "video_path": "/inbox/videos/P001.mp4",
  "source": "TopView",
  "duration_seconds": 30,
  "status": "VIDEO_READY",
  "human_approval": "PENDING"
}
```

### posts.json

```json
{
  "post_id": "",
  "product_id": "",
  "video_id": "",
  "platform": "youtube_shorts",
  "post_url": "",
  "published_at": "",
  "status": "PUBLISHED"
}
```

### metrics.json

```json
{
  "post_id": "",
  "date": "",
  "views": 0,
  "likes": 0,
  "comments": 0,
  "shares": 0,
  "saves": 0,
  "profile_clicks": 0,
  "affiliate_clicks": 0,
  "orders": 0,
  "revenue": 0
}
```

---

## 6. 운영 명령어

AI Agent는 아래 명령어를 인식해야 한다.

### 상품 탐색

```text
FIND PRODUCTS
FIND PRODUCTS category=청소 max=30
FIND PRODUCTS category=주방 price_max=20000
```

### 상품 승인

```text
APPROVE P001, P003, P007
REJECT P002
REVISE P004: 더 저렴한 대체품 찾아줘
```

### TopView 작업 요청

```text
PREPARE TOPVIEW P001
PREPARE TOPVIEW APPROVED
```

### 영상 준비 완료

```text
VIDEO READY P001 path=/inbox/videos/P001.mp4
```

### 게시 승인

```text
PUBLISH P001
SCHEDULE P001 2026-06-10 19:30
REVISE P001: 제목 덜 광고스럽게
REJECT VIDEO P001
```

### 성과 분석

```text
ANALYZE TODAY
ANALYZE LAST 7 DAYS
LOOP APPROVE
LOOP PAUSE
```

---

## 7. 기본 게시 템플릿

### 제목 공식

```text
{문제} 아직도 이렇게 해결하세요?
{문제} 스트레스 받는 사람은 이거 보세요
{공간} 정리 안 되는 이유
{행동}할 때 이거 하나 있으면 편합니다
```

### 캡션 공식

```text
{문제 상황} 때문에 불편한 사람에게 추천.

좋은 점:
- {장점 1}
- {장점 2}

아쉬운 점:
- {단점 1}

제품 링크는 프로필에 정리해뒀습니다.

이 콘텐츠에는 affiliate 링크가 포함되어 있으며, 구매 시 일정 수수료를 받을 수 있습니다.
```

### 고정댓글

```text
제품 링크는 프로필에 정리해뒀습니다.
affiliate 링크가 포함되어 있으며 구매 시 일정 수수료를 받을 수 있습니다.
```

---

## 8. 초기 추천 검색 쿼리

```text
생활꿀템 베스트
자취 꿀템 청소
주방 정리템 추천
욕실 청소 도구 추천
창틀 청소 도구
냉장고 정리 트레이
싱크대 물막이
반려동물 털 제거
옷장 정리 수납함
멀티탭 정리함
```

---

## 9. 중단 기준

아래 조건 중 하나라도 발생하면 해당 상품 또는 카테고리는 중단한다.

* 불만 댓글이 반복된다.
* 상품 품질 문제 리뷰가 많다.
* 과장 없이는 팔기 어렵다.
* affiliate 링크가 불안정하다.
* 플랫폼 정책 위반 가능성이 있다.
* 구매 전환 없이 조회수만 반복된다.
* 운영자가 중단 명령을 내린다.

---

## 10. 성공 기준

### 1차 성공

```text
7일 안에 구매 신호 댓글 발생
7일 안에 affiliate 클릭 발생
14일 안에 첫 구매 발생
```

### 2차 성공

```text
특정 카테고리에서 반복 클릭 발생
같은 문제군 상품에서 성과 재현
영상 포맷 2개 이상 검증
```

### 3차 성공

```text
월 수익 발생
성과 좋은 상품군 자동 확장
브랜드 제휴 후보 확보
```
