"""
Song Structure Models
Python models that match the JSON contract defined in README.md
"""

from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class LyricFragment:
    """Individual lyric fragment with timing and notes"""
    text: str
    notes: List[str]
    start: float
    duration: Optional[float] = None
    durations: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'text': self.text,
            'notes': self.notes,
            'start': self.start
        }
        if self.duration is not None:
            result['duration'] = self.duration
        if self.durations is not None:
            result['durations'] = self.durations
        return result


@dataclass
class Voice:
    """Voice definition with multiple lyric fragments"""
    voice_id: str
    lyrics: List[LyricFragment]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'voice_id': self.voice_id,
            'lyrics': [fragment.to_dict() for fragment in self.lyrics]
        }


@dataclass
class Effects:
    """Audio effects settings"""
    reverb: float = 0.0
    delay: float = 0.0
    distortion: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AudioClip:
    """Audio/MIDI/Lyrics clip definition"""
    id: str
    trackId: str
    startTime: float
    duration: float
    type: str  # "synth", "sample", or "lyrics"
    instrument: str
    volume: float
    effects: Effects
    notes: Optional[List[str]] = None
    sampleUrl: Optional[str] = None
    waveform: Optional[List[float]] = None
    
    # Simple lyrics fields (for basic arrangements)
    text: Optional[str] = None
    chordName: Optional[str] = None
    voiceId: Optional[str] = None
    
    # Advanced multi-voice structure (mutually exclusive with simple fields)
    voices: Optional[List[Voice]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'trackId': self.trackId,
            'startTime': self.startTime,
            'duration': self.duration,
            'type': self.type,
            'instrument': self.instrument,
            'volume': self.volume,
            'effects': self.effects.to_dict()
        }
        
        # Add optional fields only if they exist
        if self.notes is not None:
            result['notes'] = self.notes
        if self.sampleUrl is not None:
            result['sampleUrl'] = self.sampleUrl
        if self.waveform is not None:
            result['waveform'] = self.waveform
        if self.text is not None:
            result['text'] = self.text
        if self.chordName is not None:
            result['chordName'] = self.chordName
        if self.voiceId is not None:
            result['voiceId'] = self.voiceId
        if self.voices is not None:
            result['voices'] = [voice.to_dict() for voice in self.voices]
            
        return result

    def is_lyrics_clip(self) -> bool:
        """Check if this is a lyrics clip"""
        return self.type == 'lyrics'

    def has_multi_voice(self) -> bool:
        """Check if this clip uses the advanced multi-voice structure"""
        return self.voices is not None and len(self.voices) > 0

    def validate_lyrics_structure(self) -> bool:
        """Validate that lyrics clip doesn't mix simple and advanced structures"""
        if not self.is_lyrics_clip():
            return True
            
        has_simple = any([self.text, self.chordName, self.voiceId])
        has_advanced = self.has_multi_voice()
        
        # Should not have both simple and advanced structures
        return not (has_simple and has_advanced)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioClip':
        """Create AudioClip from dictionary"""
        # Parse effects
        effects_data = data.get('effects', {})
        effects = Effects(
            reverb=effects_data.get('reverb', 0.0),
            delay=effects_data.get('delay', 0.0),
            distortion=effects_data.get('distortion', 0.0)
        )
        
        # Parse voices if they exist
        voices = None
        if 'voices' in data and data['voices']:
            voices = []
            for voice_data in data['voices']:
                # Parse lyric fragments
                fragments = []
                for fragment_data in voice_data.get('lyrics', []):
                    fragment = LyricFragment(
                        text=fragment_data.get('text', ''),
                        notes=fragment_data.get('notes', []),
                        start=fragment_data.get('start', 0.0),
                        duration=fragment_data.get('duration'),
                        durations=fragment_data.get('durations')
                    )
                    fragments.append(fragment)
                
                voice = Voice(
                    voice_id=voice_data.get('voice_id', ''),
                    lyrics=fragments
                )
                voices.append(voice)
        
        return cls(
            id=data.get('id', ''),
            trackId=data.get('trackId', ''),
            startTime=data.get('startTime', 0.0),
            duration=data.get('duration', 4.0),
            type=data.get('type', 'synth'),
            instrument=data.get('instrument', 'piano'),
            volume=data.get('volume', 0.7),
            effects=effects,
            notes=data.get('notes'),
            sampleUrl=data.get('sampleUrl'),
            waveform=data.get('waveform'),
            text=data.get('text'),
            chordName=data.get('chordName'),
            voiceId=data.get('voiceId'),
            voices=voices
        )


