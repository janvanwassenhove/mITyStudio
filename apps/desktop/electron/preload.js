const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('mity', {
  onStatus: (cb) => ipcRenderer.on('status', (_e, text) => cb(text)),
  chooseFolder: () => ipcRenderer.invoke('setup:choose-folder'),
  setupDone: (workspace) => ipcRenderer.invoke('setup:done', workspace),
  // integrated title bar: recolor the native window controls with the theme
  setTitleBarTheme: (theme) => ipcRenderer.send('titlebar:theme', theme),
  // ask-first auto-update: main process detects a GitHub release, the app
  // asks the user, download + install only happen on consent
  onUpdateAvailable: (cb) => ipcRenderer.on('update:available', (_e, i) => cb(i)),
  onUpdateProgress: (cb) => ipcRenderer.on('update:progress', (_e, p) => cb(p)),
  onUpdateDownloaded: (cb) => ipcRenderer.on('update:downloaded', (_e, i) => cb(i)),
  onUpdateError: (cb) => ipcRenderer.on('update:error', (_e, err) => cb(err)),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.invoke('update:install'),
})
