# Instagram (Meta) 앱 설정 — 복붙용

clipcart OAuth: `clipcart auth instagram`  
Redirect URI: `http://localhost:8400/callback`

## 사전 조건

- Instagram **프로페셔널**(Business/Creator) 계정
- **Facebook 페이지** 1개 + IG 연결  
  (IG → 프로필 → 계정 센터 → Linked accounts)

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
| App domains | `localhost`, `lionandthelab.github.io` |
| Privacy Policy URL | `https://lionandthelab.github.io/clipcart/privacy.html` |
| Terms of Service URL | `https://lionandthelab.github.io/clipcart/terms.html` |
| User data deletion | `https://lionandthelab.github.io/clipcart/privacy.html` (5. Data Retention & Deletion) |
| Category | `Shopping` 또는 `Utilities` |

## 4. Facebook Login → Settings

| 필드 | 복붙 값 |
|------|---------|
| Valid OAuth Redirect URIs | `http://localhost:8400/callback` |
| Client OAuth login | **Yes** |
| Web OAuth login | **Yes** |
| Enforce HTTPS | **No** (localhost) |
| Use Strict Mode for redirect URIs | **Yes** |

Deauthorize callback (있으면): `http://localhost:8400/callback`

## 5. Instagram → API setup

Redirect URI: `http://localhost:8400/callback`

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

### R2 셋업 (~5분)
1. Cloudflare → **R2** → 버킷 생성(예: `clipcart-media`).
2. 버킷 → Settings → **Public Access** 허용(r2.dev 공개 URL) 또는 커스텀 도메인 연결.
3. **Manage R2 API Tokens** → S3 호환 **Access Key / Secret** 발급.
4. `.env` 채우기:

```env
CLIPCART_S3_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
CLIPCART_S3_BUCKET=clipcart-media
CLIPCART_S3_ACCESS_KEY=
CLIPCART_S3_SECRET_KEY=
CLIPCART_S3_PUBLIC_BASE=https://<bucket>.<hash>.r2.dev
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
| Redirect URI mismatch | `http://localhost:8400/callback` (https 아님) |
| 권한 거부 | Development 모드 + 본인 Admin |
| Privacy Policy 필수 | `https://lionandthelab.github.io/clipcart/privacy.html` (이미 배포됨) |
| IG 게시 실패: video_url | `CLIPCART_S3_*`(R2) 설정 또는 `--video-url` 직접 지정 (공개 mp4 URL 필요) |
