# Documentation Generation System - Usage Guide

## Overview

This repository now includes an automated documentation generation system that keeps your documentation up-to-date with your code changes.

## How It Works

### Automatic Updates
- **Trigger**: Every push to any branch automatically generates updated documentation
- **Smart Detection**: Only commits changes when documentation actually needs updating
- **Safe Branching**: Documentation updates are committed back to the same branch that triggered the workflow

### Generated Documentation

#### ARCHITECTURE.md (Root Level)
- Complete system architecture overview
- Technology stack details
- Project structure breakdown
- Component and store analysis
- Automatically updated on every relevant code change

#### docs/ Directory
- Feature-specific documentation for each component
- Categorized by functionality (AI, Audio, UI, etc.)
- Individual `.md` files for major components
- README.md with navigation and categorization

## Manual Generation

To generate documentation manually:

```bash
npm run docs
```

This runs the `scripts/generate-docs.js` script and updates all documentation files.

## Adding Component Documentation

### Method 1: JSDoc Comments (Recommended)
Add a JSDoc comment at the top of your Vue component:

```vue
/**
 * Component Name
 * 
 * Brief description of what this component does.
 * Can include multiple lines of description.
 */
<template>
  <!-- Your component template -->
</template>
```

### Method 2: Automatic Inference
If no JSDoc comment is found, the system will automatically generate descriptions based on:
- Component name patterns
- Content analysis
- Feature detection

## Loop Prevention

The workflow includes multiple safeguards to prevent infinite loops:

1. **Path Ignoring**: Ignores pushes that only modify documentation files
2. **Commit Message Skipping**: Add `[skip docs]` or `[docs skip]` to your commit message to skip documentation generation
3. **Change Detection**: Only commits when documentation actually changes

## Workflow Configuration

The GitHub Actions workflow (`.github/workflows/update-docs.yml`) is configured to:

- Run on pushes to any branch
- Install dependencies and generate documentation
- Detect changes and commit only when necessary
- Use appropriate commit messages with `[skip docs]` to prevent loops

## Best Practices

1. **Add JSDoc Comments**: Include meaningful JSDoc comments in your components for better documentation
2. **Descriptive Commit Messages**: Use clear commit messages since they may be referenced in documentation
3. **Component Organization**: Keep components organized as the documentation structure follows your component structure
4. **Regular Updates**: The system works best when code changes are frequent - documentation stays fresh automatically

## Troubleshooting

### Documentation Not Updating
1. Check if your push modified any non-documentation files
2. Ensure your commit message doesn't contain `[skip docs]`
3. Check the GitHub Actions tab for workflow status

### Loop Issues
If you experience infinite loops:
1. Add `[skip docs]` to your commit message
2. Check the `paths-ignore` configuration in the workflow file
3. Verify that documentation commits are properly tagged

### Manual Override
To force documentation regeneration:
1. Run `npm run docs` locally
2. Commit and push the changes manually
3. Or trigger the workflow by making a small code change

## File Structure

```
├── .github/workflows/update-docs.yml  # GitHub Actions workflow
├── scripts/generate-docs.js           # Documentation generation script
├── ARCHITECTURE.md                    # Auto-generated architecture docs
├── docs/                             # Feature documentation directory
│   ├── README.md                     # Documentation index
│   ├── aichat.md                     # Component documentation
│   └── ...                          # Additional component docs
└── package.json                      # npm scripts for manual generation
```

This system ensures your documentation never falls behind your code changes while requiring minimal maintenance effort.