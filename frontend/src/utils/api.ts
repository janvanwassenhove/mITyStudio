/**
 * API Utility Functions
 * Centralized API communication with the backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

interface ApiKeyStatusResponse {
  provider: string
  api_key_set: boolean
  env_var: string
}

interface AllApiKeyStatusResponse {
  [key: string]: {
    api_key_set: boolean
    env_var: string
  }
}

/**
 * Check API key status for a specific provider
 */
export const checkApiKeyStatus = async (provider: string): Promise<ApiKeyStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/ai/api-key-status?provider=${provider.toLowerCase()}`)
  
  if (!response.ok) {
    throw new Error(`Failed to check API key status: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Check API key status for all providers
 */
export const checkAllApiKeyStatus = async (): Promise<AllApiKeyStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/ai/api-key-status/all`)
  
  if (!response.ok) {
    throw new Error(`Failed to check all API key status: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Send chat message to AI
 */
export const sendChatMessage = async (
  message: string,
  provider: string,
  model: string,
  context?: any
) => {
  const response = await fetch(`${API_BASE_URL}/ai/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      provider: provider.toLowerCase(),
      model,
      context
    })
  })
  
  if (!response.ok) {
    throw new Error(`Failed to send chat message: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Get available instruments from sample library for a given category
 */
export const getSampleInstruments = async (category: string) => {
  const response = await fetch(`${API_BASE_URL}/ai/samples/instruments/${category}`)
  if (!response.ok) {
    throw new Error(`Failed to get sample instruments: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Get available chords for a specific instrument in a category
 * If you reference instrument sample paths, include category between instruments and instrument name.
 */
export const getInstrumentChords = async (category: string, instrument: string) => {
  const response = await fetch(`${API_BASE_URL}/ai/samples/instruments/${category}/${instrument}/chords`)
  
  if (!response.ok) {
    throw new Error(`Failed to get instrument chords: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Suggest chord progression for an instrument
 */
export const suggestChordProgression = async (
  category: string,
  instrument: string,
  genre: string = 'pop',
  key: string = 'C',
  mood: string = 'happy'
) => {
  const response = await fetch(`${API_BASE_URL}/ai/samples/suggest-progression`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      category,
      instrument,
      genre,
      key,
      mood
    })
  })
  
  if (!response.ok) {
    throw new Error(`Failed to suggest chord progression: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Generate smart chord progression using AI and sample library
 */
export const generateSmartProgression = async (
  category: string,
  instrument: string,
  genre: string = 'pop',
  key: string = 'C',
  mood: string = 'happy',
  complexity: string = 'simple',
  numChords: number = 4
) => {
  const response = await fetch(`${API_BASE_URL}/ai/generate/smart-progression`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      category,
      instrument,
      genre,
      key,
      mood,
      complexity,
      num_chords: numChords
    })
  })
  
  if (!response.ok) {
    throw new Error(`Failed to generate smart progression: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Get all instruments grouped by category for the instrument selection dialog
 */
export const getAllSampleInstruments = async () => {
  const response = await fetch(`${API_BASE_URL}/ai/samples/instruments/all`)
  if (!response.ok) {
    throw new Error(`Failed to get all sample instruments: ${response.statusText}`)
  }
  return response.json()
}
