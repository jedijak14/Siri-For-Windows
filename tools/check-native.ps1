$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
[void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot '../electron/native/automation.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){$errors | ForEach-Object { Write-Error $_.Message }; exit 1}
Write-Output 'Native PowerShell syntax checked. This is not interactive desktop integration testing.'
