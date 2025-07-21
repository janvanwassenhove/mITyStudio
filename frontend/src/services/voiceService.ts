/**
 * Voice Service
 * Unified frontend service for voice training and synthesis functionality
 */

export interface VoiceTrainingJob {
  id: string
  voiceId: string
  voiceName: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  audioFiles: string[]
  language: string
  type: 'recording' | 'files'
  created_at: number
  voice_characteristics?: any
  transcriptions?: any[]
  rvc_model_trained?: boolean
  rvc_model_path?: string
  error?: string
}

export interface Voice {
  id: string
  name: string
  type: 'builtin' | 'custom'
  trained: boolean
  language: string
  created_at?: string
  voice_characteristics?: any
}

export class VoiceService {
  private static readonly API_BASE = 'http://localhost:5000/api/voice'

  /**
   * Train voice from audio recording
   */
  static async trainVoiceFromRecording(
    voiceName: string,
    audioBlob: Blob,
    duration: number,
    sampleRate: number,
    language: string = 'en'
  ): Promise<string> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      formData.append('audioFile', audioBlob, 'recording.wav')
      formData.append('duration', duration.toString())
      formData.append('sampleRate', sampleRate.toString())
      formData.append('language', language)

      const response = await fetch(`${this.API_BASE}/train/recording`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Training failed')
      }

      const result = await response.json()
      return result.jobId
    } catch (error) {
      console.error('Error training voice from recording:', error)
      throw error
    }
  }

  /**
   * Train voice from multiple audio files
   */
  static async trainVoiceFromFiles(
    voiceName: string,
    audioFiles: File[],
    language: string = 'en',
    epochs: number = 100,
    speakerEmbedding: boolean = true
  ): Promise<string> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      formData.append('language', language)
      formData.append('epochs', epochs.toString())
      formData.append('speakerEmbedding', speakerEmbedding.toString())

      audioFiles.forEach((file, index) => {
        formData.append(`audio_${index}`, file, file.name)
      })

      const response = await fetch(`${this.API_BASE}/train/files`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Training failed')
      }

      const result = await response.json()
      return result.jobId
    } catch (error) {
      console.error('Error training voice from files:', error)
      throw error
    }
  }

  /**
   * Get training job status
   */
  static async getTrainingStatus(jobId: string): Promise<VoiceTrainingJob | null> {
    try {
      const response = await fetch(`${this.API_BASE}/training/${jobId}`)
      
      if (!response.ok) {
        return null
      }

      return await response.json()
    } catch (error) {
      console.error('Error getting training status:', error)
      return null
    }
  }

  /**
   * Cancel a training job
   */
  static async cancelTraining(jobId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.API_BASE}/training/${jobId}/cancel`, {
        method: 'POST'
      })
      
      return response.ok
    } catch (error) {
      console.error('Error cancelling training:', error)
      return false
    }
  }

  /**
   * Get available voices
   */
  static async getAvailableVoices(): Promise<Voice[]> {
    try {
      const response = await fetch(`${this.API_BASE}/voices`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch voices')
      }

      const result = await response.json()
      
      // Handle different response formats
      if (Array.isArray(result)) {
        return result
      } else if (result.voices && Array.isArray(result.voices)) {
        return result.voices
      } else {
        throw new Error('Invalid voices response format')
      }
    } catch (error) {
      console.error('Error getting available voices:', error)
      return []
    }
  }

  /**
   * Delete a voice
   */
  static async deleteVoice(voiceId: string): Promise<void> {
    try {
      const response = await fetch(`${this.API_BASE}/voices/${voiceId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to delete voice')
      }
    } catch (error) {
      console.error('Error deleting voice:', error)
      throw error
    }
  }

  /**
   * Test voice spoken synthesis
   */
  static async testVoiceSpoken(voiceId: string): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/test/${voiceId}`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error('Failed to generate spoken test')
      }

      return await response.blob()
    } catch (error) {
      console.error('Error testing voice spoken:', error)
      throw error
    }
  }

  /**
   * Test voice singing synthesis
   */
  static async testVoiceSinging(
    voiceId: string,
    text: string,
    notes: string | null,
    chord: string
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/test-singing/${voiceId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text,
          notes,
          chord
        })
      })

      if (!response.ok) {
        throw new Error('Failed to generate singing test')
      }

      return await response.blob()
    } catch (error) {
      console.error('Error testing voice singing:', error)
      throw error
    }
  }

  /**
   * Synthesize voice for lyrics
   */
  static async synthesizeVoice(
    voiceId: string,
    lyrics: string,
    notes: any[],
    tempo: number,
    key: string
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          voiceId,
          lyrics,
          notes,
          tempo,
          key
        })
      })

      if (!response.ok) {
        throw new Error('Failed to synthesize voice')
      }

      return await response.blob()
    } catch (error) {
      console.error('Error synthesizing voice:', error)
      throw error
    }
  }

  /**
   * Validate audio file
   */
  static validateAudioFile(file: File): { valid: boolean; error?: string } {
    const maxSize = 500 * 1024 * 1024 // 500MB
    const allowedTypes = ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/m4a', 'audio/flac', 'audio/ogg']

    if (file.size > maxSize) {
      return { valid: false, error: 'File size must be less than 500MB' }
    }

    if (!allowedTypes.includes(file.type) && !file.name.toLowerCase().match(/\.(wav|mp3|m4a|flac|ogg)$/)) {
      return { valid: false, error: 'File must be a valid audio format (WAV, MP3, M4A, FLAC, OGG)' }
    }

    return { valid: true }
  }

  /**
   * Validate recording duration
   */
  static validateRecording(duration: number): { valid: boolean; error?: string } {
    if (duration < 10) {
      return { valid: false, error: 'Recording must be at least 10 seconds long' }
    }

    if (duration > 1800) { // 30 minutes
      return { valid: false, error: 'Recording must be less than 30 minutes long' }
    }

    return { valid: true }
  }

  /**
   * Format file size in human readable format
   */
  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes'

    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  /**
   * Format duration in human readable format
   */
  static formatDuration(seconds: number): string {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = Math.round(seconds % 60)
      return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`
    } else {
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
    }
  }

  /**
   * Validate multiple uploaded files
   */
  static validateUploadedFiles(files: File[]): { valid: boolean; error?: string } {
    if (files.length === 0) {
      return { valid: false, error: 'No files selected' }
    }

    const maxFiles = 20
    if (files.length > maxFiles) {
      return { valid: false, error: `Maximum ${maxFiles} files allowed` }
    }

    for (const file of files) {
      const validation = this.validateAudioFile(file)
      if (!validation.valid) {
        return { valid: false, error: `${file.name}: ${validation.error}` }
      }
    }

    return { valid: true }
  }

  /**
   * Check upload size and provide recommendations
   */
  static checkUploadSize(files: File[]): { 
    shouldWarn: boolean; 
    totalSizeMB: number; 
    recommendation?: string 
  } {
    const totalBytes = files.reduce((sum, file) => sum + file.size, 0)
    const totalSizeMB = Math.round(totalBytes / (1024 * 1024) * 100) / 100

    if (totalSizeMB > 500) {
      return {
        shouldWarn: true,
        totalSizeMB,
        recommendation: 'Large upload detected. This may take several minutes to process and train.'
      }
    }

    return { shouldWarn: false, totalSizeMB }
  }

  /**
   * Validate recording duration (alias for validateRecording)
   */
  static validateRecordingDuration(duration: number): { valid: boolean; error?: string } {
    return this.validateRecording(duration)
  }
}
