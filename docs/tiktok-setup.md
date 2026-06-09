# TikTok Developer 앱 설정 — 복붙용

clipcart OAuth: `clipcart auth tiktok`  
Redirect URI: `http://localhost:8401/callback`  
Scopes: `user.info.basic`, `video.upload`, `video.publish`

---

## 1. 앱 만들기

[developers.tiktok.com](https://developers.tiktok.com/) → **Connect an app**

| 필드 | 복붙 |
|------|------|
| App name | `살림해결소 Clipcart` |
| App description | `Affiliate lifestyle short-form content publishing tool. Users manually approve each video before posting to TikTok.` |
| Category | `Utilities` 또는 `Shopping` |
| Website URL | `http://localhost:8401` (또는 Notion 공개 URL) |
| Privacy Policy URL | [privacy-policy-template.md](./privacy-policy-template.md) |
| Terms of Service URL | Privacy와 동일 OK |

## 2. Products

| Product | 설정 |
|---------|------|
| **Login Kit** | Web |
| **Content Posting API** | **Direct Post** Enabled, **FILE_UPLOAD** |

## 3. Scopes

- `user.info.basic`
- `video.upload`
- `video.publish` ← 필수

## 4. Login Kit → Web

| 필드 | 복붙 |
|------|------|
| Redirect URI | `http://localhost:8401/callback` |

## 5. URL Properties (Content Posting API)

앱 페이지 **URL properties** → verify (필요 시 HTTPS 도메인 사용).  
로컬 OAuth만 할 때는 Redirect URI 등록이 우선.

## 6. .env

```env
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN=
TIKTOK_REFRESH_TOKEN=
TIKTOK_PRIVACY_LEVEL=SELF_ONLY
```

**미승인 앱**: 공개 게시 불가 → `SELF_ONLY`로 본인만 보기 테스트.

## 7. OAuth

```powershell
.venv\Scripts\clipcart auth tiktok
.venv\Scripts\clipcart verify
```

---

## App Review (공개 게시)

### Explanation (영문 복붙)

```text
App name: 살림해결소 (Clipcart)

Product: Content Posting API (Direct Post) + Login Kit

Flow:
1. User logs in with TikTok OAuth (user.info.basic).
2. User manually selects and approves a product recommendation video.
3. User reviews caption including affiliate disclosure.
4. User explicitly commands PUBLISH — no automatic posting.
5. App uploads the local MP4 via FILE_UPLOAD and posts via Direct Post API.

Scopes:
- user.info.basic: verify connected TikTok account
- video.upload: upload approved video file
- video.publish: publish to user's profile after explicit approval

Privacy: SELF_ONLY during testing; PUBLIC after audit approval.
Users can revoke app access anytime in TikTok settings.

We comply with TikTok Music Usage Confirmation and commercial content disclosure requirements.
Affiliate relationship is disclosed in every caption.
```

### FAQ 답

**Who will use this app?**
```text
Only the account owner (single creator). Internal tool for affiliate lifestyle content.
```

**Estimated daily posts?**
```text
1-3 posts per day maximum, only after manual approval.
```

**Will you post on behalf of other users?**
```text
No. Each user authorizes their own account. No multi-user SaaS at launch.
```

### Demo video (최대 50MB)

1. `clipcart auth tiktok`
2. `clipcart publish P001 --platform tiktok --dry-run`
3. `--live`로 SELF_ONLY 게시
4. TikTok 앱에서 확인

---

## 자주 막히는 것

| 증상 | 해결 |
|------|------|
| redirect_uri mismatch | `http://localhost:8401/callback` |
| scope_not_authorized | `video.publish` 추가 + OAuth 재실행 |
| privacy_level_option_mismatch | `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` |
| 공개 게시 안 됨 | App Review 전에는 private만 (정상) |

---

## TikTok UX 요구 (Direct Post 가이드)

- `creator_info/query`로 허용 privacy_level 조회
- 게시 전 동의: *"By posting, you agree to TikTok's Music Usage Confirmation"*
- Commercial / affiliate content disclosure
