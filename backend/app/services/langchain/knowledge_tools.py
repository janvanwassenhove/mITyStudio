"""
mITyStudio Knowledge Tools
Provides comprehensive information about mITyStudio features, workflows, and best practices
"""

from langchain.tools import tool
from typing import Dict, List, Any

@tool
def get_mitystudio_features() -> str:
    """Get comprehensive information about mITyStudio features and capabilities"""
    return """
    mITyStudio is an AI-powered music composition studio with these key features:
    
    CORE COMPONENTS:
    - Timeline Editor: Visual arrangement of musical elements in time
    - Track Controls: Individual track management (volume, pan, effects, mute, solo)
    - Playback Controls: Play/pause/stop with BPM and key controls
    - Sample Library: Organized by categories (keyboards, strings, percussion, vocals, etc.)
    - AI Chat Assistant: Context-aware music composition help using React Agent
    - JSON Structure Panel: Advanced editing for precise control
    
    AUDIO ENGINE:
    - Built on Tone.js for real-time web audio synthesis
    - Support for multiple audio formats (WAV, MP3, OGG)
    - Real-time effects processing (reverb, delay, distortion)
    - Multi-track mixing and panning
    - Voice synthesis for lyrics with precise timing
    
    WORKFLOW STAGES:
    1. Create tracks with specific instruments from sample library
    2. Add clips to tracks with timing, effects, and musical content
    3. Arrange clips on the visual timeline
    4. Apply mixing, effects, and volume balancing
    5. Export projects or save for later editing
    
    SUPPORTED CONTENT TYPES:
    - Synthesized instruments (synth-pad, synth-lead, synth-bass)
    - Sample-based instruments (piano, guitar, drums, strings)
    - Vocals with AI-generated lyrics and timing
    - Chord progressions and harmonic structures
    - Multiple voice arrangements (soprano, alto, tenor, bass)
    
    AI CAPABILITIES:
    - Intelligent chord progression generation
    - Lyric creation with proper musical timing
    - Arrangement suggestions and best practices
    - Troubleshooting and workflow guidance
    - Context-aware composition assistance
    """

@tool
def get_workspace_layout_help() -> str:
    """Explain mITyStudio's workspace layout and navigation"""
    return """
    mITyStudio Workspace Layout:
    
    LEFT PANEL - Track Controls:
    - Track list showing all project tracks
    - Volume sliders (0.0 to 1.0) for each track
    - Pan controls (-1.0 left to 1.0 right)
    - Mute/Solo buttons for isolation
    - Add Track button with instrument selection
    - Track deletion and renaming options
    
    CENTER PANEL - Main Workspace:
    TOP: Playback Controls
    - Play/Pause/Stop buttons
    - BPM control (typical range 60-200)
    - Key selection (C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
    - Master volume control
    
    MAIN: Timeline Editor
    - Visual representation of all tracks and clips
    - Horizontal timeline showing bars/beats
    - Drag-and-drop clip arrangement
    - Zoom controls for precision editing
    - Clip selection and editing
    
    RIGHT PANEL - Tools & AI:
    - AI Chat Assistant for composition help
    - Sample Library browser with categories
    - Clip Configuration panel for selected clips
    - JSON Structure panel for advanced editing
    - Effects and mixing controls
    
    NAVIGATION TIPS:
    - Click tracks to select and configure
    - Drag clips to rearrange timing
    - Use right panel to browse instruments
    - Ask AI assistant for specific help
    - Check JSON panel for technical details
    """

@tool
def get_common_workflows() -> str:
    """Describe common workflows and best practices in mITyStudio"""
    return """
    Common mITyStudio Workflows:
    
    1. STARTING A NEW COMPOSITION:
    - Set desired tempo (BPM) and musical key
    - Add percussion/drum track first for rhythmic foundation
    - Add bass track (bass guitar, synth-bass) for harmonic foundation
    - Layer melody instruments (piano, synth-lead, guitar)
    - Add vocals/lyrics as final layer
    
    2. BUILDING SONG ARRANGEMENTS:
    - Start with simple 4-8 bar patterns
    - Use AI to generate chord progressions in your chosen key
    - Create distinct sections: intro, verse, chorus, bridge, outro
    - Vary instrumentation between sections for dynamics
    - Use clip durations to create musical phrases
    
    3. MIXING BEST PRACTICES:
    Volume Levels:
    - Drums/Percussion: 0.8-1.0 (prominent rhythm)
    - Bass: 0.7-0.9 (strong foundation)
    - Lead instruments: 0.6-0.8 (balanced presence)
    - Vocals: 0.8-1.0 (prominent and clear)
    - Background/pad instruments: 0.4-0.6 (subtle support)
    
    Panning Strategy:
    - Drums/Bass: Center (0.0)
    - Lead vocals: Center (0.0)
    - Piano: Slight left (-0.2)
    - Guitar: Slight right (0.2)
    - Strings: Spread wide (-0.6 to 0.6)
    
    4. USING AI ASSISTANT EFFECTIVELY:
    - Ask for specific musical help: "add bass line in G major"
    - Request chord progressions: "suggest jazz chord progression"
    - Get arrangement advice: "how to structure a pop ballad"
    - Generate lyrics with timing: "create verse lyrics with note timing"
    - Troubleshoot issues: "audio not playing, help debug"
    
    5. LYRICS AND VOCALS:
    - Use AI to generate lyrics with precise musical timing
    - Choose appropriate voice types (soprano, alto, tenor, bass)
    - Set proper note durations to match syllable timing
    - Use multiple voices for harmonies and choir effects
    - Balance vocal volume against instrumental tracks
    
    6. TROUBLESHOOTING COMMON ISSUES:
    - No audio: Check browser audio permissions and master volume
    - Clips not playing: Verify track is not muted and has proper timing
    - Browser console: Type audioTest() for comprehensive diagnostics
    - Audio initialization: Welcome dialog handles proper setup
    - Performance: Limit simultaneous tracks and effects for smooth playback
    """

