// Backend lifecycle: spawn uvicorn from the per-machine venv, wait for
// /api/health, kill on quit.
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')
const path = require('path')
const fs = require('fs')

let child = null

function freePort(preferred = 8930) {
  return new Promise((resolve) => {
    const srv = net.createServer()
    srv.once('error', () => {
      const s2 = net.createServer()
      s2.listen(0, '127.0.0.1', () => {
        const p = s2.address().port
        s2.close(() => resolve(p))
      })
    })
    srv.listen(preferred, '127.0.0.1', () => {
      srv.close(() => resolve(preferred))
    })
  })
}

function health(port) {
  return new Promise((resolve) => {
    const req = http.get(
      { host: '127.0.0.1', port, path: '/api/health', timeout: 1500 },
      (res) => resolve(res.statusCode === 200),
    )
    req.on('error', () => resolve(false))
    req.on('timeout', () => { req.destroy(); resolve(false) })
  })
}

async function startBackend(env, onStatus) {
  const port = await freePort()
  const logFile = path.join(env.userData || env.repoRoot, 'backend.log')
  const out = fs.openSync(logFile, 'a')

  child = spawn(
    env.python,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: env.backendDir,
      windowsHide: true,
      stdio: ['ignore', out, out],
      env: {
        ...process.env,
        MITY_ROOT: env.workspace,
        MITY_UI_DIST: env.uiDist,
        ...env.tools,
      },
    },
  )
  child.on('exit', (code) => {
    console.log('[backend] exited', code)
    child = null
  })

  for (let i = 0; i < 120; i++) {
    if (!child) throw new Error(`backend exited early — see ${logFile}`)
    if (await health(port)) return port
    if (i % 8 === 0) onStatus('Starting the audio engine…')
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`backend did not become healthy — see ${logFile}`)
}

function stopBackend() {
  if (child) {
    try { child.kill() } catch { /* already gone */ }
    child = null
  }
}

module.exports = { startBackend, stopBackend }
