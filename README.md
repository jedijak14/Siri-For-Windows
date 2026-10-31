# Siri for Windows

An independent local-first Windows assistant, built from the supplied Electron/Python app and styled using the supplied references and logo. Not affiliated with Apple or Microsoft; this is not an official Apple Siri client.

## Run

```sh
npm ci
npm start       # Windows Electron app
npm run dev     # browser preview at 0.0.0.0:3000
npm test
```

Install and run Ollama on the same machine as the desktop app or preview server, and install a local model, e.g. `ollama pull llama3.2:3b`. Image tasks need an installed model that advertises vision support. No model is bundled. Offline errors are real errors, not simulated answers. Language instructions support English, French, Japanese, Korean, Portuguese and Spanish; output quality depends on your model.

The preview uses relative `/api/…` routes, not the user's browser calling a sandbox localhost address. Camera/screen/clipboard need a secure context and permission. The preview server is development-only; production hosting requires authentication, rate limits, HTTPS, and deployment review.

## Interface

- User-supplied orb logo, charcoal glass panels, rounded conversation history tiles populated from real chats, not fabricated screenshot content.
- Selectable, safely rendered answers, expand/collapse, a detail view, selected-text copy, read-aloud, and disclosed source excerpts. No invented web citations or images.
- Optional local memory and older-message keyword retrieval; current-session follow-ups also work with persistence off. Desktop uses JSON under Electron `userData`; preview uses localStorage. Memory defaults off. Disable stops persistence/retrieval; Delete removes saved memory; New chat clears the current view.
- Windows voice selection, pace, volume and voice-dependent pitch expressivity through SSML. Dictation uses installed Windows speech components. Browser speech uses browser voices. This is not a custom neural voice engine.
- One-shot screen/window, camera and image input. No continuous background capture. Up to three images, 8 MB each.

## Writing Tools — separate from Siri

Writing Tools opens in its **own always-on-top panel**, not an in-Siri studio. On Windows, enable **Ctrl+Shift+Space** in Settings, select text in Word, Excel, a browser or another app, then invoke the shortcut. Windows UI Automation reads only the selected text after checking the process against exclusions.

Proofread, rewrite, change tone, compose drafts, generate Excel formulas or slide outlines. Review the result and explicitly confirm replacement. Before sending Ctrl+V, the native helper verifies the original process, window focus, password flag and unchanged selected text. Unsupported/changed selections are refused; use manual copy/paste. Your clipboard changes to the revision. Windows accessibility compatibility varies: this is **not a guarantee of embedding in every app**. Some apps require manual copy/paste or the Office add-in.

The optional Office task pane supports Word, Excel and PowerPoint. Host `/office/taskpane.html` through trusted HTTPS, update `SourceLocation` in `office/manifest.xml`, and sideload using Microsoft's add-in development mechanism. The default localhost HTTPS URL is a placeholder: `npm run dev` by itself serves HTTP. It reads selections only on click and inserts only after confirmation. Excel insertion requires one cell; formula insertion has a separate explicit opt-in. Office.js loads from Microsoft's hosted SDK. Outlook/OneNote do not have an embedded add-in here. Real Office validation remains required.

## Chrome and Edge — no extension required on Windows

Use **Browser** in the composer or **Read Chrome or Edge** under Visual Intelligence. The app asks you to choose a visible eligible browser window and reads currently accessible page text using Windows UI Automation. No extension, debugging port or browser restart is needed. Pages that expose no accessible text require a user-approved screenshot instead. No attempt is made to read password fields. Browser app exclusions are enforced before the page read.

Device search offers direct Chrome/Edge history search. Choose Default or Profile N and approve a temporary SQLite snapshot. Parameterized queries return up to 30 matching titles/URLs; temporary files are deleted. The live database is not modified; locked profiles can require closing the browser. Incognito history is not available.

The old `browser-extension/` is retained as an optional Chromium companion, not a dependency of the native Windows path. To use it, load unpacked and permit its exact origin in Ollama's `OLLAMA_ORIGINS`; avoid wildcards. Extension website exclusions are independent from desktop preferences. Its Open in Siri action uses the packaged app's `siriwindows://answer` handler; long answers use copy/paste.

## Inbox and device search

**Classic Outlook** search uses the currently running Outlook COM object. Each request asks permission, then searches up to 500 recent default-inbox messages and returns at most 12 matching excerpts. New Outlook, cloud mailbox APIs, other folders, voicemail and messaging stores are not supported. Outlook security policy can block access. Messages are not sent/deleted/edited. Results are attached for review and sent to the local model only when you press Send.

Folder search requires a folder selected through a native picker; supports text, markdown, exported email/CSV/JSON/log/calendar/HTML files, bounded traversal, exclusions and keyword ranking. This is not embedding-based semantic indexing. No arbitrary device-wide private-store indexing occurs.

## Reviewed cross-app tasks

