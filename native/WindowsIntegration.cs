using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Automation;
using Microsoft.Data.Sqlite;
namespace SiriNative;
public sealed record AppWindow(nint Handle,int Pid,string Process,string Title)
{
 public override string ToString()=>Title;
 public string App=>Process.ToLowerInvariant() switch{"chrome"=>"Chrome","msedge"=>"Edge","winword"=>"Word","excel"=>"Excel","powerpnt"=>"PowerPoint","outlook"=>"Outlook","onenote"=>"OneNote",_=>Process};
}
public sealed record Selection(AppWindow Window,string Text);
public static class WindowsIntegration
{
 private delegate bool EnumCallback(nint handle,nint data);
 [DllImport("user32.dll")] private static extern bool EnumWindows(EnumCallback callback,nint data);
 [DllImport("user32.dll")] private static extern bool IsWindowVisible(nint handle);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern int GetWindowText(nint handle,StringBuilder text,int count);
 [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(nint handle,out uint pid);
 [DllImport("user32.dll")] public static extern nint GetForegroundWindow();
 [DllImport("user32.dll")] private static extern bool SetForegroundWindow(nint handle);
 [DllImport("ole32.dll",CharSet=CharSet.Unicode)] private static extern int CLSIDFromProgID(string id,out Guid clsid);
 [DllImport("oleaut32.dll",PreserveSig=false)] private static extern void GetActiveObject(ref Guid clsid,nint reserved,[MarshalAs(UnmanagedType.IUnknown)] out object obj);
 public static AppWindow Info(nint handle){GetWindowThreadProcessId(handle,out var pid);using var process=Process.GetProcessById((int)pid);var title=new StringBuilder(1024);GetWindowText(handle,title,1024);return new(handle,(int)pid,process.ProcessName,title.ToString());}
 public static List<AppWindow> Browsers(Preferences settings){var result=new List<AppWindow>();EnumWindows((handle,_)=>{try{if(IsWindowVisible(handle)){var w=Info(handle);if((w.Process=="chrome"||w.Process=="msedge")&&w.Title.Length>0&&!Rules.IsExcluded(settings,w.App))result.Add(w);}}catch{}return true;},0);return result;}
 public static Source Browser(AppWindow window,Preferences settings)
 {
  if(Rules.IsExcluded(settings,window.App))throw new InvalidOperationException("This browser is excluded in Settings.");var current=Info(window.Handle);if(current.Pid!=window.Pid||current.Process!=window.Process)throw new InvalidOperationException("The browser window changed. Choose it again.");
  var root=AutomationElement.FromHandle(window.Handle);var docs=root.FindAll(TreeScope.Descendants,new PropertyCondition(AutomationElement.ControlTypeProperty,ControlType.Document));var text=new StringBuilder();
  foreach(AutomationElement doc in docs){if(doc.Current.IsOffscreen||doc.Current.IsPassword)continue;if(doc.TryGetCurrentPattern(TextPattern.Pattern,out var pattern)){text.AppendLine(((TextPattern)pattern).DocumentRange.GetText(24000));if(text.Length>=24000)break;}}
  if(text.Length==0)throw new InvalidOperationException("This page exposes no accessible text. Use the one-time screenshot tool instead. No extension is required.");return new(){App=window.App,Title=window.Title,Text=text.ToString()[..Math.Min(text.Length,24000)]};
 }
 public static Selection Selected(Preferences settings)
 {
  var window=Info(GetForegroundWindow());if(Rules.IsExcluded(settings,window.App))throw new InvalidOperationException("This app is excluded in Settings.");var element=AutomationElement.FocusedElement;if(element.Current.IsPassword||element.Current.ProcessId!=window.Pid)throw new InvalidOperationException("This field cannot be read safely.");var text="";if(element.TryGetCurrentPattern(TextPattern.Pattern,out var pattern))text=string.Join("\n",((TextPattern)pattern).GetSelection().Select(x=>x.GetText(20000)));return new(window,text);
 }
 public static async Task Paste(Selection selection,string text,Preferences settings)
 {
  if(Rules.IsExcluded(settings,selection.Window.App)||selection.Text.Length==0)throw new InvalidOperationException("No supported original selection. Copy and paste manually.");
  var current=Info(selection.Window.Handle);if(current.Pid!=selection.Window.Pid||current.Process!=selection.Window.Process)throw new InvalidOperationException("The original app changed.");
  if(!SetForegroundWindow(current.Handle))throw new InvalidOperationException("Windows blocked switching apps. Paste manually.");await Task.Delay(250);if(GetForegroundWindow()!=current.Handle)throw new InvalidOperationException("Focus changed. Nothing was inserted.");var focused=AutomationElement.FocusedElement;
  if(focused.Current.IsPassword||focused.Current.ProcessId!=current.Pid||!focused.TryGetCurrentPattern(TextPattern.Pattern,out var pattern)||string.Join("\n",((TextPattern)pattern).GetSelection().Select(x=>x.GetText(20000)))!=selection.Text)throw new InvalidOperationException("The selection changed or cannot be verified. Nothing was inserted.");
  System.Windows.Clipboard.SetText(text);System.Windows.Forms.SendKeys.SendWait("^v");
 }
 public static List<Source> Inbox(string query,Preferences settings)
 {
  if(Rules.IsExcluded(settings,"Outlook"))throw new InvalidOperationException("Outlook is excluded.");if(string.IsNullOrWhiteSpace(query))throw new ArgumentException("Enter search terms.");
  object? app=null,ns=null,folder=null,items=null;
  try{Marshal.ThrowExceptionForHR(CLSIDFromProgID("Outlook.Application",out var id));GetActiveObject(ref id,0,out app);dynamic outlook=app;ns=outlook.GetNamespace("MAPI");dynamic space=ns;folder=space.GetDefaultFolder(6);dynamic inbox=folder;items=inbox.Items;dynamic messages=items;messages.Sort("[ReceivedTime]",true);var results=new List<Source>();int count=Math.Min((int)messages.Count,500);for(int i=1;i<=count;i++){object? mail=null;try{mail=messages.Item(i);dynamic m=mail;if((int)m.Class!=43)continue;string title=(string)m.Subject??"",body=(string)m.Body??"",sender=(string)m.SenderName??"";if((title+" "+sender+" "+body).Contains(query,StringComparison.OrdinalIgnoreCase)){results.Add(new(){App="Outlook",Title=sender+" · "+title,Text=body[..Math.Min(body.Length,3000)]});if(results.Count>=12)break;}}finally{Release(mail);}}return results;}
  catch(COMException e){throw new InvalidOperationException("Open classic Outlook and allow its COM/security prompts. New Outlook is not supported. "+e.Message);}finally{Release(items);Release(folder);Release(ns);Release(app);}
 }
 private static void Release(object? value){if(value!=null&&Marshal.IsComObject(value))Marshal.ReleaseComObject(value);}
 public static List<Source> History(string browser,string profile,string query,Preferences settings)
 {
  if(browser!="Chrome"&&browser!="Edge")throw new ArgumentException("Choose Chrome or Edge.");if(Rules.IsExcluded(settings,browser))throw new InvalidOperationException("This browser is excluded.");if(!System.Text.RegularExpressions.Regex.IsMatch(profile,"\\A(Default|Profile [0-9]+)\\z"))throw new ArgumentException("Invalid profile.");if(string.IsNullOrWhiteSpace(query))throw new ArgumentException("Enter search terms.");
  var source=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),browser=="Chrome"?"Google/Chrome/User Data":"Microsoft/Edge/User Data",profile,"History");var temp=Path.Combine(Path.GetTempPath(),"SiriHistory-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(temp);
  try{foreach(var suffix in new[]{"","-wal","-shm"})if(File.Exists(source+suffix))File.Copy(source+suffix,Path.Combine(temp,"History"+suffix));using var db=new SqliteConnection(new SqliteConnectionStringBuilder{DataSource=Path.Combine(temp,"History"),Mode=SqliteOpenMode.ReadOnly,Pooling=false}.ToString());db.Open();using var command=db.CreateCommand();command.CommandText="SELECT title,url FROM urls WHERE title LIKE $query ESCAPE '^' OR url LIKE $query ESCAPE '^' ORDER BY last_visit_time DESC LIMIT 30";command.Parameters.AddWithValue("$query","%"+query.Replace("^","^^").Replace("%","^%").Replace("_","^_")+"%");using var reader=command.ExecuteReader();var result=new List<Source>();while(reader.Read())result.Add(new(){App=browser,Title=reader.IsDBNull(0)?"Page":reader.GetString(0),Text=reader.IsDBNull(1)?"":reader.GetString(1)});return result;}
  finally{try{Directory.Delete(temp,true);}catch{}}
 }
 public static void Open(string target)=>Process.Start(new ProcessStartInfo(target){UseShellExecute=true});
}
