# Enhanced Lyrics System in mITyStudio

## Overview

The mITyStudio AI Chat now features an enhanced lyrics creation and modification system that provides sophisticated support for vocal tracks with detailed linguistic and musical structure. When chatting with the AI agent, users can request lyrics creation and receive comprehensive JSON structures with syllable breakdowns, phonetic notation, and musical timing.

## Features

### 1. Enhanced JSON Structure for Lyrics

When the AI generates lyrics, it now includes:

- **Syllable Breakdown**: Detailed syllable mapping to musical notes
- **Phonetic Notation**: IPA (International Phonetic Alphabet) phonemes for pronunciation
- **Musical Timing**: Precise note durations and timing information
- **Multi-voice Support**: Support for harmony, backing vocals, and complex arrangements

### 2. Multiple Action Buttons for Lyrics

When the AI generates lyrics in the chat, three action buttons are now available:

#### 🎤 Add Vocal Track
- Creates a new vocal track in the timeline
- Adds all lyrical clips with their musical and timing data
- Preserves syllable breakdowns and phonetic information
- Perfect for creating playable vocal arrangements

#### 📝 Add to Lyrics Section  
- Extracts the text content from the lyrics JSON
- Adds it to the Song tab's lyrics section
- Useful for viewing and editing lyrics as text
- Maintains synchronization with the JSON structure

#### 🎵 Add Lyrics & Vocals (Legacy)
- Combines both vocal track creation and lyrics text addition
- Provides backward compatibility
- Handles complete lyrical integration

### 3. Enhanced AI Prompt Structure

The AI now generates lyrics using this comprehensive JSON format:

```json
{
  "id": "clip-lyrics-1",
  "trackId": "track-lyrics", 
  "startTime": 4,
  "duration": 2,
  "type": "lyrics",
  "instrument": "vocals",
  "volume": 0.8,
  "effects": { "reverb": 0, "delay": 0, "distortion": 0 },
  "voices": [
    {
      "voice_id": "soprano01",
      "lyrics": [
        {
          "text": "Shine",
          "notes": ["E4", "F4"],
          "start": 0.0,
          "durations": [0.4, 0.4],
          "syllables": [
            {
              "t": "Shine",
              "noteIdx": [0, 1],
              "dur": 0.8,
              "melisma": true
            }
          ],
          "phonemes": ["ʃ", "aɪ", "n"]
        }
      ]
    }
  ]
}
```

### 4. Song Structure Integration

The enhanced system seamlessly integrates with the existing song structure:

- **Lyrics Section**: Displays extracted text in the Song tab
- **JSON Structure**: Shows complete technical structure
- **Timeline Integration**: Vocal clips appear on the timeline with proper timing
- **Real-time Synchronization**: Changes in one view update all others

## Usage Instructions

### Creating Lyrics with AI

1. **Open AI Chat**: Click on the AI Chat tab in the right panel
2. **Request Lyrics**: Use prompts like:
   - "Generate full song lyrics with syllables and phonemes"
   - "Create verse and chorus lyrics with timing for 120 BPM"
   - "Write lyrics for a pop song with vocal harmonies"

3. **Choose Your Action**: When the AI responds with lyrics JSON:
   - Click **🎤 Add Vocal Track** to create a playable vocal track
   - Click **📝 Add to Lyrics Section** to add text to the lyrics panel
   - Click **🎵 Add Lyrics & Vocals** for complete integration

### Editing and Managing Lyrics

1. **In Song Tab**: 
   - Expand the "Lyrics" section to edit text
   - Changes automatically sync with JSON structure
   - View word count, line count, and character statistics

2. **In JSON Structure**:
   - Expand "JSON Structure" to see complete technical details
   - Edit syllable breakdowns, phonemes, and timing
   - Apply changes to update all vocal tracks

3. **In Timeline**:
   - Vocal clips appear with proper timing
   - Edit clip properties and effects
   - Modify volume, pan, and vocal effects

## Technical Details

### Syllable Structure
```json
{
  "t": "syllable_text",
  "noteIdx": [0, 1],
  "dur": 0.8,
  "melisma": true
}
```

- `t`: The syllable text
- `noteIdx`: Array of note indices this syllable spans
- `dur`: Duration of the syllable in beats
- `melisma`: Whether the syllable spans multiple notes

### Phoneme Notation
Uses standard IPA (International Phonetic Alphabet) symbols:
- `/aɪ/`: "I" sound (as in "shine")
- `/ɒ/`: "O" sound (as in "on")  
- `/ʃ/`: "SH" sound (as in "shine")
- `/n/`: "N" sound (as in "on")

### Voice IDs
Standard voice classifications:
- `soprano01`, `soprano02`: High female voices
- `alto01`, `alto02`: Low female voices  
- `tenor01`, `tenor02`: High male voices
- `bass01`, `bass02`: Low male voices

## Benefits

1. **Professional Workflow**: Supports complex vocal arrangements with precise timing
2. **Educational Value**: Shows phonetic breakdowns for pronunciation guidance
3. **Flexibility**: Multiple ways to integrate lyrics based on user needs
4. **Future-Proof**: Structure supports advanced TTS and vocal synthesis engines
5. **Synchronization**: Maintains consistency between text and musical elements

## Examples

### Simple Verse Creation
```
User: "Create a simple verse with timing for a pop song"
AI: [Generates JSON with syllables and phonemes]
Actions Available: 🎤 Add Vocal Track | 📝 Add to Lyrics Section | 🎵 Add Lyrics & Vocals
```

### Multi-Voice Harmony
```
User: "Generate backing vocals with harmony for the chorus"
AI: [Generates JSON with multiple voice parts]
Actions Available: 🎤 Add Vocal Track | 📝 Add to Lyrics Section | 🎵 Add Lyrics & Vocals
```

### Syllable-Specific Request
```
User: "Create lyrics with detailed syllable breakdown for vocal training"
AI: [Generates comprehensive JSON with detailed syllable mapping]
Actions Available: 🎤 Add Vocal Track | 📝 Add to Lyrics Section | 🎵 Add Lyrics & Vocals
```

This enhanced system provides professional-grade lyrics creation and management while maintaining the intuitive workflow that makes mITyStudio accessible to all users.