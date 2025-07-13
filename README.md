# mITyStudio - AI-Powered Music Composition Studio

A complete monorepo structure for an AI-powered music composition and production studio, featuring a Vue.js frontend, Python Flask backend, and Electron desktop application.

## Features

- Vue 3 with Composition API and `<script setup>`
- TypeScript for type safety
- Vite for lightning-fast development and builds
- Modular and scalable project structure
- **Voice Training with WAV Format**: Automatic conversion to WAV format for optimal voice training quality
- Advanced AI-powered music composition and voice synthesis
- Real-time audio processing and effects

## Song Structure JSON Contract

The song structure is represented as a JSON object with the following schema:

```jsonc
{
  "id": "string",                // Unique song/project ID
  "name": "string",              // Song/project name
  "tempo": 120,                  // Tempo in BPM
  "timeSignature": [4, 4],       // Time signature as [beats per bar, note value]
  "key": "C",                    // Musical key (e.g., "C", "G", "Am")
  "tracks": [                    // Array of track objects
    {
      "id": "string",            // Unique track ID
      "name": "string",          // Track name
      "instrument": "string",    // Instrument type (e.g., "piano", "drums")
      "volume": 0.8,             // Track volume (0.0 - 1.0)
      "pan": 0,                  // Stereo pan (-1.0 left to 1.0 right)
      "muted": false,            // Mute state
      "solo": false,             // Solo state
      "clips": [                 // Array of audio/midi clips
        {
          "id": "string",        // Unique clip ID
          "trackId": "string",   // Parent track ID
          "startTime": 0,        // Start time in seconds
          "duration": 4,         // Duration in seconds
          "type": "synth",       // "synth" or "sample"
          "instrument": "string",// Instrument or sample name
          "notes": ["C4"],       // (Optional) Array of note names
          "sampleUrl": "string", // (Optional) URL for sample
          "volume": 1.0,         // Clip volume
          "effects": {           // Clip effects
            "reverb": 0,
            "delay": 0,
            "distortion": 0
          },
          "waveform": []         // (Optional) Array of waveform data
        }
      ],
      "effects": {               // Track effects
        "reverb": 0,
        "delay": 0,
        "distortion": 0
      },
      "sampleUrl": "string",     // (Optional) URL for track sample
      "isSample": false          // (Optional) Is this a sample track
    },
    {
      "id": "track-lyrics",
      "name": "Lyrics & Vocals",
      "instrument": "vocals",
      "category": "vocals",
      "volume": 0.8,
      "pan": 0,
      "muted": false,
      "solo": false,
      "clips": [                 // Lyrics clips
        {
          "id": "clip-lyrics-1",
          "trackId": "track-lyrics",
          "startTime": 4,        // Start time in seconds
          "duration": 2,         // Duration in seconds
          "type": "lyrics",      // Clip type
          "instrument": "vocals",
          "volume": 0.8,
          "effects": { "reverb": 0, "delay": 0, "distortion": 0 },
          "voices": [            // (Optional) Advanced multi-voice structure
            {
              "voice_id": "soprano01",     // Voice identifier
              "lyrics": [
                {
                  "text": "Shine",         // Lyric text fragment
                  "notes": ["E4", "F4"],   // Notes for this fragment
                  "start": 0.0,            // Start time relative to clip (seconds)
                  "durations": [0.4, 0.4]  // Duration for each note (seconds)
                },
                {
                  "text": "on",
                  "notes": ["G4"],
                  "start": 1.0,
                  "duration": 0.6          // Single duration for single note
                }
              ]
            },
            {
              "voice_id": "bass01",
              "lyrics": [
                {
                  "text": "You",
                  "notes": ["C3"],
                  "start": 0.5,
                  "duration": 0.6
                },
                {
                  "text": "and",
                  "notes": ["D3", "E3"],
                  "start": 1.3,
                  "durations": [0.4, 0.5]
                }
              ]
            }
          ]
        }
      ],
      "effects": { "reverb": 0, "delay": 0, "distortion": 0 }
    }
  ],
  "duration": 32,                // Song duration in seconds
  "createdAt": "ISO string",     // Creation timestamp
  "updatedAt": "ISO string"      // Last update timestamp
}
```

- All fields are required unless marked as (Optional).
- The `tracks` array contains all tracks in the song, each with its own clips and settings.
- The `clips` array within each track contains audio, MIDI, or lyrics clips, with timing and instrument/sample info.
- Lyrics are stored as clips within a dedicated "Lyrics & Vocals" track with `type: "lyrics"`.
- For simple vocal arrangements, use the basic `text`, `notes`, and `chordName` fields within the clip.
- For advanced vocal arrangements, use the `voices` array within lyrics clips to define multiple voice parts with precise timing, pitch, and text mapping (do not use the basic fields when using `voices`).
- Each voice in the `voices` array can have multiple lyric fragments with individual note sequences and timing.
- Use `duration` for single notes or `durations` array for multiple notes in a lyric fragment.
- Effects are represented as numeric values (typically 0–1).

This contract is used for project import/export and for direct editing in the Song Structure panel.

## Getting Started

### Prerequisites

- Node.js (v16 or higher recommended)
- npm or yarn

