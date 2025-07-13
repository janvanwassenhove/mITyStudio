"""
Voice Training Progress Monitor
Real-time monitoring of DiffSinger training jobs
"""

import time
import threading
import logging
from typing import Dict, Callable, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TrainingProgress:
    """Training progress data structure"""
    job_id: str
    voice_name: str
    epoch: int
    total_epochs: int
    loss: float
    validation_loss: Optional[float]
    learning_rate: float
    eta_seconds: int
    status: str
    message: str


class TrainingMonitor:
    """Monitor and manage training job progress"""
    
    def __init__(self):
        self.active_jobs: Dict[str, Dict] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        self.monitor_thread = None
        self.running = False
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("Training monitor started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Training monitor stopped")
    
    def register_job(self, job_id: str, job_config: Dict, 
                    progress_callback: Optional[Callable] = None):
        """Register a new training job for monitoring"""
        self.active_jobs[job_id] = {
            'config': job_config,
            'start_time': time.time(),
            'last_update': time.time(),
            'progress': TrainingProgress(
                job_id=job_id,
                voice_name=job_config.get('voice_name', 'Unknown'),
                epoch=0,
                total_epochs=job_config.get('training', {}).get('epochs', 100),
                loss=float('inf'),
                validation_loss=None,
                learning_rate=job_config.get('training', {}).get('learning_rate', 0.0001),
                eta_seconds=0,
                status='starting',
                message='Initializing training...'
            )
        }
        
        if progress_callback:
            self.progress_callbacks[job_id] = progress_callback
        
        logger.info(f"Registered training job {job_id}")
    
    def update_progress(self, job_id: str, **kwargs):
        """Update progress for a specific job"""
        if job_id not in self.active_jobs:
            return
        
        job = self.active_jobs[job_id]
        progress = job['progress']
        
        # Update progress fields
        for key, value in kwargs.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
        
        # Calculate ETA
        if progress.epoch > 0:
            elapsed = time.time() - job['start_time']
            epochs_per_second = progress.epoch / elapsed
            remaining_epochs = progress.total_epochs - progress.epoch
            progress.eta_seconds = int(remaining_epochs / epochs_per_second) if epochs_per_second > 0 else 0
        
        job['last_update'] = time.time()
        
        # Call progress callback if registered
        if job_id in self.progress_callbacks:
            try:
                self.progress_callbacks[job_id](asdict(progress))
            except Exception as e:
                logger.error(f"Error in progress callback for {job_id}: {e}")
    
    def get_progress(self, job_id: str) -> Optional[TrainingProgress]:
        """Get current progress for a job"""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]['progress']
        return None
    
    def complete_job(self, job_id: str, success: bool = True, message: str = ""):
        """Mark a job as completed"""
        if job_id in self.active_jobs:
            progress = self.active_jobs[job_id]['progress']
            progress.status = 'completed' if success else 'failed'
            progress.message = message or ('Training completed successfully' if success else 'Training failed')
            progress.epoch = progress.total_epochs if success else progress.epoch
            
            # Keep completed jobs for a while before cleanup
            threading.Timer(300, lambda: self._cleanup_job(job_id)).start()  # 5 minutes
    
    def cancel_job(self, job_id: str):
        """Cancel a training job"""
        if job_id in self.active_jobs:
            progress = self.active_jobs[job_id]['progress']
            progress.status = 'cancelled'
            progress.message = 'Training cancelled by user'
    
    def _cleanup_job(self, job_id: str):
        """Remove a job from monitoring"""
        if job_id in self.active_jobs:
            del self.active_jobs[job_id]
        if job_id in self.progress_callbacks:
            del self.progress_callbacks[job_id]
        logger.info(f"Cleaned up training job {job_id}")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # Check for stale jobs (no updates for 30 minutes)
                stale_jobs = []
                for job_id, job in self.active_jobs.items():
                    if current_time - job['last_update'] > 1800:  # 30 minutes
                        stale_jobs.append(job_id)
                
                # Mark stale jobs as failed
                for job_id in stale_jobs:
                    logger.warning(f"Training job {job_id} appears stale, marking as failed")
                    self.complete_job(job_id, success=False, message="Training appears to have stalled")
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in training monitor loop: {e}")
                time.sleep(60)  # Wait longer on error


# Global training monitor instance
training_monitor = TrainingMonitor()
