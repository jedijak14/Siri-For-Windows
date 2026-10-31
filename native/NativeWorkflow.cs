using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Controls;
using Microsoft.Win32;
namespace SiriNative;
internal static class NativeWorkflow
{
 public static void Open(MainWindow app)
 {
  var window=new ToolWindow(app,"Review a cross-app task",740,660);window.Body.Children.Add(Ui.Label("A local model proposes a bounded plan. Nothing runs until you review it. Private data reads require separate approval. No scripts, arbitrary commands, message sending, deletion, or payment execution."));var goal=Ui.Field(window.Body,"What would you like to do?","",true);var output=Ui.Output(window.Body);var status=Ui.Label("");TaskPlan? plan=null;var cancellation=new CancellationTokenSource();window.Closed+=(_,_)=>cancellation.Cancel();var run=Ui.Async("Run reviewed plan",async()=>{});run.IsEnabled=false;
  var prepare=Ui.Async("Prepare a plan",async()=>{run.IsEnabled=false;plan=null;var response=await app.Ai.Ask(app.Store.Data.Settings,goal.Text,new(),new(),null,cancellation.Token,"Return only JSON {steps:[...]}, 1–6 steps. Allowed shapes: {action:searchInbox,query:words}, {action:searchHistory,browser:Chrome or Edge,profile:Default,query:words}, {action:summarize,instruction:words}, {action:saveNote}, {action:openApp,app:photos or explorer or settings}. All JSON keys and values must use double quotes. If unsupported, return {steps:[]}. Never include payments, commands, deletion, mail sending, or arbitrary paths.");var text=response.Answer.Trim();if(text.StartsWith("```")){var start=text.IndexOf('\n');text=start<0?text:text[(start+1)..].TrimEnd('`','\r','\n',' ');}plan=JsonSerializer.Deserialize<TaskPlan>(text,Store.Json)??throw new InvalidOperationException("No plan returned.");plan.Validate();output.Text=string.Join("\n",plan.Steps.Select((step,i)=>$"{i+1}. {step.Action} {step.Query} {step.Browser} {step.App}"));run.IsEnabled=true;status.Text="Review the plan. No action has run.";});
  // Use a single explicit runner handler; Ui.Async owns disabled/error state.
  run=Ui.Async("Run reviewed plan",async()=>{
   if(plan==null)throw new InvalidOperationException("Prepare a plan first.");plan.Validate();if(!app.Confirm("Run these steps?",output.Text))return;var context=new List<Source>();string summary="";var completed=new List<string>();
   try{foreach(var step in plan.Steps){cancellation.Token.ThrowIfCancellationRequested();status.Text="Running: "+step.Action;
    switch(step.Action){
     case "searchInbox":if(!app.Confirm("Read Outlook for this task?",step.Query))throw new OperationCanceledException("Inbox read not approved.");var inboxQuery=step.Query;context.AddRange(await Task.Run(()=>WindowsIntegration.Inbox(inboxQuery,app.Store.Data.Settings),cancellation.Token));break;
     case "searchHistory":if(!app.Confirm("Read browser history for this task?",step.Browser+" / "+step.Profile+" · "+step.Query))throw new OperationCanceledException("History read not approved.");context.AddRange(await Task.Run(()=>WindowsIntegration.History(step.Browser,step.Profile,step.Query,app.Store.Data.Settings),cancellation.Token));break;
     case "summarize":if(context.Count==0)throw new InvalidOperationException("No search results are available to summarize.");summary=(await app.Ai.Ask(app.Store.Data.Settings,step.Instruction,new(),context,null,cancellation.Token)).Answer;break;
     case "saveNote":var body=summary.Length>0?summary:string.Join("\n\n",context.Select(x=>x.Title+"\n"+x.Text));if(body.Length==0)throw new InvalidOperationException("There is no task result to save.");var picker=new SaveFileDialog{Filter="Text note|*.txt",FileName="Siri task note.txt"};if(picker.ShowDialog(window)!=true)throw new OperationCanceledException("Save cancelled.");File.WriteAllText(picker.FileName,body);break;
     case "openApp":WindowsIntegration.Open(step.App switch{"photos"=>"ms-photos:","settings"=>"ms-settings:",_=>Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)});break;
    }
    completed.Add(step.Action+": completed");output.Text=string.Join("\n",completed)+(summary.Length>0?"\n\n"+summary:"");
   }status.Text="Task complete. Only the listed steps were executed.";}
   catch(Exception error){status.Text="Stopped: "+error.Message+" Completed steps are not rolled back.";output.Text=string.Join("\n",completed)+(summary.Length>0?"\n\n"+summary:"");}
  });run.IsEnabled=false;window.Body.Children.Add(prepare);window.Body.Children.Add(run);window.Body.Children.Add(status);window.ShowDialog();
 }
}
