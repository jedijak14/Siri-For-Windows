# Siri for Windows

An independent, local-first assistant built on the supplied Electron and Python app. Not affiliated with Apple or Microsoft; does not connect to Apple Siri or Apple Intelligence. The requested reference images were not present in the uploaded files, so the existing orb design was retained and expanded.

## Start

```sh
npm ci
npm run dev           # browser preview on 0.0.0.0:3000
npm start             # native Electron desktop app
npm test              # pure-function and simulated-DOM tests
```

Install and start **Ollama** on the same machine as the desktop app or preview server:

```sh
ollama pull llama3.2:3b
# For visual tasks, also install a model whose Ollama capabilities include vision.
```

The preview proxies AI requests through relative `/api/…` routes; the browser never tries to reach the user's PC using sandbox localhost. No model is installed in this workspace, so the preview intentionally reports **Local AI · not connected**. There are no fabricated AI responses. Browser camera/screen/clipboard operations require a secure context and permission. The preview server is a development server, not a production multi-user service: do not expose it to the public without authentication, rate limits, request limits, and HTTPS.

## What is implemented

- Dedicated responsive assistant with home, writing, vision, device search, receipt, integrations, and Windows shortcut workspaces.
- User/assistant message rendering; expandable/collapsible replies, detailed answer dialog, selectable text, selective-copy and read-aloud actions. Model output is text, never executable HTML.
- Drafting, proofreading, concise/professional/friendly rewrites, personal-style prompts, Excel formulas, and presentation outlines.
- Reply-language instructions for English, French, Japanese, Korean, Portuguese, and Spanish. Actual fluency depends on the installed model; this is not a guarantee of full multilingual quality.
- Optional local conversation persistence, older-message keyword relevance retrieval, current-session follow-ups even with persistence off, deletion control. Desktop stores plaintext JSON under Electron `userData`; preview uses browser localStorage. Memory defaults off.
- Windows installed-voice selection, speech pace/volume, and calm/natural/lively pitch expressivity through SSML. Voice-dependent, not a neural expressive voice engine. Windows one-shot dictation; browser read-aloud uses browser speech synthesis.
- Explicit one-shot screen/window and camera snapshots, selected image analysis, meal/receipt prompts. Images are capped at 8 MB, three per request.
- Exact-cent bill splitting with pre-tax tip and deterministic remainder distribution. Editable subtotal/tax/tip/people. AI receipt extraction is separate and must be reviewed before entering numbers.
- Desktop search over user-selected folders and text exports (`txt`, `md`, `eml`, `csv`, `json`, `log`, `ics`, `html`), keyword relevance ranking and excerpts. Bounded traversal, no following directory symlinks, folder exclusions. This is **not embedding-based semantic search** or direct private-app database access.
- Per-source app exclusions for explicitly labeled context requests, plus browser website exclusions. Desktop folder exclusions. No automatic background learning or device-wide indexing.
- Opt-in Ctrl+Shift+Space writing shortcut; confirmed Windows Photos, Explorer, Settings, and Task Manager launches. AI-generated commands are never executed.
- Browser extension for Chromium browsers, including Chrome and Edge: selected text/page sharing, explicit screenshots, local-model answers, selected-copy, collapsible answers, and opening answers in the packaged Siri app.
- Office task-pane source and manifest for Word, Excel, PowerPoint. Reads selected text/ranges on click, sends a rewrite request, inserts only after confirmation. Excel insertion requires a single cell; formula insertion requires an explicit checkbox. Requires separate hosting/sideloading and native Office validation.
- Android native companion project that connects to a user-confirmed trusted HTTPS Siri server. No insecure JavaScript-to-native bridge or certificate bypass. It is a companion, not a standalone on-device AI engine.

## Integration setup

### Microsoft Office

