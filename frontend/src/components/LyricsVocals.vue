<template>
  <div class="lyrics-vocals">
    <div class="lyrics-header">
      <div class="header-title">
        <Mic class="header-icon" />
        <h3>Lyrics & Vocals</h3>
      </div>
      
      <div class="header-actions">
        <button class="btn btn-ghost" @click="toggleVoicePanel" title="Manage Voices">
          <User class="icon" />
          Voice
        </button>
        <button class="btn btn-ghost" @click="addLyricsSegment" title="Add Lyrics Segment">
          <Plus class="icon" />
          Add Segment
        </button>
        <button class="btn btn-ghost" @click="playLyrics" :disabled="!hasLyrics" title="Play with Vocals">
          <Play v-if="!isPlayingLyrics" class="icon" />
          <Pause v-else class="icon" />
          Play Vocals
        </button>
        <button class="btn btn-primary" @click="generateAllVoices" :disabled="!hasLyrics" title="Generate Singing Voices for All Segments">
          <Mic class="icon" />
          Generate All
        </button>
      </div>
    </div>
    
    <!-- Voice Management Panel -->
    <div v-if="showVoicePanel" class="voice-panel">
      <div class="voice-panel-header">
        <h4>Voice Management</h4>
        <button class="btn-icon" @click="closeVoicePanel">
          <X class="icon" />
        </button>
      </div>
      
      <div class="voice-tabs">
        <div class="tab-buttons">
          <button class="tab-btn" :class="{ active: activeTab === 'voices' }" @click="activeTab = 'voices'">Available Voices</button>
          <button class="tab-btn" :class="{ active: activeTab === 'record' }" @click="activeTab = 'record'">Record New</button>
          <button class="tab-btn" :class="{ active: activeTab === 'upload' }" @click="activeTab = 'upload'">Upload Audio</button>
        </div>
        
        <div class="tab-content">
          <!-- Available Voices -->
          <div v-show="activeTab === 'voices'" class="voices-list">
            <div class="voice-selector">
              <label>Default Voice:</label>
              <select v-model="selectedVoice" class="voice-select" :disabled="isLoadingVoices">
                <option value="">No default</option>
                <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
                  {{ voice.name }} ({{ voice.type === 'builtin' ? 'Built-in' : 'Custom' }})
                </option>
              </select>
            </div>
            
            <div v-if="isLoadingVoices" class="loading-voices">
              <Loader class="icon spinning" />
              <span>Loading voices...</span>
            </div>
            
            <div v-else class="voice-grid">
              <div 
                v-for="voice in availableVoices" 
                :key="voice.id"
                class="voice-card"
                :class="{ 'selected': selectedVoice === voice.id }"
                @click="selectedVoice = voice.id"
              >
                <div class="voice-info">
                  <h5>{{ voice.name }}</h5>
                  <span class="voice-type">{{ voice.type === 'builtin' ? 'Built-in' : 'Custom' }}</span>
                  <span class="voice-status" :class="{ 'trained': voice.trained }">
                    {{ voice.trained ? 'Ready' : 'Training...' }}
                  </span>
                </div>
                <div class="voice-actions">
                  <button class="btn btn-sm" @click.stop="testVoiceSpoken(voice.id)" :disabled="!voice.trained" title="Test Spoken Voice">
                    <MessageSquare class="icon" />
                    Speak
                  </button>
                  <button class="btn btn-sm btn-primary" @click.stop="testVoiceSinging(voice.id)" :disabled="!voice.trained" title="Test Singing Voice">
                    <Music class="icon" />
                    Sing
                  </button>
                  <button 
                    v-if="voice.type !== 'builtin'" 
                    class="btn btn-sm btn-danger" 
                    @click.stop="deleteVoice(voice.id)"
                    title="Delete Voice"
                  >
                    <Trash2 class="icon" />
                    Delete
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Record New Voice -->
          <div v-show="activeTab === 'record'" class="recording-section">
            <div class="recording-header">
              <h5>Record Voice Sample</h5>
              <p>Record at least 30 seconds of clear speech for better voice training</p>
              <p class="format-info">📼 Recordings are automatically converted to WAV format for optimal training quality</p>
            </div>
            
            <div class="recording-controls">
              <button 
                class="btn btn-primary btn-large" 
                @click="toggleRecording"
                :disabled="isTraining"
              >
                <Mic2 v-if="!isRecording" class="icon" />
                <Pause v-else class="icon" />
                {{ isRecording ? 'Stop Recording' : 'Start Recording' }}
              </button>
              
              <div v-if="isRecording" class="recording-info">
                <div class="recording-time">{{ formatRecordingTime(recordingTime) }}</div>
                <div class="recording-indicator"></div>
              </div>
            </div>
            
            <div v-if="recordedChunks.length > 0" class="recorded-audio">
              <h6>Recorded Audio:</h6>
              <audio v-if="recordedAudioUrl" controls :src="recordedAudioUrl"></audio>
              
              <div class="audio-actions">
                <input 
                  v-model="newVoiceName"
                  placeholder="Enter voice name..."
                  class="voice-name-input"
                />
                <button class="btn btn-primary" @click="trainVoice" :disabled="!newVoiceName.trim()">
                  <Loader v-if="isTraining" class="icon spinning" />
                  Train Voice
                </button>
                <button class="btn btn-ghost" @click="clearRecording">Clear</button>
              </div>
            </div>
          </div>
          
          <!-- Upload Audio -->
          <div v-show="activeTab === 'upload'" class="upload-section">
            <div class="upload-header">
              <h5>Upload Audio Files</h5>
              <p>Upload multiple audio files (WAV, MP3) for voice training</p>
              <p class="format-info">📁 Files are automatically converted to WAV format for optimal training quality</p>
            </div>
            
            <div class="upload-area" @click="triggerFileUpload" @dragover.prevent @drop="handleFileDrop">
              <Upload class="upload-icon" />
              <h6>Click to upload or drag & drop</h6>
              <p>Supported: WAV, MP3, M4A (Max 50MB each)</p>
              <input 
                ref="fileInput"
                type="file"
                multiple
                accept="audio/*"
                @change="handleFileUpload"
                style="display: none"
              />
            </div>
            
            <div v-if="uploadedFiles.length > 0" class="uploaded-files">
              <h6>Uploaded Files:</h6>
              <div class="file-list">
                <div v-for="file in uploadedFiles" :key="file.name" class="file-item">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ formatFileSize(file.size) }}</span>
                  <button class="btn-icon" @click="removeFile(file)">
                    <X class="icon" />
                  </button>
                </div>
              </div>
              
              <div class="upload-actions">
                <input 
                  v-model="newVoiceName"
                  placeholder="Enter voice name..."
                  class="voice-name-input"
                />
                <button class="btn btn-primary" @click="trainVoiceFromFiles" :disabled="!newVoiceName.trim()">
                  <Loader v-if="isTraining" class="icon spinning" />
                  Train Voice
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Training Progress -->
      <div v-if="trainingVoices.length > 0" class="training-progress">
        <h5>Training Progress</h5>
        <div v-for="voice in trainingVoices" :key="voice.id" class="training-item">
          <div class="training-info">
            <span class="training-name">{{ voice.name }}</span>
            <span class="training-status" :class="{ 'status-error': voice.status === 'error' }">{{ voice.status }}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: voice.progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ voice.progress }}%</span>
          
          <!-- Training Time Information -->
          <div v-if="voice.status === 'training'" class="training-info-text">
            <div class="training-timing" v-if="voice.estimated_time_remaining || voice.elapsed_time">
              <small class="timing-info">
                <span v-if="voice.elapsed_time">Elapsed: {{ voice.elapsed_time }}</span>
                <span v-if="voice.estimated_time_remaining" class="time-remaining">
                  • Estimated remaining: {{ voice.estimated_time_remaining }}
                </span>
              </small>
            </div>
            <small class="training-note">
              <i class="fas fa-info-circle"></i>
              Voice training typically takes 15-30 minutes depending on data size and complexity
            </small>
          </div>
          
          <!-- Error Message -->
          <div v-if="voice.status === 'error' && voice.error" class="training-error">
            <div class="error-message">
              <i class="fas fa-exclamation-triangle"></i>
              {{ voice.error }}
            </div>
          </div>
          
          <!-- Transcription Status -->
          <div v-if="voice.transcriptions && voice.transcriptions.length > 0" class="transcription-status">
            <div class="transcription-summary">
              <span class="transcription-label">Transcriptions:</span>
              <span class="transcription-count">{{ voice.transcriptions.length }} files</span>
            </div>
            <div class="transcription-details">
              <div v-for="(transcription, index) in voice.transcriptions" :key="index" class="transcription-item">
                <span class="transcription-file">{{ getFileName(transcription.audio_file) }}</span>
                <span class="transcription-confidence" :class="getConfidenceClass(transcription.confidence)">
                  {{ transcription.engine }} ({{ (transcription.confidence * 100).toFixed(0) }}%)
                </span>
                <div v-if="transcription.text && !transcription.error" class="transcription-preview">
                  "{{ transcription.text.substring(0, 60) }}{{ transcription.text.length > 60 ? '...' : '' }}"
                </div>
                <div v-if="transcription.error" class="transcription-error">
                  Error: {{ transcription.error }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="lyrics-content">
      <!-- Empty State -->
      <div v-if="!hasLyrics" class="empty-state">
        <Music class="empty-icon" />
        <h4>No lyrics yet</h4>
        <p>Add lyrical content with timing and vocal notes</p>
        <button class="btn btn-primary" @click="addLyricsSegment">
          <Plus class="icon" />
          Add Your First Lyrics
        </button>
      </div>
      
      <!-- Lyrics Timeline -->
      <div v-else class="lyrics-timeline">
        <div class="timeline-header">
          <div class="timeline-controls">
            <label>Current Time: {{ formatTime(currentTime) }}</label>
            <input 
              type="range" 
              :min="0" 
              :max="maxTime" 
              :value="currentTime"
              @input="seekTo($event)"
              class="timeline-scrubber"
            />
          </div>
        </div>
        
        <div class="lyrics-segments">
          <div 
            v-for="clip in lyricsClips" 
            :key="clip.id"
            class="lyrics-segment"
            :class="{
              'active': isSegmentActive(clip),
              'upcoming': isSegmentUpcoming(clip)
            }"
            @click="editClip(clip.id)"
          >
            <div class="segment-header">
              <div class="segment-timing">
                <span class="time-label">{{ formatTime(clip.startTime) }} - {{ formatTime(clip.startTime + clip.duration) }}</span>
                <span class="duration-label">({{ clip.duration.toFixed(1) }}s)</span>
              </div>
              <div class="segment-actions">
                <button class="btn-icon generate-voice" @click.stop="generateVoiceForSegment(clip)" 
                        :disabled="!hasClipContent(clip)" 
                        title="Generate Singing Voice">
                  <Mic class="icon" />
                </button>
                <button class="btn-icon play-segment" @click.stop="playSegment(clip)" title="Play Segment">
                  <Play class="icon" />
                </button>
                <button class="btn-icon" @click.stop="duplicateClip(clip)" title="Duplicate">
                  <Copy class="icon" />
                </button>
                <button class="btn-icon delete-segment" @click.stop="removeClip(clip.id)" title="Delete">
                  <Trash2 class="icon" />
                </button>
              </div>
            </div>
            
            <div class="segment-content">
              <!-- Simple lyrics display (when not using voices array) -->
              <div v-if="!clip.voices || clip.voices.length === 0" class="simple-lyrics">
                <div class="lyrics-text">
                  <span class="text-content">{{ getClipText(clip) }}</span>
                </div>
                
                <div class="vocal-info">
                  <div v-if="clip.notes && clip.notes.length" class="notes-display">
                    <span class="notes-label">Notes:</span>
                    <div class="note-pills">
                      <span v-for="note in clip.notes" :key="note" class="note-pill">
                        {{ note }}
                      </span>
                    </div>
                  </div>
                  <div v-if="clip.chordName" class="chord-info">
                    <span class="chord-label">Chord:</span>
                    <span class="chord-name">{{ clip.chordName }}</span>
                  </div>
                  <div v-if="clip.voiceId" class="voice-info">
                    <span class="voice-label">Voice:</span>
                    <span class="voice-name">{{ getVoiceName(clip.voiceId) }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Advanced multi-voice display with enhanced visualization -->
              <div v-else class="multi-voice-lyrics">
                <div class="voices-header">
                  <div class="voices-summary">
                    <Mic class="voices-icon" />
                    <span class="voices-label">{{ clip.voices.length }} Voice{{ clip.voices.length > 1 ? 's' : '' }}</span>
                    <div class="duration-badge">
                      <Clock class="duration-icon" />
                      {{ clip.duration.toFixed(1) }}s
                    </div>
                  </div>
                  <div class="voice-controls">
                    <button class="btn btn-sm" @click="toggleVoiceVisualization()" title="Toggle Timeline View">
                      <BarChart class="icon" />
                      {{ showTimelines ? 'List' : 'Timeline' }}
                    </button>
                    <button class="btn btn-sm btn-primary" @click="handlePlayMultiVoiceClip(clip)" title="Play Multi-Voice">
                      <Play class="icon" />
                      Play All
                    </button>
                  </div>
                </div>

                <!-- Timeline Visualization -->
                <div v-if="showTimelines" class="voice-timeline-container">
                  <div class="timeline-header">
                    <div class="timeline-controls">
                      <button class="btn btn-xs" @click="zoomTimeline('in')" title="Zoom In">
                        <ZoomIn class="icon" />
                      </button>
                      <button class="btn btn-xs" @click="zoomTimeline('out')" title="Zoom Out">
                        <ZoomOut class="icon" />
                      </button>
                      <button class="btn btn-xs" @click="resetTimelineZoom()" title="Reset Zoom">
                        <RotateCcw class="icon" />
                      </button>
                    </div>
                    <div class="timeline-scale">
                      <div v-for="tick in getTimelineTicks(clip)" :key="tick" class="time-tick">
                        {{ tick }}s
                      </div>
                    </div>
                  </div>
                  
                  <div class="voice-timeline" :style="{ width: getTimelineWidth(clip) + 'px' }">
                    <!-- Background grid -->
                    <div class="timeline-grid">
                      <div v-for="tick in getTimelineTicks(clip)" :key="`grid-${tick}`" 
                           class="grid-line" 
                           :style="{ left: getTimePosition(tick, clip) + '%' }"></div>
                    </div>
                    
                    <!-- Voice tracks -->
                    <div v-for="(voice, voiceIndex) in clip.voices" :key="voice.voice_id" 
                         class="voice-track" 
                         :style="{ backgroundColor: getVoiceColor(voiceIndex) + '20' }">
                      
                      <div class="voice-track-header">
                        <div class="voice-name-badge" :style="{ backgroundColor: getVoiceColor(voiceIndex) }">
                          {{ voice.voice_id }}
                        </div>
                        <div class="voice-track-controls">
                          <button class="btn btn-xs" @click="playVoiceTrack(clip, voice)" title="Play This Voice">
                            <Play class="icon" />
                          </button>
                          <button class="btn btn-xs" @click="muteVoiceTrack(clip.id, voice.voice_id)" 
                                  :class="{ active: isVoiceMuted(clip.id, voice.voice_id) }" title="Mute/Unmute">
                            <VolumeX v-if="isVoiceMuted(clip.id, voice.voice_id)" class="icon" />
                            <Volume2 v-else class="icon" />
                          </button>
                        </div>
                      </div>
                      
                      <div class="voice-fragments-timeline">
                        <div v-for="(fragment, fragmentIndex) in voice.lyrics" 
                             :key="`${voice.voice_id}-${fragmentIndex}`"
                             class="fragment-block"
                             :style="{
                               left: getTimePosition(fragment.start, clip) + '%',
                               width: getFragmentWidth(fragment) + '%',
                               backgroundColor: getVoiceColor(voiceIndex)
                             }"
                             @click="selectFragment(clip, voice, fragment)"
                             :class="{ 
                               selected: isFragmentSelected(clip.id, voice.voice_id, fragmentIndex),
                               'has-notes': fragment.notes && fragment.notes.length > 0
                             }">
                          
                          <div class="fragment-content">
                            <div class="fragment-text-preview">{{ fragment.text }}</div>
                            <div class="fragment-notes-preview" v-if="fragment.notes && fragment.notes.length">
                              <span v-for="note in fragment.notes.slice(0, 3)" :key="note" class="note-mini">{{ note }}</span>
                              <span v-if="fragment.notes.length > 3" class="notes-more">+{{ fragment.notes.length - 3 }}</span>
                            </div>
                          </div>
                          
                          <!-- Fragment handles for resizing -->
                          <div class="fragment-handle fragment-handle-left" @mousedown="startFragmentResize($event, clip, voice, fragment, 'left')"></div>
                          <div class="fragment-handle fragment-handle-right" @mousedown="startFragmentResize($event, clip, voice, fragment, 'right')"></div>
                        </div>
                      </div>
                    </div>
                    
                    <!-- Playhead -->
                    <div v-if="currentPlayhead[clip.id]" 
                         class="timeline-playhead"
                         :style="{ left: getTimePosition(currentPlayhead[clip.id], clip) + '%' }">
                      <div class="playhead-line"></div>
                      <div class="playhead-time">{{ currentPlayhead[clip.id].toFixed(1) }}s</div>
                    </div>
                  </div>
                </div>

                <!-- List View (Enhanced) -->
                <div v-else class="voices-list-enhanced">
                  <div v-for="(voice, voiceIndex) in clip.voices" :key="voice.voice_id" class="voice-section-enhanced">
                    <div class="voice-header-enhanced" :style="{ borderLeftColor: getVoiceColor(voiceIndex) }">
                      <div class="voice-identity">
                        <div class="voice-avatar" :style="{ backgroundColor: getVoiceColor(voiceIndex) }">
                          {{ voice.voice_id.charAt(0).toUpperCase() }}
                        </div>
                        <div class="voice-details">
                          <div class="voice-id-enhanced">{{ voice.voice_id }}</div>
                          <div class="voice-stats">
                            {{ voice.lyrics.length }} fragment{{ voice.lyrics.length > 1 ? 's' : '' }} • 
                            {{ getTotalVoiceDuration(voice) }}s total
                          </div>
                        </div>
                      </div>
                      <div class="voice-actions">
                        <button class="btn btn-sm" @click="playVoiceTrack(clip, voice)" title="Play Voice">
                          <Play class="icon" />
                        </button>
                        <button class="btn btn-sm" @click="handleEditVoice(clip, voice)" title="Edit Voice">
                          <Edit class="icon" />
                        </button>
                        <button class="btn btn-sm btn-danger" @click="removeVoice(clip, voice)" title="Remove Voice">
                          <Trash2 class="icon" />
                        </button>
                      </div>
                    </div>
                    
                    <div class="voice-fragments-enhanced">
                      <div v-for="(fragment, fragmentIndex) in voice.lyrics" 
                           :key="`${voice.voice_id}-${fragmentIndex}`"
                           class="fragment-enhanced"
                           @click="selectFragment(clip, voice, fragment)"
                           :class="{ selected: isFragmentSelected(clip.id, voice.voice_id, fragmentIndex) }">
                        
                        <div class="fragment-header">
                          <div class="fragment-text-main">{{ fragment.text }}</div>
                          <div class="fragment-timing">
                            <span class="time-start">{{ fragment.start.toFixed(1) }}s</span>
                            <span class="time-separator">→</span>
                            <span class="time-end">{{ (fragment.start + getFragmentDuration(fragment)).toFixed(1) }}s</span>
                          </div>
                        </div>
                        
                        <div class="fragment-body">
                          <div class="fragment-notes-display" v-if="fragment.notes && fragment.notes.length">
                            <div class="notes-label">Notes:</div>
                            <div class="notes-visual">
                              <span v-for="(note, noteIndex) in fragment.notes" 
                                    :key="note" 
                                    class="note-pill-enhanced"
                                    :style="{ backgroundColor: getNoteColor(note) }">
                                {{ note }}
                                <span v-if="fragment.durations && fragment.durations[noteIndex]" 
                                      class="note-duration">
                                  {{ fragment.durations[noteIndex].toFixed(1) }}s
                                </span>
                              </span>
                            </div>
                          </div>
                          
                          <div class="fragment-waveform" v-if="fragment.waveform">
                            <div class="waveform-mini">
                              <!-- Mini waveform visualization -->
                              <svg class="waveform-svg" viewBox="0 0 100 20">
                                <path :d="generateWaveformPath(fragment.waveform)" 
                                      :stroke="getVoiceColor(voiceIndex)" 
                                      stroke-width="0.5" 
                                      fill="none" />
                              </svg>
                            </div>
                          </div>
                        </div>
                        
                        <div class="fragment-actions">
                          <button class="btn btn-xs" @click="playFragment(clip, voice, fragment)" title="Play Fragment">
                            <Play class="icon" />
                          </button>
                          <button class="btn btn-xs" @click="editFragment(clip, voice, fragment)" title="Edit Fragment">
                            <Edit class="icon" />
                          </button>
                          <button class="btn btn-xs btn-danger" @click="removeFragment(clip, voice, fragment)" title="Remove Fragment">
                            <Trash2 class="icon" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Add Voice Button -->
                  <div class="add-voice-section">
                    <button class="btn btn-ghost btn-block" @click="handleAddVoiceToClip(clip)" title="Add New Voice">
                      <Plus class="icon" />
                      Add Voice Track
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Edit Segment Modal -->
    <div v-show="editingClip !== null" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingClip === 'new' ? 'Add' : 'Edit' }} Lyrics Segment</h3>
          <button class="btn-icon" @click="closeEditModal">
            <X class="icon" />
          </button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>Lyrics Text:</label>
            <textarea 
              v-model="segmentForm.text"
              placeholder="Enter lyrics text..."
              class="form-textarea"
              rows="3"
            ></textarea>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Start Time (seconds):</label>
              <input 
                v-model.number="segmentForm.startTime"
                type="number"
                step="0.1"
                min="0"
                class="form-input"
              />
            </div>
            <div class="form-group">
              <label>End Time (seconds):</label>
              <input 
                v-model.number="segmentForm.endTime"
                type="number"
                step="0.1"
                :min="segmentForm.startTime + 0.1"
                class="form-input"
              />
            </div>
          </div>
          
          <div class="form-group">
            <label>Vocal Notes (comma-separated):</label>
            <input 
              v-model="segmentForm.notesInput"
              type="text"
              placeholder="e.g., C4, E4, G4"
              class="form-input"
              @input="updateNotes"
            />
            <small class="form-help">Enter note names like C4, D#4, F5, etc.</small>
          </div>
          
          <div class="form-group">
            <label>Chord Name (optional):</label>
            <input 
              v-model="segmentForm.chordName"
              type="text"
              placeholder="e.g., C major, Dm7"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label>Voice for this segment:</label>
            <select v-model="segmentForm.voiceId" class="form-select">
              <option value="">Use default voice</option>
              <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
                {{ voice.name }} ({{ voice.type === 'builtin' ? 'Built-in' : 'Custom' }})
              </option>
            </select>
            <small class="form-help">Select a voice for singing this segment</small>
          </div>
          
          <!-- Form validation feedback -->
          <div v-if="!isFormValid" class="form-validation">
            <p class="validation-message">
              <span v-if="!segmentForm.text.trim()">⚠️ Lyrics text is required</span>
              <span v-else-if="segmentForm.startTime >= segmentForm.endTime">⚠️ End time must be after start time</span>
            </p>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="closeEditModal">Cancel</button>
          <button 
            class="btn btn-primary" 
            @click="saveSegment" 
            :disabled="!isFormValid"
            :title="!isFormValid ? 'Please fill in lyrics text and ensure end time is after start time' : ''"
          >
            {{ editingClip === 'new' ? 'Add' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { DiffSingerService } from '../services/diffSingerService'
import { useMultiVoiceVisualization } from '../composables/useMultiVoiceVisualization'
import { useVoiceManagement } from '../composables/useVoiceManagement'
import { 
  Mic, Plus, Play, Pause, Music, Copy, Trash2, X, User, Upload, Mic2, Loader, 
  VolumeX, Volume2, Edit, ZoomIn, ZoomOut, RotateCcw, BarChart, MessageSquare, Clock
} from 'lucide-vue-next'

const audioStore = useAudioStore()

// Initialize composables
const multiVoiceVisualization = useMultiVoiceVisualization()
const voiceManagement = useVoiceManagement()

// Destructure commonly used methods and state
const {
  showTimelines,
  timelineZoom,
  selectedFragment: selectedFragmentFromComposable,
  toggleVoiceVisualization,
  getVoiceColor,
  zoomTimeline,
  resetTimelineZoom,
  getTimelineTicks,
  getTimelineWidth,
  getTimePosition,
  selectFragment,
  getFragmentWidth,
  isFragmentSelected,
  getFragmentDuration,
  getTotalVoiceDuration,
  getNoteColor
} = multiVoiceVisualization

const {
  mutedVoices,
  playVoiceTrack,
  muteVoiceTrack,
  isVoiceMuted,
  editVoice,
  removeVoice,
  addVoiceToClip,
  playMultiVoiceClip
} = voiceManagement

// State
const editingClip = ref<string | null>(null) // Changed to store clip ID instead of index
const currentTime = ref(0)
const isPlayingLyrics = ref(false)

// Voice management state
const showVoicePanel = ref(false)
const activeTab = ref<'voices' | 'record' | 'upload'>('voices')
const isRecording = ref(false)
const isTraining = ref(false)
const isLoadingVoices = ref(false)
const recordingTime = ref(0)
const audioRecorder = ref<MediaRecorder | null>(null)
const recordedChunks = ref<Blob[]>([])
const selectedVoice = ref<string>('default')

// Additional state for UI
const newVoiceName = ref('')
const uploadedFiles = ref<File[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

// Voice data - will be loaded from backend
const availableVoices = ref<Array<{
  id: string
  name: string
  type: 'builtin' | 'custom'
  trained: boolean
}>>([])

const trainingVoices = ref<Array<{
  id: string
  name: string
  status: 'preparing' | 'uploading' | 'training' | 'ready' | 'error'
  progress: number
  audioFiles: string[]
  error?: string
  estimated_time_remaining?: string
  elapsed_time?: string
  transcriptions?: Array<{
    audio_file: string
    text: string
    confidence: number
    engine: string
    transcription_file?: string
    error?: string
  }>
}>>([])

// Recording constraints
const recordingConstraints = {
  audio: {
    sampleRate: 44100,
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true
  }
}

// Enhanced recording configuration for better quality WAV export
const mediaRecorderOptions = {
  mimeType: 'audio/webm;codecs=opus', // Use best available codec
  audioBitsPerSecond: 128000 // Higher bitrate for better quality
}

// Lyrics data from song structure - now using track/clip pattern
const lyricsTrack = computed(() => {
  return audioStore.getLyricsTrack()
})

const lyricsClips = computed(() => {
  const track = lyricsTrack.value
  if (!track) return []
  // Sort clips by start time for proper timeline display
  return [...track.clips].sort((a, b) => a.startTime - b.startTime)
})

const hasLyrics = computed(() => lyricsClips.value.length > 0)

const maxTime = computed(() => {
  if (!hasLyrics.value) return 30
  return Math.max(...lyricsClips.value.map(clip => clip.startTime + clip.duration), 30)
})

// Enhanced computed properties for visualization
const timelineWidth = computed(() => Math.max(maxTime.value * 50 * timelineZoom.value, 800))

const timelineMarkers = computed(() => {
  const markers = []
  const step = timelineZoom.value > 2 ? 0.5 : timelineZoom.value > 1 ? 1 : 2
  for (let i = 0; i <= maxTime.value; i += step) {
    markers.push(i)
  }
  return markers
})

const voiceStats = computed(() => {
  const stats = new Map<string, { fragments: number, totalDuration: number }>()
  
  lyricsClips.value.forEach(clip => {
    if (clip.voices && Array.isArray(clip.voices)) {
      clip.voices.forEach((voice: any) => {
        const voiceId = voice.voice_id || 'default'
        const existing = stats.get(voiceId) || { fragments: 0, totalDuration: 0 }
        
        const fragmentCount = voice.lyrics ? voice.lyrics.length : 0
        const duration = voice.lyrics ? 
          voice.lyrics.reduce((sum: number, f: any) => sum + (f.duration || 0), 0) : 0
        
        stats.set(voiceId, {
          fragments: existing.fragments + fragmentCount,
          totalDuration: existing.totalDuration + duration
        })
      })
    }
  })
  
  return stats
})

// Segment form
const segmentForm = ref({
  text: '',
  startTime: 0,
  endTime: 4,
  notes: [] as string[],
  notesInput: '',
  chordName: '',
  voiceId: ''
})

// Computed
const isFormValid = computed(() => {
  return segmentForm.value.text.trim() !== '' && 
         segmentForm.value.startTime < segmentForm.value.endTime
})

// Methods
const formatTime = (time: number): string => {
  const minutes = Math.floor(time / 60)
  const seconds = Math.floor(time % 60)
  const centiseconds = Math.floor((time % 1) * 100)
  return `${minutes}:${seconds.toString().padStart(2, '0')}.${centiseconds.toString().padStart(2, '0')}`
}

const isSegmentActive = (clip: any): boolean => {
  return currentTime.value >= clip.startTime && currentTime.value <= (clip.startTime + clip.duration)
}

const isSegmentUpcoming = (clip: any): boolean => {
  return currentTime.value < clip.startTime && currentTime.value >= clip.startTime - 2
}

const seekTo = (event: Event) => {
  const target = event.target as HTMLInputElement
  currentTime.value = parseFloat(target.value)
}

const addLyricsSegment = () => {
  // Find a good default start time
  let defaultStartTime = 0
  if (hasLyrics.value) {
    const lastClip = lyricsClips.value[lyricsClips.value.length - 1]
    defaultStartTime = lastClip.startTime + lastClip.duration
  }
  
  segmentForm.value = {
    text: '',
    startTime: defaultStartTime,
    endTime: defaultStartTime + 4,
    notes: [],
    notesInput: '',
    chordName: '',
    voiceId: ''
  }
  
  editingClip.value = 'new' // 'new' indicates new clip
}

const editClip = (clipId: string) => {
  const clip = lyricsClips.value.find(c => c.id === clipId)
  if (!clip) return
  
  segmentForm.value = {
    text: getClipText(clip),
    startTime: clip.startTime,
    endTime: clip.startTime + clip.duration,
    notes: [...getClipNotes(clip)],
    notesInput: getClipNotes(clip).join(', '),
    chordName: clip.chordName || '',
    voiceId: clip.voiceId || ''
  }
  editingClip.value = clipId
}

const closeEditModal = () => {
  editingClip.value = null
}

const updateNotes = () => {
  segmentForm.value.notes = segmentForm.value.notesInput
    .split(',')
    .map(note => note.trim())
    .filter(note => note !== '')
}

const saveSegment = () => {
  const newSegment = {
    startTime: segmentForm.value.startTime,
    endTime: segmentForm.value.endTime,
    text: segmentForm.value.text,
    notes: segmentForm.value.notes,
    chordName: segmentForm.value.chordName || undefined,
    voiceId: segmentForm.value.voiceId || undefined
  }
  
  if (editingClip.value === 'new') {
    // Add new clip
    audioStore.addLyricsSegment(newSegment)
  } else if (editingClip.value) {
    // Update existing clip
    audioStore.updateLyricsSegment(editingClip.value, newSegment)
  }
  
  closeEditModal()
}

const removeClip = (clipId: string) => {
  if (confirm('Remove this lyrics segment?')) {
    audioStore.removeLyricsSegment(clipId)
  }
}

const duplicateClip = (clip: any) => {
  const newSegment = {
    startTime: clip.startTime + clip.duration,
    endTime: clip.startTime + clip.duration * 2,
    text: clip.text,
    notes: clip.notes || [],
    chordName: clip.chordName,
    voiceId: clip.voiceId
  }
  
  audioStore.addLyricsSegment(newSegment)
}

const playSegment = (clip: any) => {
  currentTime.value = clip.startTime
  // Here you could integrate with audio playback to actually play the clip
  console.log(`Playing segment: "${clip.text}" from ${clip.startTime}s to ${clip.startTime + clip.duration}s`)
}

const playLyrics = () => {
  isPlayingLyrics.value = !isPlayingLyrics.value
  if (isPlayingLyrics.value) {
    // Start playback with lyrics highlighting
    startLyricsPlayback()
  } else {
    stopLyricsPlayback()
  }
}

const startLyricsPlayback = () => {
  // This could integrate with the main audio playback system
  console.log('Starting lyrics playback')
  // For now, just simulate playback by updating currentTime
  const interval = setInterval(() => {
    if (!isPlayingLyrics.value) {
      clearInterval(interval)
      return
    }
    currentTime.value += 0.1
    if (currentTime.value >= maxTime.value) {
      isPlayingLyrics.value = false
      clearInterval(interval)
    }
  }, 100)
}

const stopLyricsPlayback = () => {
  isPlayingLyrics.value = false
  console.log('Stopping lyrics playback')
}

// Watch for audio store playback changes
watch(() => audioStore.currentTime, (newTime) => {
  currentTime.value = newTime
})

watch(() => audioStore.isPlaying, (playing) => {
  if (!playing) {
    isPlayingLyrics.value = false
  }
})

// Computed properties for voice management
const recordedAudioUrl = computed(() => {
  if (recordedChunks.value.length === 0) return null
  const blob = new Blob(recordedChunks.value, { type: 'audio/webm' })
  return URL.createObjectURL(blob)
})

// Voice Management Methods
const toggleVoicePanel = async () => {
  const wasOpen = showVoicePanel.value
  showVoicePanel.value = !showVoicePanel.value
  
  // Refresh voices when opening the panel for the first time or if it was closed
  if (!wasOpen && showVoicePanel.value) {
    await loadAvailableVoices()
  }
}

const closeVoicePanel = () => {
  showVoicePanel.value = false
}

const testVoiceSpoken = async (voiceId: string) => {
  try {
    console.log('Testing spoken voice:', voiceId)
    const audioBlob = await DiffSingerService.testVoiceSpoken(voiceId)
    
    // Create audio URL and play
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    audio.play()
    
    // Clean up URL after playing
    audio.onended = () => URL.revokeObjectURL(audioUrl)
  } catch (error) {
    console.error('Error testing spoken voice:', error)
    alert('Error testing spoken voice. Please try again.')
  }
}

const testVoiceSinging = async (voiceId: string) => {
  try {
    console.log('Testing singing voice:', voiceId)
    const audioBlob = await DiffSingerService.testVoiceSinging(voiceId)
    
    // Create audio URL and play
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    audio.play()
    
    // Clean up URL after playing
    audio.onended = () => URL.revokeObjectURL(audioUrl)
  } catch (error) {
    console.error('Error testing singing voice:', error)
    alert('Error testing singing voice. Please try again.')
  }
}

const deleteVoice = async (voiceId: string) => {
  if (confirm('Delete this voice? This action cannot be undone.')) {
    try {
      await DiffSingerService.deleteVoice(voiceId)
      
      // Reload available voices from backend
      await loadAvailableVoices()
      
      console.log('Deleted voice:', voiceId)
    } catch (error) {
      console.error('Error deleting voice:', error)
      alert('Error deleting voice. Please try again.')
    }
  }
}

// Recording Methods
const toggleRecording = async () => {
  if (isRecording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia(recordingConstraints)
    
    // Try to use best available MIME type for recording
    let mimeType = 'audio/webm;codecs=opus'
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = 'audio/webm'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/mp4'
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = '' // Use default
        }
      }
    }
    
    const options = mimeType ? { 
      mimeType,
      audioBitsPerSecond: 128000 
    } : { audioBitsPerSecond: 128000 }
    
    audioRecorder.value = new MediaRecorder(stream, options)
    recordedChunks.value = []
    
    audioRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.value.push(event.data)
      }
    }
    
    audioRecorder.value.start()
    isRecording.value = true
    recordingTime.value = 0
    
    // Update recording time every second
    const timer = setInterval(() => {
      if (!isRecording.value) {
        clearInterval(timer)
        return
      }
      recordingTime.value += 1
    }, 1000)
    
  } catch (error) {
    console.error('Error starting recording:', error)
    alert('Could not access microphone. Please check permissions.')
  }
}

