using SiriNative;
int checks=0;
void Check(bool condition,string label){if(!condition)throw new Exception(label);checks++;}
void Reject(Action action,string label){try{action();}catch(ArgumentException){checks++;return;}throw new Exception(label);}
var now=DateTimeOffset.UtcNow;
Check(Rules.WakeAllowed("Hey Siri",.9f,now,now.AddSeconds(-10),true),"wake phrase accepted");
Check(!Rules.WakeAllowed("Hey Siri",.9f,now,now.AddSeconds(-10),false),"disabled means no activation");
Check(!Rules.WakeAllowed("Siri",.9f,now,now.AddSeconds(-10),true),"exact grammar phrase");
Check(!Rules.WakeAllowed("Hey Siri",.5f,now,now.AddSeconds(-10),true),"low confidence blocked");
Check(!Rules.WakeAllowed("Hey Siri",.9f,now,now.AddSeconds(-1),true),"cooldown enforced");
Check(Rules.Cents(1.005m)==101,"decimal rounding");
for(int count=1;count<=40;count++){
 var names=Enumerable.Range(0,count).Select(i=>"Diner "+i).ToArray();var bill=Rules.Split(names,new(){new(19.99m,Enumerable.Range(0,count).ToArray()),new(4.03m,new[]{0})},1.77m,18);
 Check(bill.Sum(x=>x.Items)==2402,"item cent conservation");Check(bill.Sum(x=>x.Tax)==177,"tax conservation");Check(bill.Sum(x=>x.Tip)==432,"tip conservation");Check(bill.Sum(x=>x.Total)==3011,"total conservation");
}
Reject(()=>Rules.Split(new[]{"A","a"},new(){new(10,new[]{0})},0,0),"duplicate diners");
Reject(()=>Rules.Split(new[]{"A"},new(){new(10,Array.Empty<int>())},0,0),"unassigned item");
Reject(()=>Rules.Split(new[]{"A"},new(){new(10,new[]{4})},0,0),"invalid owner");
Reject(()=>Rules.Cents(-1),"negative amount");
Reject(()=>Rules.ValidateEntry(new(){Title="",Body="text"}),"blank note");
Reject(()=>Rules.ValidateEntry(new(){Title="Title",Body=new string('x',100001)}),"oversized note");
Check(Rules.Venmo("@friend",12.34m,"Dinner & tip").Host=="venmo.com","payment origin");
Reject(()=>Rules.Venmo("https://evil.test",10,""),"invalid payment username");
Reject(()=>Rules.Venmo("friend",-1,""),"negative payment");
Console.WriteLine($"{checks} native domain checks passed. Microphone, accessibility, and real app interaction still require device testing.");