**Cross-app tasks** asks the local model for a bounded plan, shows the proposed steps, then validates the plan again in the native process. A reviewed plan can search classic Outlook, search Chrome/Edge history, summarize approved results, save a text note using a native Save dialog, and open Photos/Explorer/Settings. Each private-data read asks permission. At most six steps; execution stops at the first failure and reports completed steps. Tasks run only while the app is open.

This is scoped, user-approved orchestration, **not unrestricted autonomous control**. The runner rejects arbitrary commands, scripts, arbitrary write paths, email sending, deletion and payments. Saved notes are not automatically shared. Partially completed tasks are reported, not rolled back.

## Meals and receipts

- Meal vision prompts provide uncertain, non-medical estimates. A valid structured response `{name,items:[{name,calories,protein,carbs,fat}],uncertainty}` has a **Review & log meal** action. Otherwise enter the estimates manually.
- The local nutrition journal lets you review foods and macros, updates totals immediately as values change, and supports save/edit/delete. Nothing is saved without a click. Desktop stores `nutrition.json`; preview uses localStorage. Independent from chat Memory; not connected to an external health account.
- The receipt calculator splits a reviewed subtotal, tax and pre-tax tip with exact-cent remainder distribution. OCR/model extraction must be checked before entering amounts. Equal shares only; not per-diner item assignments.
- Venmo integration validates a username and amount, asks confirmation and opens the official HTTPS payment handoff. You must authenticate and confirm in Venmo. Current client support for the URL parameters and payment status cannot be verified by Siri. **No payment is submitted or confirmed by this app.** Apple Cash has no supported Windows payment integration here.

## Privacy and native compatibility

`electron/native/automation.ps1` implements Windows Accessibility/Outlook operations. Native code runs only on a user action or opt-in shortcut; no startup persistence, browser automation debugging port, hidden capture or arbitrary model-generated commands. App exclusions are checked before native reads. They are not a system-wide DLP policy: manually pasted text or a screenshot can contain an excluded app, so review content before sharing. Office permissions and optional extension site exclusions are separate.

Windows UI Automation, Outlook COM, native insertion and real Office interoperability cannot be fully validated in this Linux workspace. Security policies, app versions and accessibility support can change behavior. Universal app embedding, stock Camera “Siri Mode”, private voicemail/messaging attachment ingestion, photo batch editing/sharing, unrestricted autonomous cross-app actions, payment execution, and continuous real-time screen awareness are **not implemented**.

## Android companion

The native Android project uses the supplied logo and connects only after the user confirms a trusted HTTPS Siri server. No insecure JavaScript bridge, certificate bypass or HTTP allowance. The server's responsive interface provides the glass mobile chat/history design. Your phone cannot reach your PC using localhost. This APK is a **server-backed companion**, not bundled on-device AI; native Android screen/camera/file chooser and Windows app controls are not implemented in the WebView. Do not describe it as feature-parity with the Windows app.

## Packaging and validation

```sh
npm run build:win             # portable Windows .exe
npm run build:win:installer   # NSIS installer
npm run build:android        # JDK 17, Android SDK 35, Gradle 8.9 required
```

Windows outputs go to `dist/`; Android debug APK to `android/app/build/outputs/apk/debug/app-debug.apk`. Windows binaries are unsigned; debug APKs use the Android development key. Release signing requires a separate process.

`.github/workflows/build.yml` builds on Windows and Android-capable runners and uploads artifact archives. Both jobs completed successfully for commit `0c94c796bd70a207c7deeb6a8780fc1eb0cb2752` in [build run 41232146663](https://github.com/jedijak14/Siri-For-Windows/actions/runs/41232146663).

- [Windows Electron portable EXE archive](https://github.com/jedijak14/Siri-For-Windows/actions/runs/41232146663/artifacts/13053863953)
- [Android debug companion APK archive](https://github.com/jedijak14/Siri-For-Windows/actions/runs/41232146663/artifacts/13054440385)

Download and extract the archives while signed into GitHub. Artifact URLs expire under the repository retention policy. Archive SHA-256 digests and sizes are recorded in `docs/build-artifacts.json`. The sandbox blocks GitHub's blob-storage download redirects, so these binaries are hosted on GitHub rather than copied into the local repository folder. Manual dispatch returned HTTP 403; push-triggered builds worked.

Local validation: **19 passing tests** (pure functions, SQLite snapshot/query handling, plan validation and simulated-DOM interactions), JavaScript/XML syntax checks, no production npm advisories. These are not real native desktop/Office/Android device tests. PowerShell syntax, UI Automation assembly loading, and native C# helper compilation passed in the Windows workflow. Desktop/mobile Chromium smoke checks also passed: separate writing popup, honest offline errors, mobile menu/back navigation, no page errors or horizontal overflow. Legacy Python tests need Tkinter, absent here. Build-time transitive npm advisories remain; review before release.

Local Windows packaging was retried and blocked fetching Electron by certificate/download-network restrictions. Local Android tooling is absent. GitHub runner builds produced actual EXE and APK artifacts; no TLS verification was disabled. Build outputs/caches are ignored and must not be committed. The original Python/Tkinter app remains available as an alternative legacy interface, not the new Electron renderer.
