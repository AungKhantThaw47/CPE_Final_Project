#!/usr/bin/env python3
"""
Script to clean DVB news articles from GCS bucket.
Fetches articles from crawler bucket, cleans them, and stores in cleaned bucket.
"""

import os
import re
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional

# Common Myanmar author name patterns
AUTHOR_NAME_PATTERN = re.compile(r'^[\u1000-\u109F\u200B-\u200D\uAA60-\uAA7F]{2,20}$')

# Source citation patterns
SOURCE_PATTERNS = [
    re.compile(r'^Source\s*:\s*.+', re.IGNORECASE),
    re.compile(r'^ရင်းမြစ်\s*:\s*.+'),
    re.compile(r'^သတင်းရင်းမြစ်\s*:\s*.+'),
]

def is_likely_author_name(line):
    """Check if a line is likely an author name."""
    line = line.strip()
    
    if not line:
        return False
    
    if AUTHOR_NAME_PATTERN.match(line):
        return True
    
    clean_line = line.replace('။', '').replace('၊', '').strip()
    
    if len(clean_line) <= 15 and AUTHOR_NAME_PATTERN.match(clean_line):
        return True
    
    return False


def is_source_citation(line):
    """Check if a line is a source citation."""
    line = line.strip()
    
    if not line:
        return False
    
    for pattern in SOURCE_PATTERNS:
        if pattern.match(line):
            return True
    
    return False


def clean_text_content(content: str) -> tuple:
    """
    Clean text content by removing author names and source citations.
    Returns (cleaned_content, was_modified)
    """
    if not content:
        return content, False
    
    lines = content.split('\n')
    modified = False
    
    # Remove trailing empty lines
    while lines and lines[-1].strip() == '':
        lines.pop()
    
    if not lines:
        return content, False
    
    # Remove author names and source citations from the end
    while lines:
        last_line = lines[-1].strip()
        
        if is_likely_author_name(last_line):
            lines.pop()
            modified = True
            while lines and lines[-1].strip() == '':
                lines.pop()
        elif is_source_citation(last_line):
            lines.pop()
            modified = True
            while lines and lines[-1].strip() == '':
                lines.pop()
        else:
            break
    
    if modified and lines:
        cleaned_content = '\n'.join(lines)
        if not cleaned_content.endswith('\n'):
            cleaned_content += '\n'
        return cleaned_content, True
    
    return content, False


def fetch_articles_from_gcs(bucket_name: str, date_str: Optional[str] = None, 
                            prefix_path: str = "dvb") -> List[Dict]:
    """Fetch all articles from GCS bucket for a specific date."""
    if not date_str:
        # Use 2 days ago to ensure crawler has finished
        two_days_ago = datetime.now() - timedelta(days=2)
        date_str = two_days_ago.strftime('%Y-%m-%d')
    
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
        
        prefix = f"{prefix_path}/{date_str}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        txt_blobs = [b for b in blobs if b.name.endswith('.txt')]
        json_blobs = [b for b in blobs if b.name.endswith('.json')]
        
        print(f"📊 Found {len(blobs)} total files")
        print(f"   - Text articles: {len(txt_blobs)}")
        print(f"   - JSON metadata: {len(json_blobs)}")
        print()
        
        if not txt_blobs:
            print("⚠️  No text articles found!")
            return []
        
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
    """Read a single article from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        content = blob.download_as_text()
        return content
        
    except Exception as e:
        print(f"❌ Error reading {blob_name}: {e}")
        return None


def upload_cleaned_article(content: str, bucket_name: str, destination_path: str) -> bool:
    """Upload cleaned article content to GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        
        blob.upload_from_string(content, content_type='text/plain')
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to {destination_path}: {e}")
        return False


def process_and_clean_articles(source_bucket: str, target_bucket: str, 
                               date_str: Optional[str] = None, 
                               prefix_path: str = "dvb") -> Dict[str, int]:
    """Process all articles: fetch, clean, and upload to target bucket."""
    if not date_str:
        # Use 2 days ago to ensure crawler has finished
        two_days_ago = datetime.now() - timedelta(days=2)
        date_str = two_days_ago.strftime('%Y-%m-%d')
    
    print()
    print("=" * 60)
    print("Processing and Cleaning Articles")
    print("=" * 60)
    print(f"📥 Source: gs://{source_bucket}/{prefix_path}/{date_str}/")
    print(f"📤 Target: gs://{target_bucket}/dvb_cleaned/{date_str}/")
    print()
    
    articles = fetch_articles_from_gcs(source_bucket, date_str, prefix_path)
    
    if not articles:
        return {"total": 0, "cleaned": 0, "unchanged": 0, "errors": 0}
    
    stats = {"total": len(articles), "cleaned": 0, "unchanged": 0, "errors": 0}
    
    print(f"Processing {stats['total']} articles...")
    print()
    
    for i, article in enumerate(articles, 1):
        filename = article['filename']
        print(f"[{i}/{stats['total']}] {filename}")
        
        content = read_article_from_gcs(source_bucket, article['blob_name'])
        
        if content is None:
            stats['errors'] += 1
            print(f"  ❌ Failed to read")
            continue
        
        cleaned_content, was_modified = clean_text_content(content)
        
        destination_path = f"dvb_cleaned/{date_str}/{filename}"
        success = upload_cleaned_article(cleaned_content, target_bucket, destination_path)
        
        if success:
            if was_modified:
                stats['cleaned'] += 1
                print(f"  ✅ Cleaned and uploaded")
            else:
                stats['unchanged'] += 1
                print(f"  ⏭️  No changes, uploaded as-is")
        else:
            stats['errors'] += 1
            print(f"  ❌ Upload failed")
    
    return stats


if __name__ == "__main__":
    # Pipeline mode - reads from GCS_BUCKET environment variable
    # Automatically derives cleaned bucket name
    source_bucket = os.environ.get('GCS_BUCKET')
    date_str = os.environ.get('PROCESS_DATE')
    prefix_path = os.environ.get('GCS_PREFIX', 'dvb')
    
    if not source_bucket:
        print("❌ Error: GCS_BUCKET environment variable not set")
        exit(1)
    
    # Derive target bucket: crawler-data -> cleaned-crawler-data
    target_bucket = source_bucket.replace('-crawler-data', '-cleaned-crawler-data')
    
    print("=" * 60)
    print("DVB Article Cleaner - Pipeline Mode")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Source bucket: {source_bucket}")
    print(f"  Target bucket: {target_bucket}")
    print(f"  Process date: {date_str or '2 days ago (default)'}")
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
        final_date = date_str or (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        print(f"   Cleaned data: gs://{target_bucket}/dvb_cleaned/{final_date}/")

        # Create completion marker file to trigger classifier
        try:
            client = storage.Client()
            marker_path = f"dvb_cleaned/{final_date}/_COMPLETE"
            marker_blob = client.bucket(target_bucket).blob(marker_path)
            marker_blob.upload_from_string("", content_type='text/plain')
            print(f"   Completion marker: gs://{target_bucket}/{marker_path}")
        except Exception as e:
            print(f"   ⚠️  Failed to create completion marker: {e}")

        exit(0)