const stopRecording = () => {
  if (audioRecorder.value && isRecording.value) {
    audioRecorder.value.stop()
    isRecording.value = false
    
    // Stop all tracks
    audioRecorder.value.stream?.getTracks().forEach(track => track.stop())
  }
}

const clearRecording = () => {
  recordedChunks.value = []
  recordingTime.value = 0
  newVoiceName.value = ''
}

const formatRecordingTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// File Upload Methods
const triggerFileUpload = () => {
  fileInput.value?.click()
}

const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    const files = Array.from(target.files)
    const validFiles: File[] = []
    
    files.forEach(file => {
      const validation = DiffSingerService.validateAudioFile(file)
      if (validation.valid) {
        validFiles.push(file)
      } else {
        alert(`${file.name}: ${validation.error}`)
      }
    })
    
    uploadedFiles.value.push(...validFiles)
  }
}

const handleFileDrop = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer?.files) {
    const files = Array.from(event.dataTransfer.files)
    const validFiles: File[] = []
    
    files.forEach(file => {
      const validation = DiffSingerService.validateAudioFile(file)
      if (validation.valid) {
        validFiles.push(file)
      } else {
        alert(`${file.name}: ${validation.error}`)
      }
    })
    
    uploadedFiles.value.push(...validFiles)
  }
}

