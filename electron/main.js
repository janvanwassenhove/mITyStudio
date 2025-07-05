/**
 * mITyStudio Electron Main Process
 * 
 * This file controls the lifecycle of the Electron application.
 * It manages the main window, backend server, and system integration.
 */

const { app, BrowserWindow, Menu, dialog, shell, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const serve = require('electron-serve')
const Store = require('electron-store')

// Initialize electron store for persistent settings
const store = new Store()

// Enable development mode
const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev')

// Serve frontend files
const loadURL = serve({ directory: path.join(__dirname, '../frontend/dist') })

// Global references
let mainWindow
let backendProcess

/**
 * Create the main application window
 */
function createMainWindow() {
  // Get window state from store
  const windowState = store.get('windowState', {
    width: 1400,
    height: 900,
    x: undefined,
    y: undefined,
    maximized: false
  })

  mainWindow = new BrowserWindow({
    width: windowState.width,
    height: windowState.height,
    x: windowState.x,
    y: windowState.y,
    minWidth: 1200,
    minHeight: 700,
    show: false, // Don't show until ready
    icon: path.join(__dirname, 'assets/icon.png'),
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: !isDev
    }
  })

  // Restore maximized state
  if (windowState.maximized) {
    mainWindow.maximize()
  }

  // Save window state on close
  mainWindow.on('close', () => {
    const bounds = mainWindow.getBounds()
    store.set('windowState', {
      ...bounds,
      maximized: mainWindow.isMaximized()
    })
  })

  // Load the application
  if (isDev) {
    // Development: load from Vite dev server
    mainWindow.loadURL('http://localhost:5173')
    // Open DevTools
    mainWindow.webContents.openDevTools()
  } else {
    // Production: load from built files
    loadURL(mainWindow)
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    
    // Focus window
    if (isDev) {
      mainWindow.focus()
    }
  })

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  return mainWindow
}

/**
 * Start the Python Flask backend server
 */
function startBackendServer() {
  if (isDev) {
    console.log('Development mode: Backend should be started manually')
    return
  }

  const backendPath = path.join(__dirname, '../backend')
  const pythonExecutable = process.platform === 'win32' ? 'python.exe' : 'python3'
  
  console.log('Starting backend server...')
  
  backendProcess = spawn(pythonExecutable, ['run.py'], {
    cwd: backendPath,
    stdio: 'pipe',
    env: {
      ...process.env,
      FLASK_ENV: 'production',
      PORT: '5000'
    }
  })

  backendProcess.stdout.on('data', (data) => {
    console.log(`Backend: ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`Backend Error: ${data}`)
  })

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`)
  })

  backendProcess.on('error', (err) => {
    console.error('Failed to start backend:', err)
    dialog.showErrorBox(
      'Backend Error',
      'Failed to start the backend server. Please check your Python installation.'
    )
  })
}

/**
 * Stop the backend server
 */
function stopBackendServer() {
  if (backendProcess) {
    console.log('Stopping backend server...')
    backendProcess.kill()
    backendProcess = null
  }
}

/**
 * Create application menu
 */