@tool
def explain_json_structure() -> str:
    """Explain mITyStudio's JSON song structure in detail"""
    return """
    mITyStudio JSON Song Structure:
    
    TOP-LEVEL SONG STRUCTURE:
    {
      "name": "My Song Title",
      "tempo": 120,              // BPM (beats per minute)
      "key": "C",               // Musical key (C, C#, D, etc.)
      "duration": 32,           // Total song length in bars
      "tracks": [...],          // Array of track objects
      "updatedAt": "timestamp"  // Last modification time
    }
    
    TRACK STRUCTURE:
    {
      "id": "unique-track-id",     // UUID or descriptive ID
      "name": "Track Name",        // Display name
      "instrument": "piano",       // Must match available instruments
      "category": "keyboards",     // Instrument category
      "volume": 0.8,              // 0.0 (silent) to 1.0 (full)
      "pan": 0,                   // -1.0 (left) to 1.0 (right)
      "muted": false,             // Track mute state
      "solo": false,              // Track solo state
      "clips": [...],             // Array of clip objects
      "effects": {                // Track-level effects
        "reverb": 0,              // 0.0 to 1.0
        "delay": 0,               // 0.0 to 1.0
        "distortion": 0           // 0.0 to 1.0
      }
    }
    
    STANDARD CLIP STRUCTURE:
    {
      "id": "unique-clip-id",
      "trackId": "parent-track-id",
      "startTime": 0,             // Start position in bars
      "duration": 4,              // Length in bars
      "type": "synth",            // synth, sample, lyrics
      "instrument": "piano",      // Must match track instrument
      "volume": 0.8,              // Clip-specific volume
      "effects": {                // Clip-specific effects
        "reverb": 0,
        "delay": 0,
        "distortion": 0
      }
      // Additional properties based on clip type...
    }
    
    SYNTH CLIPS (Additional Properties):
    {
      "notes": ["C4", "E4", "G4"], // Array of note names
      "sampleDuration": 2,          // Duration per note in bars
      // ... standard clip properties
    }
    
    LYRICS CLIPS (CRITICAL STRUCTURE):
    {
      "type": "lyrics",
      "instrument": "vocals",
      "voices": [                   // REQUIRED: Multi-voice array
        {
          "voice_id": "soprano01",  // Use: soprano01, alto01, tenor01, bass01
          "lyrics": [               // Array of lyric fragments
            {
              "text": "mitystudio forever in our hearts", // Lyric text
              "notes": ["C4", "D4"],  // Corresponding notes
              "start": 0.0,           // Start time within clip (seconds)
              "durations": [0.5, 0.5] // Duration per note (for multiple notes)
            },
            {
              "text": "today",
              "notes": ["E4"],
              "start": 1.0,
              "duration": 1.0         // Single duration (for single note)
            }
          ]
        }
      ]
    }
    
    IMPORTANT RULES:
    - All IDs must be unique within their scope
    - Instruments must exist in the sample library
    - Voice IDs must be valid: soprano01, alto01, tenor01, bass01
    - Times and durations use bars for clips, seconds for lyrics timing
    - Effects values range from 0.0 to 1.0
    - For lyrics: use "duration" for single notes, "durations" for multiple notes
    - All JSON must be valid and properly structured
    """

