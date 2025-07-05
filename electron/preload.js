/**
 * mITyStudio Electron Preload Script
 * 
 * This script runs in the renderer process and provides a secure bridge
 * between the main process and the web content.
 */

const { contextBridge, ipcRenderer } = require('electron')

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // App information
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getAppPath: () => ipcRenderer.invoke('get-app-path'),

  // File dialogs
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
  showMessageBox: (options) => ipcRenderer.invoke('show-message-box', options),

  // Menu actions
  onMenuAction: (callback) => {
    ipcRenderer.on('menu-action', (event, action, ...args) => {
      callback(action, ...args)
    })
  },

  // System integration
  openExternal: (url) => {
    // This would be handled by the main process
    ipcRenderer.send('open-external', url)
  },

  // Project file operations
  saveProject: (projectData) => ipcRenderer.invoke('save-project', projectData),
  loadProject: (filePath) => ipcRenderer.invoke('load-project', filePath),

  // Audio export
  exportAudio: (audioData, options) => ipcRenderer.invoke('export-audio', audioData, options),

  // Backend communication helpers
  backendRequest: async (endpoint, options = {}) => {
    const baseUrl = 'http://localhost:5000'
    const url = `${baseUrl}${endpoint}`
    
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      return await response.json()
    } catch (error) {
      console.error('Backend request failed:', error)
      throw error
    }
  },

  // Settings and preferences
  getSetting: (key, defaultValue) => ipcRenderer.invoke('get-setting', key, defaultValue),
  setSetting: (key, value) => ipcRenderer.invoke('set-setting', key, value),

  // Development utilities
  isDev: process.env.NODE_ENV === 'development',
  
  // Platform information
  platform: process.platform,
  
  // Constants
  constants: {
    BACKEND_URL: 'http://localhost:5000',
    APP_NAME: 'mITyStudio'
  }
})

// Expose a limited set of Node.js APIs for specific use cases
contextBridge.exposeInMainWorld('nodeAPI', {
  path: {
    join: (...args) => require('path').join(...args),
    dirname: (path) => require('path').dirname(path),
    basename: (path) => require('path').basename(path),
    extname: (path) => require('path').extname(path)
  }
})

// Console logging for debugging
console.log('mITyStudio preload script loaded')

// Notify when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  console.log('mITyStudio DOM content loaded')
  
  // Add Electron-specific class to body for styling
  document.body.classList.add('electron-app')
  
  // Add platform-specific class
  document.body.classList.add(`platform-${process.platform}`)
})

// Handle uncaught errors
window.addEventListener('error', (event) => {
  console.error('Uncaught error in renderer:', event.error)
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection in renderer:', event.reason)
})
