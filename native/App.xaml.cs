using System;
using System.Windows;
namespace SiriNative;
public partial class App : Application
{
 protected override void OnStartup(StartupEventArgs e)
 {
  base.OnStartup(e);
  DispatcherUnhandledException += (_,args) => { MessageBox.Show(args.Exception.Message,"Siri for Windows"); args.Handled=true; };
  MainWindow=new MainWindow(); MainWindow.Show();
 }
}
