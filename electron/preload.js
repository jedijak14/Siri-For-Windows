const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("siri", Object.freeze({
  listLibrary: (kind) => ipcRenderer.invoke("library:list",kind),
  saveLibrary: (kind,item) => ipcRenderer.invoke("library:save",kind,item),
  removeLibrary: (kind,id) => ipcRenderer.invoke("library:remove",kind,id),
  cancelRequest: (id) => ipcRenderer.invoke("assistant:cancel",id),
  runWorkflow: (plan) => ipcRenderer.invoke("workflow:run",plan),
  openWriting: () => ipcRenderer.invoke("writing:open"),
  writingContext: () => ipcRenderer.invoke("writing:context"),
  replaceSelection: (text) => ipcRenderer.invoke("writing:replace",text),
  readBrowser: () => ipcRenderer.invoke("native:browser"),
  searchInbox: (query) => ipcRenderer.invoke("native:outlook",query),
  searchBrowserHistory: (payload) => ipcRenderer.invoke("native:history",payload),
  listMeals: () => ipcRenderer.invoke("diet:list"),
  saveMeal: (meal) => ipcRenderer.invoke("diet:save",meal),
  deleteMeal: (id) => ipcRenderer.invoke("diet:delete",id),
  reviewPayment: (payload) => ipcRenderer.invoke("payment:review",payload),
  onWritingContext: (callback) => {const listener=(_event,data)=>callback(data);ipcRenderer.on("writing:context",listener);return ()=>ipcRenderer.removeListener("writing:context",listener);},
  openWindowsApp: (id) => ipcRenderer.invoke("windows:open-app", id),
  onOpenAnswer: (callback) => {
    const listener = (_event, text) => callback(text);
    ipcRenderer.on("answer:open", listener);
    return () => ipcRenderer.removeListener("answer:open", listener);
  },
  listModels: () => ipcRenderer.invoke("models:list"),
  ask: (payload) => ipcRenderer.invoke("assistant:ask", payload),
  listHistory: () => ipcRenderer.invoke("history:list"),
  clearHistory: () => ipcRenderer.invoke("history:clear"),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
  addPrivacyExclusion: () => ipcRenderer.invoke("privacy:exclude-folder"),
  removePrivacyExclusion: (folder) => ipcRenderer.invoke("privacy:remove-exclusion", folder),
  chooseSearchFolder: () => ipcRenderer.invoke("context:choose-folder"),
  searchFolder: (folder, query) => ipcRenderer.invoke("context:search-folder", folder, query),
  readClipboard: () => ipcRenderer.invoke("clipboard:read"),
  writeClipboard: (text) => ipcRenderer.invoke("clipboard:write", text),
  listVoices: () => ipcRenderer.invoke("speech:voices"),
  speak: (payload) => ipcRenderer.invoke("speech:speak", payload),
  listen: () => ipcRenderer.invoke("speech:listen"),
  openPhotos: () => ipcRenderer.invoke("app:open-photos"),
  onWritingShortcut: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("shortcut:writing", listener);
    return () => ipcRenderer.removeListener("shortcut:writing", listener);
  },
}));
