# Siri for Windows — native Windows edition

The primary Windows app is now a **native C# / WPF executable**, not Electron, Chromium, a WebView, Python, or a browser window. It is published as one self-contained x64 `.exe`, with the .NET runtime bundled. No Node.js, Electron or separately installed .NET runtime is needed to run it. Some bundled native libraries are extracted to the normal .NET single-file cache at launch; it is not an installer or a web shell.

This is an independent community project, not an official Apple or Microsoft product. Local AI still requires a running **Ollama** installation and an installed model; model weights are not bundled into the executable. Cloud-tagged models are hidden, and selected-model metadata is checked for remote/cloud configuration before any prompt is sent.

## A quieter desktop app

The native window follows the supplied reference's structure: a blue conversation sidebar, a dark main conversation area, a quiet empty state, a bottom composer, and genuinely rounded native window borders (including the tool dialogs and wake bubble). Custom title-bar controls retain dragging, minimizing, maximizing and closing; maximized windows use square edges as on Windows. The sidebar contains conversations—not a long feature list. Secondary actions live in **one Tools menu**. Writing assistance opens in a **separate native window**.

The browser preview was simplified too, but it is a companion/legacy web interface, not the implementation packaged into the primary Windows EXE.

## “Hey Siri”

1. Run the native app and open **Settings & privacy**.
2. Enable **Listen for ‘Hey Siri’ while this app is running**, then confirm microphone use and Save.
3. Keep the app running, including minimized to the taskbar, and say **Hey Siri**.

The Windows `System.Speech` engine recognizes that exact English phrase locally and opens a small, always-on-top **Siri bubble**, without expanding the full conversation window. The bubble captures one following utterance locally and puts the recognized words in its composer. Review them and press **Ask**, or type instead. The bubble can display the local model’s answer and retain a short in-memory follow-up conversation. **Stop** or closing the bubble cancels its current dictation/request; the separately opted-in wake listener can resume. **Open app** hides the bubble and opens the main app. A confidence threshold and cooldown reduce accidental triggers. The visible status changes to **Hey Siri is listening**. The microphone is not recorded to a file or sent to Ollama/cloud services by this wake-word listener.

**Voice activation is off at every launch.** Turning it off or closing the app disposes the recognizer. It does not install a background service, startup entry, or OS-wide assistant replacement, and cannot respond after the app exits. An installed **English Windows speech recognizer**, working microphone, and Windows desktop-microphone permission are required. Accuracy, background noise, hardware and enterprise policy need real-device testing. Automated CI does not verify actual spoken audio. Enabling wake recognition explicitly consents to both wake-phrase listening and a single, visible follow-up dictation when the bubble appears. It does not automatically send recognized text to the model. A manually opened bubble does not start microphone capture.

A second launch activates the running instance instead of starting a second microphone listener or competing data writer.

## Choose the model

Use **Choose model…** in the sidebar, or the model selectors in **Settings & privacy**. Installed Ollama models load automatically; **Refresh installed models** reloads the list. Select a text model and a separate image/vision model, then Save. The choices persist and apply to main chat, the Siri bubble, writing assistance and reviewed tasks. Choose **Automatic** to let Siri pick. Current choices stay visible if Ollama is offline; models are not downloaded or switched behind your back. Image requests reject models without advertised vision support.

## Siri in Windows Settings

From the published EXE, open **Settings & privacy → Add Siri Settings to Windows Settings** and approve the per-user registration. No administrator rights are required. Windows then lists **Siri for Windows — Settings integration** under **Settings → Apps → Installed apps**. Open its menu and choose **Modify** to launch Siri's settings. Some Windows versions expose Modify only through Control Panel Programs and Features. A `siriforwindows:` URI handler opens the same settings window.

**This is an Apps integration, not a custom page in the main Windows Settings navigation.** Ordinary desktop apps cannot add an arbitrary Siri pane there through a supported public extension API. Keep the EXE at its registered path; moving/renaming it requires registering again. You can remove the listing/link from Siri Settings or its Windows Apps Uninstall action. Removing the integration does **not** delete the portable EXE, your saved data, or Ollama.