1. Serve the preview/task-pane routes through a **trusted HTTPS** endpoint under your control (including a trusted localhost certificate for local development).
2. Change `SourceLocation` in `office/manifest.xml` to that endpoint's `/office/taskpane.html`. The default localhost HTTPS URL is a development placeholder; `npm run dev` alone serves HTTP and is not enough for Office.
3. Sideload the XML manifest using your Microsoft Office development/add-in deployment mechanism. Word, Excel, PowerPoint are declared hosts. Outlook and OneNote currently use the clipboard/export workflow, not embedded add-ins.
4. Review text and formulas before inserting. Office.js is loaded from Microsoft's hosted SDK at runtime; it is not bundled. The add-in has not been run inside real Office here.

### Browser extension

Load `browser-extension/` as an unpacked extension from Chrome/Edge's Extensions developer mode. It uses `activeTab`: no persistent all-sites page reading. Exclude websites from its popup. Only the current tab is captured; browser-internal/restricted pages cannot be shared.

Ollama must permit your exact extension origin through `OLLAMA_ORIGINS` (e.g. `chrome-extension://YOUR_INSTALLED_EXTENSION_ID`); restart Ollama after changing it. Avoid a wildcard origin. Keep Ollama bound to loopback. The extension's local Ollama server is on the browser's machine, not the hosted preview machine. For answers under 14,000 characters, **Open in Siri app** uses the packaged app's `siriwindows://answer` handler; longer answers can be copied. Closing the popup can discard an in-progress answer; it is not a persistent background chat.

### Privacy boundaries

App exclusions apply to **context sources you identify in the desktop composer**, not a system-wide DLP policy. The app cannot reliably identify every application visible in a screenshot or pasted text; do not share excluded content. Browser exclusions are stored independently from desktop preferences. Office add-ins require separate document permissions and are not controlled by the desktop app's source exclusions. Disabling Memory stops further persistence/context retrieval; use Delete memory to remove previously saved data. Clearing saved memory does not clear text already visible in the current chat; New chat does that. Screenshots are one-shot, not continuous live awareness. Nothing silently scans mail, history, calendars, photos, or private app stores.

## Requested features that still need native integrations

These are **not implemented as working device/account integrations**:

- Universal embedding into every Microsoft app, every browser, or every keyboard.
- Continuous on-screen awareness or autonomous cross-app reading/actions.
- Direct Outlook inbox, voicemail, calendar attendees, messaging attachments, Chrome/Edge private history, Reading List database ingestion. User-selected exports can be supplied instead.
- Automated photo batch editing/sharing.
- Stock Windows/phone Camera app “Siri Mode”; this project has its own desktop camera snapshot UI instead.
- Automatic dietary-record updates or a persistent nutrition tracker. Meal analysis is approximate model output, not a validated nutritional calculation.
- Item-assigned receipt splitting and Apple Cash/Venmo payment shortcuts. The included deterministic calculator splits a reviewed subtotal equally and never sends money.
- Standalone Android model inference, native Android camera/screen sharing, or Windows control from Android. Its WebView does not grant those permissions.

## Build binaries

```sh
npm run build:win              # dist/Siri-for-Windows-2.0.0-x64.exe (portable)
npm run build:win:installer    # NSIS installer on Windows
npm run build:android          # Android SDK 35, JDK 17, Gradle 8.9 required
```

Android output: `android/app/build/outputs/apk/debug/app-debug.apk`. Debug APKs use the development debug key; distribution needs a release signing process. Windows binaries are unsigned. The retained Python/Tkinter app is an alternative legacy interface (`python service.py`), not the new Electron renderer.

### Build status in this workspace

- `npm test`: **10 passing** (domain logic and jsdom interactions, not real Chromium/Office/native OS tests).
- Electron packaging was attempted but failed fetching the Windows runtime: certificate verification failure and blocked redirect to `objects.githubusercontent.com`. No `.exe` was produced. TLS verification was not disabled.
- Android packaging was attempted but failed because `gradle` is absent; this Linux environment also lacks Java and the Android SDK. No `.apk` was produced.
- Legacy Python tests cannot run here because system Tkinter is absent.
- `.github/workflows/build.yml` provides Windows and Android artifact jobs for runners with the needed tooling and network access. It has **not** been dispatched or verified in GitHub Actions.
- Build outputs, caches, and downloaded runtimes are ignored; do not commit large generated binaries.

