# mITyStudio - Revolutionary AI Music Composition Studio

**Transform your musical ideas into professional compositions with the power of artificial intelligence.**

mITyStudio is a complete AI-powered music production suite that empowers musicians, producers, and creators to compose, arrange, and produce high-quality music with unprecedented ease and creativity.

## 🎵 Why Choose mITyStudio?

### **Create Music Like Never Before**
- **AI-Powered Composition**: Generate melodies, harmonies, and arrangements instantly
- **Intelligent Voice Synthesis**: Transform lyrics into professional vocal performances
- **Real-Time Collaboration**: Work with AI assistants that understand music theory
- **Professional Quality**: Studio-grade audio processing and effects

### **Perfect For Everyone**
- **Beginners**: No music theory required - let AI guide your creativity
- **Professionals**: Advanced tools for complex compositions and arrangements
- **Content Creators**: Quickly generate royalty-free music for videos and projects
- **Educators**: Teach music composition with interactive AI assistance

### **Key Benefits**
- ⚡ **10x Faster Composition**: Create complete songs in minutes, not hours
- 🎯 **Professional Results**: Industry-standard audio quality and mixing
- 🧠 **AI Learning**: The more you use it, the better it understands your style
- 💰 **Cost Effective**: Replace expensive studio time and session musicians
- 🌐 **Cross-Platform**: Works on Windows, Mac, and Linux

## 🚀 Get Started in 3 Simple Steps

### 1. **Quick Installation**
Download and run our one-click installer - no technical setup required!

**Windows:**
```bash
setup.bat
```

**Mac/Linux:**
```bash
./setup.sh
```

### 2. **Launch & Create**
Start the application and begin composing immediately:

```bash
start.bat    # Windows
./start.sh   # Mac/Linux
```

### 3. **Compose Your First Song**
- Choose a genre or mood
- Let AI generate a foundation
- Customize with your creative input
- Export professional-quality audio

## ✨ Powerful Features

### **AI-Powered Music Generation**
- **Smart Chord Progressions**: Generate harmonically rich progressions in any style
- **Melody Creation**: AI-composed melodies that fit your chord changes perfectly
- **Rhythm & Beats**: Intelligent drum patterns and rhythmic elements
- **Style Adaptation**: Create music in any genre from classical to electronic

### **Advanced Vocal Synthesis**
- **Natural Voice Generation**: Convert text to singing with realistic vocal performances
- **Multiple Voice Types**: Soprano, alto, tenor, bass - all professionally trained
- **Harmony Generation**: Automatic background vocals and harmonies
- **Phonetic Precision**: Advanced syllable mapping for perfect pronunciation

### **Professional Production Tools**
- **Real-Time Effects**: Reverb, delay, compression, and more
- **Multi-Track Mixing**: Professional mixing console with unlimited tracks
- **Audio Analysis**: AI-powered feedback on your mix and master
- **Export Options**: High-quality WAV, MP3, and more formats

### **Intelligent Song Structure**
- **Section Management**: Organize verses, choruses, and bridges effortlessly
- **Cross-Section Editing**: Seamlessly edit across song boundaries
- **Template Library**: Start with professional song structures
- **Visual Timeline**: See your entire composition at a glance

## 🎯 Perfect Use Cases

### **Music Producers**
- Quickly prototype song ideas
- Generate reference tracks for clients
- Create backing tracks and demos
- Explore new musical styles

### **Content Creators**
- Generate royalty-free background music
- Create custom themes and jingles
- Match music to video content mood
- Produce podcast intros and outros

### **Educators & Students**
- Interactive music theory learning
- Composition assignments and exercises
- Demonstrate musical concepts
- Create practice tracks

### **Songwriters**
- Overcome writer's block with AI inspiration
- Experiment with different arrangements
- Develop rough ideas into full songs
- Collaborate with AI co-writers

## 🏆 What Makes Us Different

### **Industry-Leading AI**
Built on cutting-edge language models and music AI research, mITyStudio understands music theory, composition techniques, and production best practices.

### **User-Friendly Design**
No steep learning curve - if you can hum a melody, you can create professional music with mITyStudio.

### **Constant Evolution**
Regular updates bring new AI capabilities, instruments, and features based on user feedback.

### **Professional Support**
Comprehensive documentation, tutorials, and community support to help you succeed.

## 💡 Quick Start Guide

### **New to Music Production?**
1. Choose a genre template
2. Let AI generate a basic structure
3. Add your lyrics or melody ideas
4. Customize the arrangement
5. Export your finished song

### **Experienced Producer?**
1. Import your existing project
2. Use AI for creative suggestions
3. Generate missing parts or variations
4. Fine-tune with professional tools
5. Export stems or final mix

## 🔧 System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, or Linux Ubuntu 18.04+
- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 2GB free space
- **Audio**: Audio interface or sound card recommended
- **Internet**: Required for AI features and updates

## 📞 Support & Community