const removeFile = (file: File) => {
  const index = uploadedFiles.value.indexOf(file)
  if (index !== -1) {
    uploadedFiles.value.splice(index, 1)
  }
}

const formatFileSize = (bytes: number) => {
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  if (bytes === 0) return '0 Bytes'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
}

// Audio format conversion utilities
const convertToWAV = async (audioBlob: Blob): Promise<Blob> => {
  try {
    // Create audio context for WAV conversion
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    
    // Decode the audio data
    const arrayBuffer = await audioBlob.arrayBuffer()
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
    
    // Convert to WAV format
    const wavBlob = await audioBufferToWav(audioBuffer)
    
    console.log(`✅ Converted recording: ${audioBlob.type} -> WAV (${formatFileSize(wavBlob.size)})`)
    return wavBlob
    
  } catch (error) {
    console.warn('Failed to convert to WAV, using original format:', error)
    return audioBlob // Fallback to original if conversion fails
  }
}

const audioBufferToWav = (audioBuffer: AudioBuffer): Promise<Blob> => {
  return new Promise((resolve) => {
    const numberOfChannels = audioBuffer.numberOfChannels
    const sampleRate = audioBuffer.sampleRate
    const length = audioBuffer.length
    const arrayBuffer = new ArrayBuffer(44 + length * numberOfChannels * 2)
    const view = new DataView(arrayBuffer)
    
    // WAV header
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i))
      }
    }
    
    const writeInt16 = (offset: number, value: number) => {
      view.setInt16(offset, value, true)
    }
    
    const writeInt32 = (offset: number, value: number) => {
      view.setInt32(offset, value, true)
    }
    
    // RIFF chunk descriptor
    writeString(0, 'RIFF')
    writeInt32(4, 36 + length * numberOfChannels * 2)
    writeString(8, 'WAVE')
    
    // FMT sub-chunk
    writeString(12, 'fmt ')
    writeInt32(16, 16)
    writeInt16(20, 1) // PCM format
    writeInt16(22, numberOfChannels)
    writeInt32(24, sampleRate)
    writeInt32(28, sampleRate * numberOfChannels * 2)
    writeInt16(32, numberOfChannels * 2)
    writeInt16(34, 16)
    
    // Data sub-chunk
    writeString(36, 'data')
    writeInt32(40, length * numberOfChannels * 2)
    
    // Write audio data
    const channels = []
    for (let i = 0; i < numberOfChannels; i++) {
      channels.push(audioBuffer.getChannelData(i))
    }
    
    let offset = 44
    for (let i = 0; i < length; i++) {
      for (let channel = 0; channel < numberOfChannels; channel++) {
        let sample = Math.max(-1, Math.min(1, channels[channel][i]))
        sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF
        view.setInt16(offset, sample, true)
        offset += 2
      }
    }
    
    resolve(new Blob([arrayBuffer], { type: 'audio/wav' }))
  })
}

