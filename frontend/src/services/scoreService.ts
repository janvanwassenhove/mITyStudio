/**
 * Score Service
 * Handles API calls for musical score sheet uploads and processing
 */

export interface ScoreFile {
  file_id: string
  filename: string
  category: string
  status: 'uploading' | 'success' | 'error'
  analysis?: ScoreAnalysis
  error?: string
}

export interface ScoreAnalysis {
  type: string
  estimated_key?: string
  estimated_tempo?: number
  time_signature?: string
  instruments?: string[]
  suggested_instruments?: string[]
  difficulty_level?: string
  detected_elements?: Record<string, any>
  chord_progressions?: string[]
  note: string
}

export interface UploadResult {
  success: boolean
  files_processed: number
  results: ScoreFile[]
  message: string
}

export class ScoreService {
  private static readonly API_BASE = '/api/scores'

  /**
   * Upload musical score sheets or tablatures
   */
  static async uploadScores(files: File[]): Promise<UploadResult> {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const response = await fetch(`${this.API_BASE}/upload`, {
      method: 'POST',
      body: formData
    })

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error || 'Upload failed')
    }

    return result
  }

  /**
   * Get detailed analysis of a processed score file
   */
  static async getScoreAnalysis(fileId: string): Promise<ScoreAnalysis> {
    const response = await fetch(`${this.API_BASE}/analyze/${fileId}`)
    
    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error || 'Failed to get analysis')
    }

    return result
  }

  /**
   * Generate JSON structure from processed score
   */
  static async generateJsonStructure(
    fileId: string, 
    instrumentName: string = 'piano',
    trackName: string = 'Score Track'
  ): Promise<any> {
    const response = await fetch(`${this.API_BASE}/generate-json/${fileId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        instrument: instrumentName,
        trackName: trackName
      })
    })

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error || 'Failed to generate JSON structure')
    }

    return result.json_structure
  }

  /**
   * List all uploaded scores
   */
  static async listScores(): Promise<ScoreFile[]> {
    const response = await fetch(`${this.API_BASE}/list`)
    
    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error || 'Failed to list scores')
    }

    return result.scores
  }

  /**
   * Delete a processed score
   */
  static async deleteScore(fileId: string): Promise<void> {
    const response = await fetch(`${this.API_BASE}/delete/${fileId}`, {
      method: 'DELETE'
    })

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error || 'Failed to delete score')
    }
  }

  /**
   * Get supported file formats
   */
  static async getSupportedFormats(): Promise<any> {
    const response = await fetch(`${this.API_BASE}/supported-formats`)
    
    const result = await response.json()

    if (!response.ok) {
      throw new Error('Failed to get supported formats')
    }

    return result
  }

  /**
   * Send chat message with score context
   */
  static async chatWithScores(
    message: string,
    scoreFileIds: string[],
    provider: string = 'anthropic',
    model: string = 'claude-4-sonnet',
    context: any = {}
  ): Promise<any> {
    console.log('[ScoreService] Sending chat with scores:', {
      message: message.substring(0, 100) + (message.length > 100 ? '...' : ''),
      scoreFileIds,
      provider,
      model,
      contextKeys: Object.keys(context)
    })

    try {
      const response = await fetch('/api/ai/chat-with-scores', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message,
          score_file_ids: scoreFileIds,
          provider,
          model,
          context
        })
      })

      console.log('[ScoreService] Response status:', response.status, response.statusText)

      const result = await response.json()
      
      console.log('[ScoreService] Response data:', {
        success: response.ok,
        hasContent: !!result?.response,
        hasError: !!result?.error,
        responseKeys: Object.keys(result || {})
      })

      if (!response.ok) {
        console.error('[ScoreService] API Error:', result)
        throw new Error(result.error || 'Failed to send message with scores')
      }

      return result
    } catch (error) {
      console.error('[ScoreService] Network/Parse Error:', error)
      throw error
    }
  }

  /**
   * Validate file before upload
   */
  static validateFile(file: File): { valid: boolean; error?: string } {
    const allowedExtensions = [
      'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'svg',  // Sheet music
      'gtp', 'gpx', 'gp5', 'gp4', 'ptb', 'tef',          // Tablature
      'xml', 'musicxml', 'mxl',                           // MusicXML
      'mid', 'midi',                                      // MIDI
      'abc', 'ly',                                        // Notation
      'txt', 'tab'                                        // Text tabs
    ]
    
    const maxSize = 10 * 1024 * 1024 // 10MB
    
    const extension = file.name.split('.').pop()?.toLowerCase()
    
    if (!extension || !allowedExtensions.includes(extension)) {
      return {
        valid: false,
        error: `Unsupported file type. Supported: ${allowedExtensions.join(', ')}`
      }
    }
    
    if (file.size > maxSize) {
      return {
        valid: false,
        error: `File too large. Maximum size is 10MB`
      }
    }
    
    return { valid: true }
  }

  /**
   * Get file category from filename
   */
  static getFileCategory(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase() || ''
    
    if (['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'svg'].includes(extension)) {
      return 'sheet_music'
    } else if (['gtp', 'gpx', 'gp5', 'gp4', 'ptb', 'tef'].includes(extension)) {
      return 'tablature'
    } else if (['xml', 'musicxml', 'mxl'].includes(extension)) {
      return 'musicxml'
    } else if (['mid', 'midi'].includes(extension)) {
      return 'midi'
    } else if (['abc', 'ly'].includes(extension)) {
      return 'notation'
    } else if (['txt', 'tab'].includes(extension)) {
      return 'text_tab'
    } else {
      return 'unknown'
    }
  }
}