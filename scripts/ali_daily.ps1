# Windows 작업 스케줄러용 알리익스프레스 데일리 실행 (하루 1회).
# 윈도우 쿠팡 데일리(daily_task.ps1, 아침 07:20)와 별개의 두 번째 파이프라인.
# --force: 같은 날 다른 소스가 이미 게시했어도 알리를 진행. 상품/이름/니치 중복은
# history.json 원장이 차단(실행 전 git pull 로 다른 머신 게시분까지 반영).
Set-Location "c:\Users\ikess\Workspace\lionandthelab\clipcart"
# 비대화형(cp949) 환경에서 유니코드 출력이 UnicodeEncodeError 로 죽는 것 방지
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$log = "logs\task_scheduler_ali.log"
function Log($m) { "[$(Get-Date -Format o)] $m" | Out-File $log -Append -Encoding utf8 }

Log "ali run start"

# 1) 최신 엔진 + 타 머신 게시 원장 받기 (런타임 변경은 autostash 보존). 실패해도 진행.
try {
    git pull --rebase --autostash origin master 2>&1 | Out-File $log -Append -Encoding utf8
} catch {
    Log "git pull failed: $_"
}

# 2) 의존성 동기화 (엔진 업그레이드가 새 패키지를 요구할 수 있음)
& .venv\Scripts\python.exe -m pip install -q -r requirements.txt 2>&1 | Out-File $log -Append -Encoding utf8
& .venv\Scripts\python.exe -m pip install -q -e . 2>&1 | Out-File $log -Append -Encoding utf8

# 3) 알리 소스로 생성·업로드
& .venv\Scripts\clipcart.exe daily --source aliexpress --live --force 2>&1 | Out-File $log -Append -Encoding utf8
Log "exit=$LASTEXITCODE"

# 4) 게시 원장 git 공유 — 다른 머신과 상품/니치 중복 방지. 충돌 시 abort 로 안전 유지.
try {
    git add data 2>&1 | Out-File $log -Append -Encoding utf8
    git commit -m "data: scheduled aliexpress publish ledger sync" 2>&1 | Out-File $log -Append -Encoding utf8
    git pull --rebase --autostash origin master 2>&1 | Out-File $log -Append -Encoding utf8
    if ($LASTEXITCODE -eq 0) {
        git push origin master 2>&1 | Out-File $log -Append -Encoding utf8
    } else {
        git rebase --abort 2>&1 | Out-File $log -Append -Encoding utf8
        Log "ledger rebase conflict — aborted, push skipped"
    }
} catch { Log "ledger sync failed: $_" }
