using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
namespace SiriNative;
internal sealed class WakeBubble : Window
{
 private readonly MainWindow app;
 private readonly TextBox prompt=new(){AcceptsReturn=true,TextWrapping=TextWrapping.Wrap,MinHeight=60,MaxHeight=110,ToolTip="Ask Siri; Enter sends, Shift+Enter adds a line."};
 private readonly TextBox answer=new(){IsReadOnly=true,TextWrapping=TextWrapping.Wrap,MinHeight=110,MaxHeight=210,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};
 private readonly TextBlock status=Ui.Label("Type a request or select Dictate. Nothing sends until you press Ask.");
 private readonly List<Turn> history=new();
 private CancellationTokenSource? operation;
 public WakeBubble(MainWindow app)
 {
  this.app=app;Style=(Style)Application.Current.FindResource(typeof(Window));Title="Siri bubble";Width=430;Height=480;ResizeMode=ResizeMode.NoResize;Topmost=true;ShowInTaskbar=false;WindowStartupLocation=WindowStartupLocation.Manual;var area=SystemParameters.WorkArea;Left=Math.Max(area.Left,area.Right-Width-24);Top=Math.Max(area.Top,area.Bottom-Height-24);
  var body=new StackPanel{Margin=new Thickness(20,8,20,18)};body.Children.Add(new Image{Source=new BitmapImage(new Uri("pack://application:,,,/Assets/siri-logo.png")),Width=54,Height=54,Margin=new Thickness(0,0,0,12)});body.Children.Add(prompt);var actions=new WrapPanel{Margin=new Thickness(0,10,0,0)};actions.Children.Add(Ui.Async("Dictate",Dictate));actions.Children.Add(Ui.Async("Ask",Ask));actions.Children.Add(Ui.Button("Stop",()=>operation?.Cancel()));actions.Children.Add(Ui.Button("Open app",()=>{operation?.Cancel();Hide();app.Show();app.WindowState=WindowState.Normal;app.Activate();}));body.Children.Add(actions);body.Children.Add(answer);body.Children.Add(status);Content=new ScrollViewer{Content=body,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};
  System.Windows.Automation.AutomationProperties.SetAutomationId(prompt,"BubblePrompt");System.Windows.Automation.AutomationProperties.SetAutomationId(answer,"BubbleAnswer");prompt.PreviewKeyDown+=async(_,e)=>{if(e.Key==Key.Enter&&(Keyboard.Modifiers&ModifierKeys.Shift)==0){e.Handled=true;try{await Ask();}catch(Exception error){status.Text=error.Message;}}};Closed+=(_,_)=>operation?.Cancel();Loaded+=(_,_)=>prompt.Focus();
 }
 public async Task Dictate()
 {
  if(operation!=null)return;using var cancellation=new CancellationTokenSource();operation=cancellation;status.Text="Listening for one utterance… Close or Stop cancels. Review before Ask.";try{prompt.Text=await app.Speech.Dictate(cancellation.Token);status.Text="Review the words, then Ask. Audio was not saved.";}catch(OperationCanceledException){status.Text="Stopped.";}catch(Exception error){status.Text=error.Message;}finally{operation=null;}
 }
 private async Task Ask()
 {
  if(operation!=null||string.IsNullOrWhiteSpace(prompt.Text))return;var question=prompt.Text.Trim();using var cancellation=new CancellationTokenSource();operation=cancellation;status.Text="Asking the selected local model…";try{var response=await app.Ai.Ask(app.Store.Data.Settings,question,history,new(),null,cancellation.Token);cancellation.Token.ThrowIfCancellationRequested();answer.Text=response.Answer;history.Add(new(){Question=question,Answer=response.Answer,Model=response.Model});if(history.Count>8)history.RemoveAt(0);prompt.Clear();status.Text="Answered locally · "+response.Model;}catch(OperationCanceledException){status.Text="Stopped.";}catch(Exception error){status.Text=error.Message;}finally{operation=null;}
 }
}