## Quick Start

### First Time Setup

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

**Windows:**
```bash
start.bat
```

**Linux/macOS:**
```bash
./start.sh
```

### Available Launch Scripts

- **`start.bat`/`start.sh`** - Main launch script (full environment)
- **`dev.bat`/`dev.sh`** - Development mode with auto-reload
- **`desktop.bat`** - Launch Electron desktop app
- **`build.bat`** - Production build
- **`setup.bat`/`setup.sh`** - First-time environment setup

📖 **See [LAUNCH_GUIDE.md](LAUNCH_GUIDE.md) for detailed script documentation**

### Manual Installation

```bash
git clone https://github.com/yourusername/mITyStudio.git
cd mITyStudio

# Install all dependencies
npm run install:all

# Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys
```

### Manual Development Server

```bash
# Start backend
cd backend && source venv/bin/activate && python run.py

# Start frontend (in new terminal)
cd frontend && npm run dev
```

### Manual Production Build

```bash
npm run build

### Linting

```bash
npm run lint
```

## Contact

For questions or support, please contact mityjohn.com.

## 🏗️ Project Structure

```
mITyStudio/
├── frontend/           # Vue.js application
│   ├── src/
│   │   ├── components/ # Vue components
│   │   ├── stores/     # Pinia state management
│   │   ├── assets/     # Static assets
│   │   └── utils/      # Utility functions
│   ├── public/         # Public assets
│   ├── package.json    # Frontend dependencies
│   └── vite.config.ts  # Vite configuration
├── backend/            # Python Flask API
│   ├── app/
│   │   ├── api/        # API routes
│   │   ├── services/   # Business logic
│   │   ├── models/     # Database models
│   │   └── utils/      # Backend utilities
│   ├── requirements.txt # Python dependencies
│   ├── app.py          # Flask application
│   └── run.py          # Development server
├── electron/           # Electron desktop app
│   ├── main.js         # Main process
│   ├── preload.js      # Preload script
│   └── package.json    # Electron dependencies
├── package.json        # Root package.json (monorepo)
└── README.md           # This file
```

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.8+ and pip
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd mITyStudio
   ```

2. **Install all dependencies:**
   ```bash
   npm run install:all
   ```

3. **Set up environment variables:**
   ```bash
   # Copy the example environment file
   cp backend/.env.example backend/.env
   
   # Edit the .env file with your API keys
   # Add your OpenAI, Anthropic, and Google API keys
   ```

### Development

#### Option 1: Run Frontend and Backend Separately

1. **Start the backend:**
   ```bash
   cd backend
   python run.py
   ```
   The backend will run on `http://localhost:5000`

2. **Start the frontend (in a new terminal):**
   ```bash
   cd frontend
   npm run dev
   ```
   The frontend will run on `http://localhost:5173`

#### Option 2: Run Both with Concurrent Scripts

```bash
npm run dev
```

#### Option 3: Run as Electron Desktop App

```bash
npm run start:electron
```

## 🧩 Architecture

### Frontend (Vue.js)

- **Framework:** Vue 3 with Composition API
- **State Management:** Pinia
- **Build Tool:** Vite
- **Styling:** CSS3 with CSS Variables
- **Audio:** Tone.js for audio synthesis and playback
- **UI Components:** Custom components with Lucide icons

### Backend (Python Flask)

- **Framework:** Flask with Blueprint architecture
- **AI Integration:** LangChain for advanced AI interactions
- **Audio Processing:** librosa, soundfile, pydub
- **Database:** SQLAlchemy (SQLite default, configurable)
- **Authentication:** Flask-JWT-Extended
- **API Documentation:** RESTful API design

### Desktop App (Electron)

- **Framework:** Electron 22+
- **Architecture:** Main process + renderer process
- **Security:** Context isolation enabled
- **File Handling:** Native file dialogs
- **System Integration:** Menu bar, notifications

## 🤖 AI Features

### Chat Assistant
- Multi-provider support (OpenAI, Anthropic, Google)
- Context-aware music composition advice
- Actionable suggestions with direct integration

### Music Generation
- Chord progression generation
- Melody creation
- Drum pattern suggestions
- Instrument recommendations

### Audio Analysis
- Tempo detection
- Key analysis
- Frequency spectrum analysis
- Mix feedback

## 🔐 Environment Configuration

Create a `.env` file in the backend directory:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# AI Service API Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_API_KEY=your-google-api-key

# Database
DATABASE_URL=sqlite:///mitystudio.db

# File Upload
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
```

## 📦 Development Scripts

### Root Level Scripts

- `npm run dev` - Start both frontend and backend
- `npm run build` - Build all components
- `npm run install:all` - Install all dependencies
- `npm run clean` - Clean all build artifacts
- `npm run start:electron` - Run Electron app

### Frontend Scripts

- `npm run dev` - Start Vite dev server
- `npm run build` - Build for production
- `npm run preview` - Preview production build

### Backend Scripts

- `python run.py` - Start Flask development server
- `pip install -r requirements.txt` - Install Python dependencies

### Electron Scripts

- `npm start` - Run Electron app
- `npm run build` - Build desktop application

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

**Happy Music Making! 🎵**
