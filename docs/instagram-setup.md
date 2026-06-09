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
| App contact email | (본인 이메일) |

## 2. Product 추가

1. **Facebook Login for Business** → Set up  
2. **Instagram** → Set up (Instagram API)

## 3. Settings → Basic

| 필드 | 복붙 값 |
|------|---------|
| Display name | `살림해결소` |
| App domains | `localhost` |
| Privacy Policy URL | [privacy-policy-template.md](./privacy-policy-template.md) Notion URL |
| Terms of Service URL | Privacy와 동일 URL OK |
| User data deletion | Data deletion instructions URL (템플릿 참고) |
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
| Privacy Policy 필수 | Notion 공개 URL 1페이지 |
