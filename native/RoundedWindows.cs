using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shell;
namespace SiriNative;
internal static class RoundedWindows
{
 [DllImport("gdi32.dll")]private static extern nint CreateRoundRectRgn(int left,int top,int right,int bottom,int ellipseWidth,int ellipseHeight);
 [DllImport("gdi32.dll")]private static extern bool DeleteObject(nint region);
 [DllImport("user32.dll")]private static extern int SetWindowRgn(nint window,nint region,bool redraw);
 [DllImport("dwmapi.dll")]private static extern int DwmSetWindowAttribute(nint window,int attribute,ref int value,int size);
 public static void Apply(Window window)
 {
  if(window.Tag is string marker&&marker=="SiriRounded")return;window.Tag="SiriRounded";
  var original=window.Content;window.Content=null;window.WindowStyle=WindowStyle.None;
  WindowChrome.SetWindowChrome(window,new WindowChrome{CaptionHeight=0,ResizeBorderThickness=new Thickness(window.ResizeMode==ResizeMode.NoResize?0:6),GlassFrameThickness=new Thickness(0),UseAeroCaptionButtons=false,CornerRadius=new CornerRadius(20)});
  var shell=new DockPanel();var caption=new DockPanel{Height=36,Background=new SolidColorBrush(Color.FromRgb(19,26,34))};DockPanel.SetDock(caption,Dock.Top);
  var controls=new StackPanel{Orientation=Orientation.Horizontal};DockPanel.SetDock(controls,Dock.Right);
  void Control(string name,string glyph,Action action){var button=new Button{Content=glyph,ToolTip=name,Width=40,Padding=new Thickness(0),Margin=new Thickness(0),Background=Brushes.Transparent,BorderThickness=new Thickness(0)};System.Windows.Automation.AutomationProperties.SetName(button,name);button.Click+=(_,_)=>action();controls.Children.Add(button);}
  if(window.ResizeMode!=ResizeMode.NoResize){Control("Minimize","−",()=>window.WindowState=WindowState.Minimized);Control("Maximize / restore","□",()=>window.WindowState=window.WindowState==WindowState.Maximized?WindowState.Normal:WindowState.Maximized);}
  Control("Close","×",window.Close);caption.Children.Add(controls);caption.Children.Add(new TextBlock{Text=window.Title,Margin=new Thickness(14,0,0,0),VerticalAlignment=VerticalAlignment.Center,FontSize=11,Foreground=new SolidColorBrush(Color.FromRgb(159,180,198))});caption.MouseLeftButtonDown+=(_,e)=>{if(e.ClickCount==2&&window.ResizeMode==ResizeMode.CanResize)window.WindowState=window.WindowState==WindowState.Maximized?WindowState.Normal:WindowState.Maximized;else if(e.LeftButton==System.Windows.Input.MouseButtonState.Pressed)window.DragMove();};shell.Children.Add(caption);shell.Children.Add(new ContentPresenter{Content=original});
  window.Content=new Border{CornerRadius=new CornerRadius(20),BorderThickness=new Thickness(1),BorderBrush=new SolidColorBrush(Color.FromRgb(52,69,86)),Background=window.Background,Child=shell};
  void Shape(){var handle=new WindowInteropHelper(window).Handle;if(handle==0)return;int dark=1,round=2;DwmSetWindowAttribute(handle,20,ref dark,4);DwmSetWindowAttribute(handle,33,ref round,4);if(window.WindowState==WindowState.Maximized){SetWindowRgn(handle,0,true);return;}var transform=PresentationSource.FromVisual(window)?.CompositionTarget?.TransformToDevice??Matrix.Identity;var region=CreateRoundRectRgn(0,0,(int)Math.Ceiling(window.ActualWidth*transform.M11)+1,(int)Math.Ceiling(window.ActualHeight*transform.M22)+1,(int)(40*transform.M11),(int)(40*transform.M22));if(region!=0&&SetWindowRgn(handle,region,true)==0)DeleteObject(region);}
  window.SizeChanged+=(_,_)=>Shape();window.StateChanged+=(_,_)=>Shape();Shape();
 }
}