## Features implemented directly in the native EXE

- Local chat through Ollama's HTTP API, installed text/vision model choices, language preferences, per-conversation follow-ups, optional saved conversations and searchable history.
- Expand/collapse replies, selectable text, copy selected text/all, an answer detail window, saved answers, notes, and explicit source excerpts. Model output is plain selectable text, not executable markup. Images/text exports attach through a native file picker.
- Windows voice selection and speaking pace, reply read-aloud, and explicit one-shot English dictation. Wake recognition is paused during dictation/read-aloud to avoid competing listeners or self-triggering.
- Separate Writing Tools: drafts, proofreading, tone/length changes, formulas and slide outlines. Opt-in **Ctrl+Shift+Space** reads the active app's selected text using Windows UI Automation. Replacements require confirmation and verification of the original process, foreground window, non-password field and unchanged selection. Unsupported fields use manual copy/paste. Excel evaluates inserted formulas; review external references carefully.
- Chrome/Edge page text via **Windows UI Automation**, with a native window picker and permission prompt. **No extension or debugging port is needed.** Inaccessible pages use a user-approved screenshot instead; this is not continuous background screen awareness.
- Classic Outlook inbox search through the running Outlook COM object, capped at 500 recent default-inbox items / 12 matching excerpts. Requires approval. New Outlook and other mailbox APIs are not supported. No email is sent, deleted or changed.
- Chrome/Edge history through a temporary SQLite snapshot of the selected Default/Profile N store, with parameterized queries and cleanup. No incognito access; locks can require closing the browser.
- User-selected folder text search, skipping reparse/symlink directories, bounded traversal/read volume and excerpt results. This is keyword search, not embedding-based device-wide indexing.
- One-time primary-display screenshots, with explicit consent and an image review before attachment. Screenshots can contain excluded/private app content; review before sending.
- Local notes, saved answers and reminders with search, pin, edit, delete, explicit context attachment and text export. Reminders are best-effort status alerts while the app is running, not OS background alarms.
- A reviewed nutrition journal with editable foods/macros. Structured meal JSON can be opened from a reply for review; estimates are not medical advice and are never auto-saved to a health account.
- Native itemized bill splitting using decimal/integer-cent arithmetic and proportional tax/pre-tax tip allocation. A Venmo link is a reviewed external handoff, **not payment execution or verification**. Apple Cash is not integrated.
- Reviewed cross-app tasks: a locally generated, validated plan can search approved Outlook/history, summarize results, save a text note to a user-selected destination and open Photos/Explorer/Settings. At most six allowlisted steps. It rejects scripts, arbitrary commands/paths, sending/deletion and payments, and stops on the first failure. Completed steps are not rolled back.

All of these native implementations are under `native/`; they do not call the Electron app, a PowerShell bridge, a Node process or a hosted UI. Windows Camera can be opened from Tools, but native in-app live camera capture is not yet implemented—take a photo in Camera, then attach it.

## Privacy and saved data

Native state is plaintext JSON under `%LOCALAPPDATA%\SiriForWindowsNative\state.json`. Notes, answers, reminders and meals persist independently of chat Memory. Conversation persistence defaults off. Each saved library is capped at 1,000 entries; conversations retain at most 250 turns and the most recent 200 conversations are persisted. Writes replace a temporary file atomically. Unreadable data is not silently overwritten.

App exclusions are checked case-insensitively before direct reads and before using shared sources; prior turns from newly excluded sources are omitted from follow-up AI context. Exclusions are not a system-wide DLP policy: pasted text, old deliberately saved notes, exported files and screenshots can contain excluded content. Review what you share. Current native folder search is explicit selection, not a folder-exclusion policy or background index.

The native store is **separate** from legacy Electron/browser stores. This version does not automatically migrate or synchronize old conversations, tags or libraries. Advanced legacy features such as word-level writing diffs, tags, Markdown previews and the command palette are not all ported to the native UI yet. Do not equate a native rewrite with universal application compatibility.

