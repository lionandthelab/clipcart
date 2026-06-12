# 콘텐츠 퀄리티 개선 — 데이터 가용성 조사 (2026-06-12)

> 상태: **조사 완료, 구현 보류.** 외부에서 개발 중인 영상 엔진과 동기화/머지 후 방향 확정 예정.
> 이 문서는 그때 바로 결정에 쓰기 위한 사실 정리다. (코드는 아직 변경하지 않음.)

## 배경

운영자 요청: 현재 자동 생성 숏폼의 퀄리티가 낮다. 다음 5가지를 만족하도록 대본·편집 엔진 개선.

1. API로 **상세페이지 내용**을 파악해 핵심 셀링포인트 도출
2. **AI 생성 티 나는 사람 이미지 회피** — Pexels 실영상 또는 현상만 공감되게
3. **실제 리뷰 캡처**해서 보여주고 읽어주기
4. 가격만 부르지 말고 **할인율 명확히 + 수량 표현**
5. **신빙성 훅 강화**("처음엔 안 믿겼는데 정말") + **다양한 목소리**로 여러 사람 증언처럼

## 현재 엔진 구조 (요약)

| 영역 | 위치 | 현 동작 |
|---|---|---|
| 상품 데이터 | [src/clipcart/coupang.py](../src/clipcart/coupang.py) | 쿠팡 파트너스 search/goldbox/deeplink. **이름·가격·이미지·로켓여부·rank만** |
| 상품 선정 | [src/clipcart/research/auto_select.py](../src/clipcart/research/auto_select.py) | 31개 니치 풀 순환 + 점수화 + 중복방지 |
| 대본 생성 | [src/clipcart/video/copywriter.py](../src/clipcart/video/copywriter.py), [niches.py](../src/clipcart/research/niches.py) | **LLM 미사용.** 니치 템플릿(hook/problem/usage/benefit/downside) 치환 |
| 영상 비트 | [src/clipcart/video/promo/beats.py](../src/clipcart/video/promo/beats.py) | 6비트(hook→problem→product→usage→result→cta) |
| 미디어 | [src/clipcart/video/promo/sources.py](../src/clipcart/video/promo/sources.py), [broll.py](../src/clipcart/video/promo/broll.py) | Pexels 실영상 / Gemini 생성이미지 / 쿠팡 제품이미지 |
| TTS | [src/clipcart/video/promo/tts_typecast.py](../src/clipcart/video/promo/tts_typecast.py) | **Typecast 단일 음성**(진희), 톤별 감정만 변경. 폴백 edge-tts |
| 합성 | [src/clipcart/video/promo/editor.py](../src/clipcart/video/promo/editor.py) | moviepy 3단(상단 훅+광고배너 / 중앙 미디어 / 하단 자막) |
| 가격 표시 | beats.py product 비트 | `{price:,}원`만. **원가·할인%·수량 없음** |

## 핵심 발견 — 데이터 가용성 (실측)

### 쿠팡
- **파트너스 search·goldbox API 필드 (실측, 둘 다 동일):**
  `productId, productName, productPrice, productImage, productUrl, isRocket, isFreeShipping, categoryName, keyword, rank`
  → **원가·할인율·리뷰·평점·수량/옵션 전부 없음.**
- **상세페이지 직접 요청 = 403 (WAF/봇 차단, 실측.)** `https://www.coupang.com/vp/products/{id}` 및 `/items` 모두 차단.
  → 스크래핑으로 리뷰·할인 가져오기 불가(헤드리스 우회는 CLAUDE.md 1.2 "플랫폼 약관 우회 자동화 금지"와 충돌).

### 알리익스프레스 (공식 affiliate API)
- 엔드포인트 `aliexpress.affiliate.productdetail.get` — 쿠팡엔 없는 데이터를 **합법적으로** 제공:
  - `target_original_price` (원가), `discount` (할인%), `target_sale_price` (판매가)
  - `evaluate_rate` (긍정 평점 %, 별점 정수 아님), `lastest_volume` (최근 판매량)
  - 다중 이미지, 카테고리, 커미션율. `target_currency=KRW`, `target_language=KO` 지원.
- **리뷰 텍스트는 알리도 공식 API 미제공** (집계 평점%만).
- 게이트웨이 `http://gw.api.taobao.com/router/rest` (POST), 서명 MD5(정렬 파라미터를 secret으로 감싸 해시).
- Python SDK: `python-aliexpress-api` (v3.1.0, 2024-12, MIT). 무료, ~5,000회/일.
- 자격증명: App Key/Secret + Tracking ID(PID). `openservice.aliexpress.com` 가입 + 승인 1~2일, PID는 `portals.aliexpress.com`.
- **함정:** 해외 직배송 7~30일 → "로켓배송 내일 옴 / 즉시 생활해결" 살림해결소 포지셔닝과 충돌. CLAUDE.md 전체가 쿠팡 파트너스 기준(고지문구·SUB_ID).