// Voice Training Methods
const trainVoice = async () => {
  if (!newVoiceName.value.trim()) return
  
  // Validate recording duration
  const validation = DiffSingerService.validateRecording(recordingTime.value)
  if (!validation.valid) {
    alert(validation.error)
    return
  }
  
  isTraining.value = true
  const voiceId = `voice-${Date.now()}`
  
  // Add to training queue
  trainingVoices.value.push({
    id: voiceId,
    name: newVoiceName.value,
    status: 'preparing',
    progress: 0,
    audioFiles: []
  })
  
  try {
    // Create audio blob from recorded chunks
    const originalBlob = new Blob(recordedChunks.value, { type: 'audio/webm' })
    console.log(`📹 Original recording: ${originalBlob.type} (${formatFileSize(originalBlob.size)})`)
    
    // Convert to WAV format for better training quality
    const wavBlob = await convertToWAV(originalBlob)
    console.log(`🎵 Converted to WAV for training: ${formatFileSize(wavBlob.size)}`)
    
    // Update status to training
    const trainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (trainIndex !== -1) {
      trainingVoices.value[trainIndex].status = 'training'
    }
    
    const jobId = await DiffSingerService.trainVoiceFromRecording(
      newVoiceName.value,
      wavBlob, // Use WAV blob instead of original
      {
        duration: recordingTime.value,
        sampleRate: 44100,
        language: 'en'
      }
    )
    
    // Monitor training progress
    await monitorTrainingProgress(jobId, voiceId)
    
    // Reload available voices from backend
    await loadAvailableVoices()
    
    // Remove from training queue
    const finalTrainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (finalTrainIndex !== -1) {
      trainingVoices.value.splice(finalTrainIndex, 1)
    }
    
    // Clear recording
    clearRecording()
    
    console.log(`✅ Voice training completed: ${newVoiceName.value}`)
    
  } catch (error) {
    console.error('Error training voice:', error)
    alert('Error training voice. Please try again.')
    
    // Remove from training queue on error
    const trainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (trainIndex !== -1) {
      trainingVoices.value.splice(trainIndex, 1)
    }
  } finally {
    isTraining.value = false
  }
}

