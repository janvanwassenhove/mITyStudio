import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { sampleIndexedDB } from '../services/sampleIndexedDB'
import { storeSampleMetadata, storeBulkSampleMetadata } from '../utils/api'

export interface LocalSample {
  id: string
  name: string
  file?: File // Optional since it may not be available after restoration
  fileId: string // Reference to IndexedDB stored file
  url: string
  duration: number
  size: number
  type: string
  category: SampleCategory
  tags: string[]
  bpm?: number
  key?: string
  createdAt: string
  waveform?: number[]
}

export type SampleCategory = 
  | 'drums' 
  | 'bass' 
  | 'melodic' 
  | 'vocals' 
  | 'fx' 
  | 'loops' 
  | 'oneshots' 
  | 'ambient' 
  | 'percussion'
  | 'uncategorized'

export interface SampleLibrary {
  [category: string]: LocalSample[]
}

export const useSampleStore = defineStore('samples', () => {
  // State
  const localSamples = ref<LocalSample[]>([])
  const isLoading = ref(false)
  const loadingProgress = ref(0)
  const selectedCategory = ref<SampleCategory>('uncategorized')
  const searchQuery = ref('')
  const sortBy = ref<'name' | 'date' | 'duration' | 'size'>('name')
  const sortOrder = ref<'asc' | 'desc'>('asc')

  // Audio context for analysis
  let audioContext: AudioContext | null = null

  // Computed
  const sampleLibrary = computed<SampleLibrary>(() => {
    const library: SampleLibrary = {};
    localSamples.value.forEach(sample => {
      if (!library[sample.category]) {
        library[sample.category] = [];
      }
      library[sample.category].push(sample);
    });
    return library;
  })

  const filteredSamples = computed(() => {
    let samples = selectedCategory.value === 'uncategorized'
      ? localSamples.value
      : localSamples.value.filter(s => s.category === selectedCategory.value)

    // Apply search filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      samples = samples.filter(sample => 
        sample.name.toLowerCase().includes(query) ||
        sample.tags.some(tag => tag.toLowerCase().includes(query))
      )
    }

    // Apply sorting
    samples.sort((a, b) => {
      let aValue: any, bValue: any
      
      switch (sortBy.value) {
        case 'name':
          aValue = a.name.toLowerCase()
          bValue = b.name.toLowerCase()
          break
        case 'date':
          aValue = new Date(a.createdAt).getTime()
          bValue = new Date(b.createdAt).getTime()
          break
        case 'duration':
          aValue = a.duration
          bValue = b.duration
          break
        case 'size':
          aValue = a.size
          bValue = b.size
          break
        default:
          return 0
      }

      if (sortOrder.value === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0
      }
    })

    return samples
  })

  const categories = computed(() => {
    const cats = new Set<SampleCategory>()
    localSamples.value.forEach(sample => cats.add(sample.category))
    return Array.from(cats).sort()
  })

  const totalSamples = computed(() => localSamples.value.length)
  const totalSize = computed(() => 
    localSamples.value.reduce((sum, sample) => sum + sample.size, 0)
  )

  // Initialize audio context
  const initAudioContext = async () => {
    if (!audioContext) {
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    }
    
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }
  }

  // Analyze audio file to extract metadata
  const analyzeAudioFile = async (file: File): Promise<{
    duration: number
    bpm?: number
    key?: string
    waveform?: number[]
  }> => {
    try {
      await initAudioContext()
      if (!audioContext) throw new Error('Audio context not available')

      const arrayBuffer = await file.arrayBuffer()
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
      
      const duration = audioBuffer.duration
      const channelData = audioBuffer.getChannelData(0)
      
      // Generate simplified waveform (downsample for visualization)
      const waveformLength = 1200 // Increased from 200 for smoother waveform
      const blockSize = Math.floor(channelData.length / waveformLength)
      const waveform: number[] = []
      
      for (let i = 0; i < waveformLength; i++) {
        let sum = 0
        for (let j = 0; j < blockSize; j++) {
          sum += Math.abs(channelData[i * blockSize + j] || 0)
        }
        waveform.push(sum / blockSize)
      }

      // Basic BPM detection (simplified)
      const bpm = detectBPM(channelData, audioBuffer.sampleRate)
      
      return {
        duration,
        bpm,
        waveform
      }
    } catch (error) {
      console.warn('Audio analysis failed:', error)
      return { duration: 0 }
    }
  }

  // Simple BPM detection algorithm
  const detectBPM = (channelData: Float32Array, sampleRate: number): number | undefined => {
    try {
      // This is a simplified BPM detection - in a real app you'd use more sophisticated algorithms
      const windowSize = Math.floor(sampleRate * 0.1) // 100ms windows
      const energyWindows: number[] = []
      
      for (let i = 0; i < channelData.length - windowSize; i += windowSize) {
        let energy = 0
        for (let j = 0; j < windowSize; j++) {
          energy += channelData[i + j] * channelData[i + j]
        }
        energyWindows.push(energy)
      }
      
      // Find peaks in energy
      const peaks: number[] = []
      for (let i = 1; i < energyWindows.length - 1; i++) {
        if (energyWindows[i] > energyWindows[i - 1] && energyWindows[i] > energyWindows[i + 1]) {
          peaks.push(i)
        }
      }
      
      if (peaks.length < 2) return undefined
      
      // Calculate average interval between peaks
      const intervals: number[] = []
      for (let i = 1; i < peaks.length; i++) {
        intervals.push(peaks[i] - peaks[i - 1])
      }
      
      const avgInterval = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length
      const timePerWindow = windowSize / sampleRate
      const beatsPerSecond = 1 / (avgInterval * timePerWindow)
      const bpm = Math.round(beatsPerSecond * 60)
      
      // Return BPM if it's in a reasonable range
      return (bpm >= 60 && bpm <= 200) ? bpm : undefined
    } catch (error) {
      return undefined
    }
  }

  // Categorize sample based on filename and audio characteristics
  const categorizeSample = (file: File, audioData: any): SampleCategory => {
    const name = file.name.toLowerCase()
    const { duration, bpm } = audioData

    // Keyword-based categorization
    const keywords = {
      drums: ['kick', 'snare', 'hihat', 'hat', 'cymbal', 'tom', 'clap', 'rim', 'perc'],
      bass: ['bass', 'sub', '808', 'low'],
      melodic: ['piano', 'guitar', 'synth', 'lead', 'melody', 'chord', 'arp'],
      vocals: ['vocal', 'voice', 'singing', 'rap', 'spoken', 'choir'],
      fx: ['fx', 'effect', 'sweep', 'riser', 'impact', 'crash', 'whoosh'],
      loops: ['loop', 'full', 'mix', 'beat'],
      ambient: ['ambient', 'pad', 'atmosphere', 'drone', 'texture'],
      percussion: ['perc', 'shaker', 'tambourine', 'conga', 'bongo']
    }

    // Check keywords first
    for (const [category, words] of Object.entries(keywords)) {
      if (words.some(word => name.includes(word))) {
        return category as SampleCategory
      }
    }

    // Duration-based categorization
    if (duration) {
      if (duration < 2) {
        return 'oneshots'
      } else if (duration > 8) {
        return 'loops'
      }
    }

    // BPM-based hints
    if (bpm) {
      if (bpm >= 120 && bpm <= 140 && duration > 4) {
        return 'loops'
      }
    }

    return 'uncategorized'
  }

  // Generate tags for sample
  const generateTags = (file: File, category: SampleCategory, audioData: any): string[] => {
    const tags: string[] = []
    const name = file.name.toLowerCase()
    const { duration, bpm, key } = audioData

    // Add category as tag
    tags.push(category)

    // Duration-based tags
    if (duration) {
      if (duration < 1) tags.push('short')
      else if (duration < 5) tags.push('medium')
      else tags.push('long')
    }

    // BPM-based tags
    if (bpm) {
      tags.push(`${bpm}bpm`)
      if (bpm < 90) tags.push('slow')
      else if (bpm < 120) tags.push('medium-tempo')
      else if (bpm < 140) tags.push('fast')
      else tags.push('very-fast')
    }

    // Key-based tags
    if (key) {
      tags.push(key)
    }

    // File format
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (extension) {
      tags.push(extension)
    }

    // Common descriptive words from filename
    const descriptiveWords = name.match(/\b(dry|wet|clean|dirty|deep|bright|dark|warm|cold|hard|soft|punchy|smooth)\b/g)
    if (descriptiveWords) {
      tags.push(...descriptiveWords)
    }

    return [...new Set(tags)] // Remove duplicates
  }

  // Load samples from files
  const loadSamples = async (files: FileList | File[]) => {
    if (!files.length) return

    isLoading.value = true
    loadingProgress.value = 0

    const fileArray = Array.from(files)
    const validFiles = fileArray.filter(file => 
      file.type.startsWith('audio/') || 
      /\.(mp3|wav|ogg|m4a|aac|flac)$/i.test(file.name)
    )

    if (validFiles.length === 0) {
      isLoading.value = false
      throw new Error('No valid audio files found')
    }

    const newSamples: LocalSample[] = []

    for (let i = 0; i < validFiles.length; i++) {
      const file = validFiles[i]
      
      try {
        // Store file in IndexedDB first
        const fileId = await sampleIndexedDB.storeFile(file)
        
        // Create object URL for immediate playback
        const url = URL.createObjectURL(file)
        
        // Analyze audio file
        const audioData = await analyzeAudioFile(file)
        
        // Categorize sample
        const category = categorizeSample(file, audioData)
        
        // Generate tags
        const tags = generateTags(file, category, audioData)
        
        const sample: LocalSample = {
          id: `local-${Date.now()}-${i}`,
          name: file.name.replace(/\.[^/.]+$/, ''), // Remove extension
          file,
          fileId, // Store IndexedDB reference
          url,
          duration: audioData.duration,
          size: file.size,
          type: file.type || 'audio/unknown',
          category,
          tags,
          bpm: audioData.bpm,
          key: audioData.key,
          waveform: audioData.waveform,
          createdAt: new Date().toISOString()
        }
        
        newSamples.push(sample)
        
      } catch (error) {
        console.warn(`Failed to process ${file.name}:`, error)
      }
      
      loadingProgress.value = ((i + 1) / validFiles.length) * 100
    }

    // Add to store
    localSamples.value.push(...newSamples)
    
    // Sync metadata with backend for AI agents
    try {
      await syncSampleMetadataToBackend(newSamples)
    } catch (error) {
      console.warn('Failed to sync sample metadata to backend:', error)
    }
    
    isLoading.value = false
    loadingProgress.value = 0

    return newSamples
  }

  // Sync sample metadata to backend for AI agent awareness
  const syncSampleMetadataToBackend = async (samples: LocalSample[]) => {
    try {
      const metadataToSync = samples.map(sample => ({
        id: sample.id,
        name: sample.name,
        duration: sample.duration,
        category: sample.category,
        tags: sample.tags,
        bpm: sample.bpm,
        key: sample.key,
        waveform: sample.waveform,
        createdAt: sample.createdAt,
        updatedAt: new Date().toISOString()
      }))

      if (metadataToSync.length === 1) {
        await storeSampleMetadata(metadataToSync[0])
      } else if (metadataToSync.length > 1) {
        await storeBulkSampleMetadata(metadataToSync)
      }

      console.log(`Synced ${metadataToSync.length} sample(s) metadata to backend`)
    } catch (error) {
      console.error('Error syncing sample metadata to backend:', error)
      throw error
    }
  }

  // Sync all existing samples to backend
  const syncAllSamplesToBackend = async () => {
    try {
      await syncSampleMetadataToBackend(localSamples.value)
    } catch (error) {
      console.warn('Failed to sync all samples to backend:', error)
    }
  }

  // Remove sample
  const removeSample = async (sampleId: string) => {
    const index = localSamples.value.findIndex(s => s.id === sampleId)
    if (index !== -1) {
      const sample = localSamples.value[index]
      
      // Clean up object URL
      if (sample.url) {
        URL.revokeObjectURL(sample.url)
      }
      
      // Remove from IndexedDB
      try {
        await sampleIndexedDB.deleteFile(sample.fileId)
      } catch (error) {
        console.warn(`Failed to delete file from IndexedDB: ${error}`)
      }
      
      // Remove from store
      localSamples.value.splice(index, 1)
    }
  }

  // Update sample category
  const updateSampleCategory = (sampleId: string, category: SampleCategory) => {
    const sample = localSamples.value.find(s => s.id === sampleId)
    if (sample) {
      sample.category = category
      // Update tags to include new category
      if (!sample.tags.includes(category)) {
        sample.tags.push(category)
      }
    }
  }

  // Update sample tags
  const updateSampleTags = (sampleId: string, tags: string[]) => {
    const sample = localSamples.value.find(s => s.id === sampleId)
    if (sample) {
      sample.tags = [...new Set(tags)] // Remove duplicates
    }
  }

  // Clear all samples
  const clearAllSamples = async () => {
    // Clean up object URLs
    localSamples.value.forEach(sample => {
      if (sample.url) {
        URL.revokeObjectURL(sample.url)
      }
    })
    
    // Clear from IndexedDB
    try {
      await sampleIndexedDB.clearAllFiles()
    } catch (error) {
      console.warn(`Failed to clear IndexedDB: ${error}`)
    }
    
    // Clear from store
    localSamples.value = []
  }

  // Export sample library
  const exportSampleLibrary = () => {
    const exportData = localSamples.value.map(sample => ({
      id: sample.id,
      name: sample.name,
      duration: sample.duration,
      size: sample.size,
      type: sample.type,
      category: sample.category,
      tags: sample.tags,
      bpm: sample.bpm,
      key: sample.key,
      createdAt: sample.createdAt
    }))
    
    return JSON.stringify(exportData, null, 2)
  }

  // Get sample by ID
  const getSample = (sampleId: string) => {
    return localSamples.value.find(s => s.id === sampleId)
  }

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Format duration
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // --- Persistence helpers ---
  const SAMPLES_STORAGE_KEY = 'mitystudio_samples_v1'

  // Save sample metadata to localStorage (excluding File objects)
  const saveSamplesToStorage = () => {
    const metadata = localSamples.value.map(sample => {
      const { file, ...meta } = sample
      return meta
    })
    localStorage.setItem(SAMPLES_STORAGE_KEY, JSON.stringify(metadata))
  }

  // Load sample metadata from localStorage and restore from IndexedDB
  const loadSamplesFromStorage = async () => {
    const raw = localStorage.getItem(SAMPLES_STORAGE_KEY)
    if (!raw) return
    
    try {
      const metadata = JSON.parse(raw)
      if (Array.isArray(metadata)) {
        const restoredSamples: LocalSample[] = []
        
        for (const meta of metadata) {
          try {
            // Try to restore the blob URL from IndexedDB
            const url = await sampleIndexedDB.createBlobURL(meta.fileId)
            
            if (url) {
              restoredSamples.push({
                ...meta,
                file: undefined, // File object not available after restoration
                url // Restored blob URL
              })
            } else {
              console.warn(`Could not restore file for sample: ${meta.name}`)
              // Keep the sample but without a working URL
              restoredSamples.push({
                ...meta,
                file: undefined,
                url: '' // No working URL
              })
            }
          } catch (error) {
            console.warn(`Failed to restore sample ${meta.name}:`, error)
          }
        }
        
        localSamples.value = restoredSamples
        console.log(`Restored ${restoredSamples.length} samples from storage`)
      }
    } catch (e) {
      console.warn('Failed to load samples from storage:', e)
    }
  }

  // Get storage usage information
  const getStorageInfo = async () => {
    try {
      const indexedDBInfo = await sampleIndexedDB.getStorageInfo()
      const localStorageSize = localStorage.getItem(SAMPLES_STORAGE_KEY)?.length || 0
      
      return {
        indexedDB: indexedDBInfo,
        localStorage: {
          metadataSize: localStorageSize * 2, // Approximate size in bytes (UTF-16)
          samples: localSamples.value.length
        },
        total: {
          samples: localSamples.value.length,
          estimatedSize: indexedDBInfo.estimatedSize
        }
      }
    } catch (error) {
      console.warn('Failed to get storage info:', error)
      return null
    }
  }

  // Restore a specific sample's file data
  const restoreSampleFile = async (sampleId: string): Promise<File | null> => {
    const sample = localSamples.value.find(s => s.id === sampleId)
    if (!sample || !sample.fileId) return null
    
    try {
      const file = await sampleIndexedDB.getFile(sample.fileId)
      if (file) {
        sample.file = file
        // Update URL if needed
        if (!sample.url) {
          sample.url = URL.createObjectURL(file)
        }
      }
      return file
    } catch (error) {
      console.warn(`Failed to restore file for sample ${sample.name}:`, error)
      return null
    }
  }

  // Watch for changes and persist metadata
  watch(localSamples, saveSamplesToStorage, { deep: true })

  // Initialize store - load samples from storage
  const initializeStore = async () => {
    try {
      await sampleIndexedDB.init()
      await loadSamplesFromStorage()
    } catch (error) {
      console.warn('Failed to initialize sample store:', error)
    }
  }

  // Call initialization
  initializeStore()

  return {
    // State
    localSamples,
    isLoading,
    loadingProgress,
    selectedCategory,
    searchQuery,
    sortBy,
    sortOrder,

    // Computed
    sampleLibrary,
    filteredSamples,
    categories,
    totalSamples,
    totalSize,

    // Actions
    loadSamples,
    removeSample,
    updateSampleCategory,
    updateSampleTags,
    clearAllSamples,
    exportSampleLibrary,
    getSample,
    formatFileSize,
    formatDuration,
    getStorageInfo,
    restoreSampleFile,
    syncSampleMetadataToBackend,
    syncAllSamplesToBackend
  }
})