Before shipping: run the workflow, test on Windows and real Office/Android devices, validate manifests/deep links/permissions, review `npm audit` findings for build-time transitive dependencies, add release signing, and deploy an authenticated HTTPS companion server if needed.

## Reference-led native update

The four reference images are now supplied. The user-supplied logo is used in the app and Windows/Android icons. The interface now uses charcoal glass, rounded history cards populated from real conversations, quieter chrome, expandable replies and disclosed source excerpts. No screenshot conversations, private messages, or citations are fabricated as live data.

### Separate Writing Tools

Writing Tools is **not an in-Siri writing studio**. The toolbar opens a separate always-on-top Electron panel. On Windows, opt into **Ctrl+Shift+Space**, select text in an app, and invoke the shortcut. Windows UI Automation reads only the selected text. Excluded process names are checked before selection is read. Revise the text in the panel, then explicitly confirm replacement. Before sending Ctrl+V, the native helper checks the original process, foreground window, password flag, and that the selected text still matches. It refuses unsupported or changed selections; use manual copy/paste instead. The clipboard is changed to your revision. This is a native keyboard/accessibility workflow, not a claim that every app exposes compatible selection APIs or has a built-in ribbon add-in.

### Chrome and Edge — no extension required on Windows

Use **Browser** in the composer or **Read Chrome or Edge** in Visual Intelligence. The app enumerates eligible visible browser windows, asks which window you approve, and reads its currently accessible page text through Windows UI Automation. No extension, browser debugging port, or browser restart is required. Pages that do not expose text must use a user-approved screenshot instead; password fields are never deliberately read. This requires real Windows desktop testing and does not function in the hosted Linux preview. The old optional browser extension remains available but is not required for this native path.

Device search also offers explicit history search over a temporary copy of the Default or Profile N Chrome/Edge `History` SQLite database. It uses parameterized queries, removes temporary files, and never modifies the live history. Locked files can require closing the browser. It does not expose incognito history or arbitrary browser profiles. App exclusions apply before reads.

### Inbox, nutrition, and payment boundaries

- **Classic Outlook:** approved searches use the running Outlook COM object and inspect up to the latest 500 default-inbox mail items, returning at most 12 matching excerpts. COM policy prompts, locked stores, or a non-running classic Outlook can block access. New Outlook, Gmail, voicemail and messaging stores are not implemented. No mail is sent, deleted, or changed.
- **Nutrition journal:** user-reviewed items persist locally, can be edited/deleted, and totals update as values change. A meal response containing valid JSON `{name, items:[{name, calories, protein, carbs, fat}], uncertainty}` has a **Review & log meal** action. Estimates are not saved automatically and have no clinical validation. Native data is in `nutrition.json` under Electron userData; preview uses localStorage. It is independent of chat Memory.
- **Venmo:** the split-bill pane validates a username and amount and, after a native confirmation, opens an official Venmo HTTPS payment handoff. It does not authenticate an account, submit a transfer, know whether the URL parameters are accepted by the current Venmo client, or verify success. Apple Cash has no supported Windows payment API in this project. **Payment execution remains unimplemented**, not simulated.
- Native integrations are implemented in `electron/native/automation.ps1` and `integrations.js`. This environment can test validators, SQLite snapshots and simulated UI interactions, but cannot validate Windows UI Automation, Outlook COM, native paste behavior or real Office interoperability.

The older implementation list above describes the first iteration; this update supersedes its statements that browser history, Outlook reads and a nutrition tracker are entirely absent. Unrestricted autonomous cross-app operation, universal app embedding, automatic private-store indexing, photo batch editing/sharing and actual payment execution are still not implemented. These cannot responsibly be described as “exactly working” without native/account integrations and device testing.
