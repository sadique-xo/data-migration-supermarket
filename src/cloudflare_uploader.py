"""
Cloudflare Images Uploader Module

Handles uploading images to Cloudflare Images API.
"""

import os
import logging
from typing import Dict, Optional, Tuple, Any

import requests
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

# API configuration
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareUploadError(Exception):
    """Custom exception for Cloudflare upload failures."""
    pass


class CloudflareUploader:
    """Handles uploading images to Cloudflare Images."""
    
    def __init__(self, account_id: str, api_token: str, images_hash: str):
        """
        Initialize the Cloudflare uploader.
        
        Args:
            account_id: Cloudflare Account ID
            api_token: API token with Images permissions
            images_hash: Cloudflare Images delivery hash
        """
        self.account_id = account_id
        self.api_token = api_token
        self.images_hash = images_hash
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}'
        })
        
    def _get_api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{CLOUDFLARE_API_BASE}/accounts/{self.account_id}/images/v1{endpoint}"
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        retry=retry_if_exception_type((requests.RequestException, CloudflareUploadError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def upload_image(
        self, 
        image_path: str,
        custom_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        require_signed_urls: bool = False
    ) -> Dict[str, Any]:
        """
        Upload an image to Cloudflare Images.
        
        Args:
            image_path: Path to the local image file
            custom_id: Optional custom ID for the image
            metadata: Optional metadata to attach to the image
            require_signed_urls: Whether to require signed URLs for this image
            
        Returns:
            Cloudflare API response with image details
            
        Raises:
            CloudflareUploadError: If upload fails after retries
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        url = self._get_api_url("")
        
        # Prepare form data
        files = {
            'file': (os.path.basename(image_path), open(image_path, 'rb'))
        }
        
        data = {}
        if custom_id:
            data['id'] = custom_id
        if metadata:
            # Cloudflare expects metadata as JSON string
            import json
            data['metadata'] = json.dumps(metadata)
        if require_signed_urls:
            data['requireSignedURLs'] = 'true'
        
        try:
            response = self.session.post(url, files=files, data=data, timeout=60)
            result = response.json()
            
            if not result.get('success'):
                errors = result.get('errors', [])
                error_msg = '; '.join(e.get('message', str(e)) for e in errors)
                
                # Check for rate limiting
                if response.status_code == 429:
                    raise CloudflareUploadError(f"Rate limited: {error_msg}")
                
                # Check for duplicate
                if any('already exists' in e.get('message', '').lower() for e in errors):
                    logger.warning(f"Image already exists: {custom_id}")
                    # Try to get existing image info
                    return self._handle_duplicate(custom_id)
                
                raise CloudflareUploadError(f"Upload failed: {error_msg}")
            
            logger.info(f"Successfully uploaded: {image_path}")
            return result.get('result', {})
            
        except requests.RequestException as e:
            raise CloudflareUploadError(f"Request failed: {e}") from e
        finally:
            files['file'][1].close()
    
    def _handle_duplicate(self, image_id: str) -> Dict[str, Any]:
        """Handle case where image already exists."""
        try:
            return self.get_image_details(image_id)
        except Exception:
            return {'id': image_id}
    
    def get_image_details(self, image_id: str) -> Dict[str, Any]:
        """
        Get details of an uploaded image.
        
        Args:
            image_id: The Cloudflare image ID
            
        Returns:
            Image details from Cloudflare
        """
        url = self._get_api_url(f"/{image_id}")
        
        response = self.session.get(url, timeout=30)
        result = response.json()
        
        if not result.get('success'):
            errors = result.get('errors', [])
            error_msg = '; '.join(e.get('message', str(e)) for e in errors)
            raise CloudflareUploadError(f"Failed to get image details: {error_msg}")
        
        return result.get('result', {})
    
    def delete_image(self, image_id: str) -> bool:
        """
        Delete an image from Cloudflare Images.
        
        Args:
            image_id: The Cloudflare image ID
            
        Returns:
            True if deleted successfully
        """
        url = self._get_api_url(f"/{image_id}")
        
        response = self.session.delete(url, timeout=30)
        result = response.json()
        
        return result.get('success', False)
    
    def list_images(self, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """
        List images in your Cloudflare Images account.
        
        Args:
            page: Page number
            per_page: Results per page
            
        Returns:
            List response with images and pagination
        """
        url = self._get_api_url("")
        params = {'page': page, 'per_page': per_page}
        
        response = self.session.get(url, params=params, timeout=30)
        result = response.json()
        
        if not result.get('success'):
            errors = result.get('errors', [])
            error_msg = '; '.join(e.get('message', str(e)) for e in errors)
            raise CloudflareUploadError(f"Failed to list images: {error_msg}")
        
        return result
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for your Cloudflare Images account.
        
        Returns:
            Usage statistics (count, storage used, etc.)
        """
        url = self._get_api_url("/stats")
        
        response = self.session.get(url, timeout=30)
        result = response.json()
        
        if not result.get('success'):
            return {}
        
        return result.get('result', {})
    
    def generate_delivery_url(
        self, 
        image_id: str, 
        variant: str = "public"
    ) -> str:
        """
        Generate a Cloudflare Images delivery URL.
        
        Args:
            image_id: The uploaded image ID
            variant: Variant name or flexible transform params
            
        Returns:
            Complete delivery URL
        """
        return f"https://imagedelivery.net/{self.images_hash}/{image_id}/{variant}"


def test_connection(account_id: str, api_token: str) -> Tuple[bool, str]:
    """
    Test Cloudflare API connection and permissions.
    
    Args:
        account_id: Cloudflare Account ID
        api_token: API token
        
    Returns:
        Tuple of (success, message)
    """
    url = f"{CLOUDFLARE_API_BASE}/accounts/{account_id}/images/v1/stats"
    headers = {'Authorization': f'Bearer {api_token}'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        result = response.json()
        
        if result.get('success'):
            stats = result.get('result', {})
            count = stats.get('count', {})
            return True, f"Connected! Images: {count.get('current', 0)}/{count.get('allowed', 0)}"
        else:
            errors = result.get('errors', [])
            error_msg = '; '.join(e.get('message', str(e)) for e in errors)
            return False, f"API Error: {error_msg}"
            
    except requests.RequestException as e:
        return False, f"Connection failed: {e}"
