const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('mity', {
  onStatus: (cb) => ipcRenderer.on('status', (_e, text) => cb(text)),
  chooseFolder: () => ipcRenderer.invoke('setup:choose-folder'),
  setupDone: (workspace) => ipcRenderer.invoke('setup:done', workspace),
  // integrated title bar: recolor the native window controls with the theme
  setTitleBarTheme: (theme) => ipcRenderer.send('titlebar:theme', theme),
})
