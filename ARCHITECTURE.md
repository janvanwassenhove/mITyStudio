# mITyStudio Architecture

## Overview

mITyStudio is a modern web-based digital audio workstation (DAW) built with Vue 3, TypeScript, and Vite. The application provides AI-powered music composition tools and a comprehensive audio production environment.

## Technology Stack

- **Frontend Framework**: Vue 3 with Composition API
- **Language**: TypeScript
- **Build Tool**: Vite
- **State Management**: Pinia
- **Audio Processing**: Tone.js
- **HTTP Client**: Axios
- **Internationalization**: Vue I18n
- **Icons**: Lucide Vue Next
- **Utilities**: VueUse

## Project Structure

```
src/
├── components/          # Vue components
├── stores/             # Pinia stores for state management
├── assets/             # Static assets
├── locales/            # Internationalization files
├── style.css          # Global styles
└── main.ts            # Application entry point
```

## Core Components

### AIChat

AI Chat Component Provides an intelligent chat interface for music composition assistance. Features real-time AI responses, contextual suggestions, and integration with the main audio production workflow.

**Features:**
- AI Chat Integration
- Audio Processing
- Timeline Editing

**Location:** `src/components/AIChat.vue`

### AppHeader

Main application header with navigation and controls

**Features:**
- Audio Processing
- Theme Management

**Location:** `src/components/AppHeader.vue`

### JSONStructurePanel

Side panel component with various tools and settings

**Features:**
- Audio Processing

**Location:** `src/components/JSONStructurePanel.vue`

### PlaybackControls

Audio playback and control component

**Features:**
- Audio Processing

**Location:** `src/components/PlaybackControls.vue`

### RightPanelToggle

Side panel component with various tools and settings

**Features:**
- AI Chat Integration
- Audio Processing
- Theme Management
- Sample Management
- Timeline Editing

**Location:** `src/components/RightPanelToggle.vue`

### SampleLibrary

Sample library management and organization

**Features:**
- Audio Processing
- Sample Management

**Location:** `src/components/SampleLibrary.vue`

### ThemeToggle

Theme management and customization component

**Features:**
- Theme Management

**Location:** `src/components/ThemeToggle.vue`

### TimelineEditor

Timeline editor for arranging musical elements

**Features:**
- Audio Processing
- Sample Management
- Timeline Editing

**Location:** `src/components/TimelineEditor.vue`

### TrackControls

Individual track controls and management

**Features:**
- Audio Processing
- Sample Management
- Timeline Editing

**Location:** `src/components/TrackControls.vue`


## State Management (Pinia Stores)

### Ai Store

Manages application state

**State Variables:**
- `isGenerating`
- `selectedProvider`
- `selectedModel`

**Actions:**
- `addMessage()`
- `clearMessages()`
- `setProvider()`
- `setModel()`
- `getAvailableModels()`

**Location:** `src/stores/aiStore.ts`

### Audio Store

Manages application state

**State Variables:**
- `isPlaying`
- `currentTime`
- `isLooping`
- `metronomeEnabled`
- `masterVolume`
- `zoom`
- `isInitialized`
- `isInitializing`

**Actions:**
- `scheduleClip()`
- `scheduleMetronome()`
- `clearScheduledEvents()`
- `generateAndScheduleSong()`
- `pause()`
- `stop()`
- `setTempo()`
- `addTrack()`
- `removeTrack()`
- `updateTrack()`
- `addClip()`
- `removeClip()`
- `updateClip()`
- `updateSongStructure()`
- `loadSongStructure()`
- `exportSongStructure()`
- `toggleLoop()`
- `toggleMetronome()`
- `setMasterVolume()`
- `setZoom()`
- `selectTrack()`
- `resetAudio()`

**Location:** `src/stores/audioStore.ts`

### Sample Store

Manages application state

**State Variables:**
- `isLoading`
- `loadingProgress`
- `searchQuery`

**Actions:**
- `removeSample()`
- `updateSampleCategory()`
- `updateSampleTags()`
- `clearAllSamples()`
- `exportSampleLibrary()`
- `getSample()`

**Location:** `src/stores/sampleStore.ts`

### Theme Store

Manages application state

**State Variables:**
- `systemPrefersDark`

**Actions:**
- `setMode()`
- `toggleMode()`
- `applyTheme()`
- `updateMetaThemeColor()`
- `detectSystemTheme()`
- `saveToStorage()`
- `loadFromStorage()`
- `initializeTheme()`
- `applyPresetTheme()`

**Location:** `src/stores/themeStore.ts`


## Key Features

1. **AI-Powered Composition**: Integrated AI chat for music creation assistance
2. **Audio Production**: Full timeline editor with track management
3. **Sample Library**: Comprehensive sample management and organization
4. **Theme System**: Customizable themes with light/dark mode support
5. **Real-time Audio**: WebAudio-based audio processing with Tone.js
6. **Internationalization**: Multi-language support

## Data Flow

1. **User Interactions**: Components handle user input and emit events
2. **State Updates**: Pinia stores manage application state changes
3. **Audio Processing**: Tone.js handles real-time audio synthesis and effects
4. **AI Integration**: AI store manages chat interactions and responses

## Development Workflow

1. **Development Server**: `npm run dev`
2. **Production Build**: `npm run build`
3. **Preview**: `npm run preview`

## Browser Compatibility

- Modern browsers with WebAudio API support
- ES6+ JavaScript support required
- WebRTC support recommended for advanced features


*This documentation is automatically generated. Last updated: 2025-07-05T12:12:02.950Z*

