#!/usr/bin/env python3
"""
Script to remove author names from DVB news articles.
Fetches articles from GCS bucket, cleans them, and stores in cleaned bucket.
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional

# Common Myanmar author name patterns
# Author names are usually 2-6 Myanmar characters at the end of the file
# on their own line
AUTHOR_NAME_PATTERN = re.compile(r'^[\u1000-\u109F\u200B-\u200D\uAA60-\uAA7F]{2,20}$')

# Source citation patterns
SOURCE_PATTERNS = [
    re.compile(r'^Source\s*:\s*.+', re.IGNORECASE),
    re.compile(r'^ရင်းမြစ်\s*:\s*.+'),
    re.compile(r'^သတင်းရင်းမြစ်\s*:\s*.+'),
]

def is_likely_author_name(line):
    """
    Check if a line is likely an author name.
    Author names are typically:
    - Short (2-20 Myanmar characters)
    - Only Myanmar script
    - No spaces (or minimal spaces)
    - Not a sentence (no ။ or။ at end typically, or very short even if it has one)
    """
    line = line.strip()
    
    # Empty line
    if not line:
        return False
    
    # Check if it's very short and only Myanmar characters
    if AUTHOR_NAME_PATTERN.match(line):
        return True
    
    # Check if it's a short name with minimal punctuation
    # Remove common Myanmar punctuation
    clean_line = line.replace('။', '').replace('၊', '').strip()
    
    # Author names are usually short (less than 15 characters without punctuation)
    if len(clean_line) <= 15 and AUTHOR_NAME_PATTERN.match(clean_line):
        return True
    
    return False

def is_source_citation(line):
    """
    Check if a line is a source citation.
    """
    line = line.strip()
    
    if not line:
        return False
    
    # Check against source patterns
    for pattern in SOURCE_PATTERNS:
        if pattern.match(line):
            return True
    
    return False


def clean_text_content(content: str) -> tuple[str, bool]:
    """
    Clean text content by removing author names and source citations.
    
    Args:
        content: Article text content
    
    Returns:
        Tuple of (cleaned_content, was_modified)
    """
    if not content:
        return content, False
    
    lines = content.split('\n')
    original_line_count = len(lines)
    modified = False
    
    # Remove trailing empty lines first
    while lines and lines[-1].strip() == '':
        lines.pop()
    
    if not lines:
        return content, False
    
    # Keep removing lines from the end if they match author name or source patterns
    while lines:
        last_line = lines[-1].strip()
        
        if is_likely_author_name(last_line):
            lines.pop()
            modified = True
            # Remove any empty lines after removing author name
            while lines and lines[-1].strip() == '':
                lines.pop()
        elif is_source_citation(last_line):
            lines.pop()
            modified = True
            # Remove any empty lines after removing source citation
            while lines and lines[-1].strip() == '':
                lines.pop()
        else:
            # No more author names or sources to remove
            break
    
    if modified and lines:
        cleaned_content = '\n'.join(lines)
        if not cleaned_content.endswith('\n'):
            cleaned_content += '\n'
        return cleaned_content, True
    
    return content, False


def upload_cleaned_article(content: str, bucket_name: str, destination_path: str) -> bool:
    """
    Upload cleaned article content to GCS.
    
    Args:
        content: Cleaned article content
        bucket_name: Target GCS bucket name
        destination_path: Destination path in bucket
    
    Returns:
        True if upload successful, False otherwise
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        
        blob.upload_from_string(
            content,
            content_type='text/plain'
        )
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to {destination_path}: {e}")
        return False
    """
    Remove author name and source citations from the end of an article file.
    Returns True if file was modified, False otherwise.
    
    Note: This function is kept for compatibility but not used in GCS pipeline.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return False
        
        original_line_count = len(lines)
        modified = False
        
        # Remove trailing empty lines first
        while lines and lines[-1].strip() == '':
            lines.pop()
        
        if not lines:
            return False
        
        # Keep removing lines from the end if they match author name or source patterns
        while lines:
            last_line = lines[-1].strip()
            
            if is_likely_author_name(last_line):
                print(f"Found author name '{last_line}' in {os.path.basename(file_path)}")
                lines.pop()
                modified = True
                # Remove any empty lines after removing author name
                while lines and lines[-1].strip() == '':
                    lines.pop()
            elif is_source_citation(last_line):
                print(f"Found source citation '{last_line}' in {os.path.basename(file_path)}")
                lines.pop()
                modified = True
                # Remove any empty lines after removing source citation
                while lines and lines[-1].strip() == '':
                    lines.pop()
            else:
                # No more author names or sources to remove
                break
        
        if modified and lines:
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                # Ensure file ends with a newline if it has content
                if lines and not lines[-1].endswith('\n'):
                    f.write('\n')
            
            return True
        
        return False
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def fetch_articles_from_gcs(bucket_name: str, date_str: Optional[str] = None, 
                            prefix_path: str = "dvb") -> List[Dict]:
    """
    Fetch all articles from GCS bucket for a specific date.
    
    Args:
        bucket_name: GCS bucket name
        date_str: Date in YYYY-MM-DD format (defaults to yesterday)
        prefix_path: Base prefix path (default: "dvb")
    
    Returns:
        List of article metadata dictionaries
    """
    # Default to yesterday if no date specified
    if not date_str:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    
    print("=" * 60)
    print("Fetching Articles from GCS Bucket")
    print("=" * 60)
    print(f"📦 Bucket: gs://{bucket_name}")
    print(f"📅 Date: {date_str}")
    print(f"📂 Prefix: {prefix_path}/{date_str}/")
    print()
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # List all blobs in the date folder
        prefix = f"{prefix_path}/{date_str}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Filter for .txt files only
        txt_blobs = [b for b in blobs if b.name.endswith('.txt')]
        json_blobs = [b for b in blobs if b.name.endswith('.json')]
        
        print(f"📊 Found {len(blobs)} total files")
        print(f"   - Text articles: {len(txt_blobs)}")
        print(f"   - JSON metadata: {len(json_blobs)}")
        print()
        
        if not txt_blobs:
            print("⚠️  No text articles found!")
            return []
        
        # Build article list
        articles = []
        for blob in txt_blobs:
            articles.append({
                'blob_name': blob.name,
                'filename': os.path.basename(blob.name),
                'size': blob.size,
                'bucket': bucket_name,
                'date': date_str
            })
        
        print(f"✅ Successfully fetched {len(articles)} article references")
        return articles
        
    except Exception as e:
        print(f"❌ Error fetching articles: {e}")
        raise


def read_article_from_gcs(bucket_name: str, blob_name: str) -> Optional[str]:
    """
    Read a single article from GCS.
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Full path to the blob
    
    Returns:
        Article content as string, or None if error
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        content = blob.download_as_text()
        return content
        
    except Exception as e:
        print(f"❌ Error reading {blob_name}: {e}")
        return None


