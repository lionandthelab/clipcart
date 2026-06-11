# Windows 작업 스케줄러용 데일리 실행 스크립트
# 매 실행마다 최신 엔진을 git pull + 의존성 동기화 후 생성한다.
# (origin/master 에 엔진을 push 하면 다음 아침 실행이 자동으로 새 엔진을 사용)
# 파이프라인 자체가 '오늘 이미 게시' 체크를 하므로 중복 실행에 안전하다.
Set-Location "c:\Users\ikess\Workspace\lionandthelab\clipcart"
$log = "logs\task_scheduler.log"
function Log($m) { "[$(Get-Date -Format o)] $m" | Out-File $log -Append -Encoding utf8 }

Log "daily run start"

# 1) 최신 엔진 받기 (런타임 데이터 변경은 autostash 로 보존). 실패해도 기존 코드로 진행.
try {
    git pull --rebase --autostash origin master 2>&1 | Out-File $log -Append -Encoding utf8
} catch {
    Log "git pull failed: $_"
}

# 2) 의존성 동기화 (엔진 업그레이드가 새 패키지를 요구할 수 있음)
& .venv\Scripts\python.exe -m pip install -q -r requirements.txt 2>&1 | Out-File $log -Append -Encoding utf8
& .venv\Scripts\python.exe -m pip install -q -e . 2>&1 | Out-File $log -Append -Encoding utf8

# 3) 최신 엔진으로 생성·업로드 (promo 엔진, 실패 시 kinetic 자동 폴백)
& .venv\Scripts\clipcart.exe daily --live 2>&1 | Out-File $log -Append -Encoding utf8
Log "exit=$LASTEXITCODE"
