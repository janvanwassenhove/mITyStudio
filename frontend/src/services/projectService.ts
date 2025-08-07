/**
 * Project Service
 * Handles communication with the backend project API
 */

export interface Project {
  id: string
  name: string
  description: string
  genre: string
  tempo: number
  key: string
  time_signature: [number, number]
  duration: number
  user_id: string
  track_count: number
  created_at: string
  updated_at: string
  tags: string[]
  is_public: boolean
}

export interface Track {
  id: string
  project_id: string
  name: string
  instrument: string
  volume: number
  pan: number
  muted: boolean
  soloed: boolean
  order: number
  effects: any
  created_at: string
  updated_at: string
}

export interface AudioClip {
  id: string
  track_id: string
  start_time: number
  duration: number
  type: string
  instrument: string
  volume: number
  effects: any
  midi_data?: any
  text?: string
  lyrics?: any
  voice_id?: string
  created_at: string
  updated_at: string
}

class ProjectService {
  private baseUrl = '/api/projects'

  /**
   * Get all projects for the current user
   */
  async getProjects(page = 1, perPage = 10, userId = 'default'): Promise<{
    projects: Project[]
    pagination: {
      page: number
      per_page: number
      total: number
      pages: number
    }
  }> {
    const response = await fetch(`${this.baseUrl}?page=${page}&per_page=${perPage}&user_id=${userId}`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch projects: ${response.statusText}`)
    }
    
    return await response.json()
  }

  /**
   * Get a specific project by ID
   */
  async getProject(projectId: string): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/${projectId}`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch project: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.project
  }

  /**
   * Create a new project
   */
  async createProject(projectData: {
    name: string
    description?: string
    genre?: string
    tempo?: number
    key?: string
    time_signature?: [number, number]
    user_id?: string
  }): Promise<Project> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(projectData)
    })
    
    if (!response.ok) {
      throw new Error(`Failed to create project: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.project
  }

  /**
   * Create a project from a generated song structure
   */
  async createProjectFromSongStructure(songStructure: any, userId = 'default'): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/from-song-structure`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        song_structure: songStructure,
        user_id: userId
      })
    })
    
    if (!response.ok) {
      throw new Error(`Failed to create project from song structure: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.project
  }

  /**
   * Update an existing project
   */
  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/${projectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updates)
    })
    
    if (!response.ok) {
      throw new Error(`Failed to update project: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.project
  }

  /**
   * Update a project with a new song structure
   */
  async updateProjectFromSongStructure(projectId: string, songStructure: any): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/${projectId}/update-from-song-structure`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        song_structure: songStructure
      })
    })
    
    if (!response.ok) {
      throw new Error(`Failed to update project from song structure: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.project
  }

  /**
   * Delete a project
   */
  async deleteProject(projectId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/${projectId}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error(`Failed to delete project: ${response.statusText}`)
    }
  }

  /**
   * Get tracks for a project
   */
  async getProjectTracks(projectId: string): Promise<Track[]> {
    const response = await fetch(`${this.baseUrl}/${projectId}/tracks`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch project tracks: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.tracks
  }

  /**
   * Get clips for a track
   */
  async getTrackClips(projectId: string, trackId: string): Promise<AudioClip[]> {
    const response = await fetch(`${this.baseUrl}/${projectId}/tracks/${trackId}/clips`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch track clips: ${response.statusText}`)
    }
    
    const data = await response.json()
    return data.clips
  }

  /**
   * Export project as JSON
   */
  async exportProject(projectId: string, includeAudio = false): Promise<any> {
    const response = await fetch(`${this.baseUrl}/${projectId}/export?format=json&include_audio=${includeAudio}`)
    
    if (!response.ok) {
      throw new Error(`Failed to export project: ${response.statusText}`)
    }
    
    return await response.json()
  }
}

export const projectService = new ProjectService()