### 리뷰 텍스트 결론
- **쿠팡·알리 모두 공식 API로 실제 리뷰 텍스트를 주지 않는다.**
- 유일한 경로: 스크래핑 또는 유료 액터(예: Apify `aliexpress-reviews-scraper`) → ToS·비용·취약성 부담.

### Claude 크롬 플러그인 (Claude for Chrome)
- 실제 로그인 브라우저 세션이라 WAF는 통과하지만, **사람이 떠 있는 포그라운드 대화형**에서만 동작.
- **무인 데일리 파이프라인(매일 07:20, 사람·브라우저 없음)에 붙일 수 없다.** clipcart의 핵심인 전자동과 배치됨.
- 또한 현재 개발 환경(터미널 CLI)엔 해당 확장의 브라우저 제어 도구가 연결돼 있지 않음.
- → 임시 수동 데이터 수집엔 가능, **자동 엔진 데이터 소스로는 부적합.**

## 사용 가능한 키 (.env, 값 비공개)

`ELEVENLABS_API_KEY` ×2 · `OPENROUTER_API_KEY` · `GEMINI_API_KEY` · `PEXELS_API_KEY` · `TYPECAST_API_KEY`
→ **다중 음성(요구 5)·LLM 셀링포인트(요구 1)·제품이미지 비전분석은 신규 비용 없이 즉시 가능.**

## 요구사항별 실현 가능성 / 권장 구현

| # | 요구 | 공식 API로 가능? | 권장 구현 |
|---|---|---|---|
| 1 | 상세 셀링포인트 | △ | OpenRouter LLM + Gemini 비전으로 **상품명 + 제품이미지** 분석해 셀링포인트 추출(상세페이지 스크래핑 불필요). 니치 템플릿 → 상품별 카피로 대체 |
| 2 | AI 사람 회피 | ✅ | beats.py `empathy` 프롬프트에서 "person" 제거, **현상/오브젝트만** 생성. Pexels 실영상 우선순위 상향 |
| 3 | 실제 리뷰 | ❌ | 공식 경로 없음. 스크래퍼/유료 액터만 가능(별도 결정). **조작·허위 후기 금지(CLAUDE.md 1.2) 절대 준수** |
| 4 | 할인율 | ❌(쿠팡) / ✅(알리) | 쿠팡 유지 시 보류, 알리 도입 시 `discount`/`target_original_price`로 표시 |
| 4 | 수량 | △ | **상품명 파싱**(대용량/서랍형/N개/N매 등) 또는 LLM 추출 |
| 5 | 다중 음성 | ✅ | **ElevenLabs**(키 보유) 또는 **Typecast 다중 voice_id** — 비트별 다른 목소리. tts_typecast.py `_voice_id()`를 role 인자 받게 확장 |
| 5 | 신빙성 훅 | ✅ | LLM로 호기심·신빙성 훅 생성(컴플라이언스 범위 내, 허위 후기 금지). 니치별 훅 변형 풀 |

> **주의:** 요구 5의 "여러 사람 증언처럼"은 **실제 리뷰가 있을 때만** 인용. 리뷰 데이터가 없으면 일반적 사용감을 따옴표 없이 — 가짜 후기를 만들어내면 CLAUDE.md 1.2 "허위 사용 후기 작성" 위반.

## 방향 옵션 (머지 후 결정)

1. **(추천) 쿠팡 유지 + API-only 대개선** — 스크래핑·신규자격 없이 즉시: 요구 2·1·4(수량)·5 전부. 리뷰·할인%는 보류. 가장 견고·합법·무인운영 안전.
2. **쿠팡 + 알리 메타데이터 병행** — 위 + 알리 API로 원가/할인%/평점 확보(요구 4 할인 충족). 단 알리 자격증명·해외배송 포지셔닝 충돌 감수. 리뷰 텍스트는 여전히 불가.
3. **리뷰 텍스트까지 실데이터** — 스크래퍼/유료 Apify 도입(요구 3). ToS·비용·취약성 감수.

## 후속 참고 (알리 도입 시 빠른 시작)

```bash
pip install python-aliexpress-api==3.1.0
```
```python
from aliexpress_api import AliexpressApi, models
api = AliexpressApi(key=APP_KEY, secret=APP_SECRET,
                    language=models.Language.KO, currency=models.Currency.KRW,
                    tracking_id=PID)
products = api.get_products_details(["<product_id>"])  # original_price, discount, evaluate_rate ...
```

## 출처
- 쿠팡 파트너스 Open API (현 클라이언트: `src/clipcart/coupang.py`) — search/goldbox 필드 실측
- AliExpress Open Platform: openservice.aliexpress.com · portals.aliexpress.com
- `aliexpress.affiliate.productdetail.get` 필드: botize.com/method/aliexpress_associates/get_product_detail
- Python SDK: pypi.org/project/python-aliexpress-api (GitHub: sergioteula/python-aliexpress-api)
- 리뷰 미제공/스크래퍼: dev.to/zuplo/a-developers-guide-to-the-aliexpress-api · apify.com (aliexpress-reviews-scraper)
