"""내 영상에서 채널 소유자가 단 링크 댓글 중 최신 1개만 남기고 정리."""

import sys

import clipcart.config  # noqa: F401
from googleapiclient.discovery import build

from clipcart.publishing.youtube import YouTubePublisher

sys.stdout.reconfigure(encoding="utf-8")

video_id = sys.argv[1] if len(sys.argv) > 1 else "C9_x6RbEZuw"
keep_id = sys.argv[2] if len(sys.argv) > 2 else None  # 남길 top-level comment id

yt = YouTubePublisher()
youtube = build("youtube", "v3", credentials=yt._build_credentials())

resp = youtube.commentThreads().list(
    part="snippet", videoId=video_id, maxResults=100, textFormat="plainText"
).execute()

mine = []
for item in resp.get("items", []):
    top = item["snippet"]["topLevelComment"]
    text = top["snippet"].get("textOriginal", "")
    if "link.coupang.com" in text:
        mine.append((top["id"], text.split("\n")[0]))

print(f"발견한 링크 댓글 {len(mine)}개:")
for cid, preview in mine:
    print(f"  {cid}  {preview}")

if keep_id:
    to_delete = [cid for cid, _ in mine if cid != keep_id]
else:
    # keep_id 미지정 시 가장 마지막(최신) 것만 남김
    to_delete = [cid for cid, _ in mine[1:]]

for cid in to_delete:
    youtube.comments().delete(id=cid).execute()
    print(f"삭제: {cid}")

print(f"정리 완료. 삭제 {len(to_delete)}개.")
