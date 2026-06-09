# 플랫폼 연동 개요

clipcart 기본 게시 대상: **Instagram Reels**, **TikTok**, **Pinterest**

YouTube는 코드에 포함되어 있으나 기본 publish 대상에서 제외되어 있습니다.

## CLI

```powershell
cd c:\Users\ikess\Workspace\lionandthelab\clipcart
.venv\Scripts\activate

clipcart status    # .env 설정 확인
clipcart verify    # API 토큰 실제 검증

clipcart auth instagram
clipcart auth tiktok
clipcart auth pinterest
```

## Redirect URI (Developer Console에 등록)

| 플랫폼 | Redirect URI |
|--------|----------------|
| Instagram (Meta) | `http://localhost:8400/callback` |
| TikTok | `http://localhost:8401/callback` |
| Pinterest | `http://localhost:8402/callback` |

## 게시

```powershell
clipcart approve P001
# inbox/videos/P001.mp4 준비

clipcart publish P001 --dry-run
clipcart publish P001 --platform tiktok --live
clipcart publish P001 --video-url https://cdn.../P001.mp4 --cover-url https://cdn.../cover.jpg --live
```

### 플랫폼별 특이사항

- **Instagram**: Reels API는 **공개 video_url** 필요. 로컬 mp4는 CDN 업로드 후 `--video-url` 사용.
- **TikTok**: 로컬 mp4 **직접 업로드** 가능. App Review 전에는 `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` (비공개).
- **Pinterest**: **Standard access** 필요 (Trial은 POST 불가). 비디오 Pin은 **cover_image_url** 필수.

## 환경 변수

`.env.example` 참고. `.env`는 git에 포함하지 않습니다.

## 규제·고지

- affiliate/협찬 콘텐츠는 광고·수수료 관계를 명확히 고지
- 국내 운영 시 공정위 추천·보증 광고 고지 리스크 검토
- [YouTube Data API — Upload](https://developers.google.com/youtube/v3/guides/uploading_a_video)
- [KFTC Influencer Marketing Handbook](https://www.kimchang.com/en/insights/detail.kc?idx=21962&sch_section=4)
