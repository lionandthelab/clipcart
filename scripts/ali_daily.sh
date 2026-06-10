#!/bin/sh
# macOS launchd용 알리익스프레스 자동 실행 (6시간마다: 00/06/12/18시 KST).
# 윈도우 쿠팡 데일리(아침 07:20)와 별개의 두 번째 파이프라인.
# --force: 같은 날 여러 편 게시 허용(6시간 주기). 상품/이름/니치 중복은
# history.json 원장이 차단하므로 같은 영상이 반복되지는 않는다.
PROJ="/Users/mac/Workspace/lionandthelab/clipcart"
cd "$PROJ" || exit 1
mkdir -p logs
echo "[$(date -u +%FT%TZ)] ali run start" >> logs/task_scheduler_ali.log
"$PROJ/.venv/bin/clipcart" daily --source aliexpress --live --force >> logs/task_scheduler_ali.log 2>&1
echo "[$(date -u +%FT%TZ)] exit=$?" >> logs/task_scheduler_ali.log
