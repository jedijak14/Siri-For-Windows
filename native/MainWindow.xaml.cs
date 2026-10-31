using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;
using Microsoft.Win32;
namespace SiriNative;
public partial class MainWindow : Window
{
 internal readonly Store Store=new();
 internal readonly LocalAi Ai=new();
 internal readonly SpeechService Speech=new();
 private Conversation current=new();
 private readonly List<Source> sources=new();
 private string? image;
 private CancellationTokenSource? request;
 private bool loadingHistory;
 private readonly DispatcherTimer reminders=new(){Interval=TimeSpan.FromMinutes(1)};
 private readonly HashSet<string> reminded=new();
 private HwndSource? hwndSource;
 private const int HotkeyId=8301;
 [System.Runtime.InteropServices.DllImport("user32.dll")]private static extern bool RegisterHotKey(nint handle,int id,uint modifiers,uint key);
 [System.Runtime.InteropServices.DllImport("user32.dll")]private static extern bool UnregisterHotKey(nint handle,int id);
 public MainWindow()
 {
  InitializeComponent();RefreshHistory();Speech.Woke+=()=>Dispatcher.BeginInvoke(new Action(()=>{if(!Speech.Armed)return;Show();WindowState=WindowState.Normal;Activate();Prompt.Focus();Status.Text="Listening phrase detected. Type a request, or click dictation.";}));Speech.Failed+=error=>Dispatcher.BeginInvoke(new Action(()=>{Speech.StopWake();UpdateWake();Status.Text="Voice activation stopped: "+error;}));
  Loaded+=async(_,_)=>{if(Store.LoadError!=null)MessageBox.Show(this,Store.LoadError,"Saved data");await RefreshModels();};
  SourceInitialized+=(_,_)=>{hwndSource=HwndSource.FromHwnd(new WindowInteropHelper(this).Handle);hwndSource?.AddHook(WindowMessage);};
  Closed+=(_,_)=>{request?.Cancel();reminders.Stop();Speech.Dispose();if(hwndSource!=null){UnregisterHotKey(hwndSource.Handle,HotkeyId);hwndSource.RemoveHook(WindowMessage);}try{Store.Save();}catch{}};
  reminders.Tick+=(_,_)=>CheckReminders();reminders.Start();CheckReminders();
 }
 private nint WindowMessage(nint hwnd,int msg,nint wParam,nint lParam,ref bool handled){if(msg==0x0312&&(int)wParam==HotkeyId){handled=true;try{var selected=WindowsIntegration.Selected(Store.Data.Settings);new WritingWindow(this,selected).Show();}catch(Exception error){MessageBox.Show(this,error.Message,"Writing Tools");}}return 0;}
 internal bool SetWritingShortcut(bool enabled){if(hwndSource==null)return false;UnregisterHotKey(hwndSource.Handle,HotkeyId);var result=!enabled||RegisterHotKey(hwndSource.Handle,HotkeyId,0x4000|0x0002|0x0004,0x20);ShortcutEnabled=enabled&&result;return result;}
 private void CheckReminders(){foreach(var entry in Store.Data.Reminders.Where(x=>!x.Done&&x.Due<=DateTimeOffset.Now)){var key=entry.Id+entry.Due;if(reminded.Add(key))Status.Text="Reminder due: "+entry.Title+" · Open Tools → Reminders.";}}
 internal async Task RefreshModels(){try{var models=await Ai.Models();ModelStatus.Text=models.Length==0?"Install a local Ollama model":"Local model ready · "+(Store.Data.Settings.Model.Length>0?Store.Data.Settings.Model:models[0]);}catch{ModelStatus.Text="Local AI not connected · Start Ollama";}}
 internal bool ShortcutEnabled {get;private set;}
 internal void RefreshConversationList(){NewChat(this,new RoutedEventArgs());RefreshHistory();}
 internal void UpdateWake()=>WakeStatus.Text=Speech.Armed?"●  Hey Siri is listening":Speech.Requested?"◌  Hey Siri paused for speech":"○  Hey Siri is off";
 internal bool Confirm(string title,string text)=>MessageBox.Show(OwnedWindows.Cast<Window>().FirstOrDefault(w=>w.IsActive)??this,text,title,MessageBoxButton.YesNo,MessageBoxImage.Question,MessageBoxResult.No)==MessageBoxResult.Yes;
 internal void Notify(string text)=>Status.Text=text;
 internal void AddSources(IEnumerable<Source> incoming){foreach(var source in incoming){if(Rules.IsExcluded(Store.Data.Settings,source.App))throw new InvalidOperationException(source.App+" is excluded.");if(sources.Count>=12)throw new InvalidOperationException("Use up to twelve text excerpts per request.");sources.Add(new(){App=source.App,Title=source.Title,Text=source.Text[..Math.Min(source.Text.Length,24000)]});}RenderAttachments();Status.Text="Context attached. Review your question, then press Send.";Prompt.Focus();}
 private void RenderAttachments(){Attachments.Children.Clear();foreach(var source in sources.ToArray()){var button=new Button{Content="×  "+(source.Title.Length>45?source.Title[..45]+"…":source.Title),FontSize=10};button.Click+=(_,_)=>{sources.Remove(source);RenderAttachments();};Attachments.Children.Add(button);}if(image!=null){var button=new Button{Content="×  Attached image",FontSize=10};button.Click+=(_,_)=>{image=null;RenderAttachments();};Attachments.Children.Add(button);}}
 private void NewChat(object sender,RoutedEventArgs e){request?.Cancel();current=new();sources.Clear();image=null;RenderAttachments();Messages.Children.Clear();EmptyState.Visibility=Visibility.Visible;ConversationTitle.Text="Siri";Prompt.Clear();HistoryList.SelectedItem=null;}
 private void FilterHistory(object sender,TextChangedEventArgs e){if(HistoryList!=null)RefreshHistory();}
 private void RefreshHistory(){loadingHistory=true;var query=HistorySearch?.Text??"";HistoryList.ItemsSource=Store.Data.Conversations.Where(x=>x.Title.Contains(query,StringComparison.OrdinalIgnoreCase)||x.Turns.Any(t=>t.Question.Contains(query,StringComparison.OrdinalIgnoreCase)||t.Answer.Contains(query,StringComparison.OrdinalIgnoreCase))).Reverse().ToList();loadingHistory=false;}
 private void SelectConversation(object sender,SelectionChangedEventArgs e){if(loadingHistory||HistoryList.SelectedItem is not Conversation selected)return;request?.Cancel();current=selected;sources.Clear();image=null;RenderAttachments();Messages.Children.Clear();foreach(var turn in current.Turns)RenderTurn(turn);EmptyState.Visibility=current.Turns.Count==0?Visibility.Visible:Visibility.Collapsed;ConversationTitle.Text=current.Title;}
 private void PromptKeyDown(object sender,KeyEventArgs e){if(e.Key==Key.Enter&&(Keyboard.Modifiers&ModifierKeys.Shift)==0){e.Handled=true;Send(sender,e);}}
 private async void Send(object sender,RoutedEventArgs e)
 {
  if(request!=null||string.IsNullOrWhiteSpace(Prompt.Text))return;var question=Prompt.Text.Trim();var conversation=current;var shared=sources.Select(x=>new Source{App=x.App,Title=x.Title,Text=x.Text}).ToList();using var cancellation=new CancellationTokenSource();request=cancellation;SendButton.IsEnabled=false;StopButton.Visibility=Visibility.Visible;Status.Text="Working locally…";
  try{var response=await Ai.Ask(Store.Data.Settings,question,conversation.Turns,shared,image,cancellation.Token);cancellation.Token.ThrowIfCancellationRequested();if(current!=conversation)return;var turn=new Turn{Question=question,Answer=response.Answer,Model=response.Model,Sources=shared};conversation.Turns.Add(turn);if(conversation.Turns.Count>250)conversation.Turns.RemoveAt(0);if(!Store.Data.Conversations.Contains(conversation))Store.Data.Conversations.Add(conversation);conversation.Title=conversation.Turns[0].Question[..Math.Min(70,conversation.Turns[0].Question.Length)];ConversationTitle.Text=conversation.Title;RenderTurn(turn);RefreshHistory();Prompt.Clear();sources.Clear();image=null;RenderAttachments();Status.Text="Answered on this device · "+response.Model;if(Store.Data.Settings.Memory){try{Store.Save();}catch(Exception saveError){Status.Text="Answer ready, but conversation was not saved: "+saveError.Message;}}}
  catch(OperationCanceledException){if(current==conversation)Status.Text="Stopped. Draft and attachments were kept.";}
  catch(Exception error){if(current==conversation)Status.Text="Could not answer: "+error.Message+" · Check Ollama and your chosen model.";}
  finally{request=null;SendButton.IsEnabled=true;StopButton.Visibility=Visibility.Collapsed;}
 }
 private void Stop(object sender,RoutedEventArgs e)=>request?.Cancel();
 private void RenderTurn(Turn turn)
 {
  EmptyState.Visibility=Visibility.Collapsed;var question=new Border{Background=new SolidColorBrush(Color.FromRgb(37,52,67)),CornerRadius=new CornerRadius(17,17,3,17),Padding=new Thickness(13,9,13,9),Margin=new Thickness(75,6,0,20),HorizontalAlignment=HorizontalAlignment.Right,MaxWidth=650,Child=new TextBlock{Text=turn.Question,TextWrapping=TextWrapping.Wrap}};Messages.Children.Add(question);
  var panel=new StackPanel{Margin=new Thickness(0,0,0,29)};var text=new TextBox{Text=turn.Answer,IsReadOnly=true,TextWrapping=TextWrapping.Wrap,AcceptsReturn=true,BorderThickness=new Thickness(0),Background=Brushes.Transparent,Padding=new Thickness(0),FontSize=14,MaxHeight=290,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};panel.Children.Add(text);
  var actions=new StackPanel{Orientation=Orientation.Horizontal,Margin=new Thickness(0,10,0,0)};var expand=new Button{Content="Expand",FontSize=10,Padding=new Thickness(7,3,7,3),Background=Brushes.Transparent};expand.Click+=(_,_)=>{var expanded=double.IsPositiveInfinity(text.MaxHeight);text.MaxHeight=expanded?290:double.PositiveInfinity;expand.Content=expanded?"Expand":"Collapse";};actions.Children.Add(expand);var more=new Button{Content="⋯",Padding=new Thickness(9,1,9,1),Background=Brushes.Transparent};var menu=new ContextMenu();void Option(string label,Action action){var item=new MenuItem{Header=label};item.Click+=(_,_)=>{try{action();}catch(Exception error){MessageBox.Show(this,error.Message,label);}};menu.Items.Add(item);}Option("Copy selected text / answer",()=>Clipboard.SetText(text.SelectedText.Length>0?text.SelectedText:turn.Answer));Option("Open answer",()=>Tools.Read(this,turn.Question,turn.Answer));Option("Save answer",()=>{Store.Data.SavedAnswers.Add(new(){Title=turn.Question[..Math.Min(200,turn.Question.Length)],Body=turn.Answer});Store.Save();Notify("Answer saved. Open Tools → Saved answers.");});Option("Make a note",()=>Tools.EditEntry(this,Store.Data.Notes,new(){Title=turn.Question[..Math.Min(200,turn.Question.Length)],Body=turn.Answer},false));Option("Read aloud",async()=>{try{await Speech.Speak(turn.Answer,Store.Data.Settings);}catch(Exception error){Notify(error.Message);}finally{UpdateWake();}});Option("Review meal JSON",()=>Tools.MealFromAnswer(this,turn.Answer));more.ContextMenu=menu;more.Click+=(_,_)=>{menu.PlacementTarget=more;menu.IsOpen=true;};actions.Children.Add(more);actions.Children.Add(new TextBlock{Text=turn.Model,Foreground=new SolidColorBrush(Color.FromRgb(120,146,166)),FontSize=10,VerticalAlignment=VerticalAlignment.Center,Margin=new Thickness(7,0,0,0)});panel.Children.Add(actions);
  if(turn.Sources.Count>0){var excerpts=new StackPanel();foreach(var source in turn.Sources)excerpts.Children.Add(new TextBox{Text=source.Title+"\n"+source.Text[..Math.Min(1500,source.Text.Length)],IsReadOnly=true,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(0,5,0,5),FontSize=11});panel.Children.Add(new Expander{Header=turn.Sources.Count+" explicitly shared sources",Content=excerpts,Margin=new Thickness(0,8,0,0),Foreground=Foreground});}Messages.Children.Add(panel);ChatScroll.ScrollToEnd();
 }
 private async void Dictate(object sender,RoutedEventArgs e){try{Status.Text="Listening for one utterance…";Prompt.Text=await Speech.Dictate();Status.Text="Dictation ready. Review, then Send.";}catch(Exception error){Status.Text=error.Message;}finally{UpdateWake();}}
 private void AttachFile(object sender,RoutedEventArgs e)
 {
  var picker=new OpenFileDialog{Filter="Images and text exports|*.png;*.jpg;*.jpeg;*.webp;*.txt;*.md;*.csv;*.eml;*.json;*.log;*.ics;*.html",Multiselect=true};if(picker.ShowDialog(this)!=true)return;try{foreach(var file in picker.FileNames){var info=new FileInfo(file);if(info.Length>8*1024*1024)throw new InvalidOperationException("Each attachment must be under 8 MB.");if(new[]{".png",".jpg",".jpeg",".webp"}.Contains(info.Extension.ToLowerInvariant())){if(image!=null)throw new InvalidOperationException("Use one image per native request.");image=Convert.ToBase64String(File.ReadAllBytes(file));}else AddSources(new[]{new Source{Title=info.Name,Text=File.ReadAllText(file)}});}RenderAttachments();}catch(Exception error){MessageBox.Show(this,error.Message,"Attachment");}
 }
 private void SettingsClick(object sender,RoutedEventArgs e)=>Tools.Settings(this);
 private void OpenTools(object sender,RoutedEventArgs e)
 {
  var menu=new ContextMenu();void Add(string title,Action action){var item=new MenuItem{Header=title};item.Click+=(_,_)=>{try{action();}catch(Exception error){MessageBox.Show(this,error.Message,title);}};menu.Items.Add(item);}
  Add("Writing Tools ↗",()=>new WritingWindow(this,null).Show());Add("Read Chrome or Edge…",()=>Tools.Browser(this));Add("Search classic Outlook…",()=>Tools.Inbox(this));Add("Search browser history…",()=>Tools.History(this));Add("Search a folder…",()=>Tools.Folder(this));Add("Attach a screenshot…",()=>Tools.Screenshot(this));menu.Items.Add(new Separator());Add("Review a cross-app task…",()=>NativeWorkflow.Open(this));Add("Notes",()=>Tools.Library(this,"Notes",Store.Data.Notes));Add("Saved answers",()=>Tools.Library(this,"Saved answers",Store.Data.SavedAnswers));Add("Reminders",()=>Tools.Library(this,"Reminders",Store.Data.Reminders,true));Add("Nutrition journal",()=>Tools.Meals(this));Add("Itemized bill split",()=>Tools.Bill(this));Add("Analyze attached meal",()=>{Prompt.Text="Estimate this meal. Return only JSON {name,items:[{name,calories,protein,carbs,fat}],uncertainty}. I will review before saving. Do not treat estimates as medical advice.";Prompt.Focus();});menu.Items.Add(new Separator());Add("Open Windows Camera",()=>WindowsIntegration.Open("microsoft.windows.camera:"));Add("Open Photos",()=>{if(Confirm("Open Photos?","Open the Windows Photos app?"))WindowsIntegration.Open("ms-photos:");});Add("Settings & privacy",()=>Tools.Settings(this));menu.PlacementTarget=ToolsButton;menu.IsOpen=true;
 }
 internal void AttachPng(byte[] bytes){if(bytes.Length>8*1024*1024)throw new InvalidOperationException("Screenshot is over 8 MB. Choose a smaller image instead.");image=Convert.ToBase64String(bytes);RenderAttachments();Notify("One screenshot attached. Review your question before sending.");}
}
