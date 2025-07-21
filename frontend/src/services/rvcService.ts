/**
 * RVC (Retrieval-based Voice Conversion) Service
 * Frontend service for RVC voice cloning functionality
 */

export interface RVCVoice {
  voice_id: string
  source: 'upload' | 'record'
  status: 'ready' | 'training' | 'failed'
  model_type?: string
  training_files_count?: number
  voice_characteristics?: {
    fundamental_freq: number
    formant_shift: number
    voice_texture: number
    voice_warmth: number
    pitch_range: [number, number]
    file_count: number
    total_duration: number
  }
  sample_rate?: number
}

export interface RVCTrainingResponse {
  voice_id: string
  status: string
  model_path: string
}

export interface RVCUploadResponse {
  message: string
  voiceName: string
  fileCount: number
  tempFolder: string
  status: string
}

export class RVCService {
  private static readonly API_BASE = 'http://localhost:5000/api/voice/rvc'

  /**
   * Upload audio files for RVC training
   */
  static async uploadFilesForTraining(
    voiceName: string,
    audioFiles: File[]
  ): Promise<RVCUploadResponse> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      
      audioFiles.forEach((file) => {
        formData.append('files', file)
      })

      const response = await fetch(`${this.API_BASE}/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        if (response.status === 413) {
          throw new Error('Files too large. The total upload size exceeds the server limit. Please try uploading fewer files at once or compress your audio files.')
        }
        throw new Error(error.error || 'Failed to upload files')
      }
      
      return await response.json()
    } catch (error) {
      console.error('Error uploading files for RVC training:', error)
      throw error
    }
  }

  /**
   * Upload a mic recording for RVC training
   */
  static async uploadRecordingForTraining(
    voiceName: string,
    audioBlob: Blob
  ): Promise<RVCUploadResponse> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      
      // Determine filename based on blob type
      let filename = 'recording.webm'
      if (audioBlob.type === 'audio/wav') {
        filename = 'recording.wav'
      } else if (audioBlob.type === 'audio/mp3') {
        filename = 'recording.mp3'
      }
      
      formData.append('audio', audioBlob, filename)

      const response = await fetch(`${this.API_BASE}/record`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        if (response.status === 413) {
          throw new Error('Recording too large. Please record shorter segments or reduce audio quality.')
        }
        throw new Error(error.error || 'Failed to upload recording')
      }
      
      return await response.json()
    } catch (error) {
      console.error('Error uploading recording for RVC training:', error)
      throw error
    }
  }

  /**
   * Train an RVC voice model
   */
  static async trainVoice(
    voiceId: string,
    tempFolder: string
  ): Promise<RVCTrainingResponse> {
    try {
      const response = await fetch(`${this.API_BASE}/${voiceId}/train`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tempFolder
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to start training')
      }
      
      return await response.json()
    } catch (error) {
      console.error('Error training RVC voice:', error)
      throw error
    }
  }

  /**
   * Get list of all RVC voices
   */
  static async getVoices(): Promise<RVCVoice[]> {
    try {
      const response = await fetch(`${this.API_BASE}/voices`)
      if (!response.ok) {
        throw new Error('Failed to fetch RVC voices')
      }
      
      const data = await response.json()
      return data.voices || []
    } catch (error) {
      console.error('Error fetching RVC voices:', error)
      throw error
    }
  }

  /**
   * Get singing test audio for an RVC voice
   */
  static async getSingingTest(voiceId: string): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/${voiceId}/sing`)
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to get singing test')
      }
      
      return await response.blob()
    } catch (error) {
      console.error('Error getting RVC singing test:', error)
      throw error
    }
  }

  /**
   * Play singing test audio
   */
  static async playSingingTest(voiceId: string): Promise<void> {
    try {
      const audioBlob = await this.getSingingTest(voiceId)
      
      // Create and play audio
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)
      
      audio.play()
      
      // Clean up URL after playing
      audio.onended = () => URL.revokeObjectURL(audioUrl)
      audio.onerror = () => URL.revokeObjectURL(audioUrl)
      
    } catch (error) {
      console.error('Error playing RVC singing test:', error)
      throw error
    }
  }

  /**
   * Validate recording duration for RVC training
   */
  static validateRecordingDuration(durationSeconds: number): { valid: boolean; error?: string } {
    const minDuration = 30 // 30 seconds minimum
    
    if (durationSeconds < minDuration) {
      return {
        valid: false,
        error: `Recording too short. Minimum ${minDuration} seconds required for voice cloning.`
      }
    }
    
    return { valid: true }
  }  /**
   * Validate uploaded files for RVC training
   */
  static validateUploadedFiles(files: File[]): { valid: boolean; error?: string } {
    if (files.length === 0) {
      return { valid: false, error: 'No files selected' }
    }

    // Check file types
    const allowedTypes = ['audio/wav', 'audio/mp3', 'audio/m4a', 'audio/webm']
    const invalidFiles = files.filter(file => !allowedTypes.includes(file.type))
    
    if (invalidFiles.length > 0) {
      return {
        valid: false,
        error: `Invalid file types: ${invalidFiles.map(f => f.name).join(', ')}. Only WAV, MP3, and M4A files are supported.`
      }
    }

    // Check total duration estimate (rough estimate based on file sizes)
    const totalSizeMB = files.reduce((sum, file) => sum + file.size, 0) / (1024 * 1024)
    const estimatedDurationMinutes = totalSizeMB * 2 // Rough estimate: 1MB ≈ 2 minutes of audio
    
    if (estimatedDurationMinutes < 10) {
      return {
        valid: false,
        error: 'Insufficient audio data. Please upload at least 10 minutes of audio for best results.'
      }
    }

    return { valid: true }
  }

  /**
   * Format file size for display
   */
  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes'
    
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  /**
   * Format duration for display
   */
  static formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    
    if (minutes === 0) {
      return `${remainingSeconds}s`
    }
    
    return `${minutes}m ${remainingSeconds}s`
  }

  /**
   * Check total file size and provide recommendations
   */
  static checkUploadSize(files: File[]): { 
    totalSizeMB: number; 
    recommendation: string; 
    shouldWarn: boolean 
  } {
    const totalBytes = files.reduce((sum, file) => sum + file.size, 0)
    const totalSizeMB = totalBytes / (1024 * 1024)
    
    let recommendation = ''
    let shouldWarn = false
    
    if (totalSizeMB > 800) { // Approaching 1GB limit
      recommendation = 'Very large upload detected. Consider uploading in smaller batches for better reliability.'
      shouldWarn = true
    } else if (totalSizeMB > 500) {
      recommendation = 'Large upload detected. Upload may take several minutes.'
      shouldWarn = true
    } else if (totalSizeMB > 100) {
      recommendation = 'Medium-sized upload. Perfect for high-quality voice training.'
    } else {
      recommendation = 'Small upload. Consider adding more audio for better voice clone quality.'
    }
    
    return {
      totalSizeMB: Math.round(totalSizeMB * 100) / 100,
      recommendation,
      shouldWarn
    }
  }
}
