"""
Progress Tracker Module

Handles state persistence for resume capability and progress reporting.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

STATE_FILE_NAME = "migration_state.json"


@dataclass
class MigrationState:
    """Migration state data structure."""
    
    # Timestamps
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    
    # Input info
    input_file: str = ""
    total_items: int = 0
    
    # Progress counters
    processed_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    
    # Tracking
    processed_urls: List[str] = field(default_factory=list)
    failed_items: List[Dict[str, str]] = field(default_factory=list)
    mappings: List[Dict[str, str]] = field(default_factory=list)


class ProgressTracker:
    """
    Tracks migration progress and persists state for resume capability.
    """
    
    def __init__(self, state_dir: str, input_file: str = ""):
        """
        Initialize the progress tracker.
        
        Args:
            state_dir: Directory to store state file
            input_file: Path to the input CSV file
        """
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, STATE_FILE_NAME)
        self.state = MigrationState()
        self.state.input_file = input_file
        
        # Ensure state directory exists
        os.makedirs(state_dir, exist_ok=True)
    
    def load_state(self) -> bool:
        """
        Load state from file if exists.
        
        Returns:
            True if state was loaded, False if starting fresh
        """
        if not os.path.exists(self.state_file):
            self.state.started_at = datetime.now().isoformat()
            return False
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.state = MigrationState(**data)
            
            logger.info(f"Loaded state: {self.state.processed_count}/{self.state.total_items} processed")
            return True
            
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.state.started_at = datetime.now().isoformat()
            return False
    
    def save_state(self) -> None:
        """Save current state to file."""
        self.state.updated_at = datetime.now().isoformat()
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def set_total(self, total: int) -> None:
        """Set total number of items to process."""
        self.state.total_items = total
    
    def is_processed(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        return url in self.state.processed_urls
    
    def mark_success(
        self, 
        url: str, 
        new_url: str, 
        image_id: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Mark an item as successfully processed.
        
        Args:
            url: Original image URL
            new_url: New Cloudflare Images URL
            image_id: Cloudflare image ID
            metadata: Optional additional metadata
        """
        self.state.processed_urls.append(url)
        self.state.processed_count += 1
        self.state.success_count += 1
        
        mapping = {
            'old_url': url,
            'new_url': new_url,
            'cloudflare_image_id': image_id,
            'status': 'success',
            'error': ''
        }
        
        if metadata:
            mapping.update(metadata)
        
        self.state.mappings.append(mapping)
        
        # Auto-save periodically
        if self.state.processed_count % 10 == 0:
            self.save_state()
    
    def mark_failed(
        self, 
        url: str, 
        error: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Mark an item as failed.
        
        Args:
            url: Original image URL
            error: Error message
            metadata: Optional additional metadata
        """
        self.state.processed_urls.append(url)
        self.state.processed_count += 1
        self.state.failed_count += 1
        
        failed_item = {
            'old_url': url,
            'new_url': '',
            'cloudflare_image_id': '',
            'status': 'failed',
            'error': error
        }
        
        if metadata:
            failed_item.update(metadata)
        
        self.state.failed_items.append(failed_item)
        self.state.mappings.append(failed_item)
        
        # Auto-save on failures
        self.save_state()
    
    def mark_skipped(self, url: str, reason: str = "") -> None:
        """Mark an item as skipped."""
        self.state.processed_urls.append(url)
        self.state.processed_count += 1
        self.state.skipped_count += 1
    
    def mark_complete(self) -> None:
        """Mark migration as complete."""
        self.state.completed_at = datetime.now().isoformat()
        self.save_state()
    
    def get_mappings(self) -> List[Dict[str, str]]:
        """Get all mappings (success and failed)."""
        return self.state.mappings
    
    def get_successful_mappings(self) -> List[Dict[str, str]]:
        """Get only successful mappings."""
        return [m for m in self.state.mappings if m.get('status') == 'success']
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress statistics."""
        progress_pct = 0
        if self.state.total_items > 0:
            progress_pct = (self.state.processed_count / self.state.total_items) * 100
        
        return {
            'total': self.state.total_items,
            'processed': self.state.processed_count,
            'success': self.state.success_count,
            'failed': self.state.failed_count,
            'skipped': self.state.skipped_count,
            'remaining': self.state.total_items - self.state.processed_count,
            'progress_percent': round(progress_pct, 1)
        }
    
    def print_summary(self) -> None:
        """Print a summary of the migration."""
        progress = self.get_progress()
        
        print("\n" + "=" * 50)
        print("MIGRATION SUMMARY")
        print("=" * 50)
        print(f"Total items:    {progress['total']}")
        print(f"Processed:      {progress['processed']}")
        print(f"  ✓ Success:    {progress['success']}")
        print(f"  ✗ Failed:     {progress['failed']}")
        print(f"  ⊘ Skipped:    {progress['skipped']}")
        print(f"Progress:       {progress['progress_percent']}%")
        
        if self.state.failed_count > 0:
            print("\nFailed items:")
            for item in self.state.failed_items[:5]:  # Show first 5
                print(f"  - {item.get('old_url', 'unknown')[:60]}...")
                print(f"    Error: {item.get('error', 'unknown')}")
            if self.state.failed_count > 5:
                print(f"  ... and {self.state.failed_count - 5} more")
        
        print("=" * 50 + "\n")
    
    def reset(self) -> None:
        """Reset state (use with caution)."""
        self.state = MigrationState()
        self.state.started_at = datetime.now().isoformat()
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        logger.info("State reset")
