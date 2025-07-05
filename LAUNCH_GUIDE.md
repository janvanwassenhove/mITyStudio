# mITyStudio Launch Scripts

This document describes the various launch scripts available for mITyStudio to ease development, testing, and deployment.

## Quick Start

### First Time Setup
Choose the setup script for your platform:

**Windows:**
```bash
setup.bat
```

**Linux/macOS:**
```bash
chmod +x *.sh
./setup.sh
```

### Launch Application
After setup, use the main launch script:

**Windows:**
```bash
start.bat
```

**Linux/macOS:**
```bash
./start.sh
```

## Available Scripts

### 🚀 Main Launch Scripts

#### `start.bat` / `start.sh`
**Purpose:** Main launch script for full development environment

**What it does:**
- Checks for Node.js and Python installation
- Installs missing dependencies automatically
- Creates Python virtual environment if needed
- Copies `.env.example` to `.env` if needed
- Starts both backend and frontend servers
- Opens separate terminal windows for each service

**Ports:**
- Frontend: http://localhost:5173
- Backend: http://localhost:5000

**Usage:**
```bash
# Windows
start.bat

# Linux/macOS
./start.sh
```

---

### 🔧 Development Scripts

#### `dev.bat` / `dev.sh`
**Purpose:** Development mode with enhanced features

**What it does:**
- Sets up development environment
- Enables Flask debug mode and auto-reload
- Starts frontend with Vite hot module replacement
- Optimized for development workflow

**Features:**
- Automatic code reloading
- Enhanced error messages
- Development-specific configurations

**Usage:**
```bash
# Windows
dev.bat

# Linux/macOS
./dev.sh
```

---

### 🏗️ Build Scripts

#### `build.bat`
**Purpose:** Production build preparation

**What it does:**
- Validates prerequisites
- Installs all dependencies
- Builds frontend for production (optimized bundle)
- Creates production requirements file
- Prepares backend for deployment

**Output:**
- Frontend build: `frontend/dist/`
- Production-ready backend with gunicorn

**Usage:**
```bash
build.bat
```

**Production deployment command:**
```bash
cd backend
venv\Scripts\activate
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

---

### 🖥️ Desktop App Scripts

#### `desktop.bat`
**Purpose:** Launch Electron desktop application

**What it does:**
- Checks if backend is running (starts if needed)
- Installs Electron dependencies if missing
- Launches the desktop application

**Requirements:**
- Backend must be running on port 5000
- Electron dependencies installed

**Usage:**
```bash
desktop.bat
```

---

### ⚙️ Setup Scripts

#### `setup.bat` / `setup.sh`
**Purpose:** Complete environment setup for new installations

**What it does:**
- Validates all prerequisites (Node.js, Python, Git)
- Installs all workspace dependencies
- Sets up Python virtual environment
- Creates basic `.env` file with default values
- Provides guidance for API key configuration

**Prerequisites checked:**
- Node.js (18.x or 20.x LTS recommended)
- Python (3.8+ recommended)
- Git (optional but recommended)

**Usage:**
```bash
# Windows
setup.bat