- **Documentation**: Comprehensive guides and tutorials
- **Community Forum**: Connect with other creators
- **Video Tutorials**: Step-by-step learning resources
- **Email Support**: Direct technical assistance
- **Feature Requests**: Help shape the future of mITyStudio

---

## 🛠️ For Developers

<details>
<summary>Technical Documentation & Setup</summary>

# mITyStudio - AI-Powered Music Composition Studio

A complete monorepo structure for an AI-powered music composition and production studio, featuring a Vue.js frontend, Python Flask backend, and Electron desktop application.

## Features

- **Voice Training with WAV Format**: Automatic conversion to WAV format for optimal voice training quality
- **Advanced AI-powered music composition and voice synthesis**
- **Real-time audio processing and effects**
- **Extended Vocal Structure**: Syllable-level note mapping with IPA phonemes for precise vocal synthesis
- **Song Section Management**: Structured song organization with intro, verse, chorus sections
- **Cross-Boundary Clip Support**: Clips can span multiple song sections seamlessly
- **Melisma Detection**: Automatic detection and marking of extended vocal runs
- **Multi-Voice Harmony**: Support for multiple vocal tracks with stereo positioning

## Song Structure JSON Contract

The song structure is represented as a JSON object with the following schema:

```jsonc
{
  "id": "string",                // Unique song/project ID
  "name": "string",              // Song/project name
  "tempo": 120,                  // Tempo in BPM
  "timeSignature": [4, 4],       // Time signature as [beats per bar, note value]
  "key": "C",                    // Musical key (e.g., "C", "G", "Am")
  "structure": {                 // Song structure with sections
    "sections": [
      {
        "id": "sec-intro",       // Unique section ID
        "type": "intro",         // Section type (intro, verse, chorus, bridge, outro)
        "label": "Intro",        // Display label
        "startTime": 0.0,        // Start time in seconds
        "endTime": 8.0,          // End time in seconds
        "index": 1               // Section index for ordering
      },
      {
        "id": "sec-v1",
        "type": "verse",
        "label": "Verse 1",
        "startTime": 8.0,
        "endTime": 24.0,
        "index": 1
      },
      {
        "id": "sec-chorus",
        "type": "chorus",
        "label": "Chorus",
        "startTime": 24.0,
        "endTime": 40.0,
        "index": 1
      }
    ]
  },
  "tracks": [                    // Array of track objects
    {
      "id": "string",            // Unique track ID
      "name": "string",          // Track name
      "instrument": "string",    // Instrument type (e.g., "piano", "drums")
      "category": "string",      // Instrument category (keyboards, strings, etc.)
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
          "type": "synth",       // "synth", "sample", or "lyrics"
          "instrument": "string",// Instrument or sample name
          "notes": ["C4"],       // (Optional) Array of note names
          "sampleUrl": "string", // (Optional) URL for sample
          "volume": 1.0,         // Clip volume
          "effects": {           // Clip effects
            "reverb": 0,
            "delay": 0,
            "distortion": 0,
            "pitchShift": 0,
            "chorus": 0,
            "filter": 0,
            "bitcrush": 0
          },
          "waveform": []         // (Optional) Array of waveform data
        }
      ],
      "effects": {               // Track effects
        "reverb": 0,
        "delay": 0,
        "distortion": 0,
        "pitchShift": 0,
        "chorus": 0,
        "filter": 0,
        "bitcrush": 0
      },
      "sampleUrl": "string",     // (Optional) URL for track sample
      "isSample": false          // (Optional) Is this a sample track
    },
    {
      "id": "track-soprano",
      "name": "Soprano Voice",
      "instrument": "vocals",
      "category": "vocals",
      "voiceId": "soprano01",    // Voice identifier for this track
      "volume": 0.8,
      "pan": -0.2,               // Slight left pan for separation
      "muted": false,
      "solo": false,
      "clips": [                 // Voice clips for this specific voice
        {
          "id": "clip-v1-soprano-a",
          "trackId": "track-soprano",
          "type": "lyrics",      // Clip type
          "sectionId": "sec-v1", // Section reference for visualization
          "startTime": 8.0,      // Start time in seconds
          "duration": 4.0,       // Duration in seconds
          "voiceId": "soprano01", // Voice for this clip (matches track voiceId)
          "lyrics": [            // Extended lyrics structure
            {
              "text": "Shine bright like a diamond",   // Lyric text fragment
              "start": 0.0,      // Start time relative to clip (seconds)
              "notes": ["E4", "F4", "G4", "A4", "B4"], // Notes for this fragment
              "durations": [0.3, 0.3, 0.4, 0.5, 0.5], // Duration for each note (seconds)
              "syllables": [     // Syllable breakdown with note mapping
                {"t": "Shine", "noteIdx": [0], "dur": 0.3},
                {"t": "bright", "noteIdx": [1], "dur": 0.3},
                {"t": "like", "noteIdx": [2], "dur": 0.4},
                {"t": "a", "noteIdx": [3], "dur": 0.5},
                {"t": "dia-mond", "noteIdx": [4], "dur": 0.5, "melisma": true}
              ],
              "phonemes": ["ʃ", "aɪ", "n", " ", "b", "r", "aɪ", "t", " ", "l", "aɪ", "k", " ", "ɑ", " ", "d", "aɪ", "ɑ", "m", "ə", "n", "d"]
            }
          ],
          "tags": ["lead"],      // Flexible tags: lead, harmony, choir, adlib
          "volume": 0.8,
          "effects": { "reverb": 0.2, "delay": 0, "distortion": 0 }
        }
      ],
      "effects": { "reverb": 0.2, "delay": 0, "distortion": 0 }
    },
    {
      "id": "track-alto",
      "name": "Alto Voice",
      "instrument": "vocals",
      "category": "vocals",
      "voiceId": "alto01",       // Voice identifier for this track
      "volume": 0.7,
      "pan": 0.2,                // Slight right pan for separation
      "muted": false,
      "solo": false,
      "clips": [                 // Voice clips for this specific voice
        {
          "id": "clip-v1-alto-a",
          "trackId": "track-alto",
          "type": "lyrics",      // Clip type
          "sectionId": "sec-v1", // Section reference
          "startTime": 10.0,     // Slightly offset start for harmony
          "duration": 6.0,       // Duration in seconds
          "voiceId": "alto01",   // Voice for this clip (matches track voiceId)
          "lyrics": [            // Extended lyrics structure
            {
              "text": "So shine tonight",
              "start": 0.0,      // Start time relative to clip
              "notes": ["C4", "D4", "E4", "F4"],
              "durations": [0.5, 0.5, 0.5, 1.5],
              "syllables": [     // Syllable breakdown
                {"t": "So", "noteIdx": [0], "dur": 0.5},
                {"t": "shine", "noteIdx": [1], "dur": 0.5},
                {"t": "to-", "noteIdx": [2], "dur": 0.5},
                {"t": "night", "noteIdx": [3], "dur": 1.5, "melisma": true}
              ],
              "phonemes": ["s", "oʊ", " ", "ʃ", "aɪ", "n", " ", "t", "ə", "n", "aɪ", "t"]
            }
          ],
          "tags": ["harmony"],   // Harmony voice
          "sectionSpans": [      // For clips crossing section boundaries
            {"sectionId": "sec-v1", "startOffset": 2.0, "duration": 4.0},
            {"sectionId": "sec-chorus", "startOffset": 0.0, "duration": 2.0}
          ],
          "volume": 0.7,
          "effects": { "reverb": 0.1, "delay": 0, "distortion": 0 }
        }
      ],
      "effects": { "reverb": 0.1, "delay": 0, "distortion": 0 }
    }
  ],
  "duration": 40.0,              // Song duration in seconds
  "createdAt": "ISO string",     // Creation timestamp
  "updatedAt": "ISO string",     // Last update timestamp
  "lyrics": "Shine bright like a diamond\nSo shine tonight"
}
```

