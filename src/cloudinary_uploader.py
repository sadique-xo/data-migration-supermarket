"""
Cloudinary Uploader Module

Handles uploading images to Cloudinary with transformation URL generation.
"""

import os
import logging
from typing import Dict, Optional, Any

import cloudinary
import cloudinary.uploader
import cloudinary.api
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
MIN_WAIT_SECONDS = 2
MAX_WAIT_SECONDS = 30


class CloudinaryUploadError(Exception):
    """Custom exception for Cloudinary upload failures."""
    pass


class CloudinaryUploader:
    """Handles uploading images to Cloudinary."""
    
    def __init__(
        self, 
        cloud_name: str, 
        api_key: str, 
        api_secret: str,
        folder: str = "product-images"
    ):
        """
        Initialize the Cloudinary uploader.
        
        Args:
            cloud_name: Cloudinary cloud name
            api_key: Cloudinary API key
            api_secret: Cloudinary API secret
            folder: Folder to organize uploads
        """
        self.cloud_name = cloud_name
        self.folder = folder
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def upload_image(
        self, 
        image_path: str,
        public_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload an image to Cloudinary.
        
        Args:
            image_path: Path to the local image file
            public_id: Optional custom public ID (filename in Cloudinary)
            metadata: Optional metadata to attach (stored as context)
            
        Returns:
            Cloudinary upload response with image details
            
        Raises:
            CloudinaryUploadError: If upload fails after retries
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Build upload options
        options = {
            'folder': self.folder,
            'resource_type': 'image',
            'overwrite': True,
            'unique_filename': False,
            'use_filename': True,
        }
        
        if public_id:
            options['public_id'] = public_id
        
        if metadata:
            # Store metadata as context (key=value|key2=value2 format)
            context_str = '|'.join(f"{k}={v}" for k, v in metadata.items() if v)
            if context_str:
                options['context'] = context_str
        
        try:
            logger.info(f"Uploading to Cloudinary: {image_path}")
            result = cloudinary.uploader.upload(image_path, **options)
            
            logger.info(f"Successfully uploaded: {result.get('public_id')}")
            return result
            
        except cloudinary.exceptions.Error as e:
            logger.error(f"Cloudinary error: {e}")
            raise CloudinaryUploadError(f"Upload failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error uploading to Cloudinary: {e}")
            raise CloudinaryUploadError(f"Unexpected error: {e}") from e
    
    def upload_from_url(
        self, 
        url: str,
        public_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload an image directly from URL (no local download needed).
        
        Args:
            url: URL of the image to upload
            public_id: Optional custom public ID
            metadata: Optional metadata
            
        Returns:
            Cloudinary upload response
        """
        options = {
            'folder': self.folder,
            'resource_type': 'image',
            'overwrite': True,
            'unique_filename': False,
        }
        
        if public_id:
            options['public_id'] = public_id
        
        if metadata:
            context_str = '|'.join(f"{k}={v}" for k, v in metadata.items() if v)
            if context_str:
                options['context'] = context_str
        
        try:
            logger.info(f"Uploading from URL to Cloudinary: {url[:80]}...")
            result = cloudinary.uploader.upload(url, **options)
            logger.info(f"Successfully uploaded: {result.get('public_id')}")
            return result
            
        except Exception as e:
            logger.error(f"Error uploading from URL: {e}")
            raise CloudinaryUploadError(f"URL upload failed: {e}") from e
    
    def generate_url(
        self, 
        public_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: Optional[int] = None,
        format: str = "auto",
        crop: str = "scale"
    ) -> str:
        """
        Generate a Cloudinary delivery URL with transformations.
        
        Matches the original Grofers transforms: f=auto, fit=scale-down, q=70, w=270
        
        Args:
            public_id: The image public ID in Cloudinary
            width: Target width
            height: Target height
            quality: Quality (1-100)
            format: Format (auto, webp, jpg, png)
            crop: Crop mode (scale, fill, fit, etc.)
            
        Returns:
            Complete Cloudinary delivery URL with transforms
        """
        transformations = []
        
        if width:
            transformations.append(f"w_{width}")
        if height:
            transformations.append(f"h_{height}")
        if quality:
            transformations.append(f"q_{quality}")
        if format:
            transformations.append(f"f_{format}")
        if crop:
            transformations.append(f"c_{crop}")
        
        transform_str = ','.join(transformations).replace(',', ',')
        
        # Build URL: https://res.cloudinary.com/{cloud_name}/image/upload/{transforms}/{public_id}
        if transformations:
            return f"https://res.cloudinary.com/{self.cloud_name}/image/upload/{','.join(transformations)}/{public_id}"
        else:
            return f"https://res.cloudinary.com/{self.cloud_name}/image/upload/{public_id}"
    
    def generate_url_like_grofers(self, public_id: str) -> str:
        """
        Generate URL matching Grofers CDN params: f=auto,fit=scale-down,q=70,w=270
        
        Args:
            public_id: The image public ID
            
        Returns:
            URL with matching transformations
        """
        return self.generate_url(
            public_id,
            width=270,
            quality=70,
            format="auto",
            crop="scale"
        )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get Cloudinary account usage statistics."""
        try:
            return cloudinary.api.usage()
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return {}
    
    def delete_image(self, public_id: str) -> bool:
        """Delete an image from Cloudinary."""
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get('result') == 'ok'
        except Exception as e:
            logger.error(f"Error deleting image: {e}")
            return False


def test_connection(cloud_name: str, api_key: str, api_secret: str) -> tuple[bool, str]:
    """
    Test Cloudinary connection and credentials.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Test API access
        usage = cloudinary.api.usage()
        used = usage.get('credits', {}).get('used_percent', 0)
        
        return True, f"Connected! Credit usage: {used:.1f}%"
        
    except cloudinary.exceptions.AuthorizationRequired:
        return False, "Invalid API credentials"
    except Exception as e:
        return False, f"Connection failed: {e}"
