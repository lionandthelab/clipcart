# 영상 템플릿 스펙 — "이야기 릴스 (story)"

> 상태: **설계 완료, 구현 대기.** 멀티에이전트 리서치(유명 채널 4렌즈) → 합성 → 적대적 컴플라이언스/실현성 검증(8건 반영) 결과. 운영자 요청(2026-06-16): "인스타 릴스 감성, 20대 취향, 부드러운 전환, 밝고 화사, 모던·깔끔 제품 사용, 스토리텔링."
>
> ⚠️ 구현 대상이 전부 **머지 보류 중인 영상 엔진**(`src/clipcart/video/**`)이다. 이 문서는 외부 엔진 머지 후(또는 운영자가 보류 해제 시) 그대로 구현하기 위한 **작업 지시서**다. 관련: [[engine-merge-pending]]

## 컨셉

광고가 아니라 **"옆자리 친구가 들려주는 짧은 생활 이야기"**처럼 느껴지는 릴스풍 스토리텔링 템플릿. 현 promo의 검정 3단 광고 레이아웃·휘익 슬램·노랑/빨강 강조를 버리고 → **밝고 화사한 크림 배경 풀블리드 + 부드러운 크로스디졸브 + 잔잔한 1인칭 관찰 내레이션**으로.

3대 전략축:
1. **BGM 불가를 무기로** — 음악 없이 "듣는 이야기"(내레이션 주음원 + 호흡 여백 + lavfi 앰비언트 베드).
2. **윤리 제약을 화법으로 정확 준수** — "내가 써봤다"(허위후기) 금지를 **관찰·가정·발견 화법**으로 구조적 회피("이런 사람 있죠 / 그러다 이런 걸 봤어요").
3. **7비트 골격 유지, 말의 역할만 스토리 곡선으로 재배치** — 기존 beats 구조를 갈아엎지 않아 구현 리스크↓.

## 내러티브 아크 (32~36초)

| 비트 | 초 | 내레이션(예시 골격) | 자막 | 비주얼 | 전환 |
|---|---|---|---|---|---|
| **hook** 장면 진입 + **시작 고지** | 0–5 | "자취하다 보면, 이런 사소한 거에 은근 신경 쓰일 때 있잖아요." | 이거, 나만 그런 거 아니죠? | 화사한 아침 생활 한 컷(풀블리드). **0.5~3.5s 확정형 고지 크림칩 베이크인** | fade-in 0.4s, 훅 직후 0.4s 정적 |
| **problem** 작은 불편 | 5–11 | "별거 아닌데… 매번 손이 한 번씩 더 가더라고요." | 매번 손이 한 번 더 가는 거 | 화사한 '현실 생활감'(과장된 더러움 X), 사람/손 없음 | crossfade 0.35s |
| **switch** 발견 | 11–17 | "그러다 이런 걸 봤어요. 요즘은 이렇게들 두더라고요." | 그러다 이런 걸 봤어요 | 제품이 집 한구석에 자연스럽게 놓인 화보샷(창가 자연광) | crossfade 0.35s, 약한 scale-up 팝 |
| **product** 발견의 디테일 | 17–23 | "근데 생각보다 별거 아니더라고요. {price}원이면 한 번 둬볼 만하죠." | {제품명·가격} | 실제 리스팅 사진/화보 퀵컷, 크림 카드 | crossfade 0.3s, soft chime |
| **usage** 사용 | 23–29 | "쓰는 것도 어렵지 않아요. {usage}" | {사용 요약} | 사용 실영상 + 제품 사진. ASMR 구간엔 내레이션 비우고 생활음 전면 | crossfade 0.35s |
| **result** 소소한 변화 | 29–34 | "그 작은 게, 생각보다 편해요." (수치 있을 때만 "이미 N명이 시켰더라고요") | {효과 요약} | 화사한 after 장면 | crossfade 0.3s |
| **cta** 솔직한 한 마디 + **끝 고지** | 34–38 | "근데 솔직히 {downside}는 좀 아쉬워요. 그래도 궁금하면, 링크는 고정 댓글에 둘게요." | 링크는 고정 댓글에 ▼ | 리뷰 카드/제품컷 + **끝 고지 크림칩** | crossfade 0.3s → 로고 fade |

## script.py — 새 SCRIPT_STYLE (추가)

```python
{
    "name": "story",
    "switch": "{old_way}, 다들 한 번쯤 그러잖아요. 그러다 이런 걸 봤어요.",
    "switch_caption": "그러다 이런 걸 봤어요",
    "switch_emphasis": "이런 걸 봤어요",
    "usage": "쓰는 것도 어렵지 않더라고요. {usage}",
    "result_tail": "그 작은 게 생각보다 편해요.",
    "cta": "근데 솔직히 {downside}는 좀 아쉬워요. 그래도 궁금하면 링크는 고정 댓글에 둘게요.",
}
```
전부 관찰·가정·발견 화법 → 허위후기 게이트와 충돌 없음.

