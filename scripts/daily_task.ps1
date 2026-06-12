# Windows 작업 스케줄러용 데일리 실행 스크립트
# 매 실행마다 최신 엔진을 git pull + 의존성 동기화 후 생성한다.
# (origin/master 에 엔진을 push 하면 다음 아침 실행이 자동으로 새 엔진을 사용)
# 파이프라인 자체가 '오늘 이미 게시' 체크를 하므로 중복 실행에 안전하다.
Set-Location "c:\Users\ikess\Workspace\lionandthelab\clipcart"
# 비대화형(cp949) 환경에서 유니코드 출력이 UnicodeEncodeError 로 죽는 것 방지
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
# clipcart 의 UTF-8 stdout 을 PowerShell 이 cp949 로 오독해 로그가 깨지는 것 방지
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
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

# 3.5) 성과 스냅샷 수집 + 링크인바이오 페이지 갱신 (실패해도 게시와 무관)
try { & .venv\Scripts\clipcart.exe metrics --days 7 2>&1 | Out-File $log -Append -Encoding utf8 } catch { Log "metrics failed: $_" }
try { & .venv\Scripts\clipcart.exe bio 2>&1 | Out-File $log -Append -Encoding utf8 } catch { Log "bio failed: $_" }

# 4) 게시 원장(history/posts/state) git 공유 — 다른 머신(Mac 알리)과 상품/니치 중복 방지.
#    실행 전 pull 로 타 머신 게시분을 이미 반영했고, 여기선 이번 게시분을 push 한다.
#    충돌 시 rebase 를 abort 해 저장소를 깨끗이 유지(다음 실행에서 재동기화).
try {
    git add data docs/bio 2>&1 | Out-File $log -Append -Encoding utf8
    git commit -m "data: scheduled coupang publish ledger sync" 2>&1 | Out-File $log -Append -Encoding utf8
    git pull --rebase --autostash origin master 2>&1 | Out-File $log -Append -Encoding utf8
    if ($LASTEXITCODE -eq 0) {
        git push origin master 2>&1 | Out-File $log -Append -Encoding utf8
    } else {
        git rebase --abort 2>&1 | Out-File $log -Append -Encoding utf8
        Log "ledger rebase conflict — aborted, push skipped"
    }
} catch { Log "ledger sync failed: $_" }
