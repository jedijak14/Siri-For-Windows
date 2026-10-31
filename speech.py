"""Optional, built-in Windows speech via .NET System.Speech."""

import subprocess
import sys


class SpeechError(RuntimeError):
    """Raised when Windows speech services are unavailable or fail."""


def _powershell(script, text=None, timeout=20):
    if sys.platform != "win32":
        raise SpeechError("Built-in Windows speech is available only on Windows.")
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpeechError(f"Could not start Windows speech: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or "Windows speech returned an error."
        raise SpeechError(detail)
    return result.stdout.strip()


def speak(text):
    """Speak text using an installed Windows SAPI voice; no download required."""
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$text = [Console]::In.ReadToEnd(); "
        "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$speaker.Speak($text); $speaker.Dispose()"
    )
    _powershell(script, text=text)


def listen_once(timeout_seconds=8):
    """Capture one dictation utterance with the installed Windows recognizer."""
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
        "$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
        "$result = $recognizer.Recognize([TimeSpan]::FromSeconds("
        f"{int(timeout_seconds)})); "
        "if ($null -ne $result) { [Console]::Out.Write($result.Text) }; "
        "$recognizer.Dispose()"
    )
    transcript = _powershell(script, timeout=timeout_seconds + 12)
    if not transcript:
        raise SpeechError(
            "No speech was recognized. Check that Windows has an installed "
            "speech recognition language and microphone."
        )
    return transcript
