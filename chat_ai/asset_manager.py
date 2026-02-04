"""
Asset Manager - Multi-modal content storage and delivery system
Handles images, videos, 3D models, and 360° panoramas
"""
import os
import json
import hashlib
import shutil
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AssetManager:
    """Manages generated and uploaded media assets for the Universal Platform."""
    
    SUPPORTED_TYPES = {
        'image': ['.png', '.jpg', '.jpeg', '.webp', '.gif'],
        'video': ['.mp4', '.webm', '.mov'],
        '360_video': ['.mp4', '.webm'],  # 360° videos
        '3d_model': ['.gltf', '.glb', '.obj', '.fbx'],
        'audio': ['.mp3', '.wav', '.ogg']
    }
    
    def __init__(self, storage_dir: str = 'assets'):
        """
        Initialize Asset Manager.
        
        Args:
            storage_dir: Base directory for asset storage
        """
        self.storage_dir = storage_dir
        self.metadata_file = os.path.join(storage_dir, 'assets_metadata.json')
        
        # Create storage structure
        self._init_storage()
        
        # Load metadata
        self.metadata = self._load_metadata()
    
    def _init_storage(self):
        """Create storage directory structure."""
        subdirs = ['images', 'videos', '360_videos', '3d_models', 'audio', 'temp']
        
        for subdir in subdirs:
            path = os.path.join(self.storage_dir, subdir)
            os.makedirs(path, exist_ok=True)
    
    def _load_metadata(self) -> Dict:
        """Load asset metadata from JSON file."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {'assets': {}, 'version': '1.0'}
        return {'assets': {}, 'version': '1.0'}
    
    def _save_metadata(self):
        """Save asset metadata to JSON file."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate SHA256 hash of file for deduplication."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file: {e}")
            return ""
    
    def _detect_asset_type(self, file_path: str) -> Optional[str]:
        """Detect asset type from file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        
        for asset_type, extensions in self.SUPPORTED_TYPES.items():
            if ext in extensions:
                return asset_type
        return None
    
    def store_asset(
        self, 
        file_path: str, 
        asset_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
        domain: str = 'general',
        experience_id: Optional[str] = None
    ) -> str:
        """
        Store an asset and return its ID.
        
        Args:
            file_path: Path to the file to store
            asset_type: Type of asset (auto-detected if None)
            metadata: Additional metadata
            domain: Domain this asset belongs to
            experience_id: Associated experience ID
            
        Returns:
            Asset ID (hash-based)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Detect type if not provided
        if asset_type is None:
            asset_type = self._detect_asset_type(file_path)
            if asset_type is None:
                raise ValueError(f"Unsupported file type: {file_path}")
        
        # Generate hash for deduplication
        file_hash = self._get_file_hash(file_path)
        if not file_hash:
            raise ValueError("Could not generate file hash")
        
        # Check if asset already exists
        if file_hash in self.metadata['assets']:
            logger.info(f"Asset already exists: {file_hash}")
            return file_hash
        
        # Determine storage subdirectory
        subdir_map = {
            'image': 'images',
            'video': 'videos',
            '360_video': '360_videos',
            '3d_model': '3d_models',
            'audio': 'audio'
        }
        subdir = subdir_map.get(asset_type, 'images')
        
        # Generate filename with hash
        ext = os.path.splitext(file_path)[1]
        filename = f"{file_hash}{ext}"
        dest_path = os.path.join(self.storage_dir, subdir, filename)
        
        # Copy file
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            raise
        
        # Store metadata
        asset_meta = {
            'id': file_hash,
            'type': asset_type,
            'filename': filename,
            'path': dest_path,
            'url': f'/static/assets/{subdir}/{filename}',
            'domain': domain,
            'experience_id': experience_id,
            'size': os.path.getsize(dest_path),
            'created_at': datetime.now().isoformat(),
            'custom_metadata': metadata or {}
        }
        
        self.metadata['assets'][file_hash] = asset_meta
        self._save_metadata()
        
        logger.info(f"Stored asset: {file_hash} ({asset_type})")
        return file_hash
    
    def get_asset(self, asset_id: str) -> Optional[Dict]:
        """
        Retrieve asset metadata by ID.
        
        Args:
            asset_id: Asset ID (hash)
            
        Returns:
            Asset metadata dictionary or None
        """
        return self.metadata['assets'].get(asset_id)
    
    def get_asset_url(self, asset_id: str) -> Optional[str]:
        """Get the URL for an asset."""
        asset = self.get_asset(asset_id)
        return asset.get('url') if asset else None
    
    def list_assets(
        self, 
        asset_type: Optional[str] = None,
        domain: Optional[str] = None,
        experience_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        List assets with optional filters.
        
        Args:
            asset_type: Filter by asset type
            domain: Filter by domain
            experience_id: Filter by experience ID
            limit: Maximum number of results
            
        Returns:
            List of asset metadata dictionaries
        """
        results = []
        
        for asset_id, asset in self.metadata['assets'].items():
            # Apply filters
            if asset_type and asset.get('type') != asset_type:
                continue
            if domain and asset.get('domain') != domain:
                continue
            if experience_id and asset.get('experience_id') != experience_id:
                continue
            
            results.append(asset)
            
            if len(results) >= limit:
                break
        
        # Sort by creation date (newest first)
        results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return results
    
    def delete_asset(self, asset_id: str) -> bool:
        """
        Delete an asset.
        
        Args:
            asset_id: Asset ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        asset = self.get_asset(asset_id)
        if not asset:
            return False
        
        # Delete file
        try:
            if os.path.exists(asset['path']):
                os.remove(asset['path'])
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
        
        # Remove from metadata
        del self.metadata['assets'][asset_id]
        self._save_metadata()
        
        logger.info(f"Deleted asset: {asset_id}")
        return True
    
    def optimize_for_delivery(
        self, 
        asset_id: str, 
        target: str = 'web'
    ) -> Optional[str]:
        """
        Optimize asset for specific delivery target.
        
        Args:
            asset_id: Asset ID
            target: Target platform ('web', 'ar', 'vr', 'hologram')
            
        Returns:
            Optimized asset ID or None
        """
        asset = self.get_asset(asset_id)
        if not asset:
            return None
        
        # TODO: Implement optimization logic
        # For now, return original asset
        # Future: resize images, transcode videos, compress models
        
        logger.info(f"Optimization for {target} not yet implemented")
        return asset_id
    
    def create_asset_bundle(
        self, 
        asset_ids: List[str],
        bundle_name: str
    ) -> str:
        """
        Create a bundle of multiple assets (for experiences).
        
        Args:
            asset_ids: List of asset IDs to bundle
            bundle_name: Name for the bundle
            
        Returns:
            Bundle ID
        """
        bundle_id = hashlib.sha256(bundle_name.encode()).hexdigest()[:16]
        
        bundle_meta = {
            'id': bundle_id,
            'name': bundle_name,
            'assets': asset_ids,
            'created_at': datetime.now().isoformat()
        }
        
        # Store bundle in metadata
        if 'bundles' not in self.metadata:
            self.metadata['bundles'] = {}
        
        self.metadata['bundles'][bundle_id] = bundle_meta
        self._save_metadata()
        
        logger.info(f"Created bundle: {bundle_id} with {len(asset_ids)} assets")
        return bundle_id
    
    def get_bundle(self, bundle_id: str) -> Optional[Dict]:
        """Get bundle metadata."""
        return self.metadata.get('bundles', {}).get(bundle_id)
    
    def get_statistics(self) -> Dict:
        """Get storage statistics."""
        stats = {
            'total_assets': len(self.metadata['assets']),
            'by_type': {},
            'by_domain': {},
            'total_size_mb': 0
        }
        
        for asset in self.metadata['assets'].values():
            # Count by type
            asset_type = asset.get('type', 'unknown')
            stats['by_type'][asset_type] = stats['by_type'].get(asset_type, 0) + 1
            
            # Count by domain
            domain = asset.get('domain', 'general')
            stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1
            
            # Sum size
            stats['total_size_mb'] += asset.get('size', 0) / (1024 * 1024)
        
        stats['total_size_mb'] = round(stats['total_size_mb'], 2)
        return stats
