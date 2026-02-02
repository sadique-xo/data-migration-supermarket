#!/usr/bin/env python3
"""
Cloudinary Image Migration Script

Migrates images from Grofers CDN to Cloudinary with transformation support.
"""

import csv
import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from tqdm import tqdm

from src.csv_handler import read_input_csv, write_mapping_csv, get_image_column
from src.url_transformer import (
    parse_transform_params, 
    extract_image_id_from_path,
)
from src.image_downloader import download_image, validate_image, DownloadError
from src.cloudinary_uploader import CloudinaryUploader, CloudinaryUploadError, test_connection
from src.progress_tracker import ProgressTracker


# Directories
DOWNLOADS_DIR = "downloads"
OUTPUT_DIR = "output"
LOGS_DIR = "logs"
STATE_DIR = "output"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    log_file = os.path.join(LOGS_DIR, f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_config() -> dict:
    """Load configuration from environment."""
    # Try loading from config.env
    if os.path.exists('config.env'):
        load_dotenv('config.env')
    else:
        load_dotenv()  # Try .env
    
    config = {
        'cloud_name': os.getenv('CLOUDINARY_CLOUD_NAME', ''),
        'api_key': os.getenv('CLOUDINARY_API_KEY', ''),
        'api_secret': os.getenv('CLOUDINARY_API_SECRET', ''),
        'folder': os.getenv('CLOUDINARY_FOLDER', 'product-images'),
    }
    
    return config


def validate_config(config: dict, dry_run: bool = False) -> bool:
    """Validate configuration."""
    if dry_run:
        return True
    
    required = ['cloud_name', 'api_key', 'api_secret']
    missing = [k for k in required if not config.get(k)]
    
    if missing:
        print(f"\n❌ Missing required configuration: {', '.join(missing)}")
        print("\nPlease set these in config.env:")
        print("  CLOUDINARY_CLOUD_NAME=your_cloud_name")
        print("  CLOUDINARY_API_KEY=your_api_key")
        print("  CLOUDINARY_API_SECRET=your_api_secret")
        return False
    
    return True


def migrate(
    input_file: str,
    output_file: Optional[str] = None,
    dry_run: bool = False,
    resume: bool = False,
    batch_size: Optional[int] = None,
    upload_from_url: bool = False,
    clean_downloads: bool = False
) -> int:
    """
    Run the migration process.
    
    Args:
        input_file: Path to input CSV
        output_file: Path to output mapping CSV
        dry_run: If True, validate without uploading
        resume: Resume from previous state
        batch_size: Process N items at a time
        upload_from_url: Upload directly from URL (skip local download)
        clean_downloads: Delete downloaded images after successful upload
        
    Returns:
        Exit code (0 for success)
    """
    logger = logging.getLogger(__name__)
    
    # Load and validate config
    config = load_config()
    if not validate_config(config, dry_run):
        return 1
    
    # Test connection (unless dry run)
    if not dry_run:
        print("\n🔗 Testing Cloudinary connection...")
        success, message = test_connection(
            config['cloud_name'], 
            config['api_key'], 
            config['api_secret']
        )
        if not success:
            print(f"❌ Connection failed: {message}")
            return 1
        print(f"✓ {message}")
    
    # Setup directories
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Default output file
    if not output_file:
        output_file = os.path.join(OUTPUT_DIR, "mapping.csv")
    
    # Initialize progress tracker
    tracker = ProgressTracker(STATE_DIR, input_file)
    
    if resume:
        if tracker.load_state():
            print(f"📂 Resuming from previous state...")
        else:
            print("📂 No previous state found, starting fresh...")
    else:
        tracker.reset()
    
    # Read input CSV
    print(f"\n📄 Reading input file: {input_file}")
    try:
        products = read_input_csv(input_file)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return 1
    
    tracker.set_total(len(products))
    print(f"   Found {len(products)} products to process")
    
    # Apply batch size limit
    if batch_size:
        products = products[:batch_size]
        print(f"   Processing batch of {batch_size} items")
    
    # Initialize uploader (unless dry run)
    uploader = None
    if not dry_run:
        uploader = CloudinaryUploader(
            config['cloud_name'],
            config['api_key'],
            config['api_secret'],
            config['folder']
        )
    
    # Process products
    print(f"\n🚀 Starting migration {'(DRY RUN)' if dry_run else ''}...\n")
    
    for product in tqdm(products, desc="Migrating"):
        # Get image URL
        image_url = get_image_column(product)
        if not image_url:
            logger.warning(f"No image URL found for product: {product.get('Name', 'Unknown')}")
            tracker.mark_skipped(str(product), "No image URL")
            continue
        
        # Skip if already processed
        if tracker.is_processed(image_url):
            logger.debug(f"Skipping already processed: {image_url}")
            continue
        
        # Prepare metadata
        metadata = {
            'product_name': product.get('Name', ''),
            'main_category': product.get('Main Category', ''),
            'sub_category': product.get('Sub Category', ''),
        }
        
        try:
            # Extract image ID for naming
            image_id = extract_image_id_from_path(image_url)
            
            # Get transform parameters (for reference)
            transform_params = parse_transform_params(image_url)
            
            if dry_run:
                # Dry run: just validate
                logger.info(f"[DRY RUN] Would process: {product.get('Name', 'Unknown')}")
                logger.info(f"  URL: {image_url}")
                logger.info(f"  Transforms: {transform_params}")
                
                # Generate sample URL
                sample_url = f"https://res.cloudinary.com/CLOUD/image/upload/w_270,q_70,f_auto,c_scale/product-images/{image_id}"
                tracker.mark_success(
                    image_url,
                    f"[DRY RUN] {sample_url}",
                    image_id,
                    metadata
                )
                continue
            
            # Upload to Cloudinary
            if upload_from_url:
                # Direct URL upload (no local download)
                logger.info(f"Uploading from URL: {product.get('Name', 'Unknown')}")
                upload_result = uploader.upload_from_url(
                    image_url,
                    public_id=image_id,
                    metadata=metadata
                )
            else:
                # Download first, then upload
                logger.info(f"Downloading: {product.get('Name', 'Unknown')}")
                local_path, file_size = download_image(image_url, DOWNLOADS_DIR, image_id)
                
                if not validate_image(local_path):
                    raise DownloadError("Invalid image file")
                
                logger.info(f"Uploading to Cloudinary: {local_path}")
                upload_result = uploader.upload_image(
                    local_path,
                    public_id=image_id,
                    metadata=metadata
                )
                
                # Clean up download if requested
                if clean_downloads and os.path.exists(local_path):
                    os.remove(local_path)
            
            # Get the public ID from result
            public_id = upload_result.get('public_id', f"{config['folder']}/{image_id}")
            
            # Generate new URL with Grofers-like transforms (w=270, q=70, f=auto)
            new_url = uploader.generate_url_like_grofers(public_id)
            
            # Record success
            tracker.mark_success(image_url, new_url, public_id, metadata)
            logger.info(f"Success: {new_url}")
            
        except (DownloadError, CloudinaryUploadError) as e:
            logger.error(f"Failed to process {image_url}: {e}")
            tracker.mark_failed(image_url, str(e), metadata)
            
        except Exception as e:
            logger.exception(f"Unexpected error processing {image_url}")
            tracker.mark_failed(image_url, f"Unexpected error: {e}", metadata)
    
    # Write output mapping CSV
    print(f"\n📝 Writing mapping to: {output_file}")
    write_mapping_csv(tracker.get_mappings(), output_file)
    
    # NEW: Automated Merge - Create a full CSV with a 'New Image Link' column
    final_output_file = os.path.join(OUTPUT_DIR, f"Final_Result_{Path(input_file).stem}.csv")
    print(f"📝 Generating full result with new column: {final_output_file}")
    
    try:
        # Load mappings into memory
        mappings = {m['old_url']: m['new_url'] for m in tracker.get_mappings() if m.get('status') == 'success'}
        
        # Open original file and create merged version
        with open(input_file, 'r', encoding='utf-8-sig') as f_orig:
            reader = csv.DictReader(f_orig)
            original_fieldnames = reader.fieldnames if reader.fieldnames else []
            fieldnames = original_fieldnames + ['New Image Link']
            
            with open(final_output_file, 'w', encoding='utf-8', newline='') as f_out:
                writer = csv.DictWriter(f_out, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    old_url = row.get('Image Link', '').strip()
                    row['New Image Link'] = mappings.get(old_url, 'PENDING/FAILED')
                    writer.writerow(row)
        print(f"✅ Successfully generated {final_output_file}")
    except Exception as e:
        logger.error(f"Failed to generate merged CSV: {e}")
        print(f"⚠️ Warning: Could not generate merged CSV, but mapping is saved.")
    
    # Print summary
    tracker.print_summary()
    
    return 0 if tracker.state.failed_count == 0 else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate images from Grofers CDN to Cloudinary',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to validate CSV
  python migrate.py --input products.csv --dry-run
  
  # Full migration (download then upload)
  python migrate.py --input products.csv
  
  # Direct URL upload (faster, no local download)
  python migrate.py --input products.csv --url-upload
  
  # Resume interrupted migration
  python migrate.py --input products.csv --resume
  
  # Process only first 10 items
  python migrate.py --input products.csv --batch-size 10
"""
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input CSV file path'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output mapping CSV path (default: output/mapping.csv)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Validate without uploading'
    )
    parser.add_argument(
        '--resume', '-r',
        action='store_true',
        help='Resume from previous state'
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        help='Process only N items'
    )
    parser.add_argument(
        '--url-upload', '-u',
        action='store_true',
        dest='upload_from_url',
        help='Upload directly from URL (skip local download)'
    )
    parser.add_argument(
        '--clean-downloads',
        action='store_true',
        help='Delete downloaded images after upload'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    sys.exit(migrate(
        input_file=args.input,
        output_file=args.output,
        dry_run=args.dry_run,
        resume=args.resume,
        batch_size=args.batch_size,
        upload_from_url=args.upload_from_url,
        clean_downloads=args.clean_downloads
    ))


if __name__ == '__main__':
    main()
