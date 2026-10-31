$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class SiriWindowCheck {
 [DllImport("user32.dll")] public static extern int GetWindowRgn(IntPtr window,IntPtr region);
 [DllImport("gdi32.dll")] public static extern IntPtr CreateRectRgn(int left,int top,int right,int bottom);
 [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr region);
}
'@
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
 $second=Start-Process (Join-Path $PSScriptRoot '../native-artifacts/Siri-for-Windows.exe') -PassThru
 if (!$second.WaitForExit(10000)) { $second.Kill(); throw 'A second launch should activate the first instance and exit.' }
 if ($second.ExitCode -ne 0) { throw 'Second-instance activation returned an error.' }
 $region=[SiriWindowCheck]::CreateRectRgn(0,0,0,0)
 try { if ([SiriWindowCheck]::GetWindowRgn($app.MainWindowHandle,$region) -ne 3) { throw 'Expected a rounded (complex) native window region.' } } finally { [void][SiriWindowCheck]::DeleteObject($region) }
 function Find-Window($title) {
  $deadline=[DateTime]::UtcNow.AddSeconds(15)
  do {
   $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$title)
   $found=[System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,$condition)
   if(!$found) { $found=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition) }
   if($found) { return $found }
   Start-Sleep -Milliseconds 100
  } while ([DateTime]::UtcNow -lt $deadline)
  $windows=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
  $titles=@($windows | ForEach-Object {$_.Current.Name}) -join ' | '
  throw "Window not found: $title. Desktop windows: $titles"
 }
 $bubbleLauncher=Start-Process (Join-Path $PSScriptRoot '../native-artifacts/Siri-for-Windows.exe') -ArgumentList '--bubble' -PassThru
 if (!$bubbleLauncher.WaitForExit(10000)) { $bubbleLauncher.Kill(); throw 'Bubble activation did not hand off.' }
 $bubble=Find-Window 'Siri bubble'
 $bubblePromptCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'BubblePrompt')
 if (!$bubble.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$bubblePromptCondition)) { throw 'Bubble composer not found.' }
 if ($wake.Current.Name -notmatch 'Hey Siri is off') { throw 'Manual bubble activation must not enable wake recognition.' }
 $closeCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Close')
 $close=$bubble.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$closeCondition)
 $close.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
 $settingsLauncher=Start-Process (Join-Path $PSScriptRoot '../native-artifacts/Siri-for-Windows.exe') -ArgumentList '--settings' -PassThru
 if (!$settingsLauncher.WaitForExit(10000)) { $settingsLauncher.Kill(); throw 'Settings activation did not hand off.' }
 $settings=Find-Window 'Settings & privacy'
 foreach($id in @('TextModel','VisionModel')) {
  $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
  if (!$settings.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)) { throw "Model selector not found: $id" }
 }
 $close=$settings.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$closeCondition)
 $close.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
 Write-Output 'Native EXE launch, rounded borders, composer, wake-off default, single instance, bubble and settings/model controls passed. No microphone was enabled.'
} finally {
 if (!$app.HasExited) { [void]$app.CloseMainWindow(); if (!$app.WaitForExit(5000)) { $app.Kill() } }
}
