# clipcart — 살림해결소

생활문제 해결형 affiliate 숏폼 자동화 CLI.

## 빠른 시작

```powershell
cd c:\Users\ikess\Workspace\lionandthelab\clipcart
python -m venv .venv
.venv\Scripts\activate
pip install -e .

copy .env.example .env
# App ID/Secret 입력 후 OAuth:

clipcart auth instagram
clipcart auth tiktok
clipcart auth pinterest

clipcart status    # .env 설정 확인
clipcart verify    # API 토큰 실제 검증
```

## 플랫폼 연동 (Instagram · TikTok · Pinterest)

### 1. Instagram Reels (Meta Graph API)

**사전 조건**
- Instagram Business 또는 Creator 계정
- Facebook 페이지와 IG 연결
- Meta Developer App + `instagram_content_publish` 권한

**OAuth redirect URI** (Meta 앱 설정에 추가)
```
http://localhost:8400/callback
```

```powershell
# .env에 META_APP_ID, META_APP_SECRET 입력 후
clipcart auth instagram
clipcart verify
```

**주의**: Reels 게시는 **공개 접근 가능한 video_url** 필요. 로컬 mp4는 S3/CDN 업로드 후:

```powershell
clipcart publish P001 --video-url https://cdn.example.com/P001.mp4 --dry-run
```

### 2. TikTok (Content Posting API — Direct Post)

**사전 조건**
- [TikTok for Developers](https://developers.tiktok.com/) 앱
- `video.publish` scope **앱 심사 승인**
- Redirect URI: `http://localhost:8401/callback`

```powershell
clipcart auth tiktok
clipcart verify
```

로컬 mp4 파일 직접 업로드 지원. 초기 테스트는 `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` 권장.

### 3. Pinterest (API v5 Video Pin)

**사전 조건**
- [Pinterest Developers](https://developers.pinterest.com/) 앱
- **Standard access** (Trial은 GET만 가능, POST /pins 불가)
- OAuth 데모 영상 제출로 Standard 승급
- Redirect URI: `http://localhost:8402/callback`

```powershell
clipcart auth pinterest
# PINTEREST_COVER_IMAGE_URL — 비디오 Pin 필수 커버 이미지 (공개 URL)
clipcart verify
```

비디오 Pin 흐름: `POST /media` → AWS 업로드 → `POST /pins`

## CLI 명령어

| 명령 | 설명 |
|------|------|
| `clipcart auth instagram` | Meta OAuth → long-lived token |
| `clipcart auth tiktok` | TikTok OAuth → access token |
| `clipcart auth pinterest` | Pinterest OAuth → board ID 자동 선택 |
| `clipcart status` | .env 설정 상태 |
| `clipcart verify` | API 토큰 유효성 검사 |
| `clipcart publish P001` | Instagram+TikTok+Pinterest dry-run |
| `clipcart publish P001 --live` | 실제 게시 (approve 후) |

## 게시 예시

```powershell
clipcart approve P001
# TopView 영상 → inbox/videos/P001.mp4

clipcart publish P001 --dry-run
clipcart publish P001 --platform tiktok --live
clipcart publish P001 --video-url https://... --cover-url https://... --live
```

## 문서

- [docs/](./docs/) — 플랫폼 연동 설정 (Instagram, TikTok, Pinterest)
- `AGENTS.md` — 전체 운영 규칙
- `CLAUDE.md` — 에이전트 실행 지침
