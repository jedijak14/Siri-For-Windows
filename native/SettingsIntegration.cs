using System;
using System.IO;
using Microsoft.Win32;
namespace SiriNative;
internal static class SettingsIntegration
{
 private const string Listing=@"Software\Microsoft\Windows\CurrentVersion\Uninstall\SiriForWindowsNativeSettings";
 private const string Protocol=@"Software\Classes\siriforwindows";
 public static void Register()
 {
  var exe=Environment.ProcessPath??throw new InvalidOperationException("Cannot locate this executable.");
  if(Path.GetFileNameWithoutExtension(exe).Equals("dotnet",StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Register integration from the published EXE, not dotnet run.");
  using(var key=Registry.CurrentUser.CreateSubKey(Listing)){key.SetValue("DisplayName","Siri for Windows — Settings integration");key.SetValue("DisplayVersion","3.1.0");key.SetValue("Publisher","Siri for Windows community project");key.SetValue("InstallLocation",Path.GetDirectoryName(exe)!);key.SetValue("DisplayIcon",exe);key.SetValue("ModifyPath",$"\"{exe}\" --settings");key.SetValue("UninstallString",$"\"{exe}\" --remove-settings-integration");key.SetValue("NoModify",0,RegistryValueKind.DWord);key.SetValue("NoRepair",1,RegistryValueKind.DWord);}
  using(var key=Registry.CurrentUser.CreateSubKey(Protocol)){key.SetValue("","URL:Siri for Windows settings");key.SetValue("URL Protocol","");using var command=key.CreateSubKey(@"shell\open\command");command.SetValue("",$"\"{exe}\" --settings \"%1\"");}
 }
 public static void Remove(){Registry.CurrentUser.DeleteSubKeyTree(Listing,false);Registry.CurrentUser.DeleteSubKeyTree(Protocol,false);}
}
