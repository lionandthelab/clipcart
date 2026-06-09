# Pinterest API v5 설정 — 복붙용

clipcart OAuth: `clipcart auth pinterest`  
Redirect URI: `http://localhost:8402/callback`

**중요**: Trial access는 GET만 가능. **Standard access** 승급 후 POST `/pins` 사용.

---

## 1. 앱 만들기

[developers.pinterest.com](https://developers.pinterest.com/)

| 필드 | 복붙 |
|------|------|
| App name | `살림해결소 Clipcart` |
| Description | `Tool to publish approved lifestyle affiliate video pins after manual user approval.` |
| Redirect URI | `http://localhost:8402/callback` |

## 2. Scopes

- `boards:read`
- `pins:read`
- `pins:write`
- `user_accounts:read`

## 3. Standard access 승급

Trial → Standard: **OAuth + Pin 생성 데모 영상** 제출.

데모에 포함할 것:
1. OAuth 동의 화면 (Pinterest login)
2. Pin 생성 API 호출 (POST `/v5/pins`) 성공

## 4. .env

```env
PINTEREST_APP_ID=
PINTEREST_APP_SECRET=
PINTEREST_ACCESS_TOKEN=
PINTEREST_REFRESH_TOKEN=
PINTEREST_BOARD_ID=
PINTEREST_COVER_IMAGE_URL=
```

`PINTEREST_COVER_IMAGE_URL`: 비디오 Pin **필수** 커버 이미지 (공개 HTTPS URL).

## 5. OAuth

```powershell
.venv\Scripts\clipcart auth pinterest
.venv\Scripts\clipcart verify
```

첫 번째 보드 ID가 자동으로 `PINTEREST_BOARD_ID`에 저장됩니다.

## 6. 비디오 Pin 흐름

1. `POST /v5/media` — video 등록
2. AWS upload URL로 mp4 업로드
3. `GET /v5/media/{id}` — 처리 완료 대기
4. `POST /v5/pins` — `source_type: video_id` + `cover_image_url`

---

## App Review 설명 (영문)

```text
Single-user tool for publishing manually approved lifestyle product video pins.
User OAuth connects their Pinterest account. Each pin includes affiliate disclosure.
No bulk or automated posting without explicit user approval per video.
```

---

## 자주 막히는 것

| 증상 | 해결 |
|------|------|
| 401 on POST /pins | Standard access 미승인 |
| cover_image_url required | `PINTEREST_COVER_IMAGE_URL` 설정 |
| Trial only GET | Standard access 데모 제출 |