### Extended Features

- **Song Structure**: The `structure` object contains sections that define the song layout (intro, verse, chorus, etc.)
- **Syllable Mapping**: Each lyric fragment includes a `syllables` array that maps syllables to specific notes with timing
- **IPA Phonemes**: The `phonemes` array contains International Phonetic Alphabet symbols for TTS/singing engines
- **Section References**: Clips include `sectionId` to reference song structure sections
- **Section Spans**: For clips crossing section boundaries, use `sectionSpans` to define timing within each section
- **Flexible Tags**: Vocal clips support `tags` array for classification (lead, harmony, choir, adlib)
- **Melisma Support**: Syllables can be marked with `melisma: true` for extended vocal runs
- **Enhanced Effects**: Extended effects support including pitchShift, chorus, filter, and bitcrush

### Key Rules

- All fields are required unless marked as (Optional).
- The `tracks` array contains all tracks in the song, each with its own clips and settings.
- The `clips` array within each track contains audio, MIDI, or lyrics clips, with timing and instrument/sample info.
- Each voice has its own dedicated track with `instrument: "vocals"` and a `voiceId` field to identify the specific voice.
- Vocal tracks contain clips with `type: "lyrics"` that hold the lyrics and musical information for that specific voice.
- Each lyrics clip contains a `lyrics` array with text fragments, notes, timing, syllables, and phonemes for that voice only.
- Use `duration` for single notes or `durations` array for multiple notes in a lyric fragment.
- Multiple voice tracks can be synchronized by adjusting their `startTime` and using appropriate `pan` values for stereo separation.
- The `voiceId` field on both tracks and clips ensures consistency and allows for voice-specific processing.
- Effects are represented as numeric values (typically 0–1) and can be applied per track or per clip.
- Section structure helps with visualization and navigation within the song timeline.

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

**Ready to revolutionize your music creation process?**

[Download mITyStudio](#) | [Watch Demo](#) | [Join Community](#)

*Transform your musical vision into reality with AI-powered composition tools that understand creativity.*
