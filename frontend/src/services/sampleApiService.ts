/**
 * Sample API Service
 * Handles communication with the backend sample storage API
 */

export interface BackendSample {
  id: string
  name: string
  original_filename: string
  file_size: number
  duration: number
  sample_rate: number
  channels: number
  bpm?: number
  key?: string
  category: string
  waveform_data: number[]
  audio_features: Record<string, any>
  tags: string[]
  created_at: string
  updated_at: string
  url: string
}

export interface SampleUploadResponse {
  success: boolean
  samples: BackendSample[]
  uploaded_count: number
}

export interface SamplesResponse {
  success: boolean
  samples: BackendSample[]
  total_count: number
}

class SampleApiService {
  private baseUrl = '/api/samples'
  private userId = 'demo-user' // TODO: Get from auth store

  /**
   * Upload multiple sample files to the backend
   */
  async uploadSamples(files: FileList): Promise<SampleUploadResponse> {
    const formData = new FormData()
    
    // Add all files to form data
    Array.from(files).forEach(file => {
      formData.append('files', file)
    })

    const response = await fetch(`${this.baseUrl}/upload`, {
      method: 'POST',
      headers: {
        'X-User-ID': this.userId
      },
      body: formData
    })

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get all samples for the current user
   */
  async getSamples(filters?: {
    category?: string
    search?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  }): Promise<SamplesResponse> {
    const params = new URLSearchParams()
    
    if (filters?.category) params.append('category', filters.category)
    if (filters?.search) params.append('search', filters.search)
    if (filters?.sort_by) params.append('sort_by', filters.sort_by)
    if (filters?.sort_order) params.append('sort_order', filters.sort_order)

    const response = await fetch(`${this.baseUrl}?${params}`, {
      headers: {
        'X-User-ID': this.userId
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch samples: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get a specific sample by ID
   */
  async getSample(sampleId: string): Promise<{ success: boolean; sample: BackendSample }> {
    const response = await fetch(`${this.baseUrl}/${sampleId}`, {
      headers: {
        'X-User-ID': this.userId
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch sample: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Update sample metadata
   */
  async updateSample(sampleId: string, data: {
    name?: string
    category?: string
    bpm?: number
    key?: string
    tags?: string[]
  }): Promise<{ success: boolean; sample: BackendSample }> {
    const response = await fetch(`${this.baseUrl}/${sampleId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': this.userId
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      throw new Error(`Failed to update sample: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Delete a sample
   */
  async deleteSample(sampleId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${this.baseUrl}/${sampleId}`, {
      method: 'DELETE',
      headers: {
        'X-User-ID': this.userId
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to delete sample: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Delete multiple samples
   */
  async bulkDeleteSamples(sampleIds: string[]): Promise<{ success: boolean; deleted_count: number; message: string }> {
    const response = await fetch(`${this.baseUrl}/bulk-delete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': this.userId
      },
      body: JSON.stringify({ sample_ids: sampleIds })
    })

    if (!response.ok) {
      throw new Error(`Failed to delete samples: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get available categories
   */
  async getCategories(): Promise<{ success: boolean; categories: string[] }> {
    const response = await fetch(`${this.baseUrl}/categories`)

    if (!response.ok) {
      throw new Error(`Failed to fetch categories: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get available tags
   */
  async getTags(): Promise<{ success: boolean; tags: Array<{ id: string; name: string }> }> {
    const response = await fetch(`${this.baseUrl}/tags`)

    if (!response.ok) {
      throw new Error(`Failed to fetch tags: ${response.statusText}`)
    }

    return response.json()
  }

  /**
   * Get the URL for a sample's audio file
   */
  getSampleAudioUrl(sampleId: string): string {
    return `${this.baseUrl}/${sampleId}/audio`
  }

  /**
   * Convert backend sample to frontend LocalSample format
   */
  backendToLocalSample(backendSample: BackendSample) {
    return {
      id: backendSample.id,
      name: backendSample.name,
      url: this.getSampleAudioUrl(backendSample.id),
      duration: backendSample.duration,
      size: backendSample.file_size,
      waveform: backendSample.waveform_data,
      category: backendSample.category as any,
      tags: backendSample.tags,
      bpm: backendSample.bpm,
      key: backendSample.key,
      createdAt: backendSample.created_at,
      sampleRate: backendSample.sample_rate,
      channels: backendSample.channels,
      audioFeatures: backendSample.audio_features
    }
  }
}

export const sampleApiService = new SampleApiService()
