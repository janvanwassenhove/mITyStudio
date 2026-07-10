const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('mity', {
  onStatus: (cb) => ipcRenderer.on('status', (_e, text) => cb(text)),
  chooseFolder: () => ipcRenderer.invoke('setup:choose-folder'),
  setupDone: (workspace) => ipcRenderer.invoke('setup:done', workspace),
})
