using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
namespace SiriNative;
internal sealed class WritingWindow : ToolWindow
{
 private readonly MainWindow app;
 private readonly Selection? selection;
 private readonly TextBox input;
 private readonly TextBox result;
 private readonly TextBlock status;
 private CancellationTokenSource? request;
 private readonly Button replace;
 public WritingWindow(MainWindow app,Selection? selection):base(app,"Writing Tools",530,690)
 {
  this.app=app;this.selection=selection;Topmost=true;
  Body.Children.Add(Ui.Label(selection?.Window.Title??"Select text in your app, then use the opt-in Ctrl+Shift+Space shortcut. Unsupported fields can use copy/paste."));input=Ui.Field(Body,"Your text or draft description",selection?.Text??"",true);input.MaxLength=20000;var buttons=new WrapPanel();Body.Children.Add(buttons);
  foreach(var task in new[]{"Proofread","Rewrite","Make professional","Make friendly","Make concise","Compose a draft","Excel formula","Slide outline"})buttons.Children.Add(Ui.Async(task,()=>Revise(task)));
  status=Ui.Label("");Body.Children.Add(status);result=Ui.Output(Body);result.MinHeight=100;replace=Ui.Async("Replace verified selection",async()=>{if(selection==null||string.IsNullOrWhiteSpace(result.Text))throw new InvalidOperationException("No original selection or result. Copy and paste manually.");if(!app.Confirm("Replace selected text?","Review your revision. Insert it into "+selection.Window.Title+" only if the original selection can still be verified? Your clipboard will contain the revision."))return;Hide();try{await WindowsIntegration.Paste(selection,result.Text,app.Store.Data.Settings);replace.IsEnabled=false;status.Text="Paste shortcut sent to the verified selection. Check your app.";}finally{Show();}});replace.IsEnabled=selection?.Text.Length>0;
  var actions=new WrapPanel();actions.Children.Add(Ui.Button("Use copied text",()=>input.Text=Clipboard.ContainsText()?Clipboard.GetText():""));actions.Children.Add(Ui.Button("Copy result",()=>{if(result.Text.Length>0)Clipboard.SetText(result.SelectedText.Length>0?result.SelectedText:result.Text);}));actions.Children.Add(replace);actions.Children.Add(Ui.Button("Stop",()=>request?.Cancel()));Body.Children.Add(actions);Body.Children.Add(Ui.Label("Separate native panel. No text is replaced automatically. Accessibility support varies by app; password fields and changed selections are refused."));Closed+=(_,_)=>request?.Cancel();
 }
 private async Task Revise(string task)
 {
  if(request!=null)return;if(string.IsNullOrWhiteSpace(input.Text))throw new InvalidOperationException("Add some text or describe a draft.");if(selection!=null&&app.Store.Data.Settings.ExcludedApps.Contains(selection.Window.App))throw new InvalidOperationException("This app is now excluded.");using var cancellation=new CancellationTokenSource();request=cancellation;status.Text="Revising locally…";try{var response=await app.Ai.Ask(app.Store.Data.Settings,task+":\n"+input.Text,new(),new(),null,cancellation.Token,"Return only the finished text or formula, with no introduction. Preserve names, facts and numbers unless the user asks to change them.");cancellation.Token.ThrowIfCancellationRequested();result.Text=response.Answer;replace.IsEnabled=selection?.Text.Length>0;status.Text="Review before copying or inserting · "+response.Model;}catch(OperationCanceledException){status.Text="Stopped. Draft kept.";}finally{request=null;}
 }
}
