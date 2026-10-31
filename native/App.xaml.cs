using System;
using System.IO.Pipes;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
namespace SiriNative;
public partial class App : Application
{
 private Mutex? instance;
 private readonly CancellationTokenSource lifetime=new();
 private bool ownsInstance;
 protected override void OnStartup(StartupEventArgs e)
 {
  base.OnStartup(e);
  instance=new Mutex(true,"Local\\SiriForWindowsNative",out ownsInstance);
  if(!ownsInstance){try{using var pipe=new NamedPipeClientStream(".","SiriForWindowsNativeActivate",PipeDirection.Out);pipe.Connect(1500);pipe.WriteByte(1);}catch{MessageBox.Show("Siri is already running or finishing startup. Use its taskbar window.","Siri for Windows");}Shutdown();return;}
  DispatcherUnhandledException += (_,args) => { MessageBox.Show(args.Exception.Message,"Siri for Windows"); args.Handled=true; };
  MainWindow=new MainWindow();MainWindow.Show();_ = ListenForActivation();
 }
 private async Task ListenForActivation()
 {
  while(!lifetime.IsCancellationRequested){try{using var pipe=new NamedPipeServerStream("SiriForWindowsNativeActivate",PipeDirection.In,1,PipeTransmissionMode.Byte,PipeOptions.Asynchronous|PipeOptions.CurrentUserOnly);await pipe.WaitForConnectionAsync(lifetime.Token);var signal=new byte[1];if(await pipe.ReadAsync(signal,lifetime.Token)==1&&signal[0]==1)Dispatcher.BeginInvoke(new Action(()=>{if(MainWindow!=null){MainWindow.Show();MainWindow.WindowState=WindowState.Normal;MainWindow.Activate();}}));}catch(OperationCanceledException){return;}catch{try{await Task.Delay(500,lifetime.Token);}catch(OperationCanceledException){return;}}}
 }
 protected override void OnExit(ExitEventArgs e){lifetime.Cancel();if(ownsInstance)instance?.ReleaseMutex();instance?.Dispose();base.OnExit(e);}
}