## Build and run from source

On Windows with the .NET 8 SDK and package-network access:

```powershell
dotnet run --project native/SiriNative.csproj
dotnet run --project native/tests/NativeChecks.csproj -c Release
dotnet publish native/SiriNative.csproj -c Release -r win-x64 --self-contained true -o native-artifacts
```

The result is `native-artifacts/Siri-for-Windows.exe`. It is unsigned. SmartScreen may warn about unsigned community software; signing is not configured. The primary workflow's artifact is named **Siri-for-Windows-Native-exe**. Older artifacts named `Siri-for-Windows-exe` contain the old Electron build; do not confuse them.

The GitHub Windows job checks native arithmetic/wake/validation rules, publishes the self-contained EXE, verifies there are no required loose DLLs, launches the actual WPF app, finds its composer through accessibility, checks that wake recognition is visibly off, tests second-instance activation, checks the rounded native region, opens the bubble without microphone capture, and verifies the actual text/vision selectors in the Settings dialog. It never enables the runner's microphone. Real Windows/Office/Outlook/hardware behavior needs device testing.

## Android and legacy/browser edition

The Android APK is still the separately built **HTTPS-server-backed companion**, not a .NET app or on-device model. Its server must host the companion web UI; the native WPF EXE does not expose a companion HTTP server. Android image/file picking and origin-gated camera permission remain available. Windows app control and screen sharing are not implemented on Android.

The prior Electron/web edition is retained for compatibility and the browser preview:

```sh
npm ci
npm run dev                     # browser companion preview
npm start                       # primary native app (.NET SDK required)
npm run start:electron:legacy    # optional legacy Electron app
npm run build:electron:legacy    # explicitly optional legacy packaging
npm run start:native             # .NET SDK required
npm run build:win                # now publishes the native .NET EXE
npm test                        # companion/domain tests
```

See [legacy documentation](docs/legacy-electron.md) for its Office add-in, optional extension and browser-specific setup. Universal Microsoft-app embedding, unrestricted autonomous control, stock Camera Siri mode, direct private voicemail/messaging attachment stores, photo batch sharing/editing, and actual payment execution remain unimplemented. The native EXE does not acquire these capabilities merely by being native.

## Direct downloads / current build status

**[Download Siri-for-Windows.exe directly — no ZIP](https://github.com/jedijak14/Siri-For-Windows/releases/latest/download/Siri-for-Windows.exe)**

Close an older running copy of Siri before opening the new EXE, or single-instance activation will bring the old version forward. This is unsigned community software; Windows may show a SmartScreen warning. No installer or separate .NET runtime is required. The downloadable file is a real, self-contained native Windows executable, not a renamed archive or a downloader stub.

**Verified 3.1 build:** [exact EXE asset](https://github.com/jedijak14/Siri-For-Windows/releases/download/native-v3.1-build20/Siri-for-Windows.exe) · [successful Windows UI/build checks](https://github.com/jedijak14/Siri-For-Windows/actions/runs/41237175652). Built from `d02c3e56722f80a99e57e8ff637424090aba32bc`; actual EXE size 73,190,934 bytes. Binary SHA-256: `2dfe9fb20a69c1dec902c0dc36ec70377486bbc1fafba1508f1050d14c8f4210`.

The release asset is published directly by the Windows build job **after** successful native compile/package and actual UI smoke checks. GitHub Actions still retains optional ZIP archives as CI artifacts, but those are no longer the primary Windows download. Exact versioned release links, file sizes and API-reported binary SHA-256 digests are recorded in [`docs/build-artifacts.json`](docs/build-artifacts.json). Prior artifact records are preserved separately.

The sandbox cannot download binary-storage redirects, so compiled binaries are hosted on GitHub Releases rather than copied into this checkout. The primary Windows link serves the EXE itself, with no extraction step. Private repositories may require GitHub sign-in. No TLS verification was disabled. Generated runtimes, binaries and build caches are ignored rather than committed.
