"""
Image Downloader Module

Handles downloading images with retry logic and error handling.
"""

import os
import hashlib
import logging
from typing import Tuple, Optional
from pathlib import Path

import requests
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .url_transformer import build_original_url, get_file_extension, extract_image_id_from_path

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 10

# Request configuration
REQUEST_TIMEOUT = 30
CHUNK_SIZE = 8192

# User agent to avoid blocks
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DownloadError(Exception):
    """Custom exception for download failures."""
    pass


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
    retry=retry_if_exception_type((requests.RequestException, DownloadError)),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def download_image(
    url: str, 
    save_dir: str,
    filename: Optional[str] = None,
    use_original_url: bool = True
) -> Tuple[str, int]:
    """
    Download an image from URL with retry logic.
    
    Args:
        url: The image URL to download
        save_dir: Directory to save the downloaded image
        filename: Optional custom filename (without extension)
        use_original_url: Whether to strip transform params and use original URL
        
    Returns:
        Tuple of (saved_file_path, file_size_bytes)
        
    Raises:
        DownloadError: If download fails after all retries
    """
    # Build the download URL
    download_url = build_original_url(url) if use_original_url else url
    
    # Determine filename
    if not filename:
        filename = extract_image_id_from_path(url)
    
    extension = get_file_extension(url)
    save_path = os.path.join(save_dir, f"{filename}.{extension}")
    
    # Ensure save directory exists
    os.makedirs(save_dir, exist_ok=True)
    
    # Check if already downloaded
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        logger.info(f"Image already exists: {save_path}")
        return save_path, os.path.getsize(save_path)
    
    logger.info(f"Downloading: {download_url}")
    
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'image/*,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        response = requests.get(
            download_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            stream=True
        )
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            # Try the transformed URL as fallback
            if use_original_url:
                logger.warning(f"Non-image content type: {content_type}, trying transformed URL")
                return download_image(url, save_dir, filename, use_original_url=False)
            raise DownloadError(f"Unexpected content type: {content_type}")
        
        # Write to file
        total_size = 0
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
        
        if total_size == 0:
            raise DownloadError("Downloaded file is empty")
        
        logger.info(f"Downloaded {total_size} bytes to {save_path}")
        return save_path, total_size
        
    except requests.RequestException as e:
        # Clean up partial download
        if os.path.exists(save_path):
            os.remove(save_path)
        logger.error(f"Download failed for {url}: {e}")
        raise DownloadError(f"Download failed: {e}") from e


def get_file_hash(filepath: str) -> str:
    """
    Calculate MD5 hash of a file for deduplication.
    
    Args:
        filepath: Path to the file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def validate_image(filepath: str) -> bool:
    """
    Basic validation that the file is a valid image.
    
    Args:
        filepath: Path to the image file
        
    Returns:
        True if valid, False otherwise
    """
    if not os.path.exists(filepath):
        return False
    
    if os.path.getsize(filepath) == 0:
        return False
    
    # Check magic bytes for common image formats
    magic_bytes = {
        b'\x89PNG\r\n\x1a\n': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',  # WebP starts with RIFF
    }
    
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
            
        for magic, format_name in magic_bytes.items():
            if header.startswith(magic):
                return True
        
        # WebP specific check
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True
            
        logger.warning(f"Unknown image format for {filepath}")
        return True  # Allow unknown formats to proceed
        
    except Exception as e:
        logger.error(f"Error validating image {filepath}: {e}")
        return False
