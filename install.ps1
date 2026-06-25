# One-shot installer for the Claude Code status line on Windows (PowerShell).
# Copies statusline.py into %USERPROFILE%\.claude and wires the statusLine block
# into settings.json (preserving any existing settings).
#
# Usage (from the repo folder):
#   powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"

# Resolve the Python launcher (prefer the 'py' launcher, then 'python').
$py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { Write-Error "Python 3 is required but was not found on PATH."; exit 1 }

$claudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null

$srcDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$destPy   = Join-Path $claudeDir "statusline.py"
$settings = Join-Path $claudeDir "settings.json"

Copy-Item (Join-Path $srcDir "statusline.py") $destPy -Force
Write-Host "OK  installed statusline.py -> $destPy"

# The status line command. 'py' uses the Windows Python launcher.
$command = "$py `"$destPy`""

# Merge the statusLine block into settings.json without clobbering other keys.
$data = @{}
if (Test-Path $settings) {
    try {
        $existing = Get-Content -Raw -Path $settings | ConvertFrom-Json
        # convert PSCustomObject to a hashtable so we can add/replace a key
        $data = @{}
        foreach ($p in $existing.PSObject.Properties) { $data[$p.Name] = $p.Value }
    } catch {
        Write-Warning "$settings is not valid JSON; leaving it untouched. Add this manually:"
        Write-Host (@{ statusLine = @{ type = "command"; command = $command; padding = 0 } } | ConvertTo-Json -Depth 5)
        exit 0
    }
}
$data["statusLine"] = @{ type = "command"; command = $command; padding = 0 }
($data | ConvertTo-Json -Depth 10) | Set-Content -Path $settings -Encoding UTF8
Write-Host "OK  wired statusLine into $settings"
Write-Host ""
Write-Host "Done. Open a new Claude Code session (or wait for the next render) to see it."
Write-Host "Tip: use Windows Terminal for proper Unicode/ANSI rendering."
