# AI Lyrics JSON Integration Guide

## Overview

The LangChain React agent now supports automatic integration of AI-generated lyrics JSON into your song structure. When the AI assistant generates lyrics in the correct JSON format, you can seamlessly integrate them into your mITyStudio project.

## New Features

### 1. Auto-Detection Integration
- **Tool**: `integrate_ai_lyrics_response`
- **Purpose**: Automatically detects and integrates lyrics JSON from AI responses
- **Usage**: Scans AI response text for valid lyrics JSON and applies it to your song

### 2. Direct JSON Application
- **Tool**: `apply_ai_generated_lyrics`
- **Purpose**: Apply pre-validated lyrics JSON with specific integration modes
- **Usage**: Direct application of lyrics JSON with control over how it's integrated

### 3. Integration Modes

#### `auto` (Default)
- System automatically determines the best integration method
- Creates new track if no vocal tracks exist
- Adds to existing vocal track if available

#### `new_track`
- Always creates a new vocal track for the lyrics
- Best for: Separate vocal parts, different singers, or organized arrangement

#### `existing_track` 
- Adds lyrics to the first available vocal track
- Best for: Adding verses/choruses to existing vocal track

#### `clip_only`
- Adds only the lyrics clip to an existing vocal track
- Best for: Adding individual lyrics sections

### 4. Seamless Chat Integration
- **Method**: `chat_with_auto_integration`
- **Purpose**: Chat with AI assistant and automatically integrate any lyrics JSON found in responses
- **Benefits**: Zero-friction workflow from AI generation to song integration

## JSON Structure Validation

All integration tools include comprehensive validation to ensure:
- Correct track structure (vocals category, proper effects)
- Valid clip structure (lyrics type, vocals instrument)
- Proper voices array format
- Correct duration/durations usage for notes
- Valid voice_id naming (soprano01, alto01, etc.)

## Example Workflow

1. **Chat with AI**: "Create lyrics for my chorus in C major"
2. **AI Generates**: Proper JSON structure with voices array
3. **Auto-Integration**: System detects JSON and offers integration
4. **Validation**: Structure is validated before application
5. **Application**: Lyrics are seamlessly added to your song

## Benefits

- **Seamless Workflow**: No manual copying/pasting of JSON
- **Structure Compliance**: Automatic validation ensures correct format
- **Flexible Integration**: Multiple modes for different use cases
- **Error Prevention**: Validation prevents malformed lyrics data
- **Backward Compatible**: Works with existing lyrics tools

## Technical Implementation

- JSON extraction using regex patterns
- Comprehensive structure validation
- Multiple integration strategies
- Error handling and fallbacks
- LangChain tool integration
