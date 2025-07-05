# mITyStudio

A modern web application built with Vue 3, TypeScript, and Vite.

## Description

mITyStudio is a feature-rich platform designed to streamline your workflow with a fast, scalable, and maintainable codebase using the latest frontend technologies.

## Features

- Vue 3 with Composition API and `<script setup>`
- TypeScript for type safety
- Vite for lightning-fast development and builds
- Modular and scalable project structure

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
    }
  ],
  "duration": 32,                // Song duration in seconds
  "createdAt": "ISO string",     // Creation timestamp
  "updatedAt": "ISO string"      // Last update timestamp
}
```

- All fields are required unless marked as (Optional).
- The `tracks` array contains all tracks in the song, each with its own clips and settings.
- The `clips` array within each track contains audio or MIDI clips, with timing and instrument/sample info.
- Effects are represented as numeric values (typically 0–1).

This contract is used for project import/export and for direct editing in the Song Structure panel.

## Getting Started

### Prerequisites

- Node.js (v16 or higher recommended)
- npm or yarn

### Installation

```bash
git clone https://github.com/yourusername/mITyStudio.git
cd mITyStudio
npm install
```

### Running the Development Server

```bash
npm run dev
```

### Building for Production

```bash
npm run build
```

### Linting

```bash
npm run lint
```

## Contact

For questions or support, please contact mityjohn.com.
