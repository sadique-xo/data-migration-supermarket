"""
CSV Handler Module

Handles reading the input CSV and writing the output mapping CSV.
"""

import csv
import os
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def read_input_csv(filepath: str) -> List[Dict[str, str]]:
    """
    Read the input CSV file containing product data with image URLs.
    
    Args:
        filepath: Path to the input CSV file
        
    Returns:
        List of dictionaries, each containing product data
    """
    products = []
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Input CSV file not found: {filepath}")
    
    # Try different encodings to handle various CSV formats
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up column names (remove BOM, whitespace)
                    cleaned_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
                    products.append(cleaned_row)
                    
            logger.info(f"Successfully read {len(products)} rows from {filepath} using {encoding}")
            return products
            
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading CSV with {encoding}: {e}")
            continue
    
    raise ValueError(f"Could not read CSV file with any supported encoding: {filepath}")


def write_mapping_csv(
    mappings: List[Dict[str, str]], 
    output_path: str,
    include_metadata: bool = True
) -> str:
    """
    Write the URL mapping CSV file.
    
    Args:
        mappings: List of dictionaries with mapping data
        output_path: Path to write the output CSV
        include_metadata: Whether to include product metadata in output
        
    Returns:
        Path to the written file
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    if not mappings:
        logger.warning("No mappings to write")
        return output_path
    
    # Determine fieldnames from first mapping
    if include_metadata:
        fieldnames = ['old_url', 'new_url', 'cloudflare_image_id', 'product_name', 
                      'main_category', 'sub_category', 'status', 'error']
    else:
        fieldnames = ['old_url', 'new_url', 'cloudflare_image_id', 'status', 'error']
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(mappings)
    
    logger.info(f"Wrote {len(mappings)} mappings to {output_path}")
    return output_path


def get_image_column(row: Dict[str, str]) -> Optional[str]:
    """
    Extract the image URL from a row, handling various column name formats.
    
    Args:
        row: Dictionary containing CSV row data
        
    Returns:
        Image URL or None if not found
    """
    # Possible column names for image URL
    possible_names = [
        'Image Link', 'image_link', 'ImageLink', 'image_url', 
        'Image URL', 'ImageURL', 'image', 'Image', 'url', 'URL'
    ]
    
    for name in possible_names:
        if name in row and row[name]:
            return row[name]
    
    return None
