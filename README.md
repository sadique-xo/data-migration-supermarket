# Cloudinary Image Migration Tool

Migrate product images from Grofers CDN to Cloudinary with automatic transformations.

## Features

- ✅ Read product data from CSV files
- ✅ Upload to Cloudinary (direct URL or download-first)
- ✅ Generate transformed URLs matching original params (w=270, q=70)
- ✅ Create mapping CSV for database updates
- ✅ Resume interrupted migrations
- ✅ Progress tracking and logging

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Set Up Cloudinary

1. Go to [Cloudinary Console](https://console.cloudinary.com/)
2. Sign up for a free account (no card required!)
3. From the dashboard, note your:
   - **Cloud Name**
   - **API Key**
   - **API Secret**

### 3. Configure Credentials

```bash
cp config.example.env config.env
```

Edit `config.env`:
```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
CLOUDINARY_FOLDER=product-images
```

### 4. Run Migration

```bash
# Activate venv
source venv/bin/activate

# Test with dry-run first
python migrate.py --input "Data Migration - Try Sample - Sheet1.csv" --dry-run

# Run actual migration (direct URL upload - fastest)
python migrate.py --input "Data Migration - Try Sample - Sheet1.csv" --url-upload

# Or download-then-upload (slower but more reliable)
python migrate.py --input "Data Migration - Try Sample - Sheet1.csv"
```

## Usage

```bash
python migrate.py [OPTIONS]

Options:
  --input, -i        Input CSV file path (required)
  --output, -o       Output mapping CSV path (default: output/mapping.csv)
  --dry-run, -n      Validate without uploading
  --resume, -r       Resume from previous state
  --batch-size, -b   Process only N items
  --url-upload, -u   Upload directly from URL (faster)
  --clean-downloads  Delete downloaded images after upload
  --log-level        DEBUG, INFO, WARNING, ERROR (default: INFO)
```

## Output Files

The script generates two main files in the `output/` directory:

1. `mapping.csv`: A simple list of `old_url` -> `new_url` with status and errors.
2. `Final_Result_{Filename}.csv`: A **complete copy** of your original CSV with an additional column: **`New Image Link`**. This contains the ready-to-use Cloudinary URLs.

## Output URLs

Your new Cloudinary URLs will look like:
```
https://res.cloudinary.com/{cloud_name}/image/upload/w_270,q_70,f_auto,c_scale/{folder}/{image_id}
```

This matches the original Grofers transforms: `f=auto,fit=scale-down,q=70,w=270`

## Cloudinary Free Tier

- 25 Credits/month
- 1 Credit = 1,000 transformations OR 1GB storage OR 1GB bandwidth
- No credit card required!

## Project Structure

```
data-migration-supermarket/
├── migrate.py              # Main script
├── config.example.env      # Credentials template
├── requirements.txt        # Dependencies
├── src/
│   ├── csv_handler.py      # CSV I/O
│   ├── cloudinary_uploader.py  # Cloudinary SDK wrapper
│   ├── image_downloader.py # Download with retry
│   ├── url_transformer.py  # URL parsing
│   └── progress_tracker.py # State persistence
├── output/                 # Output CSVs
└── logs/                   # Log files
```
