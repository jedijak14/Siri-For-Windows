using System;
using System.IO.Pipes;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
namespace SiriNative;
public partial class App : Application
{
 private void RoundWindow(object sender,RoutedEventArgs e){if(ReferenceEquals(sender,e.OriginalSource))RoundedWindows.Apply((Window)sender);}
 private byte activation=1;
 private Mutex? instance;
 private readonly CancellationTokenSource lifetime=new();
 private bool ownsInstance;
 protected override void OnStartup(StartupEventArgs e)
 {
  base.OnStartup(e);
  if(Array.Exists(e.Args,x=>x=="--remove-settings-integration")){if(MessageBox.Show("Remove the Windows Settings listing and settings link? This does not delete your EXE or saved data.","Remove Siri Settings integration",MessageBoxButton.YesNo)==MessageBoxResult.Yes)SettingsIntegration.Remove();Shutdown();return;}
  activation=Array.Exists(e.Args,x=>x=="--settings")?(byte)2:Array.Exists(e.Args,x=>x=="--bubble")?(byte)3:(byte)1;
  instance=new Mutex(true,"Local\\SiriForWindowsNative",out ownsInstance);
  if(!ownsInstance){try{using var pipe=new NamedPipeClientStream(".","SiriForWindowsNativeActivate",PipeDirection.Out);pipe.Connect(1500);pipe.WriteByte(activation);}catch{MessageBox.Show("Siri is already running or finishing startup. Use its taskbar window.","Siri for Windows");}Shutdown();return;}
  DispatcherUnhandledException += (_,args) => { MessageBox.Show(args.Exception.Message,"Siri for Windows"); args.Handled=true; };
  MainWindow=new MainWindow();MainWindow.Show();_ = ListenForActivation();if(activation!=1)Dispatcher.BeginInvoke(new Action(()=>ActivateRequest(activation)));
 }
 private async Task ListenForActivation()
 {
  while(!lifetime.IsCancellationRequested){try{using var pipe=new NamedPipeServerStream("SiriForWindowsNativeActivate",PipeDirection.In,1,PipeTransmissionMode.Byte,PipeOptions.Asynchronous|PipeOptions.CurrentUserOnly);await pipe.WaitForConnectionAsync(lifetime.Token);var signal=new byte[1];if(await pipe.ReadAsync(signal,lifetime.Token)==1)Dispatcher.BeginInvoke(new Action(()=>ActivateRequest(signal[0])));}catch(OperationCanceledException){return;}catch{try{await Task.Delay(500,lifetime.Token);}catch(OperationCanceledException){return;}}}
 }
 private void ActivateRequest(byte command){if(MainWindow is not MainWindow app)return;if(command==3){app.ShowBubble(false);return;}if(command!=1&&command!=2)return;app.Show();app.WindowState=WindowState.Normal;app.Activate();if(command==2)Tools.Settings(app);}
 protected override void OnExit(ExitEventArgs e){lifetime.Cancel();if(ownsInstance)instance?.ReleaseMutex();instance?.Dispose();base.OnExit(e);}
}
