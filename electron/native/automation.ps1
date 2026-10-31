$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class SiriNative {
 public delegate bool EnumProc(IntPtr hwnd, IntPtr lp);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr lp);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hwnd,StringBuilder text,int length);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
}
'@
function WindowInfo([IntPtr]$hwnd) {
 [uint32]$procId=0; [void][SiriNative]::GetWindowThreadProcessId($hwnd,[ref]$procId)
 $proc=Get-Process -Id $procId -ErrorAction SilentlyContinue
 $title=New-Object System.Text.StringBuilder 1024
 [void][SiriNative]::GetWindowText($hwnd,$title,1024)
 return @{handle=$hwnd.ToInt64().ToString();pid=$procId;process=$proc.ProcessName;title=$title.ToString()}
}
switch ($payload.action) {
 'windows' {
  $list=New-Object System.Collections.Generic.List[object]
  $callback=[SiriNative+EnumProc]{ param($h,$l)
   if([SiriNative]::IsWindowVisible($h)) { $info=WindowInfo $h; if($info.title){$list.Add($info)} }
   return $true
  }
  [void][SiriNative]::EnumWindows($callback,[IntPtr]::Zero)
  ConvertTo-Json -InputObject @($list.ToArray()) -Compress -Depth 4
 }
 'foreground' { ConvertTo-Json -InputObject (WindowInfo ([SiriNative]::GetForegroundWindow())) -Compress }
 'selection' {
  $h=[SiriNative]::GetForegroundWindow();$info=WindowInfo $h
  if($payload.handle -and ($info.handle -ne $payload.handle -or $info.pid -ne $payload.pid)){throw 'The foreground app changed. Select your text and try the shortcut again.'}
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($h)
  $focused=[System.Windows.Automation.AutomationElement]::FocusedElement
  if($focused.Current.IsPassword){throw 'Password fields cannot be read.'}
  if($focused.Current.ProcessId -ne $info.pid){throw 'The focused application changed. Try again.'}
  $text=''; $pattern=$null
  if($focused.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$pattern)) {
   $text=(@($pattern.GetSelection()) | ForEach-Object { $_.GetText(20000) }) -join "`n"
  }
  # Do not select all or read whole documents as a fallback.
  $info.text=$text
  ConvertTo-Json -InputObject $info -Compress -Depth 4
 }
 'browser' {
  $h=[IntPtr][long]$payload.handle;$info=WindowInfo $h
  if($info.pid -ne $payload.pid -or $info.process -notin @('chrome','msedge')){throw 'Browser window changed. Select it again.'}
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($h)
  $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Document)
  $docs=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
  $parts=New-Object System.Collections.Generic.List[string]
  foreach($doc in $docs) {
   if($doc.Current.IsOffscreen -or $doc.Current.IsPassword){continue}
   $pattern=$null
   if($doc.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$pattern)) {
    $value=$pattern.DocumentRange.GetText(24000)
    if($value){$parts.Add($value)}
   }
   if(($parts -join '').Length -ge 24000){break}
  }
  $info.text=($parts -join "`n"); if(!$info.text){throw 'This page does not expose accessible text. Use Share screen for a one-time image instead. No extension is required.'}
  if($info.text.Length -gt 24000){$info.text=$info.text.Substring(0,24000)}
  ConvertTo-Json -InputObject $info -Compress -Depth 4
 }
 'paste' {
  $h=[IntPtr][long]$payload.handle;$info=WindowInfo $h
  if(![SiriNative]::IsWindow($h) -or $info.pid -ne $payload.pid -or $info.process -ne $payload.process){throw 'The original app is no longer available. Copy the result manually.'}
  if(![SiriNative]::SetForegroundWindow($h)){throw 'Windows blocked switching apps. Copy and paste the result manually.'}
  Start-Sleep -Milliseconds 250
  if([SiriNative]::GetForegroundWindow() -ne $h){throw 'Focus changed. Nothing was inserted.'}
  $focused=[System.Windows.Automation.AutomationElement]::FocusedElement
  if($focused.Current.IsPassword -or $focused.Current.ProcessId -ne $payload.pid){throw 'Unsafe or different target field. Nothing was inserted.'}
  $pattern=$null
  if(!$focused.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$pattern)){throw 'The target cannot verify its selection. Copy and paste manually.'}
  $selected=(@($pattern.GetSelection()) | ForEach-Object { $_.GetText(20000) }) -join "`n"
  if($selected -cne [string]$payload.original){throw 'The selected text changed. Nothing was inserted.'}
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait('^v')
  '{"attempted":true}'
 }
 'outlook' {
  # Classic Outlook only; never create a new instance or read stores without a user click.
  $outlook=[Runtime.InteropServices.Marshal]::GetActiveObject('Outlook.Application')
  $namespace=$outlook.GetNamespace('MAPI')
  $folder=$namespace.GetDefaultFolder(6)
  $items=$folder.Items; $items.Sort('[ReceivedTime]',$true)
  $query=[string]$payload.query;$found=New-Object System.Collections.Generic.List[object]
  $max=[Math]::Min($items.Count,500)
  for($i=1;$i -le $max;$i++) {
   $mail=$items.Item($i)
   if($mail.Class -ne 43){continue}
   $subject=[string]$mail.Subject;$sender=[string]$mail.SenderName
   if($subject.IndexOf($query,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or $sender.IndexOf($query,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or ([string]$mail.Body).IndexOf($query,[StringComparison]::OrdinalIgnoreCase) -ge 0){
    $body=[string]$mail.Body;if($body.Length -gt 3000){$body=$body.Substring(0,3000)}
    $found.Add(@{title=$subject;sender=$sender;date=$mail.ReceivedTime.ToString('o');text=$body;source='Outlook Inbox'})
    if($found.Count -ge 12){break}
   }
  }
  ConvertTo-Json -InputObject @($found.ToArray()) -Compress -Depth 5
 }
 default {throw 'Unsupported native operation.'}
}
