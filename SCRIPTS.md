# mITyStudio Launch Scripts Summary

## Available Scripts

### 🚀 **Quick Launch**
- **`start.bat`** (Windows) - Main launch script
- **`start.sh`** (Linux/macOS) - Main launch script  
- **`npm run quick-start`** (Cross-platform) - Uses appropriate script for your OS

### 🔧 **Development**
- **`dev.bat`** (Windows) - Development mode with auto-reload
- **`dev.sh`** (Linux/macOS) - Development mode with auto-reload
- **`npm run dev-mode`** (Cross-platform) - Uses appropriate script for your OS

### ⚙️ **Setup & Installation**
- **`setup.bat`** (Windows) - Complete environment setup
- **`setup.sh`** (Linux/macOS) - Complete environment setup
- **`npm run setup`** (Cross-platform) - Uses appropriate script for your OS

### 🏗️ **Build & Production**
- **`build.bat`** (Windows) - Production build
- **`npm run build`** (Cross-platform) - Standard build command

### 🖥️ **Desktop Application**
- **`desktop.bat`** (Windows) - Launch Electron desktop app
- **`npm run desktop`** (Cross-platform) - Launch desktop app

### 🧹 **Cleanup**
- **`cleanup.bat`** (Windows) - Reset development environment
- **`cleanup.sh`** (Linux/macOS) - Reset development environment
- **`npm run cleanup`** (Cross-platform) - Uses appropriate script for your OS

## First Time Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mITyStudio.git
   cd mITyStudio
   ```

2. **Run setup script**
   ```bash
   # Windows
   setup.bat
   
   # Linux/macOS
   chmod +x *.sh
   ./setup.sh
   
   # Cross-platform
   npm run setup
   ```

3. **Configure API keys**
   Edit `backend/.env` with your API keys:
   - OPENAI_API_KEY
   - ANTHROPIC_API_KEY
   - GOOGLE_API_KEY

4. **Launch application**
   ```bash
   # Windows
   start.bat
   
   # Linux/macOS  
   ./start.sh
   
   # Cross-platform
   npm run quick-start
   ```

## Daily Development Workflow

### Start Development
```bash
# For enhanced development experience
dev.bat        # Windows
./dev.sh       # Linux/macOS
npm run dev-mode  # Cross-platform
```

### Launch Desktop App
```bash
desktop.bat    # Windows
npm run desktop   # Cross-platform
```

### Build for Production
```bash
build.bat      # Windows
npm run build     # Cross-platform
```

### Clean Environment (if issues occur)
```bash
cleanup.bat    # Windows
./cleanup.sh   # Linux/macOS
npm run cleanup   # Cross-platform
```

## Ports & URLs

- **Frontend (Vite):** http://localhost:5173
- **Backend (Flask):** http://localhost:5000
- **Desktop App:** Electron window (uses backend on port 5000)

## Troubleshooting

### Prerequisites
- **Node.js:** 18.x or 20.x LTS
- **Python:** 3.8 or higher
- **Git:** Optional but recommended

### Common Issues
1. **Port conflicts:** Close other applications using ports 5000 or 5173
2. **Permission errors:** On Unix, run `chmod +x *.sh`
3. **Missing dependencies:** Run setup script again
4. **API key errors:** Check `backend/.env` configuration

### Getting Help
- See [LAUNCH_GUIDE.md](LAUNCH_GUIDE.md) for detailed documentation
- Check console output for specific error messages
- Ensure all prerequisites are properly installed

## Cross-Platform Notes

### Windows
- Use `.bat` files directly
- PowerShell and Command Prompt both supported
- Scripts open separate terminal windows

### Linux/macOS
- Use `.sh` files (make executable with `chmod +x *.sh`)
- Background processes managed automatically
- Use Ctrl+C to stop services

### Both Platforms
- NPM scripts (`npm run`) work everywhere
- Same functionality across all platforms
- Environment variables handled automatically
