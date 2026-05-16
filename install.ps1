$D = "$HOME\.lum"
$RAW = "https://raw.githubusercontent.com/AnrosPrac/lcli/main"

python -m pip install --user httpx websockets pynacl -q --no-warn-script-location

if (!(Test-Path $D)) { 
    New-Item -ItemType Directory -Path $D 
}

$destructContent = @"
Remove-Item -Recurse -Force "`$HOME\.lum_config" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "`$HOME\.lum_client" -ErrorAction SilentlyContinue
Remove-Item -Force "$D\lum.py" -ErrorAction SilentlyContinue
Write-Host "[✔] Lumetrix session files destroyed."
"@
$destructContent | Out-File -FilePath "$D\destruct.ps1" -Encoding utf8

Invoke-WebRequest -Uri "$RAW/lum.py" -OutFile "$D\lum.py"

$ProfilePath = $PROFILE
if (!(Test-Path $ProfilePath)) { 
    New-Item -Type File -Path $ProfilePath -Force 
}

$aliases = @"

function lum { python "$D\lum.py" `$args }
function hello-lumetrix { iex (iwr -useb https://lcli.sidhi.xyz/install.ps1) }
function lum-destruct { & "$D\destruct.ps1" }

# Hide lum commands from history
if (Get-Module -ListAvailable PSReadLine) {
    Set-PSReadLineOption -AddToHistoryHandler {
        param([string]`$line)
        if (`$line -like "lum*") { return `$false }
        return `$true
    }
}
"@

$aliases | Add-Content -Path $ProfilePath

Write-Host "[✔] Installation Complete. History protection active." -ForegroundColor Green
Write-Host "[!] Restart your terminal or run: . `$PROFILE" -ForegroundColor Yellow