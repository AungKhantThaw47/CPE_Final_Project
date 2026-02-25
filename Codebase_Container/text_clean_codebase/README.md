# DVB Burmese Text Cleaning Pipeline

Enhanced Python pipeline for cleaning Myanmar/Burmese text from DVB news articles.

## Features

✅ **DVB-Specific Cleaning**
- Removes DVB footers and source attributions
- Removes advertisement markers  
- Cleans photo credits

✅ **Burmese Text Optimization**
- Unicode NFC normalization
- Zero-width character removal
- Myanmar punctuation normalization (၊ ။)
- Proper spacing around Burmese characters

✅ **Content Quality Validation**
- Minimum length check
- Burmese character detection
- Content statistics (words, sentences, Burmese ratio)

✅ **Smart Processing**
- Handles DVB crawler JSON format
- Preserves original text for comparison
- Detailed processing statistics

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or with nix-shell
nix-shell
```

## Usage

### Set Environment Variables

```bash
export INPUT_BUCKET="your-dvb-raw-bucket"
export OUTPUT_BUCKET="your-dvb-cleaned-bucket"
export INPUT_PREFIX="dvb/"
export OUTPUT_PREFIX="cleaned/"
```

### Run the Cleaner

```bash
python default/main.py
```

### Example Output

```
============================================================
DVB BURMESE TEXT CLEANING PIPELINE
============================================================

[1/5] Processing: dvb/2026-01-28/DVB_Burmese_2026-01-28.json
✓ Downloaded: dvb/2026-01-28/DVB_Burmese_2026-01-28.json
  Processed: 25 articles
    Valid: 23, Invalid: 2
✓ Uploaded: gs://bucket/cleaned/2026-01-28/DVB_Burmese_2026-01-28.json

============================================================
TEXT CLEANING PIPELINE COMPLETED
============================================================

Article Statistics:
  Valid articles: 115
  Invalid articles: 10
  Total words: 19,550
  Average words/article: 170
============================================================
```

## Cleaning Rules

### DVB-Specific Patterns
- `သတင်းရင်းမြစ် : DVB` → removed
- `Source: DVB` → removed  
- `ဓာတ်ပုံ :` → removed
- `ကြော်ငြာ` (ads) → removed

### Burmese Text
- Zero-width chars → removed
- `။။။` → `။`
- Unicode NFC normalization
- Proper spacing

### General
- HTML tags & entities removed
- URLs & emails removed
- Whitespace normalized

## Integration with DVB Crawler

Works seamlessly with DVB crawler output format.

See full documentation in the code comments.
