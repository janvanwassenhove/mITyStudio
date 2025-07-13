"""
Database Models for mITyStudio Backend
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True)  # UUID
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Preferences
    preferences = Column(JSON, default={})
    
    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    """Project model"""
    __tablename__ = 'projects'
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50), default='pop')
    tempo = Column(Integer, default=120)
    key = Column(String(10), default='C')
    time_signature = Column(String(10), default='4/4')
    duration = Column(Float, default=0.0)  # in seconds
    
    # User relationship
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    user = relationship("User", back_populates="projects")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Settings and metadata
    settings = Column(JSON, default={})
    project_metadata = Column(JSON, default={})
    
    # Relationships
    tracks = relationship("Track", back_populates="project", cascade="all, delete-orphan")


class Track(Base):
    """Track model"""
    __tablename__ = 'tracks'
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(200), nullable=False)
    instrument = Column(String(100), default='piano')
    volume = Column(Float, default=0.8)
    pan = Column(Float, default=0.0)  # -1.0 (left) to 1.0 (right)
    muted = Column(Boolean, default=False)
    soloed = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    
    # Effects and processing
    effects = Column(JSON, default={})
    
    # Project relationship
    project_id = Column(String(36), ForeignKey('projects.id'), nullable=False)
    project = relationship("Project", back_populates="tracks")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    clips = relationship("Clip", back_populates="track", cascade="all, delete-orphan")


class Clip(Base):
    """Clip model"""
    __tablename__ = 'clips'
    
    id = Column(String(36), primary_key=True)  # UUID
    start_time = Column(Float, nullable=False)  # in seconds
    duration = Column(Float, nullable=False)  # in seconds
    clip_type = Column(String(50), default='synth')  # synth, audio, midi
    instrument = Column(String(100), default='piano')
    volume = Column(Float, default=0.7)
    
    # Audio/MIDI data
    audio_file_id = Column(String(36))  # Reference to audio file
    midi_data = Column(JSON, default=[])  # MIDI note data
    
    # Effects
    effects = Column(JSON, default={})
    
    # Track relationship
    track_id = Column(String(36), ForeignKey('tracks.id'), nullable=False)
    track = relationship("Track", back_populates="clips")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AudioFile(Base):
    """Audio file model"""
    __tablename__ = 'audio_files'
    
    id = Column(String(36), primary_key=True)  # UUID
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    sample_rate = Column(Integer, nullable=False)
    channels = Column(Integer, nullable=False)
    format = Column(String(10), nullable=False)  # wav, mp3, etc.
    
    # Audio analysis data
    waveform_data = Column(JSON)  # Downsampled waveform for visualization
    analysis_data = Column(JSON)  # Tempo, key, etc.
    
    # User relationship
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatSession(Base):
    """Chat session model for AI conversations"""
    __tablename__ = 'chat_sessions'
    
    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    project_id = Column(String(36), ForeignKey('projects.id'))  # Optional project context
    
    # Session data
    messages = Column(JSON, default=[])  # Chat message history
    context = Column(JSON, default={})  # Additional context data
    
    # AI settings
    provider = Column(String(50), default='anthropic')
    model = Column(String(100), default='claude-sonnet-4')
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIGeneration(Base):
    """AI generation history and results"""
    __tablename__ = 'ai_generations'
    
    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    project_id = Column(String(36), ForeignKey('projects.id'))  # Optional project context
    
    # Generation details
    generation_type = Column(String(50), nullable=False)  # chord_progression, melody, etc.
    prompt = Column(Text, nullable=False)
    parameters = Column(JSON, default={})
    
    # Results
    result_data = Column(JSON, nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    
    # Quality metrics
    user_rating = Column(Integer)  # 1-5 stars
    used_in_project = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create all tables
def create_tables(engine):
    """Create all database tables"""
    Base.metadata.create_all(engine)
