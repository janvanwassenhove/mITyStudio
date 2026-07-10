// Auto-update against GitHub Releases (electron-updater).
// Publishing config lives in package.json ("publish": {"provider": "github"}).
function initUpdater() {
  try {
    const { autoUpdater } = require('electron-updater')
    autoUpdater.autoDownload = true
    autoUpdater.checkForUpdatesAndNotify().catch((e) => {
      console.log('[updater] check failed:', e && e.message)
    })
  } catch (e) {
    console.log('[updater] unavailable:', e && e.message)
  }
}

module.exports = { initUpdater }