# Linux/macOS
chmod +x *.sh
./setup.sh
```

---

### 🔧 Helper Scripts

#### `status.bat`
**Purpose:** Check installation status and dependencies

**What it does:**
- Verifies Node.js and Python installation
- Checks all dependency installations
- Tests key Python packages
- Provides next steps for missing components

**Usage:**
```bash
status.bat
```

#### `install-backend.bat`
**Purpose:** Step-by-step Python backend setup

**What it does:**
- Creates Python virtual environment
- Installs dependencies one by one
- Handles common installation issues
- Provides fallbacks for optional packages

**Usage:**
```bash
install-backend.bat
```

#### `install-electron.bat`
**Purpose:** Robust Electron installation with timeout handling

**What it does:**
- Installs Electron with extended timeouts
- Uses fallback methods for slow connections
- Handles common Electron installation issues
- Verifies installation completion

**Usage:**
```bash
install-electron.bat
```

#### `fix-deps.bat`
**Purpose:** Fix existing dependency issues

**What it does:**
- Updates pip to latest version
- Reinstalls problematic packages
- Fixes version conflicts
- Updates frontend dependencies

**Usage:**
```bash
fix-deps.bat
```

#### `test-install.bat`
**Purpose:** Test installation completeness

**What it does:**
- Tests all major components
- Verifies package imports
- Checks environment configuration
- Provides troubleshooting guidance

**Usage:**
```bash
test-install.bat
```

## Project Structure

```
mITyStudio/
├── 📁 frontend/          # Vue.js frontend application
├── 📁 backend/           # Flask backend API
├── 📁 electron/          # Electron desktop app
├── 🚀 start.bat/sh       # Main launch script
├── 🔧 dev.bat/sh         # Development mode
├── 🏗️ build.bat          # Production build
├── 🖥️ desktop.bat        # Desktop app launcher
├── ⚙️ setup.bat/sh       # Initial setup
└── 📝 package.json       # Workspace configuration
```

## Configuration

### Environment Variables
Edit `backend/.env` with your API keys:

```env
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///mitystudio.db

# AI Service API Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_API_KEY=your-google-api-key
```

### API Key Sources
- **OpenAI:** https://platform.openai.com/
- **Anthropic:** https://console.anthropic.com/
- **Google:** https://console.cloud.google.com/

## Troubleshooting

### Common Issues

#### "Node.js not found"
**Solution:** Install Node.js from https://nodejs.org/
- Recommended: LTS version (18.x or 20.x)

#### "Python not found"
**Solution:** Install Python from https://python.org/
- Minimum version: 3.8
- Make sure to add Python to PATH during installation

#### "Permission denied" (Linux/macOS)
**Solution:** Make scripts executable:
```bash
chmod +x *.sh
```

#### Backend fails to start
**Solutions:**
1. Check if port 5000 is available
2. Verify `.env` file exists and has correct format
3. Ensure virtual environment is activated
4. Check Python dependencies are installed

#### Frontend fails to start
**Solutions:**
1. Check if port 5173 is available
2. Verify `node_modules` exists in frontend directory
3. Run `npm install` in frontend directory
4. Clear npm cache: `npm cache clean --force`

#### Electron installation hangs or times out
**Problem:** `npm install` in electron directory keeps spinning or times out
**Solutions:**
1. **Increase timeout and use different registry:**
   ```bash
   cd electron
   npm install --timeout=300000 --registry=https://registry.npmjs.org/
   ```

2. **Install Electron separately with verbose output:**
   ```bash
   cd electron
   npm install electron@22.3.27 --verbose
   npm install electron-builder --verbose
   npm install
   ```

3. **Clear npm cache and retry:**
   ```bash
   npm cache clean --force
   cd electron
   npm install
   ```

4. **Use alternative installation method:**
   ```bash
   cd electron
   npm install --no-optional
   npm install electron@22.3.27 --save-dev --no-optional
   ```

5. **Manual Electron installation (if all else fails):**
   ```bash
   cd electron
   npm init -y
   npm install electron@22.3.27 electron-builder@24.13.3 --save-dev
   npm install electron-serve@1.1.0 electron-store@8.1.0 node-fetch@3.3.0
   ```

#### "npm install" hangs in Electron directory
**Problem:** Running `cd electron && npm install` gets stuck and keeps spinning indefinitely.

**Solutions:**
1. **Use the helper script (recommended):**
   ```bash
   install-electron.bat
   ```

2. **Clear cache and retry:**
   ```bash
   npm cache clean --force
   cd electron
   npm install --verbose
   ```

3. **Use alternative registry:**
   ```bash
   cd electron
   npm config set electron_mirror https://npmmirror.com/mirrors/electron/
   npm install
   ```

4. **Install from workspace root:**
   ```bash
   # From the main mITyStudio directory
   npm install
   ```
   This works because of the npm workspaces configuration.

5. **If all else fails, manual Electron installation:**
   ```bash
   cd electron
   npm install electron@22.3.27 --save-dev --force
   npm install electron-serve electron-store node-fetch
   ```

#### Backend startup errors
**Problem:** Various backend startup issues

**Common Solutions:**

1. **SQLAlchemy metadata error:**
   ```
   sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved
   ```
   **Fix:** This is already resolved in the current codebase. If you see this, ensure you have the latest code.

2. **LangChain import errors:**
   ```
   ModuleNotFoundError: No module named 'langchain_community'
   ```
   **Fix:** Install missing LangChain packages:
   ```bash
   cd backend
   venv\Scripts\activate
   pip install langchain-community langchain-openai langchain-anthropic
   ```

3. **Cannot import create_app:**
   ```
   ImportError: cannot import name 'create_app' from 'app'
   ```
   **Fix:** This is resolved in the current codebase. The issue was a naming conflict between `app.py` and `app/` directory.

4. **Python path issues:**
   - Ensure you're in the backend directory when running commands
   - Activate the virtual environment before starting: `venv\Scripts\activate`
   - Check that the `.env` file exists in the backend directory

5. **Database initialization errors:**
   ```bash
   cd backend
   venv\Scripts\activate
   python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.models import create_tables; create_tables()"
   ```

## Project Maintenance

### Updating Dependencies
Regularly update dependencies to keep the project secure and efficient:

```bash
# Update frontend dependencies
cd frontend
npm update

