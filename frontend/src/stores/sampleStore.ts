import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { sampleApiService, type BackendSample } from '../services/sampleApiService'

export interface LocalSample {
  id: string
  name: string
  url: string
  duration: number
  size: number
  type?: string
  category: SampleCategory
  tags: string[]
  bpm?: number
  key?: string
  createdAt: string
  waveform?: number[]
  sampleRate?: number
  channels?: number
  audioFeatures?: Record<string, any>
  isFromBackend?: boolean // Flag to indicate if sample is stored in backend
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

  // Load samples from files - uploads to backend and syncs local state
  const loadSamples = async (files: FileList | File[]) => {
    if (!files.length) return

    isLoading.value = true
    loadingProgress.value = 0

    try {
      // Convert FileList to FileList if needed
      const fileList = files instanceof FileList ? files : {
        length: files.length,
        item: (index: number) => files[index],
        [Symbol.iterator]: function* () {
          for (let i = 0; i < files.length; i++) {
            yield files[i]
          }
        }
      } as FileList

      // Upload files to backend
      const response = await sampleApiService.uploadSamples(fileList)
      
      if (response.success) {
        // Convert backend samples to local format and add to store
        const newSamples = response.samples.map(sampleApiService.backendToLocalSample)
        localSamples.value.push(...newSamples)
        
        loadingProgress.value = 100
        console.log(`Successfully loaded ${response.uploaded_count} samples`)
      }
    } catch (error) {
      console.error('Failed to load samples:', error)
      throw error
    } finally {
      isLoading.value = false
      loadingProgress.value = 0
    }
  }

  // Sync samples from backend
  const syncSamplesFromBackend = async () => {
    try {
      const response = await sampleApiService.getSamples({
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        category: selectedCategory.value !== 'uncategorized' ? selectedCategory.value : undefined,
        search: searchQuery.value || undefined
      })

      if (response.success) {
        localSamples.value = response.samples.map(sampleApiService.backendToLocalSample)
      }
    } catch (error) {
      console.error('Failed to sync samples from backend:', error)
    }
  }

  // Remove sample
  const removeSample = async (sampleId: string) => {
    try {
      // Remove from backend if it's a backend sample
      const sample = localSamples.value.find(s => s.id === sampleId)
      if (sample?.isFromBackend) {
        await sampleApiService.deleteSample(sampleId)
      }
      
      // Remove from local store
      const index = localSamples.value.findIndex(s => s.id === sampleId)
      if (index !== -1) {
        localSamples.value.splice(index, 1)
      }
    } catch (error) {
      console.error('Failed to remove sample:', error)
      throw error
    }
  }

  // Update sample category
  const updateSampleCategory = async (sampleId: string, category: SampleCategory) => {
    const sample = localSamples.value.find(s => s.id === sampleId)
    if (sample) {
      // Update local state immediately
      sample.category = category
      
      // Update backend if it's a backend sample
      if (sample.isFromBackend) {
        try {
          await sampleApiService.updateSample(sampleId, { category })
        } catch (error) {
          console.error('Failed to update sample category on backend:', error)
          // Optionally revert local change
        }
      }
    }
  }

  // Update sample tags
  const updateSampleTags = async (sampleId: string, tags: string[]) => {
    const sample = localSamples.value.find(s => s.id === sampleId)
    if (sample) {
      // Update local state immediately
      sample.tags = [...new Set(tags)] // Remove duplicates
      
      // Update backend if it's a backend sample
      if (sample.isFromBackend) {
        try {
          await sampleApiService.updateSample(sampleId, { tags })
        } catch (error) {
          console.error('Failed to update sample tags on backend:', error)
          // Optionally revert local change
        }
      }
    }
  }

  // Clear all samples
  const clearAllSamples = async () => {
    try {
      // If samples are from backend, delete them there too
      const backendSampleIds = localSamples.value
        .filter(sample => sample.isFromBackend)
        .map(sample => sample.id)
      
      if (backendSampleIds.length > 0) {
        await sampleApiService.bulkDeleteSamples(backendSampleIds)
      }
      
      // Clear local store
      localSamples.value = []
    } catch (error) {
      console.error('Failed to clear samples:', error)
      throw error
    }
  }

  // Initialize by syncing with backend
  const initializeStore = async () => {
    try {
      await syncSamplesFromBackend()
    } catch (error) {
      console.error('Failed to initialize sample store:', error)
    }
  }

  // Call on store init
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
    formatDuration
  }
})