def process_and_clean_articles(source_bucket: str, target_bucket: str, 
                               date_str: Optional[str] = None, 
                               prefix_path: str = "dvb") -> Dict[str, int]:
    """
    Process all articles: fetch, clean, and upload to target bucket.
    
    Args:
        source_bucket: Source GCS bucket with crawled data
        target_bucket: Target GCS bucket for cleaned data
        date_str: Date in YYYY-MM-DD format (defaults to yesterday)
        prefix_path: Base prefix path (default: "dvb")
    
    Returns:
        Dictionary with processing statistics
    """
    # Default to yesterday if no date specified
    if not date_str:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')
    
    print()
    print("=" * 60)
    print("Processing and Cleaning Articles")
    print("=" * 60)
    print(f"📥 Source: gs://{source_bucket}/{prefix_path}/{date_str}/")
    print(f"📤 Target: gs://{target_bucket}/dvb_cleaned/{date_str}/")
    print()
    
    # Fetch articles
    articles = fetch_articles_from_gcs(source_bucket, date_str, prefix_path)
    
    if not articles:
        return {"total": 0, "cleaned": 0, "unchanged": 0, "errors": 0}
    
    stats = {"total": len(articles), "cleaned": 0, "unchanged": 0, "errors": 0}
    
    print(f"Processing {stats['total']} articles...")
    print()
    
    for i, article in enumerate(articles, 1):
        filename = article['filename']
        print(f"[{i}/{stats['total']}] {filename}")
        
        # Read article
        content = read_article_from_gcs(source_bucket, article['blob_name'])
        
        if content is None:
            stats['errors'] += 1
            print(f"  ❌ Failed to read")
            continue
      Source bucket: {project_id}-crawler-data (raw crawled data)
    # Target bucket: {project_id}-cleaned-crawler-data (cleaned data)
    
    source_bucket = os.environ.get('GCS_BUCKET')  # crawler-data bucket
    target_bucket = os.environ.get('GCS_CLEANED_BUCKET')  # cleaned-crawler-data bucket
    date_str = os.environ.get('PROCESS_DATE')  # Optional: specific date, defaults to yesterday
    prefix_path = os.environ.get('GCS_PREFIX', 'dvb')  # Default: 'dvb'
    
    if not source_bucket:
        print("❌ Error: GCS_BUCKET environment variable not set")
        print("   This should be automatically set by Cloud Run from Terraform config")
        exit(1)
    
    if not target_bucket:
        print("❌ Error: GCS_CLEANED_BUCKET environment variable not set")
        print("   This should point to the cleaned-crawler-data bucket")
        exit(1)
    
    print("=" * 60)
    print("DVB Article Cleaner - Pipeline Mode")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Source bucket: {source_bucket}")
    print(f"  Target bucket: {target_bucket}")
    print(f"  Process date: {date_str or 'yesterday (default)'}")
    print(f"  Prefix: {prefix_path}")
    print()
    
    # Process and clean articles
    stats = process_and_clean_articles(source_bucket, target_bucket, date_str, prefix_path)
    
    print()
    print("=" * 60)
    print("Cleaning Complete!")
    print("=" * 60)
    print(f"📊 Statistics:")
    print(f"   Total articles: {stats['total']}")
    print(f"   ✅ Cleaned: {stats['cleaned']}")
    print(f"   ⏭️  Unchanged: {stats['unchanged']}")
    print(f"   ❌ Errors: {stats['errors']}")
    print()
    
    if stats['errors'] > 0:
        print(f"⚠️  Completed with {stats['errors']} errors")
        exit(1)
    else:
        print("✅ All articles processed successfully!")
        print(f"   Cleaned data stored in: gs://{target_bucket}/dvb_cleaned/{date_str or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}/")
        exit(0eviewing First {min(sample_size, len(articles))} Articles")
    print("=" * 60)
    print()
    
    for i, article in enumerate(articles[:sample_size], 1):
        print(f"Article {i}/{len(articles)}: {article['filename']}")
        print(f"Size: {article['size']:,} bytes")
        print("-" * 60)
        
        content = read_article_from_gcs(article['bucket'], article['blob_name'])
        
        if content:
            lines = content.split('\n')
            # Show first 10 lines
            for j, line in enumerate(lines[:10], 1):
                print(f"{j:3d}: {line}")
            
            if len(lines) > 10:
                print(f"\n... {len(lines) - 10} more lines ...")
                print("\nLast 3 lines:")
                for j, line in enumerate(lines[-3:], len(lines) - 2):
                    print(f"{j:3d}: {line}")
        
        print()
    
    if len(articles) > sample_size:
        print(f"... and {len(articles) - sample_size} more articles")
        print()


if __name__ == "__main__":
    # Pipeline mode - GCS_BUCKET is set by Terraform/Cloud Run environment
    # Bucket pattern: {project_id}-crawler-data
    bucket_name = os.environ.get('GCS_BUCKET')
    date_str = os.environ.get('PROCESS_DATE')  # Optional: specific date, defaults to yesterday
    prefix_path = os.environ.get('GCS_PREFIX', 'dvb')  # Default: 'dvb'
    
    if not bucket_name:
        print("❌ Error: GCS_BUCKET environment variable not set")
        print("   This should be automatically set by Cloud Run from Terraform config")
        exit(1)
    
    print("=" * 60)
    print("DVB Article Cleaner - Pipeline Mode")
    print("=" * 60)
    print(f"Environment:")
    print(f"  GCS_BUCKET: {bucket_name}")
    print(f"  PROCESS_DATE: {date_str or 'yesterday (default)'}")
    print(f"  GCS_PREFIX: {prefix_path}")
    print()
    
    # Fetch articles from GCS
    articles = fetch_articles_from_gcs(bucket_name, date_str, prefix_path)
    
    if articles:
        # Preview first 3 articles
        preview_articles(bucket_name, date_str, prefix_path, sample_size=3)
        
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Total articles found: {len(articles)}")
        print(f"Bucket: gs://{bucket_name}")
        print(f"Date: {date_str or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}")
        print()
        print("✅ Articles fetched successfully!")
        print("   Ready for cleaning in next pipeline step")
    else:
        print("⚠️  No articles found to process")
        exit(1)
