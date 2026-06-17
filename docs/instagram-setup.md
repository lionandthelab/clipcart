# Instagram (Meta) 앱 설정 — 복붙용

clipcart OAuth: `clipcart auth instagram`  
Redirect URI: `https://acts.run/callback/`  
(자체 도메인 `acts.run` 콜백. `.env`의 `CLIPCART_OAUTH_REDIRECT`로 제어 — 아래 9번 Cloudflare 셋업 먼저. 미설정 시 `http://localhost:8400/callback` loopback으로 폴백.)

## 사전 조건

- Instagram **프로페셔널**(Business/Creator) 계정
- **Facebook 페이지** 1개 + IG 연결  
  (IG → 프로필 → 계정 센터 → Linked accounts)

---

## 0. acts.run 호스팅 (Cloudflare) — Meta 앱보다 먼저

Meta는 앱 저장 시 **Privacy Policy URL이 실제로 열려야** 하고, 통합 콜백
`https://acts.run/callback/`도 살아 있어야 한다. 그래서 도메인 먼저 띄운다.
한 계정(무료)에서 DNS + 정적페이지(Pages) + 영상(R2)을 전부 처리한다.

### 0-1. 도메인을 Cloudflare로
1. [dash.cloudflare.com](https://dash.cloudflare.com) 가입 → **Add a site** → `acts.run` 입력 → **Free** 플랜.
2. Cloudflare가 보여주는 **네임서버 2개**를, acts.run을 산 **등록업체(레지스트라)** 관리화면의
   네임서버 항목에 그대로 교체 입력. (전파 수분~수시간)
3. Cloudflare에서 도메인이 **Active** 되면 다음으로.

### 0-2. 정적 페이지 = Cloudflare Pages (privacy/terms/callback)
이 레포의 [docs/](.) 폴더를 그대로 올리면 `acts.run/privacy.html`, `/terms.html`,
`/callback/`(OAuth 코드 표시 페이지)가 한 번에 선다.

1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
   (또는 **Upload assets**로 `docs/` 폴더 드래그).
2. Git 연결 시 빌드 설정: **Framework=None**, **Build command=(비움)**,
   **Build output directory=`docs`**.
3. 배포되면 임시 `*.pages.dev` 주소가 나온다 → **Custom domains** 탭 → `acts.run` 연결
   (Cloudflare가 DNS를 자동으로 잡아줌).
4. 확인: 브라우저에서 `https://acts.run/privacy.html`, `https://acts.run/callback/` 가 열리면 OK.

> 참고: `docs/`엔 내부 메모(.md)도 들어 있다. 비밀값은 없지만 URL을 알면 열람 가능하니
> 민감 메모는 배포 전 옮겨도 됨(필수는 아님).

### 0-3. `.env`
```env
CLIPCART_OAUTH_REDIRECT=https://acts.run/callback/
```
설정하면 `clipcart auth instagram/tiktok/pinterest` 모두 이 콜백으로 가고, 페이지에 뜬
**code를 복사해 터미널에 붙여넣기**만 하면 된다. (미설정이면 localhost 자동 캐치로 폴백)

---

## 1. 앱 만들기

[developers.facebook.com](https://developers.facebook.com/) → **Create App**

| 항목 | 복붙 값 |
|------|---------|
| Use case | **Other** |
| App type | **Business** |
| App name | `살림해결소 Clipcart` |
| App contact email | `contact@lionandthelab.com` |

## 2. Product 추가

1. **Facebook Login for Business** → Set up  
2. **Instagram** → Set up (Instagram API)

## 3. Settings → Basic

| 필드 | 복붙 값 |
|------|---------|
| Display name | `살림해결소` |
| App domains | `acts.run` |
| Privacy Policy URL | `https://acts.run/privacy.html` |
| Terms of Service URL | `https://acts.run/terms.html` |
| User data deletion | `https://acts.run/privacy.html` (5. Data Retention & Deletion) |
| Category | `Shopping` 또는 `Utilities` |

## 4. Facebook Login → Settings

| 필드 | 복붙 값 |
|------|---------|
| Valid OAuth Redirect URIs | `https://acts.run/callback/` |
| Client OAuth login | **Yes** |
| Web OAuth login | **Yes** |
| Enforce HTTPS | **No** (localhost) |
| Use Strict Mode for redirect URIs | **Yes** |

Deauthorize callback (있으면): `https://acts.run/callback/`

## 5. Instagram → API setup

Redirect URI: `https://acts.run/callback/`

## 6. App roles

본인 Facebook 계정을 **Administrator**로 추가 (본인 앱이면 기본 Admin).

Development 모드: Admin/Developer/Tester만 OAuth 가능.

## 7. .env

Meta **Settings → Basic**에서:

```env
META_APP_ID=
META_APP_SECRET=
```

## 8. 토큰 발급

```powershell
.venv\Scripts\clipcart auth instagram
.venv\Scripts\clipcart verify
```

자동 저장: `META_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`

> 본인 계정만 게시하면 **개발 모드로 충분**(App Review 불필요). Admin/Tester 인 본인 IG에 게시 가능.

---

## 9. 영상 호스팅 (IG Reels 자동 게시에 필수)

IG API 는 파일 업로드가 아니라 **공개 `video_url`** 로 영상을 가져간다. clipcart 가 만든
MP4 를 S3 호환 스토리지(**Cloudflare R2 권장 — 무료·egress 무료**)에 자동 업로드해
`video/mp4` 직접 URL 을 만든다. (GitHub Pages/Release 는 비대화/redirect/content-type 문제로 부적합)

### R2 셋업 (~5분, 0번에서 만든 Cloudflare 계정 그대로)
1. Cloudflare → **R2** → 버킷 생성(예: `clipcart-media`).
2. 버킷 → Settings → 공개 접근:
   - 간단: **r2.dev Public Access** 허용 → `https://<bucket>.<hash>.r2.dev`
   - 깔끔: **Custom Domain**에 `media.acts.run` 연결(이미 Cloudflare DNS라 자동) → `https://media.acts.run`
3. **Manage R2 API Tokens** → S3 호환 **Access Key / Secret** 발급.
4. `.env` 채우기:

```env
CLIPCART_S3_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
CLIPCART_S3_BUCKET=clipcart-media
CLIPCART_S3_ACCESS_KEY=
CLIPCART_S3_SECRET_KEY=
CLIPCART_S3_PUBLIC_BASE=https://media.acts.run
```

설정되면 `clipcart publish <id> --platform instagram_reels --live` 시 **자동 업로드→게시**.
미설정이면 `--video-url <공개 mp4 URL>` 로 직접 지정(아무 공개 호스트 가능).
저장공간은 버킷 **lifecycle 규칙(예: 7일 후 삭제)** 로 관리. (S3/B2 도 동일 env 로 동작)

---

## App Review (다른 사용자까지 쓸 때)

| Permission | 복붙 설명 |
|------------|-----------|
| `instagram_basic` | `Our app reads the connected Instagram Business account profile to verify publishing setup.` |
| `instagram_content_publish` | `Our app publishes Reels only after the user manually approves each video. Used for affiliate lifestyle product content.` |
| `pages_show_list` | `Required to list Facebook Pages linked to the user's Instagram Business account.` |
| `pages_read_engagement` | `Required by Meta for Instagram API publishing integration.` |

**Screencast 설명 (영문):**

```text
User logs in via Facebook OAuth, selects a Page linked to Instagram Business account,
uploads a pre-approved vertical video, and publishes a Reel with affiliate disclosure in caption.
No automatic posting without user approval.
```

---

## 자주 막히는 것

| 에러 | 해결 |
|------|------|
| IG 계정 못 찾음 | IG 프로페셔널 + Facebook 페이지 연결 |
| Redirect URI mismatch | `https://acts.run/callback/` (https 아님) |
| 권한 거부 | Development 모드 + 본인 Admin |
| Privacy Policy 필수 | `https://lionandthelab.github.io/clipcart/privacy.html` (이미 배포됨) |
| IG 게시 실패: video_url | `CLIPCART_S3_*`(R2) 설정 또는 `--video-url` 직접 지정 (공개 mp4 URL 필요) |
