using System;
using System.Collections.Generic;
using System.Linq;
namespace SiriNative;
public sealed class Preferences
{
 public bool Memory {get;set;}
 public string Language {get;set;}="auto";
 public string Model {get;set;}="";
 public string VisionModel {get;set;}="";
 public string Voice {get;set;}="";
 public int SpeechRate {get;set;}
 public List<string> ExcludedApps {get;set;}=new();
}
public sealed class Turn
{
 public string Question {get;set;}="";
 public string Answer {get;set;}="";
 public string Model {get;set;}="";
 public DateTimeOffset At {get;set;}=DateTimeOffset.Now;
 public List<Source> Sources {get;set;}=new();
}
public sealed class Conversation
{
 public string Id {get;set;}=Guid.NewGuid().ToString("N");
 public string Title {get;set;}="New conversation";
 public List<Turn> Turns {get;set;}=new();
 public override string ToString()=>Title;
}
public sealed class Source
{
 public string Title {get;set;}="";
 public string Text {get;set;}="";
 public string App {get;set;}="";
}
public sealed class Entry
{
 public string Id {get;set;}=Guid.NewGuid().ToString("N");
 public string Title {get;set;}="";
 public string Body {get;set;}="";
 public DateTimeOffset Updated {get;set;}=DateTimeOffset.Now;
 public DateTimeOffset? Due {get;set;}
 public bool Done {get;set;}
 public bool Pinned {get;set;}
 public override string ToString()=>(Pinned?"★ ":"")+(Done?"✓ ":"")+Title+(Due.HasValue?" · "+Due.Value.ToLocalTime().ToString("g"):"");
}
public sealed class Food
{
 public string Name {get;set;}="";
 public decimal Calories {get;set;}
 public decimal Protein {get;set;}
 public decimal Carbs {get;set;}
 public decimal Fat {get;set;}
}
public sealed class Meal
{
 public string Id {get;set;}=Guid.NewGuid().ToString("N");
 public string Name {get;set;}="Meal";
 public DateTimeOffset At {get;set;}=DateTimeOffset.Now;
 public List<Food> Items {get;set;}=new();
 public override string ToString()=>Name+" · "+Items.Sum(x=>x.Calories).ToString("0")+" kcal";
}
public sealed class State
{
 public Preferences Settings {get;set;}=new();
 public List<Conversation> Conversations {get;set;}=new();
 public List<Entry> Notes {get;set;}=new();
 public List<Entry> SavedAnswers {get;set;}=new();
 public List<Entry> Reminders {get;set;}=new();
 public List<Meal> Meals {get;set;}=new();
}
public sealed record BillItem(decimal Amount,int[] Owners);
public sealed record BillShare(string Name,long Items,long Tax,long Tip)
{
 public long Total=>Items+Tax+Tip;
}
public static class Rules
{
 public static bool IsExcluded(Preferences settings,string app)=>settings.ExcludedApps.Any(x=>x.Equals(app,StringComparison.OrdinalIgnoreCase));
 public static bool WakeAllowed(string phrase,float confidence,DateTimeOffset now,DateTimeOffset last,bool enabled)=>enabled&&phrase.Trim().Equals("hey siri",StringComparison.OrdinalIgnoreCase)&&confidence>=.65f&&(now-last).TotalSeconds>=3;
 public static long Cents(decimal amount)
 {
  if(amount<0||amount>1_000_000)throw new ArgumentException("Amounts must be between 0 and 1,000,000.");
  return checked((long)decimal.Round(amount*100,0,MidpointRounding.AwayFromZero));
 }
 public static List<BillShare> Split(string[] names,List<BillItem> items,decimal tax,decimal tip)
 {
  if(names.Length<1||names.Length>50||names.Any(string.IsNullOrWhiteSpace)||names.Distinct(StringComparer.OrdinalIgnoreCase).Count()!=names.Length)throw new ArgumentException("Use 1–50 unique diner names.");
  if(items.Count<1||items.Count>200||tip<0||tip>1000)throw new ArgumentException("Add items and a valid tip percentage.");
  var portions=new long[names.Length];
  foreach(var item in items){var cents=Cents(item.Amount);var owners=item.Owners.OrderBy(x=>x).ToArray();if(owners.Length==0||owners.Distinct().Count()!=owners.Length||owners.Any(i=>i<0||i>=names.Length))throw new ArgumentException("Assign every item to valid diners without duplicates.");for(int i=0;i<owners.Length;i++)portions[owners[i]]+=cents/owners.Length+(i<cents%owners.Length?1:0);}
  long subtotal=portions.Sum(),taxCents=Cents(tax),tipCents=Cents(subtotal/100m*tip/100m);
  if(subtotal==0&&taxCents>0)throw new ArgumentException("Add a subtotal before allocating tax.");
  long[] Allocate(long amount){if(subtotal==0)return new long[names.Length];var values=portions.Select(p=>(long)decimal.Floor((decimal)amount*p/subtotal)).ToArray();var order=Enumerable.Range(0,names.Length).OrderByDescending(i=>(decimal)amount*portions[i]%subtotal).ThenBy(i=>i).ToArray();for(long remaining=amount-values.Sum(),i=0;i<remaining;i++)values[order[i]]++;return values;}
  var taxes=Allocate(taxCents);var tips=Allocate(tipCents);
  return names.Select((name,i)=>new BillShare(name,portions[i],taxes[i],tips[i])).ToList();
 }
 public static void ValidateEntry(Entry entry){if(string.IsNullOrWhiteSpace(entry.Title)||entry.Title.Length>200||entry.Body.Length>100_000)throw new ArgumentException("Use a title under 200 characters and content under 100,000 characters.");}
 public static Uri Venmo(string recipient,decimal amount,string note)
 {
  if(!System.Text.RegularExpressions.Regex.IsMatch(recipient,"^@?[A-Za-z0-9_-]{1,60}$")||amount<=0||amount>10000)throw new ArgumentException("Enter a valid Venmo username and an amount between $0.01 and $10,000.");
  return new Uri("https://venmo.com/?txn=pay&recipients="+Uri.EscapeDataString(recipient.TrimStart('@'))+"&amount="+amount.ToString("F2",System.Globalization.CultureInfo.InvariantCulture)+"&note="+Uri.EscapeDataString(note.Length>180?note[..180]:note));
 }
}
public sealed class TaskStep
{
 public string Action {get;set;}="";
 public string Query {get;set;}="";
 public string Browser {get;set;}="";
 public string Profile {get;set;}="Default";
 public string Instruction {get;set;}="Summarize the approved context.";
 public string App {get;set;}="";
}
public sealed class TaskPlan
{
 public List<TaskStep> Steps {get;set;}=new();
 public void Validate()
 {
  if(Steps==null||Steps.Count<1||Steps.Count>6)throw new ArgumentException("A plan must have 1–6 supported steps.");
  foreach(var step in Steps){if(step==null||!new[]{"searchInbox","searchHistory","summarize","saveNote","openApp"}.Contains(step.Action))throw new ArgumentException("Unsupported action. No steps were executed.");if(step.Action.StartsWith("search")&&(string.IsNullOrWhiteSpace(step.Query)||step.Query.Length>200))throw new ArgumentException("Search terms must contain 1–200 characters.");if(step.Action=="searchHistory"&&(!new[]{"Chrome","Edge"}.Contains(step.Browser)||!System.Text.RegularExpressions.Regex.IsMatch(step.Profile,"\\A(Default|Profile [0-9]+)\\z")))throw new ArgumentException("Invalid browser or profile.");if(step.Action=="summarize"&&(step.Instruction==null||step.Instruction.Length>1000))throw new ArgumentException("Invalid summary instruction.");if(step.Action=="openApp"&&!new[]{"photos","explorer","settings"}.Contains(step.App))throw new ArgumentException("This app is not in the allowed action list.");}
 }
}
