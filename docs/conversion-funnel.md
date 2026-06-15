# 전환 퍼널 · 링크 운영 (2026-06-15)

> 목표는 조회수가 아니라 **클릭·구매**다(CLAUDE.md §14: "조회수만 높고 클릭이 없으면 실패"). 이 문서는 "영상 → 링크 → 구매" 퍼널을 어떻게 잇고, 측정하고, 유지하는지의 운영 가이드다. 권위 런북 요약은 `AGENTS.md` 0.6.

## 1. 퍼널 구조

```
숏폼 영상
  │  설명문 CTA: 직접 제품링크(subId) + "프로필 링크"
  ▼
YouTube 채널 프로필 '링크'  ← 운영자가 bio URL로 1회 설정 (필수)
  ▼
bio 페이지  https://lionandthelab.github.io/clipcart/bio/
  │  '오늘의 제품' + 카테고리 + 할인/판매량 카드
  ▼
쿠팡 / 알리 제품 페이지 (상품별 subId)
  ▼
구매 (쿠팡은 24h 쿠키 — 타 상품 주문도 커미션)
```

핵심: YouTube Shorts는 플레이어에서 설명란 링크가 잘 안 눌리고, 댓글 핀은 **API로 자동화 불가**(수동). 그래서 **항상 살아있는 단일 bio 페이지 = 프로필 링크**가 가장 견고한 자동 경로다.

## 2. bio 페이지

- 공개 URL: **`https://lionandthelab.github.io/clipcart/bio/`** — GitHub Pages가 master `/docs`에서 서빙.
- 생성기: [`src/clipcart/bio/page.py`](../src/clipcart/bio/page.py), CLI `clipcart bio`.
- 내용: **현재 실공개 중인** YouTube 영상의 제품만(삭제·비공개는 YouTube 조회로 자동 제외). 최신순 dedupe 후 맨 위 '오늘의 제품' 강조 + 카테고리 그룹. 카드: 제품명·가격, (알리) 정가 취소선+할인%·만족도%·판매량. 쿠팡은 검색 API가 평점/리뷰를 안 줘 가격만.
- 쿠팡 링크는 bio 전용 subId(`bio{상품ID}`)로 재생성해 **채널설명발 클릭을 영상발과 분리** 측정. 알리는 subId 미지원이라 기존 제휴링크.
- 고지는 페이지 첫 부분(공정위): 쿠팡 + 알리 고지 둘 다 표기.

### 운영자 1회 작업
YouTube 채널 '링크'(프로필)에 bio URL 등록. `.env`의 `LINK_IN_BIO_URL`도 같은 값으로 둔다(현재 설정됨).

## 3. CTA 컨벤션 (영상 설명문)

- 템플릿: [`data/format_profile.json`](../data/format_profile.json) `description_template`.
- 순서: ① 훅 → ② **의무 고지**(공정위: 더보기 접힘 위, 250자 이내 — `compliance.py` 하드게이트가 검사) → ③ `👉 영상 속 제품 바로가기: {affiliate_url}`(상품별 subId, 측정용) → ④ `🔗 영상에 나온 모든 제품: 프로필 링크 또는 https://lionandthelab.github.io/clipcart/bio/` → 추천대상/장점/단점 → 해시태그.
- **금지:** "고정 댓글에 링크" 식 CTA. 핀이 자동으로 안 박혀 막다른 길이 된다.
- in-video 자막/내레이션(`src/clipcart/video/**`, 외부 엔진 머지 대기)은 머지 후 같은 방향으로 정렬(현재는 데이터/설명문 레벨만 적용).

## 4. 자동 동기화 — "앞으로 만들 때마다" 반영

스케줄러가 매 게시 후 자동으로 bio를 갱신·푸시한다. 별도 작업 불필요.

| 스케줄러 | 게시 후 단계 |
|---|---|
| [`scripts/daily_task.ps1`](../scripts/daily_task.ps1) (Windows·쿠팡) | `clipcart metrics` → `clipcart bio` → `git add data docs/bio` → commit/pull/push |
| [`scripts/ali_daily.sh`](../scripts/ali_daily.sh) (macOS·알리) | 동일 |

- `clipcart metrics`: YouTube 실공개 재조회 → 삭제/비공개 영상을 `NOT_LIVE`로 정정(원장 동기화) + 성과 스냅샷 누적.
- `clipcart bio`: 위 결과로 페이지 재생성(삭제분 카드 제거). push되면 GitHub Pages에 반영.
- 신규 업로드는 설명문 템플릿이 자동 적용되므로, **새 영상의 CTA·bio 반영은 사람 개입 없이 유지**된다.

## 5. 측정 (subId)

- 정산은 계정 trackingCode 기준이고 **subId는 리포트 분류용 자유값**([`coupang.py`](../src/clipcart/coupang.py) `make_sub_id`, 2026-06-12 실측). 딥링크 생성 시 `subid=`가 landingUrl에 정상 임베드됨(검증).
- 귀속 키: 영상별 `salrimshorts{상품ID}`, bio `bio{상품ID}`. 알리는 subId 미지원(영상발/bio발 구분 불가).
- 확인: `clipcart analyze` — 소스·훅 템플릿·카테고리·subId 귀속 집계.

### 2026-06-15 진단 (왜 CTA를 바꿨나)
- 30일간 **모든 per-product subId 클릭 0** (영상·bio 둘 다). 클릭/커미션은 빈 subId(45클릭·17,210원)와 베이스 `salrimshorts`(2클릭)에만.
- 딥링크 subid 임베드는 정상 → **측정 버그가 아니라 영상 링크가 실제로 안 눌림.** 36,823뷰 / 귀속 클릭 0 → 조회→클릭이 진짜 병목.
- 빈 subId 매출(17,210원)은 채널 콘텐츠가 아닌 외부 유입(주문 내역이 치약·식료품·문제집 등 — 레거시 무-subId 링크 또는 운영자 본인 쿠팡 사용 추정).
- 원인 1순위로 본 것: CTA가 핀 안 되는 "고정 댓글"을 가리킴 → **직접 링크 + 프로필(bio)** 로 전환. 효과는 영상 subId에 클릭이 0에서 올라오는지로 확인.

## 6. 과거 영상 백필

설명문 템플릿을 바꾸면 이미 올라간 영상은 옛 설명문 그대로다. 현재 템플릿으로 맞추려면:

```bash
python scripts/retrofit_descriptions.py            # dry-run (무엇을 바꿀지 출력)
python scripts/retrofit_descriptions.py --live      # 실제 YouTube 설명문 갱신
```

- 제목·태그는 보존하고 **description만** 현재 템플릿으로 교체(상품별 subId 링크 유지).
- 게시 전 컴플라이언스 게이트(`check_texts`)를 동일 적용 — 금지어/고지 문제가 있으면 그 영상만 건너뜀.
- 2026-06-15 기준 라이브 20편 전부 1회 백필 완료.

## 7. 다음 점검

- 며칠 뒤 `clipcart analyze`에서 영상 subId 귀속 클릭이 0에서 증가하는지 확인 → CTA 변경 효과 판정.
- 여전히 0이면: 프로필 링크 노출 위치(채널 배너/소개), bio 페이지 첫 화면 후킹, 제품 선정(충동구매성)으로 후속 개선.
- in-video CTA·신빙성 훅·다중 음성·실리뷰는 영상 엔진 머지 후([content-quality-upgrade.md](content-quality-upgrade.md)).