## 비주얼 테마

- **배경:** 현 `INK=(10,11,14)` 검정 3단 폐기 → `CREAM=(247,243,236)` 풀블리드. 미디어를 9:16 풀스크린, 자막/브랜드바는 반투명 오버레이. (화사 톤의 80%가 여기서 나옴)
- **팔레트:** 크림 `#F7F3EC` / 오프화이트 `#FBF8F2` / seashell `#FFF1E7` / 차콜 텍스트 `#2C2E33`(자막 흰색→차콜) / 딥세이지 단일 액센트 `#7E9B7A` / 소프트 머스타드 `#E8C9A0`.
- **레이아웃:** 풀블리드 + 좌상단 '광고' 펠릿 + 자막 세이프존 화면 **35~72% 중앙대**(인스타 하단 캡션/우측 버튼 UI 회피) + 하단 미니멀 브랜드 마크. 강조어 중앙 슬램(220px) → 약한 scale-up 팝(120px).
- **전환:** crossfade 0.3~0.4s(주력) / soft fade 0.4s / gentle scale-up 팝. *split-screen·match-cut은 v2.1 후속.*
- **타이포:** 검은고딕(BlackHanSans) 폐기 → **Pretendard**(SIL OFL, 상업OK)를 `assets/fonts`에 실제 커밋. 색이 아니라 굵기·사이즈로만 강조. 청크 최소 0.6s, `max_eojeol` 4→3. *파일 미동봉 시 story 비활성→promo 폴백.*

## Gemini 비주얼 스타일 (`sources.py` `_GEMINI_STORY`)

```
Soft bright airy lifestyle photo inside a modern 2020s South Korean apartment,
contemporary newly-built interior with recent fixtures and appliances. High-key
soft diffused natural window light, gently overexposed background, low contrast,
pastel cream and off-white palette, subtle bloom/halation glow on highlights,
soft shadows, shallow depth of field, film-like pastel color grade, clean minimal
modern styling, lots of negative space, warm cozy slow-morning mood. Absolutely
no people, no hands, no faces, no text, no watermark. Vertical 9:16. Scene:
```
제품 화보샷(`_PRODUCT_SHOT_PROMPT`)에도 "bright high-key, airy pastel background, soft bloom, low contrast, cream-toned props" 추가(제품 IDENTICAL 유지).

## TTS 디렉션 (story 전용)

- 템포 `1.24 → 1.0~1.05`(거의 가속 X, 잔잔). 비트 간 호흡 여백 `post 0.08/0.12 → 0.35/0.5`, 훅 직후 0.4s 정적.
- `_TONE_EMOTION` story 분기: hook/problem/switch/cta=(normal,1.0), product/usage=(happy,1.0), result=(happy,1.05). 전반 강도 하향(들뜸 제거).
- `CLIPCART_TTS_VOICE_ID`로 더 부드럽고 낮은 여성 보이스 분리 권장. 끝맺음이 살짝 올라가는 나직한 권유·공감 어조.
- **고지 전문은 TTS 낭독 안 함**(시작·끝 자막+설명란으로 충족). cta 끝 "광고예요"만 짧게 → target 32~36s 길이예산 보호.

## 제목 템플릿 (릴스풍, `format_profile.json` story 분기용)

```
{hook}
자취하면 이거 한 번씩 겪죠
{target}이라면 공감할걸요
요즘은 {old_way} 대신 이렇게들 두더라고요
{price_won}원으로 달라지는 {title_keyword}
{title_keyword} 쓰기 전에 이 이야기 보세요
```
> ⚠️ story 전용. 현 promo(다크/펀치) 영상에 섞으면 톤 불일치 → story 템플릿이 실제 렌더될 때 함께 적용.

## 워크드 예시 2

**텀블러 세척솔 (저주문 → 수치 생략):**
> 매일 텀블러 쓰는 사람이면, 이거 은근 신경 쓰이잖아요. 입구가 좁아서… 손이 바닥까지 안 닿더라고요. 냄새가 나도 그냥 헹구기만 하게 되고요. 그러다 이런 걸 봤어요. 요즘은 이렇게들 두더라고요. 긴 손잡이 솔이라 바닥이랑 모서리까지 닿아요. 6,900원이면 한 번 둬볼 만하죠. 쓰는 것도 어렵지 않더라고요. 솔로 안쪽을 쓱 닦고 헹구면 끝. 바닥까지 닦이니까 커피 냄새 남는 일이 줄어요. 그 작은 게 생각보다 편해요. 근데 솔직히 솔도 소모품이라 몇 달에 한 번은 갈아줘야 하는 건 좀 아쉬워요. 그래도 궁금하면 링크는 고정 댓글에 둘게요. 광고예요.

