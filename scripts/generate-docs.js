#!/usr/bin/env node

/**
 * Documentation Generator for mITyStudio
 * 
 * This script automatically generates documentation for the mITyStudio project
 * by analyzing the codebase structure, components, and stores.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

// Utility functions
function readFileContent(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    return null;
  }
}

function writeFileContent(filePath, content) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(filePath, content, 'utf-8');
}

function scanDirectory(dirPath, extensions = ['.vue', '.ts', '.js']) {
  const files = [];
  
  function scan(currentPath) {
    if (!fs.existsSync(currentPath)) return;
    
    const items = fs.readdirSync(currentPath);
    
    for (const item of items) {
      const fullPath = path.join(currentPath, item);
      const stat = fs.statSync(fullPath);
      
      if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
        scan(fullPath);
      } else if (stat.isFile() && extensions.some(ext => item.endsWith(ext))) {
        files.push({
          path: fullPath,
          name: item,
          directory: currentPath,
          relativePath: path.relative(process.cwd(), fullPath)
        });
      }
    }
  }
  
  scan(dirPath);
  return files;
}

function extractComponentInfo(filePath) {
  const content = readFileContent(filePath);
  if (!content) return null;
  
  const info = {
    name: path.basename(filePath, path.extname(filePath)),
    path: filePath,
    description: '',
    props: [],
    features: []
  };
  
  // Extract component description from comments or infer from component name/content
  const descriptionMatch = content.match(/\/\*\*\s*\n\s*\*\s*(.+?)\s*\n[\s\*]*\*\//);
  if (descriptionMatch) {
    info.description = descriptionMatch[1];
  } else {
    // Infer description based on component name and content
    const name = info.name.toLowerCase();
    if (name.includes('ai') && name.includes('chat')) {
      info.description = 'AI-powered chat interface for music composition assistance';
    } else if (name.includes('audio') || name.includes('playback')) {
      info.description = 'Audio playback and control component';
    } else if (name.includes('timeline')) {
      info.description = 'Timeline editor for arranging musical elements';
    } else if (name.includes('theme')) {
      info.description = 'Theme management and customization component';
    } else if (name.includes('sample')) {
      info.description = 'Sample library management and organization';
    } else if (name.includes('header')) {
      info.description = 'Main application header with navigation and controls';
    } else if (name.includes('track')) {
      info.description = 'Individual track controls and management';
    } else if (name.includes('panel')) {
      info.description = 'Side panel component with various tools and settings';
    }
  }
  
  // Extract features from component analysis
  if (content.includes('AI') || content.includes('chat')) {
    info.features.push('AI Chat Integration');
  }
  if (content.includes('audio') || content.includes('Audio')) {
    info.features.push('Audio Processing');
  }
  if (content.includes('theme') || content.includes('Theme')) {
    info.features.push('Theme Management');
  }
  if (content.includes('sample') || content.includes('Sample')) {
    info.features.push('Sample Management');
  }
  if (content.includes('timeline') || content.includes('Timeline')) {
    info.features.push('Timeline Editing');
  }
  
  return info;
}

function extractStoreInfo(filePath) {
  const content = readFileContent(filePath);
  if (!content) return null;
  
  const info = {
    name: path.basename(filePath, '.ts').replace('Store', ''),
    path: filePath,
    description: '',
    state: [],
    actions: []
  };
  
  // Extract store description
  const descriptionMatch = content.match(/\/\*\*\s*\n\s*\*\s*(.+?)\s*\n[\s\*]*\*\//);
  if (descriptionMatch) {
    info.description = descriptionMatch[1];
  }
  
  // Extract state variables
  const stateMatches = content.match(/const\s+(\w+)\s*=\s*ref\(/g);
  if (stateMatches) {
    info.state = stateMatches.map(match => {
      const varName = match.match(/const\s+(\w+)\s*=/)[1];
      return varName;
    });
  }
  
  // Extract actions (functions)
  const actionMatches = content.match(/const\s+(\w+)\s*=\s*\([^)]*\)\s*=>/g);
  if (actionMatches) {
    info.actions = actionMatches.map(match => {
      const actionName = match.match(/const\s+(\w+)\s*=/)[1];
      return actionName;
    });
  }
  
  return info;
}

function generateArchitectureDoc() {
  const packageJson = JSON.parse(readFileContent(path.join(projectRoot, 'package.json')));
  
  // Scan components and stores
  const components = scanDirectory(path.join(projectRoot, 'src/components'), ['.vue']);
  const stores = scanDirectory(path.join(projectRoot, 'src/stores'), ['.ts']);
  
  const componentInfos = components.map(file => extractComponentInfo(file.path)).filter(Boolean);
  const storeInfos = stores.map(file => extractStoreInfo(file.path)).filter(Boolean);
  
  const doc = `# mITyStudio Architecture

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

\`\`\`
src/
├── components/          # Vue components
├── stores/             # Pinia stores for state management
├── assets/             # Static assets
├── locales/            # Internationalization files
├── style.css          # Global styles
└── main.ts            # Application entry point
\`\`\`

## Core Components

${componentInfos.map(comp => `### ${comp.name}

${comp.description || 'Core component for the application'}

**Features:**
${comp.features.length > 0 ? comp.features.map(f => `- ${f}`).join('\n') : '- Component functionality'}

**Location:** \`${path.relative(projectRoot, comp.path)}\`
`).join('\n')}

## State Management (Pinia Stores)

${storeInfos.map(store => `### ${store.name.charAt(0).toUpperCase() + store.name.slice(1)} Store

${store.description || 'Manages application state'}

**State Variables:**
${store.state.length > 0 ? store.state.map(s => `- \`${s}\``).join('\n') : '- Various state properties'}

**Actions:**
${store.actions.length > 0 ? store.actions.map(a => `- \`${a}()\``).join('\n') : '- Various action methods'}

**Location:** \`${path.relative(projectRoot, store.path)}\`
`).join('\n')}

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

1. **Development Server**: \`npm run dev\`
2. **Production Build**: \`npm run build\`
3. **Preview**: \`npm run preview\`

## Browser Compatibility

- Modern browsers with WebAudio API support
- ES6+ JavaScript support required
- WebRTC support recommended for advanced features

*This documentation is automatically generated. Last updated: ${new Date().toISOString()}*
`;

  return doc;
}

function generateFeatureDoc(componentInfo) {
  return `# ${componentInfo.name}

## Overview

${componentInfo.description || `The ${componentInfo.name} component is a key part of the mITyStudio application.`}

## Features

${componentInfo.features.length > 0 ? componentInfo.features.map(f => `- ${f}`).join('\n') : '- Core functionality'}

## Location

\`${path.relative(projectRoot, componentInfo.path)}\`

## Usage

This component is part of the main application structure and integrates with the overall mITyStudio workflow.

*This documentation is automatically generated. Last updated: ${new Date().toISOString()}*
`;
}

function generateFeatureDocs() {
  const components = scanDirectory(path.join(projectRoot, 'src/components'), ['.vue']);
  const componentInfos = components.map(file => extractComponentInfo(file.path)).filter(Boolean);
  
  // Generate individual feature docs for major components
  const majorComponents = componentInfos.filter(comp => 
    comp.features.length > 0 || comp.name.includes('AI') || comp.name.includes('Audio') || 
    comp.name.includes('Timeline') || comp.name.includes('Sample') || comp.name.includes('Theme')
  );
  
  majorComponents.forEach(comp => {
    const featureDoc = generateFeatureDoc(comp);
    writeFileContent(path.join(projectRoot, 'docs', `${comp.name.toLowerCase()}.md`), featureDoc);
  });
  
  // Generate overview doc
  const overviewDoc = `# Feature Documentation

## Available Features

${majorComponents.map(comp => `- [${comp.name}](./${comp.name.toLowerCase()}.md) - ${comp.description || 'Core component'}`).join('\n')}

## Feature Categories

### Audio Production
${majorComponents.filter(c => c.features.some(f => f.includes('Audio') || f.includes('Timeline')))
  .map(c => `- [${c.name}](./${c.name.toLowerCase()}.md)`).join('\n')}

### AI Integration  
${majorComponents.filter(c => c.features.some(f => f.includes('AI')))
  .map(c => `- [${c.name}](./${c.name.toLowerCase()}.md)`).join('\n')}

### User Interface
${majorComponents.filter(c => c.features.some(f => f.includes('Theme')))
  .map(c => `- [${c.name}](./${c.name.toLowerCase()}.md)`).join('\n')}

### Content Management
${majorComponents.filter(c => c.features.some(f => f.includes('Sample')))
  .map(c => `- [${c.name}](./${c.name.toLowerCase()}.md)`).join('\n')}

*This documentation is automatically generated. Last updated: ${new Date().toISOString()}*
`;

  writeFileContent(path.join(projectRoot, 'docs', 'README.md'), overviewDoc);
}

// Main execution
function main() {
  console.log('🔄 Generating documentation...');
  
  // Set working directory to project root
  process.chdir(projectRoot);
  
  // Generate architecture documentation
  console.log('📐 Generating ARCHITECTURE.md...');
  const architectureDoc = generateArchitectureDoc();
  writeFileContent(path.join(projectRoot, 'ARCHITECTURE.md'), architectureDoc);
  
  // Generate feature documentation
  console.log('📚 Generating feature documentation...');
  generateFeatureDocs();
  
  console.log('✅ Documentation generation complete!');
  console.log('📄 Generated files:');
  console.log('   - ARCHITECTURE.md');
  console.log('   - docs/README.md');
  console.log('   - docs/*.md (feature docs)');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { main, generateArchitectureDoc, generateFeatureDocs };