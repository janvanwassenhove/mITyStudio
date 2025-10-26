# mITyStudio Documentation

Welcome to the comprehensive documentation for mITyStudio - the AI-powered music composition and production studio.

![mITyStudio Main Interface](assets/mITyStudio.png)

*The main interface showcasing mITyStudio's comprehensive music production environment*

## 📖 Table of Contents

### 🎵 Core System Architecture
- **[LANGGRAPH_WORKFLOWS.md](LANGGRAPH_WORKFLOWS.md)** - Multi-agent AI composition workflows with visual diagrams
- **[LANGGRAPH_IMPLEMENTATION.md](LANGGRAPH_IMPLEMENTATION.md)** - Technical implementation details and code patterns
- **[LANGGRAPH_EFFECTS_ENHANCEMENT.md](LANGGRAPH_EFFECTS_ENHANCEMENT.md)** - Audio effects processing and musical depth enhancements

### 🎤 Vocal & Lyric Processing
- **[EXTENDED_VOCAL_STRUCTURE.md](EXTENDED_VOCAL_STRUCTURE.md)** - Advanced vocal synthesis with syllable-to-note mapping
- **[MASTER_LYRIC_LANE.md](MASTER_LYRIC_LANE.md)** - Real-time karaoke visualization and multi-speaker support
- **[extended_vocal_example.json](extended_vocal_example.json)** - Complete JSON example of extended vocal structure

### 🤖 AI Intelligence Systems
- **[AI_CHAT_INSTRUMENT_AWARENESS.md](AI_CHAT_INSTRUMENT_AWARENESS.md)** - Context-aware AI chat with dynamic instrument library integration

### 🖼️ User Interface & Visual Guides
- **[VISUAL_INTERFACE_GUIDE.md](VISUAL_INTERFACE_GUIDE.md)** - Complete visual walkthrough of all interface components with screenshots
- **[INTERFACE_QUICK_REFERENCE.md](INTERFACE_QUICK_REFERENCE.md)** - Visual quick-reference guide for efficient workflow navigation

### 🎹 Audio Assets & Resources
- **[assets/](assets/)** - Sample audio files, demonstration tracks, and visual documentation
  - `samples/` - Individual instrument and vocal samples
  - `song_generation/` - Complete AI-generated song examples with review interface
  - `vocals/` - Voice model demonstrations and training data
  - `instruments/` - Visual guides for instrument selection and track management
- **[SF2/](SF2/)** - SoundFont instrument library for realistic sound synthesis

## 🖼️ Visual Feature Guide

### Sample Library Management
![Sample Library](assets/samples/TabSampleLibrary.png)

The comprehensive sample library provides organized access to all audio resources, enabling quick browsing and auditioning of samples for your compositions.

### Track-Based Sample Selection
![Track Sample Selection](assets/samples/TrackSampleSelection.png)

Each track allows for precise sample selection with real-time preview capabilities, making it easy to find the perfect sound for your arrangement.

### Instrument Selection Interface
![Instrument Selection](assets/instruments/TrackInstrumentsSelection.png)

The instrument selection panel provides access to the full SoundFont library, with categories organized for efficient workflow and sound exploration.

### Vocal Track Management
![Vocal Selection](assets/vocals/TrackVocalSelection.png)

Advanced vocal track management with support for custom voice models, harmonization, and real-time vocal synthesis.

### AI Song Generation & Review
![Song Generation Review](assets/song_generation/song_generation_review.png)

The Multi-Agent System (MAS) provides comprehensive song generation with detailed review capabilities, allowing you to evaluate and refine AI-composed content before integration.

## 🔧 Technical Overview

### AI Multi-Agent System
mITyStudio employs a sophisticated multi-agent workflow using LangGraph to coordinate different aspects of music composition:

1. **Composer Agent** - Creates chord progressions and song structure
2. **Arrangement Agent** - Determines instrumentation and track layout
3. **Lyrics Agent** - Generates contextual lyrics with syllable mapping
4. **Vocal Agent** - Handles vocal synthesis and harmony generation
5. **Effects Agent** - Applies audio processing and spatial positioning
6. **Finalization Agent** - Optimizes mix balance and final output

### Extended Vocal Capabilities
The system supports advanced vocal synthesis features:
- **Syllable-to-Note Mapping** - Precise control over lyrical timing
- **IPA Phoneme Support** - International Phonetic Alphabet for accurate pronunciation
- **Melisma Detection** - Automatic identification of extended vocal runs
- **Multi-Voice Harmony** - Coordinated harmony generation with stereo positioning
- **Section-Aware Lyrics** - Contextual lyric generation based on song structure

### SoundFont Integration
Professional-quality instrument simulation using SoundFont 2.0 technology:
- **Dynamic Sampling** - Velocity-sensitive instrument response
- **Multiple Articulations** - Various playing techniques per instrument
- **Admin-Managed Library** - Expandable instrument collection
- **Real-Time Performance** - Low-latency playback for interactive composition

## 🎯 Key Features Documented

### Functional Capabilities
- **AI-Powered Composition** - Intelligent music generation with style awareness
- **Voice Training & Synthesis** - Custom voice model creation and deployment
- **Real-Time Audio Processing** - Live effects and spatial audio positioning
- **Multi-Track Arrangement** - Complex song structures with seamless clip management
- **Karaoke Visualization** - Real-time lyric highlighting and navigation

### Technical Innovations
- **Cross-Section Clips** - Audio clips that span multiple song sections
- **Context-Aware AI Chat** - Dynamic instrument library integration for relevant suggestions
- **Extended JSON Schema** - Comprehensive song structure with vocal and timing data
- **Workflow Orchestration** - LangGraph-powered multi-agent coordination
- **Modular Architecture** - Vue.js frontend, Flask backend, Electron desktop integration

## 🚀 Getting Started

For setup and installation instructions, see the main [README.md](../README.md) in the project root.

**New to mITyStudio?** Start with the [Visual Interface Guide](VISUAL_INTERFACE_GUIDE.md) to see all features in action, or check the [Quick Reference](INTERFACE_QUICK_REFERENCE.md) for a rapid overview of key interfaces.

For specific implementation details, refer to the individual documentation files listed above.

## 📋 Development Notes

This documentation is actively maintained alongside the codebase. Each document includes:
- **Functional specifications** - What the feature does and why
- **Technical implementation** - How it works under the hood
- **Code examples** - Practical usage patterns and integration points
- **Visual diagrams** - Mermaid charts for complex workflows

## 🤝 Contributing to Documentation

When adding new features or modifying existing ones:
1. Update relevant documentation files
2. Include code examples and usage patterns
3. Add Mermaid diagrams for complex workflows
4. Provide both functional and technical perspectives
5. Test examples with the actual codebase

---

*This documentation provides the foundation for understanding and extending mITyStudio's AI-powered music composition capabilities.*
