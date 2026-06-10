# Windows 작업 스케줄러용 데일리 실행 스크립트
# 파이프라인 자체가 '오늘 이미 게시' 체크를 하므로 중복 실행에 안전하다.
Set-Location "c:\Users\ikess\Workspace\lionandthelab\clipcart"
$log = "logs\task_scheduler.log"
"[$(Get-Date -Format o)] daily run start" | Out-File $log -Append -Encoding utf8
& .venv\Scripts\clipcart.exe daily --live 2>&1 | Out-File $log -Append -Encoding utf8
"[$(Get-Date -Format o)] exit=$LASTEXITCODE" | Out-File $log -Append -Encoding utf8