const trainVoiceFromFiles = async () => {
  if (!newVoiceName.value.trim() || uploadedFiles.value.length === 0) return
  
  isTraining.value = true
  const voiceId = `voice-${Date.now()}`
  
  // Add to training queue
  trainingVoices.value.push({
    id: voiceId,
    name: newVoiceName.value,
    status: 'preparing',
    progress: 0,
    audioFiles: uploadedFiles.value.map(f => f.name)
  })
  
  try {
    // Convert uploaded files to WAV format if needed
    const processedFiles: File[] = []
    const totalFiles = uploadedFiles.value.length
    
    console.log(`📁 Processing ${totalFiles} uploaded files for training...`)
    
    for (let i = 0; i < uploadedFiles.value.length; i++) {
      const file = uploadedFiles.value[i]
      console.log(`🔄 Processing file ${i + 1}/${totalFiles}: ${file.name} (${formatFileSize(file.size)})`)
      
      // Update progress
      const trainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
      if (trainIndex !== -1) {
        trainingVoices.value[trainIndex].progress = Math.round((i / totalFiles) * 50) // 50% for file processing
      }
      
      if (file.name.toLowerCase().endsWith('.wav')) {
        // Already WAV, use as-is
        processedFiles.push(file)
        console.log(`✅ WAV file, using directly: ${file.name}`)
      } else {
        // Convert to WAV
        console.log(`🎵 Converting ${file.name} to WAV format...`)
        try {
          const audioBlob = new Blob([await file.arrayBuffer()], { type: file.type })
          const wavBlob = await convertToWAV(audioBlob)
          const wavFile = new File([wavBlob], file.name.replace(/\.[^/.]+$/, '.wav'), { type: 'audio/wav' })
          processedFiles.push(wavFile)
          console.log(`✅ Converted to WAV: ${file.name} -> ${wavFile.name}`)
        } catch (error) {
          console.warn(`⚠️ Failed to convert ${file.name}, using original:`, error)
          processedFiles.push(file) // Use original if conversion fails
        }
      }
    }
    
    // Update status to uploading
    const trainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (trainIndex !== -1) {
      trainingVoices.value[trainIndex].status = 'uploading'
      trainingVoices.value[trainIndex].progress = 50
    }
    
    console.log(`📤 Uploading ${processedFiles.length} processed files for training...`)
    
    const jobId = await DiffSingerService.trainVoiceFromFiles(
      newVoiceName.value,
      processedFiles,
      {
        language: 'en',
        epochs: 100,
        speakerEmbedding: true
      }
    )
    
    // Update status to training
    const finalTrainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (finalTrainIndex !== -1) {
      trainingVoices.value[finalTrainIndex].status = 'training'
      trainingVoices.value[finalTrainIndex].progress = 0
    }
    
    // Monitor training progress
    await monitorTrainingProgress(jobId, voiceId)
    
    // Reload available voices from backend
    await loadAvailableVoices()
    
    // Remove from training queue
    const successTrainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (successTrainIndex !== -1) {
      trainingVoices.value.splice(successTrainIndex, 1)
    }
    
    // Clear uploads
    uploadedFiles.value = []
    newVoiceName.value = ''
    
    console.log(`✅ Voice training from files completed: ${newVoiceName.value}`)
    
  } catch (error) {
    console.error('Error training voice from files:', error)
    alert('Error training voice. Please try again.')
    
    // Remove from training queue on error
    const trainIndex = trainingVoices.value.findIndex(v => v.id === voiceId)
    if (trainIndex !== -1) {
      trainingVoices.value.splice(trainIndex, 1)
    }
  } finally {
    isTraining.value = false
  }
}

