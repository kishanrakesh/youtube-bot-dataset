import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from google.cloud import storage

from app.utils.gcs_utils import read_json_from_gcs, write_json_to_gcs

__all__ = ["ManifestManager"]

logger = logging.getLogger(__name__)

BUCKET_NAME = "yt-bot-data"


# ═══════════════════════════════════════════════════════════════════
# Legacy functions (maintained for backward compatibility)
# ═══════════════════════════════════════════════════════════════════

def is_already_fetched(manifest_path: str, key: str) -> bool:
    manifest = read_json_from_gcs(BUCKET_NAME, manifest_path) or {}
    already_fetched = key in manifest
    logger.debug(f"Check if '{key}' is in manifest '{manifest_path}': {already_fetched}")
    return already_fetched

def update_manifest(manifest_path: str, key: str):
    manifest = read_json_from_gcs(BUCKET_NAME, manifest_path) or {}
    manifest[key] = True
    write_json_to_gcs(BUCKET_NAME, manifest_path, manifest)
    logger.info(f"Updated manifest '{manifest_path}' with key '{key}'")


# ═══════════════════════════════════════════════════════════════════
# Modern ManifestManager class (recommended for new code)
# ═══════════════════════════════════════════════════════════════════

class ManifestManager:
    """Manages manifest files for tracking processing state in GCS.
    
    Manifest structure:
    {
        "completed": ["path/to/file1.json", "path/to/file2.json"],
        "in_progress": "path/to/current.json" or null,
        "last_run": "2025-11-14T12:00:00Z"
    }
    
    Usage:
        manager = ManifestManager(bucket="my-bucket", manifest_path="path/to/manifest.json")
        
        if manager.is_completed("file.json"):
            return
            
        manager.mark_in_progress("file.json")
        # ... do work ...
        manager.mark_completed("file.json")
    """
    
    def __init__(self, bucket: str, manifest_path: str, storage_client: Optional[storage.Client] = None):
        """Initialize the manifest manager.
        
        Args:
            bucket: GCS bucket name
            manifest_path: Path to manifest file in bucket
            storage_client: Optional pre-configured storage client (for testing/reuse)
        """
        self.bucket = bucket
        self.manifest_path = manifest_path
        self._storage_client = storage_client or storage.Client()
        self._blob = self._storage_client.bucket(bucket).blob(manifest_path)
        
    def load(self) -> Dict:
        """Load manifest from GCS or return default structure.
        
        Returns:
            Manifest dictionary with completed, in_progress, and last_run fields
        """
        if not self._blob.exists():
            return {"completed": [], "in_progress": None, "last_run": None}
        try:
            return json.loads(self._blob.download_as_bytes())
        except Exception as e:
            logger.warning(f"Failed to load manifest {self.manifest_path}: {e}")
            return {"completed": [], "in_progress": None, "last_run": None}
    
    def save(self, manifest: Dict) -> None:
        """Save manifest to GCS with updated timestamp.
        
        Args:
            manifest: Manifest dictionary to save
        """
        manifest["last_run"] = datetime.now().isoformat(timespec="seconds") + "Z"
        self._blob.upload_from_string(json.dumps(manifest, ensure_ascii=False))
        logger.debug(f"Saved manifest to {self.manifest_path}")
    
    def is_completed(self, gcs_path: str) -> bool:
        """Check if a file has been marked as completed.
        
        Args:
            gcs_path: Path to check
            
        Returns:
            True if file is in completed list
        """
        manifest = self.load()
        return gcs_path in manifest.get("completed", [])
    
    def is_in_progress(self, gcs_path: Optional[str] = None) -> bool:
        """Check if a file is currently in progress.
        
        Args:
            gcs_path: Optional specific path to check. If None, checks if ANY file is in progress.
            
        Returns:
            True if file (or any file) is marked as in progress
        """
        manifest = self.load()
        current_in_progress = manifest.get("in_progress")
        
        if gcs_path is None:
            return current_in_progress is not None
        
        return current_in_progress == gcs_path
    
    def get_in_progress(self) -> Optional[str]:
        """Get the currently in-progress file path.
        
        Returns:
            Path of file currently in progress, or None
        """
        manifest = self.load()
        return manifest.get("in_progress")
    
    def get_completed(self) -> List[str]:
        """Get list of all completed file paths.
        
        Returns:
            List of completed file paths
        """
        manifest = self.load()
        return manifest.get("completed", [])
    
    def mark_in_progress(self, gcs_path: str) -> None:
        """Mark a file as currently being processed.
        
        Args:
            gcs_path: Path to file being processed
        """
        manifest = self.load()
        manifest["in_progress"] = gcs_path
        self.save(manifest)
        logger.info(f"Marked {gcs_path} as in progress in {self.manifest_path}")
    
    def mark_completed(self, gcs_path: str) -> None:
        """Mark a file as completed and clear in_progress.
        
        Args:
            gcs_path: Path to completed file
        """
        manifest = self.load()
        
        if gcs_path not in manifest.get("completed", []):
            manifest.setdefault("completed", []).append(gcs_path)
        
        manifest["in_progress"] = None
        self.save(manifest)
        logger.info(f"Marked {gcs_path} as completed in {self.manifest_path}")
    
    def clear_in_progress(self) -> None:
        """Clear the in_progress field (useful for error recovery)."""
        manifest = self.load()
        manifest["in_progress"] = None
        self.save(manifest)
        logger.info(f"Cleared in_progress in {self.manifest_path}")
    
    def reset(self) -> None:
        """Reset manifest to default state (for testing/debugging)."""
        manifest = {"completed": [], "in_progress": None, "last_run": None}
        self.save(manifest)
        logger.warning(f"Reset manifest {self.manifest_path}")