@tool
def get_audio_troubleshooting_guide() -> str:
    """Provide comprehensive audio troubleshooting guidance for mITyStudio"""
    return """
    mITyStudio Audio Troubleshooting Guide:
    
    COMMON ISSUES & SOLUTIONS:
    
    1. NO AUDIO PLAYBACK:
    - Check browser audio permissions (allow audio)
    - Verify master volume is above 0
    - Ensure audio context is running (Welcome dialog initializes this)
    - Check individual track volumes and mute states
    - Try browser console command: audioTest()
    
    2. AUDIO INITIALIZATION FAILED:
    - Refresh the page and go through Welcome dialog
    - Check browser compatibility (Chrome/Firefox recommended)
    - Disable browser audio blocking extensions
    - Try clicking in the browser window before playing (user gesture required)
    
    3. CLIPS NOT PLAYING:
    - Verify clip timing (startTime and duration)
    - Check track is not muted or solo'd incorrectly
    - Ensure instrument exists in sample library
    - Validate clip JSON structure
    - Check clip volume settings
    
    4. PERFORMANCE ISSUES:
    - Reduce number of simultaneous tracks
    - Lower effect levels (reverb, delay)
    - Close other browser tabs using audio
    - Check system audio latency settings
    - Use shorter clip durations for complex arrangements
    
    5. LYRICS NOT PLAYING:
    - Verify voice_id exists (soprano01, alto01, tenor01, bass01)
    - Check lyrics JSON structure follows exact format
    - Ensure proper timing (start and duration/durations)
    - Validate note names (C4, D#4, etc.)
    - Check vocal track volume and effects
    
    DIAGNOSTIC COMMANDS:
    Browser Console → audioTest()
    This will:
    - Check audio system state
    - Initialize audio if needed
    - Create test track with synth
    - Play test sounds
    - Provide detailed diagnostic information
    
    BROWSER REQUIREMENTS:
    - Modern browser with Web Audio API support
    - Chrome 66+ or Firefox 60+ recommended
    - Audio permissions enabled
    - No aggressive ad-blockers blocking audio
    
    SYSTEM AUDIO:
    - Check system volume and audio output device
    - Ensure no other applications monopolizing audio
    - Test with simple system sounds first
    - Verify headphones/speakers working properly
    
    DEVELOPMENT MODE:
    - Check browser developer console for errors
    - Look for Tone.js initialization messages
    - Verify network requests for sample loading
    - Check for JavaScript errors during playback
    
    If issues persist, use the AI assistant for specific problem diagnosis!
    """

@tool
def get_instrument_guide() -> str:
    """Provide detailed information about mITyStudio's instrument system"""
    return """
    mITyStudio Instrument Guide:
    
    INSTRUMENT CATEGORIES:
    
    KEYBOARDS:
    - piano: Acoustic piano samples
    - electric-piano: Electric piano sounds
    - organ: Hammond organ style
    - synth-pad: Warm synthesizer pads
    - synth-lead: Lead synthesizer sounds
    
    STRINGS:
    - violin: Solo violin samples
    - cello: Solo cello samples
    - string-ensemble: Full string section
    - guitar-acoustic: Acoustic guitar
    - guitar-electric: Electric guitar
    - bass-guitar: Electric bass guitar
    - synth-bass: Synthesized bass sounds
    
    PERCUSSION:
    - drum-kit: Complete drum kit
    - kick: Kick drum samples
    - snare: Snare drum samples
    - hihat: Hi-hat samples
    - crash: Crash cymbal
    - tambourine: Tambourine samples
    
    VOCAL:
    - vocals: Human voice samples
    - soprano01: High female voice (AI synthesis)
    - alto01: Lower female voice (AI synthesis)
    - tenor01: High male voice (AI synthesis)
    - bass01: Low male voice (AI synthesis)
    
    WOODWINDS:
    - flute: Flute samples
    - clarinet: Clarinet samples
    - saxophone: Saxophone samples
    
    BRASS:
    - trumpet: Trumpet samples
    - trombone: Trombone samples
    - french-horn: French horn samples
    
    USAGE GUIDELINES:
    
    1. INSTRUMENT SELECTION:
    - Use get_available_instruments() to see current library
    - Match instrument names exactly as they appear
    - Consider musical context and genre
    - Balance instruments across frequency ranges
    
    2. TRACK ASSIGNMENT:
    - One instrument per track for clarity
    - Use multiple tracks for layering
    - Group similar instruments (string section)
    - Separate lead and rhythm instruments
    
    3. MUSICAL ARRANGEMENT:
    - Low frequency: bass-guitar, synth-bass, kick
    - Mid frequency: piano, guitar, snare, vocals
    - High frequency: hihat, crash, synth-lead, flute
    - Pad instruments: synth-pad, string-ensemble
    
    4. VOLUME BALANCING:
    - Bass instruments: 0.7-0.9 (strong foundation)
    - Drums: 0.8-1.0 (rhythmic prominence)
    - Lead instruments: 0.6-0.8 (melodic clarity)
    - Pad instruments: 0.4-0.6 (background support)
    - Vocals: 0.8-1.0 (lyrical prominence)
    
    5. EFFECTS RECOMMENDATIONS:
    - Reverb: Strings (0.3-0.5), Vocals (0.2-0.4), Piano (0.1-0.3)
    - Delay: Lead instruments (0.2-0.4), Guitar (0.1-0.3)
    - Distortion: Electric guitar (0.1-0.5), Bass (0.0-0.2)
    
    Always use get_available_instruments() to check current sample library before suggesting instruments!
    """
