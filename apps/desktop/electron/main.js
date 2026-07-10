// mITyStudio desktop shell.
// Boot order: splash → first-run setup (workspace folder) → environment
// bootstrap (venv + deps + tools, first run only) → spawn backend → main
// window at the backend's origin (it serves the built UI).
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron')
const path = require('path')
const fs = require('fs')

const { ensureEnvironment } = require('./bootstrap')
const { startBackend, stopBackend } = require('./backend')
const { initUpdater } = require('./updater')

const DEV = process.env.MITY_DEV === '1'
const repoRoot = path.resolve(__dirname, '..', '..', '..')

let splash = null
let mainWin = null

function configPath() {
  return path.join(app.getPath('userData'), 'desktop-config.json')
}

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(configPath(), 'utf-8'))
  } catch {
    return {}
  }
}

function saveConfig(cfg) {
  fs.mkdirSync(app.getPath('userData'), { recursive: true })
  fs.writeFileSync(configPath(), JSON.stringify(cfg, null, 2))
}

function setStatus(text) {
  if (splash && !splash.isDestroyed()) {
    splash.webContents.send('status', text)
  }
  console.log('[boot]', text)
}

function showSplash() {
  splash = new BrowserWindow({
    width: 460,
    height: 300,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js') },
  })
  splash.loadFile(path.join(__dirname, '..', 'splash.html'))
}

function firstRunSetup() {
  return new Promise((resolve) => {
    const win = new BrowserWindow({
      width: 560,
      height: 420,
      resizable: false,
      webPreferences: { preload: path.join(__dirname, 'preload.js') },
    })
    win.removeMenu?.()
    win.loadFile(path.join(__dirname, '..', 'setup.html'))

    ipcMain.handleOnce('setup:choose-folder', async () => {
      const r = await dialog.showOpenDialog(win, {
        title: 'Choose a folder for your projects, samples and voices',
        properties: ['openDirectory', 'createDirectory'],
      })
      return r.canceled ? null : r.filePaths[0]
    })
    ipcMain.handleOnce('setup:done', (_e, workspace) => {
      win.close()
      resolve(workspace)
    })
    win.on('closed', () => resolve(null))
  })
}

async function boot() {
  showSplash()

  const cfg = loadConfig()

  // 1. workspace (first-run: let the user pick; default under Documents)
  if (!cfg.workspace) {
    if (DEV) {
      cfg.workspace = repoRoot
    } else {
      splash.hide()
      const chosen = await firstRunSetup()
      splash.show()
      cfg.workspace =
        chosen || path.join(app.getPath('documents'), 'mITyStudio')
    }
    saveConfig(cfg)
  }
  fs.mkdirSync(cfg.workspace, { recursive: true })

  // 2. environment (python venv + deps + audio tools) — no-op when ready
  let env
  try {
    env = await ensureEnvironment({
      dev: DEV,
      repoRoot,
      resourcesPath: process.resourcesPath,
      userData: app.getPath('userData'),
      workspace: cfg.workspace,
      onStatus: setStatus,
    })
  } catch (e) {
    dialog.showErrorBox(
      'mITyStudio could not set up its environment',
      String(e && e.stack ? e.stack : e),
    )
    app.quit()
    return
  }

  // 3. backend
  setStatus('Starting the audio engine…')
  let port
  try {
    port = await startBackend(env, setStatus)
  } catch (e) {
    dialog.showErrorBox(
      'mITyStudio backend failed to start',
      String(e && e.stack ? e.stack : e),
    )
    app.quit()
    return
  }

  // 4. main window
  setStatus('Opening the studio…')
  mainWin = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 980,
    minHeight: 640,
    show: false,
    backgroundColor: '#14161a',
    title: 'mITyStudio',
    icon: path.join(__dirname, '..', 'build', 'icon.png'),
  })
  mainWin.removeMenu?.()
  mainWin.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  await mainWin.loadURL(`http://127.0.0.1:${port}/`)
  mainWin.show()
  if (splash && !splash.isDestroyed()) splash.close()

  if (!DEV) initUpdater()
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWin) {
      if (mainWin.isMinimized()) mainWin.restore()
      mainWin.focus()
    }
  })
  app.whenReady().then(boot)
}

app.on('window-all-closed', () => {
  stopBackend()
  app.quit()
})
app.on('before-quit', () => stopBackend())
