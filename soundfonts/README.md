# SoundFont Files Directory

Place your SoundFont2 (.sf2) files in this directory.

## Where to find SoundFont files:

### Free SoundFonts:
- **FluidR3_GM.sf2** - General MIDI soundfont (recommended for testing)
  - Download: https://member.keymusician.com/Member/FluidR3_GM/index.html
  
- **MuseScore General** - High quality free soundfont
  - Download: https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/

- **Timbres of Heaven** - Comprehensive free soundfont
  - Download: http://midkar.com/soundfonts/

### Commercial SoundFonts:
- Look for piano, guitar, orchestral, or other instrument-specific soundfonts
- Many DAW software packages include high-quality soundfonts

## Example structure:
```
Soundfonts/
├── FluidR3_GM.sf2          # General MIDI instruments
├── piano.sf2               # Piano sounds
├── guitar.sf2              # Guitar sounds
└── orchestral.sf2          # Orchestral instruments
```

## Note:
- Files must have the `.sf2` extension
- The script will use the filename (without extension) as the instrument name
- You can have multiple soundfont files - the script can process them all
