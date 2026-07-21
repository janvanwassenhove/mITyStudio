// Ask-first auto-update against GitHub Releases (electron-updater).
// Publishing config lives in package.json ("publish": {"provider": "github"}).
//
// Flow: check on startup + every few hours → tell the RENDERER an update
// exists → the app asks the user → on consent we download (progress events)
// → user confirms restart → quitAndInstall. Nothing downloads or installs
// without the user saying yes (the old checkForUpdatesAndNotify silently
// downloaded in the background).
const { ipcMain } = require('electron')

const CHECK_EVERY_MS = 4 * 60 * 60 * 1000   // 4h

function initUpdater(win) {
  let autoUpdater
  try {
    ({ autoUpdater } = require('electron-updater'))
  } catch (e) {
    console.log('[updater] unavailable:', e && e.message)
    return
  }
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  const send = (channel, payload) => {
    try {
      if (win && !win.isDestroyed()) win.webContents.send(channel, payload)
    } catch { /* window gone */ }
  }
  autoUpdater.on('update-available', (info) => send('update:available', {
    version: info.version,
    notes: typeof info.releaseNotes === 'string' ? info.releaseNotes : '',
  }))
  autoUpdater.on('download-progress', (p) =>
    send('update:progress', { percent: Math.round(p.percent || 0) }))
  autoUpdater.on('update-downloaded', (info) =>
    send('update:downloaded', { version: info.version }))
  autoUpdater.on('error', (e) =>
    send('update:error', { message: (e && e.message) || 'update failed' }))

  ipcMain.handle('update:download', async () => {
    try {
      await autoUpdater.downloadUpdate()
      return { ok: true }
    } catch (e) {
      return { ok: false, error: e && e.message }
    }
  })
  ipcMain.handle('update:install', () => {
    setImmediate(() => autoUpdater.quitAndInstall())
    return { ok: true }
  })

  const check = () => autoUpdater.checkForUpdates().catch((e) => {
    console.log('[updater] check failed:', e && e.message)
  })
  check()
  const timer = setInterval(check, CHECK_EVERY_MS)
  if (timer.unref) timer.unref()
}

module.exports = { initUpdater }
