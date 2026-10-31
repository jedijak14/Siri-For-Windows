using System;
using System.Linq;
using System.Speech.Recognition;
using System.Speech.Synthesis;
using System.Threading.Tasks;
using System.Threading;
namespace SiriNative;
public sealed class SpeechService : IDisposable
{
 private volatile SpeechRecognitionEngine? wake;
 private readonly WakeIntent intent=new();
 private readonly SemaphoreSlim speechLock=new(1,1);
 public bool Requested=>intent.Enabled;
 private SpeechSynthesizer? speaker;
 private SpeechSynthesizer Speaker=>speaker??=new();
 private DateTimeOffset last=DateTimeOffset.MinValue;
 private bool disposed;
 public bool Armed=>wake!=null;
 public event Action? Woke;
 public event Action<string>? Failed;
 private static RecognizerInfo English()=>SpeechRecognitionEngine.InstalledRecognizers().FirstOrDefault(x=>x.Culture.TwoLetterISOLanguageName=="en")??throw new InvalidOperationException("Hey Siri needs an installed English Windows speech recognizer and a working microphone. Typing remains available.");
 public string[] Voices(){try{return Speaker.GetInstalledVoices().Where(x=>x.Enabled).Select(x=>x.VoiceInfo.Name).ToArray();}catch{return Array.Empty<string>();}}
 public void StartWake(){intent.Enable();try{StartEngine();}catch{intent.Disable();throw;}}
 private void StartEngine()
 {
  if(!intent.ShouldListen)return;
  if(disposed)throw new ObjectDisposedException(nameof(SpeechService));if(Armed)return;
  var engine=new SpeechRecognitionEngine(English());
  try{
   var builder=new GrammarBuilder{Culture=engine.RecognizerInfo.Culture};builder.Append(new Choices("hey siri"));engine.LoadGrammar(new Grammar(builder));
   engine.SpeechRecognized+=(_,e)=>{var now=DateTimeOffset.UtcNow;if(Rules.WakeAllowed(e.Result.Text,e.Result.Confidence,now,last,Armed)){last=now;Woke?.Invoke();}};
   engine.RecognizeCompleted+=(_,e)=>{if(e.Error!=null)Failed?.Invoke(e.Error.Message);};
   engine.SetInputToDefaultAudioDevice();wake=engine;engine.RecognizeAsync(RecognizeMode.Multiple);
  }catch{wake=null;engine.Dispose();throw;}
 }
 public void StopWake(){intent.Disable();StopEngine();}
 private void StopEngine(){var engine=wake;wake=null;if(engine!=null){try{engine.RecognizeAsyncCancel();}finally{engine.Dispose();}}}
 private void ResumeWake(){intent.Resume();if(!disposed&&intent.ShouldListen)try{StartEngine();}catch(Exception error){intent.Disable();Failed?.Invoke(error.Message);}}
 public async Task<string> Dictate()
 {
  await speechLock.WaitAsync();intent.Pause();StopEngine();try{if(disposed)throw new ObjectDisposedException(nameof(SpeechService));return await Task.Run(()=>{using var engine=new SpeechRecognitionEngine(English());engine.LoadGrammar(new DictationGrammar());engine.SetInputToDefaultAudioDevice();var result=engine.Recognize(TimeSpan.FromSeconds(10));return result?.Text??throw new InvalidOperationException("No speech recognized. Check your microphone and installed English speech language.");});}finally{ResumeWake();speechLock.Release();}
 }
 public async Task Speak(string text,Preferences settings)
 {
  await speechLock.WaitAsync();intent.Pause();StopEngine();try{if(disposed)throw new ObjectDisposedException(nameof(SpeechService));await Task.Run(()=>{if(settings.Voice.Length>0)Speaker.SelectVoice(settings.Voice);Speaker.Rate=Math.Clamp(settings.SpeechRate,-5,5);Speaker.Speak(text.Length>20000?text[..20000]:text);});}finally{ResumeWake();speechLock.Release();}
 }
 public void Dispose(){disposed=true;StopWake();speaker?.SpeakAsyncCancelAll();speaker?.Dispose();}
}
