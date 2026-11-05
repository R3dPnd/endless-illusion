# Create Start-menu and desktop shortcuts that open the Endless Illusion
# desktop app (pywebview, from this checkout's .venv) without a terminal.
# Run once after `python pnd.py` has set things up:
#   powershell -ExecutionPolicy Bypass -File scripts/install-shortcut.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "No .venv yet: run 'python pnd.py' in $root once first." }
if (-not (Test-Path (Join-Path $root "ui\dist\index.html"))) { throw "No client build yet: run 'python pnd.py' in $root once first." }

$shell = New-Object -ComObject WScript.Shell
$targets = @(
  (Join-Path ([Environment]::GetFolderPath("Programs")) "Endless Illusion.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Desktop")) "Endless Illusion.lnk")
)
foreach ($path in $targets) {
  $lnk = $shell.CreateShortcut($path)
  $lnk.TargetPath = $pythonw
  $lnk.Arguments = "-m hub.desktop"
  $lnk.WorkingDirectory = $root
  $lnk.Description = "Endless Illusion control plane"
  $lnk.Save()
  Write-Host "created $path"
}