// Monitor training progress
const monitorTrainingProgress = async (jobId: string, voiceId: string) => {
  const trainingVoice = trainingVoices.value.find(v => v.id === voiceId)
  if (!trainingVoice) return

  return new Promise<void>((resolve, reject) => {
    let isMonitoring = true
    let attemptCount = 0
    // Voice training can take 15-30 minutes depending on data size and epochs
    // Set timeout to 30 minutes (900 attempts * 2 seconds = 1800 seconds = 30 minutes)
    const maxAttempts = 900
    
    const checkProgress = async () => {
      if (!isMonitoring) return
      
      attemptCount++
      if (attemptCount > maxAttempts) {
        console.warn(`Training monitoring timed out for job ${jobId} after ${maxAttempts} attempts (30 minutes)`)
        isMonitoring = false
        trainingVoice.status = 'error'
        trainingVoice.error = 'Training monitoring timed out after 30 minutes. The training may still be running on the server.'
        reject(new Error('Training monitoring timed out after 30 minutes'))
        return
      }
      
      try {
        const status = await DiffSingerService.getTrainingStatus(jobId)
        
        // Map service status to UI status
        const statusMap: Record<string, 'uploading' | 'training' | 'ready' | 'error'> = {
          'pending': 'training',
          'processing': 'training',
          'completed': 'ready',
          'failed': 'error'
        }
        
        trainingVoice.status = statusMap[status.status] || 'training'
        trainingVoice.progress = status.progress
        
        // Update timing information if available
        if (status.estimated_time_remaining) {
          trainingVoice.estimated_time_remaining = status.estimated_time_remaining
        }
        if (status.elapsed_time) {
          trainingVoice.elapsed_time = status.elapsed_time
        }
        
        // Update transcriptions if available
        if (status.transcriptions) {
          trainingVoice.transcriptions = status.transcriptions
        }
        
        if (status.status === 'completed') {
          isMonitoring = false
          resolve()
        } else if (status.status === 'failed') {
          isMonitoring = false
          reject(new Error(status.error || 'Training failed'))
        } else {
          // Continue monitoring
          setTimeout(checkProgress, 2000)
        }
      } catch (error) {
        console.warn(`Training job ${jobId} monitoring error (attempt ${attemptCount}):`, error)
        
        // Check if this is a 404 (job not found) error
        if (error instanceof Error && error.message.includes('not found')) {
          console.error(`Training job ${jobId} not found. The job may have expired or the server was restarted.`)
          isMonitoring = false
          
          // Set voice status to error with clear message
          trainingVoice.status = 'error'
          trainingVoice.progress = 0
          trainingVoice.error = 'Training job not found. The job may have expired or the server was restarted.'
          
          reject(new Error('Training job not found. The job may have expired or the server was restarted.'))
        } else {
          // For other errors (network issues, etc.), retry after a longer delay
          // But stop if we've tried too many times
          if (attemptCount >= maxAttempts) {
            isMonitoring = false
            trainingVoice.status = 'error'
            reject(new Error('Training monitoring failed after multiple attempts'))
          } else {
            console.log(`Network or temporary error, retrying in 5 seconds... (attempt ${attemptCount}/${maxAttempts})`)
            setTimeout(checkProgress, 5000)
          }
        }
      }
    }
    
    checkProgress()
  })
}

