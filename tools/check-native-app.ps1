$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$app=Start-Process (Join-Path $PSScriptRoot '../native-artifacts/Siri-for-Windows.exe') -PassThru
try {
 if (!$app.WaitForInputIdle(30000)) { throw 'Native app did not reach input idle.' }
 $app.Refresh()
 if ($app.HasExited) { throw 'Native app exited before showing its UI.' }
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
 $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'Prompt')
 $prompt=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
 if (!$prompt) { throw 'The native WPF composer was not found. Check startup/resource failures.' }
 $wakeCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'WakeStatus')
 $wake=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$wakeCondition)
 if (!$wake -or $wake.Current.Name -notmatch 'Hey Siri is off') { throw 'Wake recognition must be off by default.' }
 Write-Output 'Native WPF EXE launched, composer found, voice activation visibly off. No microphone was enabled.'
} finally {
 if (!$app.HasExited) { [void]$app.CloseMainWindow(); if (!$app.WaitForExit(5000)) { $app.Kill() } }
}
