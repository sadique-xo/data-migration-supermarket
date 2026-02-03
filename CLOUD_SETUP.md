# ☁️ Running Migration in the Cloud (GitHub Actions)

This guide shows you how to run the Cloudinary image migration **in the cloud**, so it keeps running even when your laptop is closed.

## 📊 Rate Limit Info

| Free Tier Limit | Your Data | Total Time |
|----------------|-----------|------------|
| 500 requests/hour | 15,000 images | ~30 batch runs (~30 hours total) |

---

## 🚀 Setup Steps

### Step 1: Create GitHub Repository

```bash
# Initialize git (if not already)
cd /Users/sadique/Documents/data-migration-supermarket
git init

# Create .gitignore (important!)
echo "venv/
__pycache__/
*.pyc
config.env
downloads/
logs/" > .gitignore

# Add files
git add .
git commit -m "Initial commit: Cloudinary migration tool"

# Create repo on GitHub (use web or gh cli)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/data-migration-supermarket.git
git branch -M main
git push -u origin main
```

### Step 2: Add Secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `CLOUDINARY_CLOUD_NAME` | Your cloud name |
| `CLOUDINARY_API_KEY` | Your API key |
| `CLOUDINARY_API_SECRET` | Your API secret |
| `CLOUDINARY_FOLDER` | `product-images` (optional) |

### Step 3: Upload Your Full CSV

Replace the sample CSV with your 15,000 images CSV:

1. Copy your full CSV to the repo folder
2. Update `.github/workflows/migrate.yml` line 23:
   ```yaml
   INPUT_FILE: 'your-actual-filename.csv'
   ```
3. Commit and push:
   ```bash
   git add .
   git commit -m "Add full product CSV"
   git push
   ```

### Step 4: Run the Workflow

1. Go to your GitHub repo
2. Click **Actions** tab
3. Select **"Cloudinary Image Migration"**
4. Click **"Run workflow"**
5. Set options:
   - `batch_size`: `500` (max for free tier per hour)
   - `dry_run`: `true` for first test, `false` for real migration
   - `reset_state`: `false` (unless you want to start over)
6. Click **"Run workflow"**

---

## 🔄 Automated Scheduling (Optional)

To run automatically every hour until complete, edit `.github/workflows/migrate.yml`:

```yaml
on:
  workflow_dispatch:
    # ... existing inputs ...
  
  # Uncomment these lines to enable hourly runs:
  schedule:
    - cron: '0 * * * *'  # Every hour at minute 0
```

Then push the change. GitHub will run the workflow every hour!

---

## 📈 Monitoring Progress

### Check Progress in GitHub Actions

Each run shows a summary table:
- Total items
- Processed count  
- Success/Failed counts
- Remaining items
- Progress percentage

### Download Output Files

1. Go to your workflow run
2. Scroll to **Artifacts**
3. Download `migration-output-X`
4. Contains `mapping.csv`, `Final_Result_*.csv`, and state files

---

## 🔧 Troubleshooting

### "Rate limit exceeded"
- Reduce `batch_size` to 400 or less
- Add more delay: edit workflow to use `--delay 1.0`

### "State file not found"
- First run won't have state - that's normal!
- Subsequent runs will load from committed state

### "Push failed"
- Someone else pushed changes
- Run: `git pull origin main --rebase` and try again

### "Migration already complete"
- All images processed!
- Check `output/Final_Result_*.csv` for your results

---

## 📁 Output Files

After migration completes, you'll have:

| File | Contents |
|------|----------|
| `output/mapping.csv` | Old URL → New URL mappings |
| `output/Final_Result_*.csv` | Original CSV + new `New Image Link` column |
| `output/migration_state.json` | Progress state (for resume) |

---

## ⏱️ Time Estimates

| Images | Batches | Time (at 1 batch/hour) |
|--------|---------|------------------------|
| 500 | 1 | ~10-15 min |
| 5,000 | 10 | ~10 hours |
| 15,000 | 30 | ~30 hours |

**Tip**: Run 2-3 manual batches per day, or enable the hourly schedule for fully automated migration!
