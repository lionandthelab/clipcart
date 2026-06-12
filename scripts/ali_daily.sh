#!/bin/sh
# macOS launchd용 알리익스프레스 자동 실행 (6시간마다: 00/06/12/18시 KST).
# 윈도우 데일리(쿠팡 07:20 + 알리 1회)와 별개. --force: 같은 날 여러 편 허용.
# 상품/이름/니치 중복은 history.json 원장이 차단 — 실행 전 git pull 로 다른 머신
# (Windows) 게시분까지 반영하고, 게시 후 push 로 이번 게시분을 공유한다.
PROJ="/Users/mac/Workspace/lionandthelab/clipcart"
cd "$PROJ" || exit 1
mkdir -p logs
LOG="logs/task_scheduler_ali.log"
echo "[$(date -u +%FT%TZ)] ali run start" >> "$LOG"

# 1) 최신 엔진 + 타 머신 게시 원장 받기 (런타임 변경은 autostash 보존)
git pull --rebase --autostash origin master >> "$LOG" 2>&1

# 2) 의존성 동기화
"$PROJ/.venv/bin/python" -m pip install -q -r requirements.txt >> "$LOG" 2>&1
"$PROJ/.venv/bin/python" -m pip install -q -e . >> "$LOG" 2>&1

# 3) 알리 소스로 생성·업로드
"$PROJ/.venv/bin/clipcart" daily --source aliexpress --live --force >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] exit=$?" >> "$LOG"

# 4) 게시 원장 git 공유 — 다른 머신과 중복 방지. 충돌 시 abort 로 안전 유지.
git add data >> "$LOG" 2>&1
git commit -m "data: scheduled aliexpress publish ledger sync" >> "$LOG" 2>&1
if git pull --rebase --autostash origin master >> "$LOG" 2>&1; then
    git push origin master >> "$LOG" 2>&1
else
    git rebase --abort >> "$LOG" 2>&1
    echo "[$(date -u +%FT%TZ)] ledger rebase conflict — aborted, push skipped" >> "$LOG"
fi
