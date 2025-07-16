import { useAudioStore } from '../stores/audioStore';

export interface DrumPatternConfig {
  pattern: string;
  bpm: number;
  duration: number; // in bars
  volume: number;
  effects?: {
    reverb?: number;
    delay?: number;
    compression?: number;
  };
}

export interface ParsedDrumInfo {
  pattern: string;
  bpm?: number;
  duration?: number;
  description: string;
  confidence: number;
}

export default class DrumPatternService {
  private static readonly PATTERN_KEYWORDS = [
    'kick', 'snare', 'hi-hat', 'crash', 'ride', 'tom', 'cymbal',
    'beat', 'pattern', 'drum', 'rhythm', 'percussion'
  ];

  private static readonly BPM_PATTERNS = [
    /(\d+)\s*bpm/i,
    /tempo.*?(\d+)/i,
    /(\d+)\s*beats?\s*per\s*minute/i
  ];

  private static readonly DURATION_PATTERNS = [
    /(\d+)\s*bars?/i,
    /(\d+)\s*measures?/i,
    /(\d+)\s*beats?/i
  ];

  /**
   * Parse AI response for drum pattern information
   */
  static parseAIDrumSuggestion(text: string): ParsedDrumInfo | null {
    const lowerText = text.toLowerCase();
    
    // Check if this contains drum-related content
    const hasDrumKeywords = this.PATTERN_KEYWORDS.some(keyword => 
      lowerText.includes(keyword)
    );
    
    if (!hasDrumKeywords) {
      return null;
    }

    // Extract BPM
    let bpm: number | undefined;
    for (const pattern of this.BPM_PATTERNS) {
      const match = text.match(pattern);
      if (match) {
        bpm = parseInt(match[1]);
        break;
      }
    }

    // Extract duration
    let duration: number | undefined;
    for (const pattern of this.DURATION_PATTERNS) {
      const match = text.match(pattern);
      if (match) {
        duration = parseInt(match[1]);
        break;
      }
    }

    // Extract pattern description
    const patternMatch = text.match(/pattern:?\s*([^.!?]+)/i) ||
                        text.match(/drum[s]?:?\s*([^.!?]+)/i) ||
                        text.match(/rhythm:?\s*([^.!?]+)/i);
    
    const pattern = patternMatch ? patternMatch[1].trim() : 'basic pattern';

    // Calculate confidence based on specificity
    let confidence = 0.5; // base confidence
    if (bpm) confidence += 0.2;
    if (duration) confidence += 0.2;
    if (patternMatch) confidence += 0.3;

    return {
      pattern,
      bpm,
      duration,
      description: text,
      confidence: Math.min(confidence, 1.0)
    };
  }

  /**
   * Generate drum pattern based on AI suggestion
   */
  static async generateFromAISuggestion(suggestion: ParsedDrumInfo, config?: Partial<DrumPatternConfig>): Promise<void> {
    const pattern: DrumPatternConfig = {
      pattern: suggestion.pattern,
      bpm: suggestion.bpm || config?.bpm || 120,
      duration: suggestion.duration || config?.duration || 4,
      volume: config?.volume || 0.8,
      effects: config?.effects || {}
    };

    // Add to audio store
    await this.addDrumPattern(pattern);
  }

  /**
   * Create standardized drum patterns
   */
  static async addDrumPattern(config: DrumPatternConfig): Promise<void> {
    const store = useAudioStore();
    
    // Use addTrack with proper parameters
    store.addTrack(
      `Drum Pattern - ${config.pattern}`,
      'drums',
      undefined, // no sample URL for generated patterns
      'percussion'
    );
  }

  /**
   * Get available drum sounds from audio store
   */
  static getAvailableDrumSounds(): string[] {
    // Return common drum instruments available in mITyStudio
    return [
      'kick', 'snare', 'hihat', 'crash', 'ride', 'tom',
      'openhat', 'clap', 'shaker', 'cowbell'
    ];
  }

  /**
   * Validate drum pattern configuration
   */
  static validatePattern(config: DrumPatternConfig): boolean {
    return (
      config.bpm > 0 && config.bpm <= 300 &&
      config.duration > 0 && config.duration <= 32 &&
      config.volume >= 0 && config.volume <= 1
    );
  }
}

// Named export for compatibility
export { DrumPatternService };