# Update backend dependencies
cd ../backend
venv\Scripts\activate
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U
```

### Code Quality Checks
Ensure code quality and consistency:

```bash
# Check Python code style
flake8

# Check JavaScript/TypeScript code style
eslint

# Run tests
pytest
```

### Performance Optimization
Periodically profile and optimize the application:

```bash
# Profile Python application
python -m cProfile -o output.prof your_script.py

# Analyze frontend bundle size
cd frontend
npm run analyze
```

## Advanced Usage

### Custom Environment Setup
Create custom scripts by copying and modifying existing ones:

```bash
# Copy main script
cp start.bat my-custom-start.bat

# Modify ports, environment variables, etc.
```

### CI/CD Integration
Use `build.bat` in automated build pipelines:

```yaml
# Example GitHub Actions step
- name: Build mITyStudio
  run: build.bat
```

### Docker Development
Scripts work within Docker containers with proper volume mounts:

```dockerfile
COPY *.bat /app/
WORKDIR /app
CMD ["start.bat"]
```

## Support

For issues with launch scripts:
1. Check troubleshooting section above
2. Verify all prerequisites are installed
3. Check console output for specific error messages
4. Ensure all dependencies are up to date

For project-specific issues, refer to the main README.md file.

#### Electron app "ERR_FILE_NOT_FOUND" error
**Problem:** Electron app fails to load with `ERR_FILE_NOT_FOUND (-6) loading 'app://-/'`

**Cause:** The frontend hasn't been built for production yet, so the `frontend/dist` directory doesn't exist.

**Solution:**
```bash
# Build the frontend first
cd frontend
npm run build

# Or build without TypeScript checking if there are TS errors
npx vite build --mode development

# Then launch the desktop app
cd ../
desktop.bat
```

**Note:** The Electron app requires the built frontend files to serve the UI. The development server (frontend on port 5173) is separate from the Electron app.

#### Electron cache permission warnings
**Problem:** Electron shows cache-related error messages:
```
Unable to move the cache: Toegang geweigerd. (0x5)
Gpu Cache Creation failed: -2
```

**Solution:** These are harmless permission warnings and don't affect functionality. To resolve:
1. Run as administrator (not recommended for development)
2. Ignore the warnings (recommended - they don't impact the app)
3. Clear Electron cache: Delete `%APPDATA%/mITyStudio` folder
