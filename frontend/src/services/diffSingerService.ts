export interface VoiceProfile {
  id: string
  name: string
  type: 'builtin' | 'custom'
  trained: boolean
  modelPath?: string
  configPath?: string
  createdAt?: string
}

export interface TrainingJob {
  id: string
  voiceId: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  audioFiles: string[]
  estimated_time_remaining?: string
  elapsed_time?: string
  transcriptions?: Array<{
    audio_file: string
    text: string
    confidence: number
    engine: string
    language?: string
    transcription_file?: string
    error?: string
  }>
  logs?: string[]
  error?: string
}

export class DiffSingerService {
  private static readonly API_BASE = 'http://localhost:5000/api/voice'

  // Voice Management
  static async getAvailableVoices(): Promise<VoiceProfile[]> {
    try {
      const response = await fetch(`${this.API_BASE}/voices`)
      if (!response.ok) throw new Error('Failed to fetch voices')
      const data = await response.json()
      // Extract voices array from the response
      return data.voices || []
    } catch (error) {
      console.error('Error fetching voices:', error)
      // Return default voices for now
      return [
        { id: 'default', name: 'Default Voice', type: 'builtin', trained: true },
        { id: 'male-01', name: 'Male Voice 1', type: 'builtin', trained: true },
        { id: 'female-01', name: 'Female Voice 1', type: 'builtin', trained: true }
      ]
    }
  }

  static async deleteVoice(voiceId: string): Promise<void> {
    try {
      const response = await fetch(`${this.API_BASE}/voices/${voiceId}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to delete voice')
    } catch (error) {
      console.error('Error deleting voice:', error)
      throw error
    }
  }

  // Voice Training
  static async trainVoiceFromRecording(
    voiceName: string, 
    audioBlob: Blob,
    options?: { 
      sampleRate?: number
      duration?: number
      language?: string 
    }
  ): Promise<string> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      
      // Determine the proper filename and MIME type based on the blob
      let filename = 'recording.webm'
      if (audioBlob.type === 'audio/wav') {
        filename = 'recording.wav'
      } else if (audioBlob.type === 'audio/mp3') {
        filename = 'recording.mp3'
      }
      
      formData.append('audio', audioBlob, filename)
      
      if (options) {
        Object.entries(options).forEach(([key, value]) => {
          formData.append(key, value.toString())
        })
      }

      console.log(`🚀 Sending voice training request: ${voiceName}`)
      console.log(`📎 Audio file: ${filename} (${audioBlob.size} bytes, ${audioBlob.type})`)

      const response = await fetch(`${this.API_BASE}/train/recording`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Failed to start training')
      
      const result = await response.json()
      console.log(`✅ Training started successfully: Job ID ${result.jobId}`)
      return result.jobId
    } catch (error) {
      console.error('Error training voice from recording:', error)
      throw error
    }
  }

  static async trainVoiceFromFiles(
    voiceName: string,
    audioFiles: File[],
    options?: {
      language?: string
      speakerEmbedding?: boolean
      epochs?: number
    }
  ): Promise<string> {
    try {
      const formData = new FormData()
      formData.append('voiceName', voiceName)
      
      audioFiles.forEach((file, index) => {
        formData.append(`audio_${index}`, file)
      })

      if (options) {
        Object.entries(options).forEach(([key, value]) => {
          formData.append(key, value.toString())
        })
      }

      const response = await fetch(`${this.API_BASE}/train/files`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Failed to start training')
      
      const result = await response.json()
      return result.jobId
    } catch (error) {
      console.error('Error training voice from files:', error)
      throw error
    }
  }

  // Training Status
  static async getTrainingStatus(jobId: string): Promise<TrainingJob> {
    try {
      const response = await fetch(`${this.API_BASE}/training/${jobId}`)
      if (response.status === 404) {
        throw new Error(`Training job ${jobId} not found. The job may have expired or the server was restarted.`)
      }
      if (!response.ok) throw new Error('Failed to get training status')
      return await response.json()
    } catch (error) {
      console.error('Error getting training status:', error)
      throw error
    }
  }

  static async cancelTraining(jobId: string): Promise<void> {
    try {
      const response = await fetch(`${this.API_BASE}/training/${jobId}/cancel`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to cancel training')
    } catch (error) {
      console.error('Error canceling training:', error)
      throw error
    }
  }

  // Voice Synthesis
  static async synthesizeVoice(
    text: string,
    voiceId: string,
    options?: {
      speed?: number
      pitch?: number
      volume?: number
      emotionStyle?: string
      notes?: string[]
      chordName?: string
      startTime?: number
      duration?: number
    }
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text,
          voiceId,
          ...options
        })
      })

      if (!response.ok) throw new Error('Failed to synthesize voice')
      return await response.blob()
    } catch (error) {
      console.error('Error synthesizing voice:', error)
      throw error
    }
  }

  // Voice Testing
  static async testVoice(
    voiceId: string,
    testText?: string
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/test/${voiceId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: testText // If undefined, backend will use default "mitystudio forever"
        })
      })

      if (!response.ok) throw new Error('Failed to test voice')
      return await response.blob()
    } catch (error) {
      console.error('Error testing voice:', error)
      throw error
    }
  }

  // Voice Testing - Spoken
  static async testVoiceSpoken(
    voiceId: string,
    testText?: string
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/test/${voiceId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: testText, // If undefined, backend will use default "mitystudio forever"
          spoken: true    // Force spoken voice mode
        })
      })

      if (!response.ok) throw new Error('Failed to test spoken voice')
      return await response.blob()
    } catch (error) {
      console.error('Error testing spoken voice:', error)
      throw error
    }
  }

  // Voice Testing - Singing
  static async testVoiceSinging(
    voiceId: string,
    testText?: string,
    notes?: string[],
    chordName?: string
  ): Promise<Blob> {
    try {
      const response = await fetch(`${this.API_BASE}/test-singing/${voiceId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: testText,
          notes: notes,
          chordName: chordName
        })
      })

      if (!response.ok) throw new Error('Failed to test singing voice')
      return await response.blob()
    } catch (error) {
      console.error('Error testing singing voice:', error)
      throw error
    }
  }

  // Validation
  static validateAudioFile(file: File): { valid: boolean; error?: string } {
    const allowedTypes = ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/m4a', 'audio/webm']
    const maxSize = 50 * 1024 * 1024 // 50MB

    if (!allowedTypes.includes(file.type)) {
      return { 
        valid: false, 
        error: `Unsupported file type: ${file.type}. Please use WAV, MP3, or M4A.` 
      }
    }

    if (file.size > maxSize) {
      return { 
        valid: false, 
        error: `File too large: ${Math.round(file.size / 1024 / 1024)}MB. Maximum size is 50MB.` 
      }
    }

    return { valid: true }
  }

  static validateRecording(duration: number): { valid: boolean; error?: string } {
    const minDuration = 10 // 10 seconds minimum
    const maxDuration = 2100 // 35 minutes maximum

    if (duration < minDuration) {
      return { 
        valid: false, 
        error: `Recording too short: ${duration}s. Minimum duration is ${minDuration}s.` 
      }
    }

    if (duration > maxDuration) {
      return { 
        valid: false, 
        error: `Recording too long: ${duration}s. Maximum duration is ${maxDuration}s.` 
      }
    }

    return { valid: true }
  }
}
