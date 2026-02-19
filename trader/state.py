"""State management for scraper persistence and crash recovery.

This module provides state persistence capabilities so that scraper progress
can be saved on crash and resumed on restart.
"""

import json
import time
from typing import Optional, Dict, Any
from pathlib import Path


class StateManager:
    """Manages scraper state for persistence and crash recovery.
    
    The StateManager maintains the current state of scraping operations including:
    - Last URL processed
    - Current page number
    - Timestamp of last update
    - Items processed count
    - Retry count
    
    State can be:
    - Saved to a JSON file
    - Loaded from a JSON file on startup
    - Auto-saved at configurable intervals
    - Saved on uncaught exceptions (crash recovery)
    
    Attributes:
        url: The last URL being processed
        page: The current page number
        items_processed: Number of items processed so far
        retry_count: Current retry attempt count
        auto_save_interval: Auto-save after every N items (0 to disable)
        filepath: Default filepath for save/load operations
    """
    
    def __init__(
        self,
        url: str = "",
        page: int = 1,
        items_processed: int = 0,
        retry_count: int = 0,
        auto_save_interval: int = 10,
        filepath: Optional[str] = None
    ) -> None:
        """Initialize the state manager.
        
        Args:
            url: The last URL being processed (default: empty string)
            page: The current page number (default: 1)
            items_processed: Number of items processed (default: 0)
            retry_count: Current retry attempt count (default: 0)
            auto_save_interval: Auto-save every N items, 0 to disable (default: 10)
            filepath: Default filepath for save/load operations (default: None)
        """
        self.url = url
        self.page = page
        self.items_processed = items_processed
        self.retry_count = retry_count
        self.auto_save_interval = auto_save_interval
        self.filepath = filepath
        self._last_save_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a dictionary.
        
        Returns:
            Dictionary containing all state fields with timestamp.
        """
        return {
            "url": self.url,
            "page": self.page,
            "items_processed": self.items_processed,
            "retry_count": self.retry_count,
            "timestamp": time.time()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load state from a dictionary.
        
        Args:
            data: Dictionary containing state fields.
        """
        self.url = data.get("url", "")
        self.page = data.get("page", 1)
        self.items_processed = data.get("items_processed", 0)
        self.retry_count = data.get("retry_count", 0)
    
    def save(self, filepath: Optional[str] = None) -> None:
        """Save state to a JSON file.
        
        Args:
            filepath: Path to save the state file. Uses instance default if None.
        
        Raises:
            ValueError: If no filepath is provided and no default is set.
        """
        target_path = filepath or self.filepath
        if target_path is None:
            raise ValueError("No filepath provided and no default filepath set")
        
        # Ensure parent directory exists
        path_obj = Path(target_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Write state to JSON file
        with open(target_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        # Update last save count
        self._last_save_count = self.items_processed
    
    def load(self, filepath: Optional[str] = None) -> bool:
        """Load state from a JSON file.
        
        Args:
            filepath: Path to the state file to load. Uses instance default if None.
        
        Returns:
            True if state was loaded successfully, False if file doesn't exist.
        
        Raises:
            ValueError: If no filepath is provided and no default is set.
        """
        target_path = filepath or self.filepath
        if target_path is None:
            raise ValueError("No filepath provided and no default filepath set")
        
        path_obj = Path(target_path)
        if not path_obj.exists():
            return False
        
        with open(target_path, 'r') as f:
            data = json.load(f)
        
        self.from_dict(data)
        self._last_save_count = self.items_processed
        return True
    
    def record_item(self, filepath: Optional[str] = None) -> bool:
        """Record an item being processed and auto-save if needed.
        
        Increments items_processed counter and triggers auto-save if the
        configured interval has been reached.
        
        Args:
            filepath: Optional filepath for auto-save. Uses instance default if None.
        
        Returns:
            True if auto-save was triggered, False otherwise.
        """
        self.items_processed += 1
        
        # Check if auto-save should trigger
        if self.auto_save_interval > 0:
            items_since_save = self.items_processed - self._last_save_count
            if items_since_save >= self.auto_save_interval:
                self.save(filepath)
                return True
        
        return False
    
    def update(
        self,
        url: Optional[str] = None,
        page: Optional[int] = None,
        retry_count: Optional[int] = None
    ) -> None:
        """Update state fields.
        
        Args:
            url: New URL to set (if provided)
            page: New page number to set (if provided)
            retry_count: New retry count to set (if provided)
        """
        if url is not None:
            self.url = url
        if page is not None:
            self.page = page
        if retry_count is not None:
            self.retry_count = retry_count
    
    def save_on_crash(self, filepath: Optional[str] = None) -> None:
        """Save state for crash recovery.
        
        This method is designed to be called from exception handlers
        to ensure state is persisted on uncaught exceptions.
        
        Args:
            filepath: Optional filepath for saving. Uses instance default if None.
        """
        try:
            self.save(filepath)
        except Exception:
            # Best effort - don't let crash saving cause additional failures
            pass
    
    def get_timestamp(self) -> Optional[float]:
        """Get the timestamp from the current state.
        
        Returns:
            The timestamp from the last save, or None if not set.
        """
        return self.to_dict().get("timestamp")
    
    def __repr__(self) -> str:
        """String representation of the state manager."""
        return (
            f"StateManager(url={self.url!r}, page={self.page}, "
            f"items_processed={self.items_processed}, retry_count={self.retry_count})"
        )
