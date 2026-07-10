// First-run environment bootstrap: bundled Python runtime → per-machine venv
// → core dependencies → audio tools (FluidSynth/ffmpeg) → seeded workspace.
// The heavy neural voice stack installs later, on demand (setup-voice), with
// a torch build matching the detected device (CUDA > MPS > CPU).
const { spawn, execFileSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const https = require('https')

const WIN = process.platform === 'win32'

function run(cmd, args, opts = {}, onLine) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { ...opts, windowsHide: true })
    let tail = ''
    const eat = (buf) => {
      const s = buf.toString()
      tail = (tail + s).slice(-2000)
      s.split(/\r?\n/).forEach((l) => l.trim() && onLine && onLine(l.trim()))
    }
    child.stdout?.on('data', eat)
    child.stderr?.on('data', eat)
    child.on('error', reject)
    child.on('exit', (code) =>
      code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}\n${tail}`)),
    )
  })
}

function download(url, dest, onStatus) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': 'mITyStudio' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return download(res.headers.location, dest, onStatus).then(resolve, reject)
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`download failed ${res.statusCode}: ${url}`))
      }
      const total = Number(res.headers['content-length'] || 0)
      let got = 0
      const out = fs.createWriteStream(dest)
      res.on('data', (c) => {
        got += c.length
        if (total && onStatus) {
          onStatus(`Downloading ${path.basename(dest)} — ${Math.round((got / total) * 100)}%`)
        }
      })
      res.pipe(out)
      out.on('finish', () => out.close(resolve))
      out.on('error', reject)
    })
    req.on('error', reject)
  })
}

function detectDevice() {
  if (WIN || process.platform === 'linux') {
    try {
      execFileSync('nvidia-smi', ['-L'], { stdio: 'pipe', windowsHide: true })
      return 'cuda'
    } catch {
      /* no NVIDIA GPU */
    }
  }
  if (process.platform === 'darwin' && process.arch === 'arm64') return 'mps'
  return 'cpu'
}

function pythonExe(env) {
  return WIN
    ? path.join(env.venvDir, 'Scripts', 'python.exe')
    : path.join(env.venvDir, 'bin', 'python')
}

async function ensureTools(env, onStatus) {
  const binDir = path.join(env.userData, 'bin')
  fs.mkdirSync(binDir, { recursive: true })
  const tools = {}

  // ffmpeg
  const ffName = WIN ? 'ffmpeg.exe' : 'ffmpeg'
  let ff = path.join(binDir, ffName)
  if (!fs.existsSync(ff)) {
    try {
      execFileSync(WIN ? 'where' : 'which', ['ffmpeg'], { stdio: 'pipe', windowsHide: true })
      ff = 'ffmpeg' // already on PATH
    } catch {
      if (WIN) {
        onStatus('Downloading ffmpeg…')
        const zip = path.join(binDir, 'ffmpeg.zip')
        await download(
          'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
          zip, onStatus)
        await run('powershell', ['-NoProfile', '-Command',
          `Expand-Archive -Force '${zip}' '${binDir}\\ffmpeg-x'; ` +
          `Copy-Item (Get-ChildItem '${binDir}\\ffmpeg-x' -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName '${ff}'; ` +
          `Remove-Item -Recurse -Force '${binDir}\\ffmpeg-x','${zip}'`])
      } else {
        onStatus('⚠ ffmpeg not found — install it (brew install ffmpeg) for MP3 export')
        ff = null
      }
    }
  }
  if (ff && ff !== 'ffmpeg') tools.MITY_FFMPEG_PATH = ff

  // FluidSynth
  const fsName = WIN ? 'fluidsynth.exe' : 'fluidsynth'
  let fsyn = path.join(binDir, 'fluidsynth', 'bin', fsName)
  if (!fs.existsSync(fsyn)) {
    try {
      execFileSync(WIN ? 'where' : 'which', ['fluidsynth'], { stdio: 'pipe', windowsHide: true })
      fsyn = 'fluidsynth'
    } catch {
      if (WIN) {
        onStatus('Downloading FluidSynth…')
        const zip = path.join(binDir, 'fluidsynth.zip')
        await download(
          'https://github.com/FluidSynth/fluidsynth/releases/download/v2.4.3/fluidsynth-2.4.3-win10-x64.zip',
          zip, onStatus)
        await run('powershell', ['-NoProfile', '-Command',
          `Expand-Archive -Force '${zip}' '${binDir}\\fluidsynth'; Remove-Item -Force '${zip}'`])
      } else {
        onStatus('⚠ FluidSynth not found — install it (brew install fluidsynth) for instrument rendering')
        fsyn = null
      }
    }
  }
  if (fsyn && fsyn !== 'fluidsynth') tools.MITY_FLUIDSYNTH_PATH = fsyn
  return tools
}

function seedWorkspace(env, onStatus) {
  const dirs = ['scores', 'soundfonts', 'samples', 'voices/recordings',
    'voices/profiles', 'projects', 'stems', 'midi', 'exports', 'analysis-cache']
  for (const d of dirs) fs.mkdirSync(path.join(env.workspace, d), { recursive: true })
  // seed a General MIDI soundfont so every instrument has a sound on day one
  const seedDir = path.join(env.resourcesPath || '', 'seed')
  if (fs.existsSync(seedDir)) {
    for (const f of fs.readdirSync(path.join(seedDir, 'soundfonts'))) {
      const dest = path.join(env.workspace, 'soundfonts', f)
      if (!fs.existsSync(dest)) {
        onStatus(`Adding starter soundfont ${f}…`)
        fs.copyFileSync(path.join(seedDir, 'soundfonts', f), dest)
      }
    }
  }
}

async function ensureEnvironment(opts) {
  const env = {
    dev: opts.dev,
    repoRoot: opts.repoRoot,
    resourcesPath: opts.resourcesPath,
    userData: opts.userData,
    workspace: opts.workspace,
    device: detectDevice(),
  }
  const onStatus = opts.onStatus

  onStatus(env.device === 'cuda'
    ? 'GPU found — fast voice training available'
    : env.device === 'mps'
      ? 'Apple Silicon detected — voice features use MPS (unverified) / CPU'
      : 'No dedicated GPU detected — voice training will be slow (CPU); everything else is unaffected')

  if (env.dev) {
    // dev shell: reuse the repo's venv, tools from PATH, UI from studio-ui/dist
    env.venvDir = path.join(env.repoRoot, 'apps', 'studio-api', '.venv')
    env.backendDir = path.join(env.repoRoot, 'apps', 'studio-api')
    env.uiDist = path.join(env.repoRoot, 'apps', 'studio-ui', 'dist')
    env.tools = {}
    env.python = pythonExe(env)
    return env
  }

  env.backendDir = path.join(env.resourcesPath, 'backend')
  env.uiDist = path.join(env.resourcesPath, 'ui')
  env.venvDir = path.join(env.userData, 'venv')
  env.python = pythonExe(env)

  const marker = path.join(env.venvDir, '.mity-core-ok')
  if (!fs.existsSync(marker)) {
    const bundledPython = WIN
      ? path.join(env.resourcesPath, 'python', 'python.exe')
      : path.join(env.resourcesPath, 'python', 'bin', 'python3')
    if (!fs.existsSync(bundledPython)) {
      throw new Error(`bundled Python runtime missing at ${bundledPython}`)
    }
    onStatus('First run: creating the Python environment…')
    await run(bundledPython, ['-m', 'venv', env.venvDir], {}, onStatus)
    onStatus('Installing the audio engine (a few minutes, first run only)…')
    await run(env.python, ['-m', 'pip', 'install', '--no-input', '-r',
      path.join(env.backendDir, 'requirements-core.txt')], {}, (l) => {
      if (/Collecting|Installing|Downloading/.test(l)) onStatus(l.slice(0, 70))
    })
    fs.writeFileSync(marker, new Date().toISOString())
  }

  env.tools = await ensureTools(env, onStatus)
  seedWorkspace(env, onStatus)
  return env
}

module.exports = { ensureEnvironment, detectDevice, run, download, pythonExe }