// Load voices from backend
const loadAvailableVoices = async () => {
  isLoadingVoices.value = true
  try {
    const voices = await DiffSingerService.getAvailableVoices()
    
    // Ensure we have an array
    if (!Array.isArray(voices)) {
      console.warn('Expected voices array but got:', voices)
      throw new Error('Invalid voices response format')
    }
    
    availableVoices.value = voices
    
    // Set default voice if none selected or current selection is invalid
    if (!selectedVoice.value || !voices.some(v => v.id === selectedVoice.value)) {
      selectedVoice.value = voices.length > 0 ? voices[0].id : 'default'
    }
  } catch (error) {
    console.error('Error loading voices:', error)
    // Fall back to default voices if backend is not available
    availableVoices.value = [
      { id: 'default', name: 'Default Voice', type: 'builtin', trained: true },
      { id: 'male-01', name: 'Male Voice 1', type: 'builtin', trained: true },
      { id: 'female-01', name: 'Female Voice 1', type: 'builtin', trained: true }
    ]
    if (!selectedVoice.value) {
      selectedVoice.value = 'default'
    }
  } finally {
    isLoadingVoices.value = false
  }
}

// Load voices when component mounts
loadAvailableVoices()

// Helper function to get voice name by ID
const getVoiceName = (voiceId: string) => {
  const voice = availableVoices.value.find(v => v.id === voiceId)
  return voice ? voice.name : 'Unknown Voice'
}

// Generate singing voice for a lyrics segment
const generateVoiceForSegment = async (clip: any) => {
  const text = getClipText(clip)
  const notes = getClipNotes(clip)
  
  if (!text || notes.length === 0) {
    alert('This segment needs lyrics text and musical notes to generate singing voice.')
    return
  }
  
  const voiceId = getClipVoiceId(clip)
  
  try {
    console.log(`Generating singing voice for segment: "${text}" with voice: ${voiceId}`)
    
    // Create synthesis parameters with note/chord information
    const synthesisOptions = {
      speed: 1.0,
      pitch: 0.0, // Will be adjusted based on notes
      volume: 1.0,
      notes: notes,
      chordName: clip.chordName,
      startTime: clip.startTime,
      duration: clip.duration
    }
    
    // Call the backend synthesis API with note-aware parameters
    const audioBlob = await DiffSingerService.synthesizeVoice(
      text,
      voiceId,
      synthesisOptions
    )
    
    // Play the generated audio
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    audio.play()
    
    // Clean up URL after playing
    audio.onended = () => URL.revokeObjectURL(audioUrl)
    
    console.log('Voice generation completed successfully')
  } catch (error) {
    console.error('Error generating voice for segment:', error)
    alert('Error generating singing voice. Please check your settings and try again.')
  }
}

// Generate voices for all segments that have lyrics and notes
const generateAllVoices = async () => {
  const clipsWithContent = lyricsClips.value.filter(clip => hasClipContent(clip))
  
  if (clipsWithContent.length === 0) {
    alert('No segments found with both lyrics and musical notes. Please add notes to your lyrics segments first.')
    return
  }
  
  for (const clip of clipsWithContent) {
    try {
      await generateVoiceForSegment(clip)
      // Small delay between generations to avoid overwhelming the server
      await new Promise(resolve => setTimeout(resolve, 1000))
    } catch (error) {
      const text = getClipText(clip)
      console.error(`Error generating voice for segment "${text}":`, error)
    }
  }
  
  console.log(`Generated voices for ${clipsWithContent.length} segments`)
}

// Helper methods for transcription display
const getFileName = (filePath: string): string => {
  return filePath ? filePath.split('/').pop() || filePath.split('\\').pop() || filePath : 'Unknown file'
}

const getConfidenceClass = (confidence: number): string => {
  if (confidence >= 0.8) return 'confidence-high'
  if (confidence >= 0.5) return 'confidence-medium'
  return 'confidence-low'
}

// Helper functions to work with both old and new clip formats
const getClipText = (clip: any): string => {
  // For new multi-voice format
  if (clip.voices && clip.voices.length > 0) {
    return clip.voices[0].lyrics?.[0]?.text || ''
  }
  // For old format (backward compatibility)
  return clip.text || ''
}

const getClipNotes = (clip: any): string[] => {
  // For new multi-voice format
  if (clip.voices && clip.voices.length > 0) {
    return clip.voices[0].lyrics?.[0]?.notes || []
  }
  // For old format (backward compatibility)
  return clip.notes || []
}

const getClipVoiceId = (clip: any): string => {
  // For new multi-voice format
  if (clip.voices && clip.voices.length > 0) {
    return clip.voices[0].voice_id || 'default'
  }
  // For old format (backward compatibility)
  return clip.voiceId || 'default'
}

const hasClipContent = (clip: any): boolean => {
  const text = getClipText(clip)
  const notes = getClipNotes(clip)
  return text.length > 0 && notes.length > 0
}

// Additional methods for fragments that need clip context
const startFragmentResize = (event: MouseEvent, clip: any, voice: any, fragment: any, handle: 'left' | 'right') => {
  console.log('Starting fragment resize:', handle, fragment)
  event.preventDefault()
  // Would implement drag resize logic here
}

// Computed property for playhead tracking
const currentPlayhead = computed(() => {
  const playheads: Record<string, number> = {}
  lyricsClips.value.forEach(clip => {
    if (currentTime.value >= clip.startTime && currentTime.value <= clip.startTime + clip.duration) {
      playheads[clip.id] = currentTime.value - clip.startTime
    }
  })
  return playheads
})

// Wrapper methods that integrate with existing patterns
const handleEditVoice = (clip: any, voice: any) => {
  editVoice(clip, voice, editClip)
}

const handleAddVoiceToClip = (clip: any) => {
  addVoiceToClip(clip, selectedVoice.value)
}

const handlePlayMultiVoiceClip = (clip: any) => {
  playMultiVoiceClip(clip, playSegment)
}

// Fragment-specific methods
const playFragment = (clip: any, voice: any, fragment: any) => {
  console.log('Playing fragment:', fragment, 'for voice:', voice.voice_id)
  const fragmentStartTime = clip.startTime + (fragment.start || 0)
  currentTime.value = fragmentStartTime
}

const editFragment = (clip: any, voice: any, fragment: any) => {
  console.log('Editing fragment:', fragment, 'for voice:', voice.voice_id)
  selectFragment(clip, voice, fragment)
  editClip(clip.id)
}

const removeFragment = (clip: any, voice: any, fragment: any) => {
  if (confirm('Remove this fragment?')) {
    console.log('Removing fragment:', fragment, 'from voice:', voice.voice_id)
    if (voice.lyrics && Array.isArray(voice.lyrics)) {
      const index = voice.lyrics.indexOf(fragment)
      if (index !== -1) {
        voice.lyrics.splice(index, 1)
      }
    }
  }
}

const generateWaveformPath = (waveformData: number[]): string => {
  if (!waveformData || waveformData.length === 0) {
    return 'M 0 10 L 100 10' // Flat line if no data
  }
  
  const width = 100
  const height = 20
  const centerY = height / 2
  
  let path = `M 0 ${centerY}`
  
  waveformData.forEach((amplitude, index) => {
    const x = (index / (waveformData.length - 1)) * width
    const y = centerY + (amplitude * centerY * 0.8) // Scale amplitude
    path += ` L ${x} ${y}`
  })
  
  return path
}
</script>

