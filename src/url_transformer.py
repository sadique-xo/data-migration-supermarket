"""
URL Transformer Module

Handles parsing Cloudflare transform URLs and generating new Cloudflare Images URLs.
"""

import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


def parse_transform_params(url: str) -> Dict[str, str]:
    """
    Parse Cloudflare transform parameters from a CDN URL.
    
    Example input:
    https://cdn.grofers.com/cdn-cgi/image/f=auto,fit=scale-down,q=70,metadata=none,w=270/da/cms-assets/...
    
    Args:
        url: The full CDN URL with transform parameters
        
    Returns:
        Dictionary of transform parameters (e.g., {'f': 'auto', 'w': '270', 'q': '70'})
    """
    params = {}
    
    # Pattern to match the transform parameters in Cloudflare CDN URLs
    # Format: /cdn-cgi/image/param1=val1,param2=val2/path
    pattern = r'/cdn-cgi/image/([^/]+)/'
    match = re.search(pattern, url)
    
    if match:
        param_string = match.group(1)
        # Split by comma and parse each key=value pair
        for param in param_string.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip()] = value.strip()
    
    return params


def extract_original_path(url: str) -> Optional[str]:
    """
    Extract the original image path from a Cloudflare CDN URL.
    
    Args:
        url: The full CDN URL
        
    Returns:
        The original image path (e.g., 'da/cms-assets/cms/product/xxx.png')
    """
    # Pattern to match the path after transform parameters
    pattern = r'/cdn-cgi/image/[^/]+/(.+)$'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    
    # Fallback: try to get path from URL
    parsed = urlparse(url)
    return parsed.path.lstrip('/')


def extract_image_id_from_path(path: str) -> str:
    """
    Extract a unique identifier from the image path.
    
    Args:
        path: The image path
        
    Returns:
        Unique identifier string
    """
    # Extract the UUID-like filename (without extension)
    if '/' in path:
        filename = path.split('/')[-1]
    else:
        filename = path
    
    # Remove extension
    if '.' in filename:
        return filename.rsplit('.', 1)[0]
    
    return filename


def build_original_url(cdn_url: str) -> str:
    """
    Build the original (non-transformed) URL for downloading.
    
    This removes Cloudflare transform parameters to get the original image.
    
    Args:
        cdn_url: The CDN URL with transforms
        
    Returns:
        URL to the original image
    """
    parsed = urlparse(cdn_url)
    original_path = extract_original_path(cdn_url)
    
    if original_path:
        # Reconstruct URL without transform params
        return f"{parsed.scheme}://{parsed.netloc}/{original_path}"
    
    return cdn_url


def build_cloudflare_images_url(
    images_hash: str,
    image_id: str,
    variant: str = "public",
    params: Optional[Dict[str, str]] = None
) -> str:
    """
    Build a Cloudflare Images delivery URL.
    
    Cloudflare Images URL format:
    https://imagedelivery.net/{account_hash}/{image_id}/{variant}
    
    For flexible variants (if enabled):
    https://imagedelivery.net/{account_hash}/{image_id}/w=270,q=70
    
    Args:
        images_hash: Your Cloudflare Images delivery hash
        image_id: The uploaded image ID
        variant: Variant name (e.g., 'public', 'thumbnail') or flexible params
        params: Optional dict of transform params for flexible variants
        
    Returns:
        Complete Cloudflare Images delivery URL
    """
    base_url = f"https://imagedelivery.net/{images_hash}/{image_id}"
    
    if params:
        # Build flexible variant string: w=270,q=70,f=auto
        param_string = ','.join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}/{param_string}"
    
    return f"{base_url}/{variant}"


def map_transform_params(old_params: Dict[str, str]) -> Dict[str, str]:
    """
    Map old Cloudflare CDN transform params to Cloudflare Images params.
    
    Cloudflare Images supports:
    - w: width
    - h: height
    - fit: cover, contain, scale-down, crop
    - quality (q): 1-100
    - f: format (auto, webp, avif, json)
    - blur: 1-250
    - and more...
    
    Args:
        old_params: Parameters from the old CDN URL
        
    Returns:
        Mapped parameters for Cloudflare Images
    """
    # Most params map directly
    mapped = {}
    
    # Direct mappings
    direct_map = ['w', 'h', 'fit', 'q', 'f', 'blur', 'sharpen', 'brightness', 'contrast']
    
    for param in direct_map:
        if param in old_params:
            mapped[param] = old_params[param]
    
    # Handle 'quality' -> 'q' if needed
    if 'quality' in old_params:
        mapped['q'] = old_params['quality']
    
    return mapped


def get_file_extension(url: str) -> str:
    """
    Extract file extension from URL.
    
    Args:
        url: The image URL
        
    Returns:
        File extension (e.g., 'png', 'jpg')
    """
    path = extract_original_path(url) or url
    
    if '.' in path:
        ext = path.rsplit('.', 1)[-1].lower()
        # Clean up any query params
        if '?' in ext:
            ext = ext.split('?')[0]
        return ext
    
    return 'png'  # Default extension