@dataclass
class Track:
    """Track definition"""
    id: str
    name: str
    instrument: str
    volume: float
    pan: float
    muted: bool
    solo: bool
    clips: List[AudioClip]
    effects: Effects
    category: Optional[str] = None
    sampleUrl: Optional[str] = None
    isSample: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'name': self.name,
            'instrument': self.instrument,
            'volume': self.volume,
            'pan': self.pan,
            'muted': self.muted,
            'solo': self.solo,
            'clips': [clip.to_dict() for clip in self.clips],
            'effects': self.effects.to_dict()
        }
        
        # Add optional fields only if they exist
        if self.category is not None:
            result['category'] = self.category
        if self.sampleUrl is not None:
            result['sampleUrl'] = self.sampleUrl
        if self.isSample is not None:
            result['isSample'] = self.isSample
            
        return result


@dataclass
class SongStructure:
    """Complete song structure definition"""
    id: str
    name: str
    tempo: int
    timeSignature: List[int]  # [beats_per_bar, note_value]
    key: str
    tracks: List[Track]
    duration: float
    createdAt: str
    updatedAt: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'tempo': self.tempo,
            'timeSignature': self.timeSignature,
            'key': self.key,
            'tracks': [track.to_dict() for track in self.tracks],
            'duration': self.duration,
            'createdAt': self.createdAt,
            'updatedAt': self.updatedAt
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SongStructure':
        """Create SongStructure from dictionary"""
        # Parse tracks
        tracks = []
        for track_data in data.get('tracks', []):
            # Parse clips
            clips = []
            for clip_data in track_data.get('clips', []):
                # Parse effects
                effects_data = clip_data.get('effects', {})
                effects = Effects(
                    reverb=effects_data.get('reverb', 0.0),
                    delay=effects_data.get('delay', 0.0),
                    distortion=effects_data.get('distortion', 0.0)
                )
                
                # Parse voices if they exist
                voices = None
                if 'voices' in clip_data and clip_data['voices']:
                    voices = []
                    for voice_data in clip_data['voices']:
                        # Parse lyric fragments
                        fragments = []
                        for fragment_data in voice_data.get('lyrics', []):
                            fragment = LyricFragment(
                                text=fragment_data['text'],
                                notes=fragment_data['notes'],
                                start=fragment_data['start'],
                                duration=fragment_data.get('duration'),
                                durations=fragment_data.get('durations')
                            )
                            fragments.append(fragment)
                        
                        voice = Voice(
                            voice_id=voice_data['voice_id'],
                            lyrics=fragments
                        )
                        voices.append(voice)
                
                clip = AudioClip(
                    id=clip_data['id'],
                    trackId=clip_data['trackId'],
                    startTime=clip_data['startTime'],
                    duration=clip_data['duration'],
                    type=clip_data['type'],
                    instrument=clip_data['instrument'],
                    volume=clip_data['volume'],
                    effects=effects,
                    notes=clip_data.get('notes'),
                    sampleUrl=clip_data.get('sampleUrl'),
                    waveform=clip_data.get('waveform'),
                    text=clip_data.get('text'),
                    chordName=clip_data.get('chordName'),
                    voiceId=clip_data.get('voiceId'),
                    voices=voices
                )
                clips.append(clip)
            
            # Parse track effects
            track_effects_data = track_data.get('effects', {})
            track_effects = Effects(
                reverb=track_effects_data.get('reverb', 0.0),
                delay=track_effects_data.get('delay', 0.0),
                distortion=track_effects_data.get('distortion', 0.0)
            )
            
            track = Track(
                id=track_data['id'],
                name=track_data['name'],
                instrument=track_data['instrument'],
                volume=track_data['volume'],
                pan=track_data['pan'],
                muted=track_data['muted'],
                solo=track_data['solo'],
                clips=clips,
                effects=track_effects,
                category=track_data.get('category'),
                sampleUrl=track_data.get('sampleUrl'),
                isSample=track_data.get('isSample')
            )
            tracks.append(track)
        
        return cls(
            id=data['id'],
            name=data['name'],
            tempo=data['tempo'],
            timeSignature=data['timeSignature'],
            key=data['key'],
            tracks=tracks,
            duration=data['duration'],
            createdAt=data['createdAt'],
            updatedAt=data['updatedAt']
        )

    @classmethod
    def from_project_data(cls, project_data: Dict[str, Any]) -> 'SongStructure':
        """Convert legacy project data to new song structure format"""
        import uuid
        from datetime import datetime
        
        # Convert project metadata to song structure format
        song_id = project_data.get('id', str(uuid.uuid4()))
        
        # Parse time signature
        time_sig_str = project_data.get('time_signature', '4/4')
        time_sig_parts = time_sig_str.split('/')
        time_signature = [int(time_sig_parts[0]), int(time_sig_parts[1])]
        
        # Convert tracks
        tracks = []
        for track_data in project_data.get('tracks', []):
            track_id = track_data.get('id', str(uuid.uuid4()))
            
            # Convert clips
            clips = []
            for clip_data in track_data.get('clips', []):
                clip_id = clip_data.get('id', str(uuid.uuid4()))
                
                # Convert effects
                effects_data = clip_data.get('effects', {})
                effects = Effects(
                    reverb=effects_data.get('reverb', 0.0),
                    delay=effects_data.get('delay', 0.0),
                    distortion=effects_data.get('distortion', 0.0)
                )
                
                # Handle new multi-voice structure if present
                voices = None
                if 'voices' in clip_data and clip_data['voices']:
                    voices = []
                    for voice_data in clip_data['voices']:
                        fragments = []
                        for fragment_data in voice_data.get('lyrics', []):
                            fragment = LyricFragment(
                                text=fragment_data.get('text', ''),
                                notes=fragment_data.get('notes', []),
                                start=fragment_data.get('start', 0.0),
                                duration=fragment_data.get('duration'),
                                durations=fragment_data.get('durations')
                            )
                            fragments.append(fragment)
                        
                        voice = Voice(
                            voice_id=voice_data.get('voice_id', ''),
                            lyrics=fragments
                        )
                        voices.append(voice)
                
                clip = AudioClip(
                    id=clip_id,
                    trackId=track_id,
                    startTime=clip_data.get('start_time', 0.0),
                    duration=clip_data.get('duration', 4.0),
                    type=clip_data.get('type', 'synth'),
                    instrument=clip_data.get('instrument', 'piano'),
                    volume=clip_data.get('volume', 0.7),
                    effects=effects,
                    notes=clip_data.get('midi_data', []),
                    sampleUrl=clip_data.get('sample_url'),
                    waveform=clip_data.get('waveform'),
                    text=clip_data.get('lyrics'),  # Legacy lyrics field
                    chordName=clip_data.get('chord_name'),
                    voiceId=clip_data.get('voice_id'),  # Legacy voice field
                    voices=voices  # New multi-voice structure
                )
                clips.append(clip)
            
            # Convert track effects
            track_effects_data = track_data.get('effects', {})
            track_effects = Effects(
                reverb=track_effects_data.get('reverb', 0.0),
                delay=track_effects_data.get('delay', 0.0),
                distortion=track_effects_data.get('distortion', 0.0)
            )
            
            track = Track(
                id=track_id,
                name=track_data.get('name', 'Track'),
                instrument=track_data.get('instrument', 'piano'),
                volume=track_data.get('volume', 0.8),
                pan=track_data.get('pan', 0.0),
                muted=track_data.get('muted', False),
                solo=track_data.get('soloed', False),
                clips=clips,
                effects=track_effects,
                category=track_data.get('category'),
                sampleUrl=track_data.get('sample_url'),
                isSample=track_data.get('is_sample', False)
            )
            tracks.append(track)
        
        return cls(
            id=song_id,
            name=project_data.get('name', 'Untitled Song'),
            tempo=project_data.get('tempo', 120),
            timeSignature=time_signature,
            key=project_data.get('key', 'C'),
            tracks=tracks,
            duration=project_data.get('duration', 0.0),
            createdAt=project_data.get('created_at', datetime.utcnow().isoformat()),
            updatedAt=project_data.get('updated_at', datetime.utcnow().isoformat())
        )

    def get_lyrics_track(self) -> Optional[Track]:
        """Get the lyrics & vocals track if it exists"""
        for track in self.tracks:
            if track.name == "Lyrics & Vocals" or track.instrument == "vocals":
                return track
        return None

    def validate(self) -> List[str]:
        """Validate the song structure and return any errors"""
        errors = []
        
        # Validate lyrics clips
        lyrics_track = self.get_lyrics_track()
        if lyrics_track:
            for clip in lyrics_track.clips:
                if clip.is_lyrics_clip() and not clip.validate_lyrics_structure():
                    errors.append(f"Lyrics clip {clip.id} mixes simple and advanced voice structures")
        
        return errors
