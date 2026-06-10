#!/bin/sh
# macOS launchd용 알리익스프레스 데일리 실행 (매일 19:00 KST).
# 윈도우 쿠팡 데일리(아침 07:20)와 별개의 두 번째 파이프라인.
# 파이프라인이 '오늘 이미 게시(source=aliexpress)'를 체크하므로 중복 실행에 안전하다.
PROJ="/Users/mac/Workspace/lionandthelab/clipcart"
cd "$PROJ" || exit 1
mkdir -p logs
echo "[$(date -u +%FT%TZ)] ali daily start" >> logs/task_scheduler_ali.log
"$PROJ/.venv/bin/clipcart" daily --source aliexpress --live >> logs/task_scheduler_ali.log 2>&1
echo "[$(date -u +%FT%TZ)] exit=$?" >> logs/task_scheduler_ali.log