**현관 흙먼지 매트 (고주문·고만족 → '이미 N명' 삽입):**
> 현관에 모래알, 쓸어도 다음날 또 있는 거… 이런 집 꽤 있죠. 신발에 묻어 들어온 흙이, 어느새 거실까지 들어와 있더라고요. … 그러다 이런 걸 봤어요. 요즘은 현관에 이렇게들 깔더라고요. … 12,900원이면 한 번 둬볼 만하죠. … 거실에 밟히는 모래알이 눈에 띄게 줄어요. 그 작은 게 생각보다 편해요. 이미 3,200명이 시켰더라고요. 근데 솔직히 매트가 현관보다 작으면 효과가 떨어지니까, 치수는 재보고 고르는 게 좋아요. 그래도 궁금하면 링크는 고정 댓글에 둘게요. 광고예요.

## 구현 델타 (파일별 작업 지시)

| 파일 | 변경 | 규모 |
|---|---|---|
| `script.py` | `SCRIPT_STYLES`에 `story` dict 추가 | 소 |
| `beats.py` | **hook 비트에도 `disclosure` 키 부여**(시작 고지) + `CLIPCART_TEMPLATE=story` 분기(가격='발견', result 수치 조건부, cta+"광고예요"), 강조 색 차콜/세이지, gemini `style='story'` | 중 |
| `sources.py` | `_GEMINI_STORY` 상수 + `_GEMINI_STYLES['story']`, `_PRODUCT_SHOT_PROMPT` 화사 톤 추가(프롬프트만) | 소 |
| `broll.py` | story용 화사 쿼리 변형(pain 과장↓, soft natural light) | 소 |
| `editor.py` | **(중, 회귀테스트 필수)** INK→CREAM, 풀블리드 레이아웃, **하드컷→크로스페이드**(미디어 세그먼트 `beat_dur+overlap`, `with_start(t-overlap)`+마스크 `CrossFadeIn`, 오디오 `with_start(t)` 불변 → A/V 싱크 보존), SFX 톤다운(whoosh/riser/thud↓, pop→chime), 강조 슬램 완화, 자막칩 크림 톤·세이프존 35~72%, **시작 고지 오버레이**, BANNER_TEXT 소스 분기, 앰비언트 베드 입력 | 중 |
| `tts_typecast.py` | TEMPO 1.0~1.05, `_TONE_EMOTION` story 분기, post-gap↑, voice 분리, 고지 전문 미낭독 | 소 |
| `fonts.py` | Pretendard ttf `assets/fonts` 커밋 + `load_font` modern 플래그, 미동봉 시 story 비활성 | 소 |
| `sfx.py` | soft 변형(whoosh→숨결, pop→chime) + **lavfi 앰비언트 베드 합성**(저작권 0). Freesound CC0는 키 있을 때만 선택 | 소 |
| `compliance.py` | **(하드게이트 신설)** ①시작 비트(`scenes[0]`) 고지 자막 존재 검사 ②허위후기 패턴(`제가 써보니|한 달 써본|내돈내산|강추|효과 봤어요`) 차단 ③`'직접 써봤'→'써본 사람들은'` 치환을 `review_card` 존재 시에만 | 소~중 |
| `format_profile.json` | story 분기(또는 `format_profile_story.json`): 위 제목/차콜자막/잔잔TTS/`target_length 32~36` | 데이터(안전) |

## 컴플라이언스 (전부 보존·강화)

- **공정위 확정형 고지**: 영상 **시작(0.5~3.5s)·끝** 온스크린 크림칩 + 설명란 첫 부분(250자 이내), 소스별(`disclosure_for`). beats가 hook·cta 두 비트에 disclosure 부여, compliance에 **시작-고지 하드게이트 신설**.
- **허위후기 금지**(CLAUDE.md 1.2): story 카피는 전부 관찰·가정·발견 화법으로 1인칭 실사용 단정을 구조적 회피. + BANNED 패턴 확장 + sanitize 치환 조건부.
- **단점 1개 필수**: cta가 `niche['downside']`를 친구 화법으로.
- **수치 정합**: 주문수/만족도는 API 실값·조건부(`rating>=90 AND orders>=100`)만, 비면 생략.
- **BGM 불가 준수**: 음악 0, lavfi 앰비언트 베드+직접합성 SFX만.

## ⚠️ 별건 — 현 라이브 엔진 컴플라이언스 결함 (검증 중)

검증 과정에서 발견: **현 promo 엔진은 확정형 고지 전문을 영상 *끝*(cta)에만 베이크인**하고, 시작엔 "광고" 펠릿(2자)만 노출. `editor.py`의 `BANNER_TEXT`("광고 · 쿠팡 파트너스 수수료 지급") 상수는 정의돼 있으나 `render_promo`에서 실제로 그려지지 않음. `compliance.py`는 "어떤 scene이든 disclosure 보유"만 검사해 **시작 고지 누락이 게이트를 통과**. 공정위 "끝부분만 표기 불인정"에 저촉될 수 있음 → 템플릿과 별개로 **우선 점검·수정 권장**(시작 고지 베이크인 + compliance 하드게이트). 이 수정도 `editor.py`/`compliance.py`(머지 보류 영역)라 엔진 편집 결정에 포함.