function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Project',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.send('menu-action', 'new-project')
          }
        },
        {
          label: 'Open Project',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            const result = await dialog.showOpenDialog(mainWindow, {
              properties: ['openFile'],
              filters: [
                { name: 'mITyStudio Projects', extensions: ['mity'] },
                { name: 'All Files', extensions: ['*'] }
              ]
            })
            
            if (!result.canceled) {
              mainWindow.webContents.send('menu-action', 'open-project', result.filePaths[0])
            }
          }
        },
        {
          label: 'Save Project',
          accelerator: 'CmdOrCtrl+S',
          click: () => {
            mainWindow.webContents.send('menu-action', 'save-project')
          }
        },
        {
          label: 'Export Audio',
          accelerator: 'CmdOrCtrl+E',
          click: () => {
            mainWindow.webContents.send('menu-action', 'export-audio')
          }
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit()
          }
        }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { label: 'Undo', accelerator: 'CmdOrCtrl+Z', role: 'undo' },
        { label: 'Redo', accelerator: 'Shift+CmdOrCtrl+Z', role: 'redo' },
        { type: 'separator' },
        { label: 'Cut', accelerator: 'CmdOrCtrl+X', role: 'cut' },
        { label: 'Copy', accelerator: 'CmdOrCtrl+C', role: 'copy' },
        { label: 'Paste', accelerator: 'CmdOrCtrl+V', role: 'paste' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' },
        { label: 'Force Reload', accelerator: 'CmdOrCtrl+Shift+R', role: 'forceReload' },
        { label: 'Toggle Developer Tools', accelerator: 'F12', role: 'toggleDevTools' },
        { type: 'separator' },
        { label: 'Actual Size', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
        { label: 'Zoom In', accelerator: 'CmdOrCtrl+Plus', role: 'zoomIn' },
        { label: 'Zoom Out', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' },
        { type: 'separator' },
        { label: 'Toggle Fullscreen', accelerator: 'F11', role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Audio',
      submenu: [
        {
          label: 'Play/Pause',
          accelerator: 'Space',
          click: () => {
            mainWindow.webContents.send('menu-action', 'play-pause')
          }
        },
        {
          label: 'Stop',
          accelerator: 'CmdOrCtrl+.',
          click: () => {
            mainWindow.webContents.send('menu-action', 'stop')
          }
        },
        {
          label: 'Record',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            mainWindow.webContents.send('menu-action', 'record')
          }
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About mITyStudio',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About mITyStudio',
              message: 'mITyStudio',
              detail: 'AI-powered music composition studio\nVersion 1.0.0\n\nBuilt with Vue.js, Flask, and Electron'
            })
          }
        },
        {
          label: 'Learn More',
          click: () => {
            shell.openExternal('https://github.com/mitystudio/mitystudio')
          }
        }
      ]
    }
  ]

  // macOS specific menu adjustments
  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
      submenu: [
        { label: 'About ' + app.getName(), role: 'about' },
        { type: 'separator' },
        { label: 'Services', role: 'services', submenu: [] },
        { type: 'separator' },
        { label: 'Hide ' + app.getName(), accelerator: 'Command+H', role: 'hide' },
        { label: 'Hide Others', accelerator: 'Command+Shift+H', role: 'hideothers' },
        { label: 'Show All', role: 'unhide' },
        { type: 'separator' },
        { label: 'Quit', accelerator: 'Command+Q', click: () => app.quit() }
      ]
    })
  }

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

// App event handlers
app.whenReady().then(() => {
  console.log('mITyStudio starting...')
  
  // Create main window
  createMainWindow()
  
  // Create menu
  createMenu()
  
  // Start backend server
  startBackendServer()
  
  // Wait a moment for backend to start
  setTimeout(() => {
    console.log('mITyStudio ready!')
  }, 2000)
})

app.on('window-all-closed', () => {
  // Stop backend server
  stopBackendServer()
  
  // On macOS, keep app running even when all windows are closed
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow()
  }
})

app.on('before-quit', () => {
  // Stop backend server before quitting
  stopBackendServer()
})

// IPC handlers
ipcMain.handle('get-app-version', () => {
  return app.getVersion()
})

ipcMain.handle('get-app-path', () => {
  return app.getAppPath()
})

ipcMain.handle('show-save-dialog', async (event, options) => {
  const result = await dialog.showSaveDialog(mainWindow, options)
  return result
})

ipcMain.handle('show-open-dialog', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options)
  return result
})

ipcMain.handle('show-message-box', async (event, options) => {
  const result = await dialog.showMessageBox(mainWindow, options)
  return result
})

// Handle app protocol for deep linking (optional)
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('mitystudio', process.execPath, [path.resolve(process.argv[1])])
  }
} else {
  app.setAsDefaultProtocolClient('mitystudio')
}

console.log('mITyStudio Electron main process initialized')
