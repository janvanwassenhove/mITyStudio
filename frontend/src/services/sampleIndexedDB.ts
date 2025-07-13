/**
 * IndexedDB service for storing audio sample files
 * Provides persistent storage for large audio files with better performance than localStorage
 */

export interface StoredSampleFile {
  id: string
  name: string
  data: ArrayBuffer
  type: string
  size: number
  lastModified: number
  createdAt: string
}

export class SampleIndexedDB {
  private dbName = 'mITyStudioSamples'
  private version = 1
  private db: IDBDatabase | null = null

  /**
   * Initialize the IndexedDB database
   */
  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version)
      
      request.onerror = () => reject(request.error)
      request.onsuccess = () => {
        this.db = request.result
        resolve()
      }
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        
        // Create object store for sample files
        if (!db.objectStoreNames.contains('sampleFiles')) {
          const store = db.createObjectStore('sampleFiles', { keyPath: 'id' })
          store.createIndex('name', 'name', { unique: false })
          store.createIndex('type', 'type', { unique: false })
          store.createIndex('createdAt', 'createdAt', { unique: false })
        }
      }
    })
  }

  /**
   * Store a file in IndexedDB
   */
  async storeFile(file: File): Promise<string> {
    if (!this.db) await this.init()
    
    const fileId = `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const arrayBuffer = await file.arrayBuffer()
    
    const storedFile: StoredSampleFile = {
      id: fileId,
      name: file.name,
      data: arrayBuffer,
      type: file.type,
      size: file.size,
      lastModified: file.lastModified || Date.now(),
      createdAt: new Date().toISOString()
    }

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readwrite')
      const store = transaction.objectStore('sampleFiles')
      const request = store.add(storedFile)
      
      request.onsuccess = () => resolve(fileId)
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Retrieve a file from IndexedDB and convert to File object
   */
  async getFile(fileId: string): Promise<File | null> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readonly')
      const store = transaction.objectStore('sampleFiles')
      const request = store.get(fileId)
      
      request.onsuccess = () => {
        const result = request.result as StoredSampleFile
        if (result) {
          const file = new File([result.data], result.name, {
            type: result.type,
            lastModified: result.lastModified
          })
          resolve(file)
        } else {
          resolve(null)
        }
      }
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Create a blob URL from stored file data
   */
  async createBlobURL(fileId: string): Promise<string | null> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readonly')
      const store = transaction.objectStore('sampleFiles')
      const request = store.get(fileId)
      
      request.onsuccess = () => {
        const result = request.result as StoredSampleFile
        if (result) {
          const blob = new Blob([result.data], { type: result.type })
          const url = URL.createObjectURL(blob)
          resolve(url)
        } else {
          resolve(null)
        }
      }
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Delete a file from IndexedDB
   */
  async deleteFile(fileId: string): Promise<void> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readwrite')
      const store = transaction.objectStore('sampleFiles')
      const request = store.delete(fileId)
      
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Get all stored file metadata
   */
  async getAllFiles(): Promise<StoredSampleFile[]> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readonly')
      const store = transaction.objectStore('sampleFiles')
      const request = store.getAll()
      
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Clear all stored files
   */
  async clearAllFiles(): Promise<void> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readwrite')
      const store = transaction.objectStore('sampleFiles')
      const request = store.clear()
      
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error)
    })
  }

  /**
   * Get database storage usage information
   */
  async getStorageInfo(): Promise<{ count: number; estimatedSize: number }> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readonly')
      const store = transaction.objectStore('sampleFiles')
      const countRequest = store.count()
      const getAllRequest = store.getAll()
      
      let count = 0
      let estimatedSize = 0
      
      countRequest.onsuccess = () => {
        count = countRequest.result
      }
      
      getAllRequest.onsuccess = () => {
        const files = getAllRequest.result as StoredSampleFile[]
        estimatedSize = files.reduce((total, file) => total + file.size, 0)
        resolve({ count, estimatedSize })
      }
      
      getAllRequest.onerror = () => reject(getAllRequest.error)
    })
  }

  /**
   * Check if a file exists in storage
   */
  async fileExists(fileId: string): Promise<boolean> {
    if (!this.db) await this.init()

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['sampleFiles'], 'readonly')
      const store = transaction.objectStore('sampleFiles')
      const request = store.get(fileId)
      
      request.onsuccess = () => resolve(!!request.result)
      request.onerror = () => reject(request.error)
    })
  }
}

// Export singleton instance
export const sampleIndexedDB = new SampleIndexedDB()