<style scoped>
.lyrics-vocals {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.lyrics-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.header-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.header-title h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.voice-select {
  min-width: 120px;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  font-size: 0.875rem;
}

.lyrics-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.empty-state p {
  margin: 0 0 1.5rem 0;
}

/* Timeline */
.lyrics-timeline {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.timeline-header {
  background: var(--surface);
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.timeline-controls {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.timeline-controls label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.timeline-scrubber {
  width: 100%;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.timeline-scrubber::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  cursor: pointer;
}

/* Lyrics Segments */
.lyrics-segments {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.lyrics-segment {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.lyrics-segment:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
}

.lyrics-segment.active {
  border-color: var(--primary);
  background: rgba(0, 123, 255, 0.1);
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
}

.lyrics-segment.upcoming {
  border-color: #ffc107;
  background: rgba(255, 193, 7, 0.1);
}

.segment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.segment-timing {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.time-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.duration-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.segment-actions {
  display: flex;
  gap: 0.25rem;
}

.segment-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.lyrics-text {
  padding: 0.75rem;
  background: var(--background);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.text-content {
  font-size: 1rem;
  line-height: 1.4;
  color: var(--text);
  white-space: pre-wrap;
}

.vocal-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.notes-display {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.notes-label,
.chord-label,
.voice-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.note-pills {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.note-pill {
  background: var(--primary);
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.chord-name,
.voice-name {
  background: var(--accent);
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.voice-info {
  margin-bottom: 1rem;
}

.chord-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chord-name {
  background: var(--border);
  color: var(--text);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 500;
}

/* Multi-voice lyrics display */
.multi-voice-lyrics {
  padding: 0.75rem;
  background: var(--background);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.voices-header {
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.voices-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.voices-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.voice-section {
  background: var(--surface);
  border-radius: 6px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.voice-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--border);
  border-bottom: 1px solid var(--border);
}

.voice-id {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.fragments-count {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.voice-fragments {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.fragment {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem;
  background: var(--background);
  border-radius: 4px;
  border: 1px solid var(--border);
}

.fragment-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text);
}

.fragment-details {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.fragment-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: var(--surface);
  padding: 0.125rem 0.375rem;
  border-radius: 3px;
}

.fragment-notes {
  display: flex;
  gap: 0.25rem;
}

.note-pill.small {
  padding: 0.125rem 0.375rem;
  font-size: 0.625rem;
}

.fragment-duration {
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: var(--surface);
  padding: 0.125rem 0.375rem;
  border-radius: 3px;
}

/* Buttons */
.btn-icon {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text-secondary);
}

.btn-icon:hover {
  background: var(--border);
  color: var(--text);
}

.btn-icon.play-segment:hover {
  background: var(--primary);
  color: white;
}

.btn-icon.generate-voice:hover {
  background: var(--accent);
  color: white;
}

.btn-icon.generate-voice:disabled {
  background: var(--border);
  color: var(--text-secondary);
  cursor: not-allowed;
}

.btn-icon.delete-segment:hover {
  background: var(--error);
  color: white;
}

.btn-icon .icon {
  width: 14px;
  height: 14px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--surface);
  border-radius: 12px;
  width: 90vw;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
  border: 1px solid var(--border);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-header h3 {
  margin: 0;
  color: var(--text);
}

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

/* Form */
.form-group {
  margin-bottom: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: var(--text);
  font-weight: 500;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.form-help {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Scrollbar */
.lyrics-content::-webkit-scrollbar {
  width: 6px;
}

.lyrics-content::-webkit-scrollbar-track {
  background: transparent;
}

.lyrics-content::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.lyrics-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

/* Form validation */
.form-validation {
  margin-top: 1rem;
  padding: 0.75rem;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: 6px;
}

.validation-message {
  margin: 0;
  color: #ff6b6b;
  font-size: 0.875rem;
  font-weight: 500;
}

/* Voice Management Panel */
.voice-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 1rem;
  max-height: 60vh;
  overflow-y: auto;
}

.voice-panel-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.voice-panel-header h4 {
  margin: 0;
  color: var(--text);
}

.voice-tabs {
  padding: 1rem;
}

.tab-buttons {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  padding: 0.5rem 1rem;
  border: none;
  background: none;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s ease;
}

.tab-btn.active,
.tab-btn:hover {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.voices-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Loading voices */
.loading-voices {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2rem;
  color: var(--text-secondary);
}

.loading-voices .icon {
  width: 20px;
  height: 20px;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.voice-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.voice-select {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--background);
  color: var(--text);
}

.voice-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

.voice-card {
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--background);
  transition: all 0.2s ease;
}

.voice-card:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(0, 123, 204, 0.1);
}

.voice-card.selected {
  border-color: var(--primary);
  background: rgba(0, 123, 204, 0.05);
}

.voice-info {
  margin-bottom: 1rem;
}

.voice-info h5 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.voice-type {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: var(--border);
  border-radius: 4px;
  font-size: 0.75rem;
   margin-right: 0.5rem;
}

.voice-status {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  background: #ffd700;
  color: #000;
}

.voice-status.trained {
  background: #4caf50;
  color: white;
}

.voice-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.voice-actions .btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.voice-actions .btn .icon {
  width: 14px;
  height: 14px;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.btn-danger {
  background: #f44336;
  color: white;
}

.btn-danger:hover {
  background: #d32f2f;
}

/* Recording Section */
.recording-section {
  padding: 1rem 0;
}

.recording-header {
  margin-bottom: 1rem;
}

.recording-header h5 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.recording-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.recording-controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.btn-large {
  padding: 1rem 2rem;
  font-size: 1.1rem;
  min-width: 200px;
}

.recording-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.recording-time {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--primary);
  font-family: monospace;
}

.recording-indicator {
  width: 12px;
  height: 12px;
  background: #f44336;
  border-radius: 50%;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 1; }
}

.recorded-audio {
  padding: 1rem;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.recorded-audio h6 {
  margin: 0 0 1rem 0;
  color: var(--text);
}

.recorded-audio audio {
  width: 100%;
  margin-bottom: 1rem;
}

.audio-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.voice-name-input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--background);
  color: var(--text);
}

/* Upload Section */
.upload-section {
  padding: 1rem 0;
}

.upload-header {
  margin-bottom: 1rem;
}

.upload-header h5 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.upload-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.upload-area {
  border: 2px dashed var(--border);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--background);
}

.upload-area:hover {
  border-color: var(--primary);
  background: rgba(0, 123, 204, 0.05);
}

.upload-icon {
  width: 48px;
  height: 48px;
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

.upload-area h6 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.upload-area p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.uploaded-files {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.uploaded-files h6 {
  margin: 0 0 1rem 0;
  color: var(--text);
}

.file-list {
  margin-bottom: 1rem;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem;
  background: var(--background);
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.file-name {
  flex: 1;
  color: var(--text);
}

.file-size {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-right: 0.5rem;
}

.upload-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* Training Progress */
.training-progress {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--surface);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.training-progress h5 {
  margin: 0 0 1rem 0;
  color: var(--text);
}

.training-item {
  margin-bottom: 1rem;
}

.training-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.training-name {
  font-weight: 500;
  color: var(--text);
}

.training-status {
  font-size: 0.875rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.training-status.status-error {
  color: var(--error);
  font-weight: 500;
}

.training-error {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: rgba(var(--error-rgb), 0.1);
  border: 1px solid var(--error);
  border-radius: 4px;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--error);
  font-size: 0.875rem;
}

.error-message i {
  font-size: 1rem;
}

.training-info-text {
  margin-top: 0.5rem;
}

.training-note {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.training-note i {
  color: var(--primary);
}

.training-timing {
  margin-bottom: 0.5rem;
}

.timing-info {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.time-remaining {
  color: var(--primary);
  font-weight: 500;
}

.progress-bar {
  height: 8px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Transcription Status */
.transcription-status {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: var(--background);
  border-radius: 4px;
  border: 1px solid var(--border);
}

.transcription-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.transcription-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text);
}

.transcription-count {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.transcription-details {
  margin-top: 0.25rem;
}

.transcription-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.25rem;
  background: var(--surface);
  border-radius: 3px;
  border-left: 3px solid var(--border);
  margin-bottom: 0.25rem;
}

.transcription-file {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text);
}

.transcription-confidence {
  font-size: 0.75rem;
  font-weight: 500;
}

.confidence-high {
  color: #10b981;
  border-left-color: #10b981;
}

.confidence-medium {
  color: #f59e0b;
  border-left-color: #f59e0b;
}

.confidence-low {
  color: #ef4444;
  border-left-color: #ef4444;
}

.transcription-preview {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-style: italic;
  line-height: 1.3;
}

.transcription-error {
  font-size: 0.75rem;
  color: #ef4444;
  font-style: italic;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.format-info {
  font-size: 0.8rem !important;
  color: var(--primary) !important;
  background: var(--surface-light);
  padding: 0.5rem;
  border-radius: 4px;
  border-left: 3px solid var(--primary);
  margin: 0.75rem 0 !important;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .segment-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
  
  .notes-display {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
