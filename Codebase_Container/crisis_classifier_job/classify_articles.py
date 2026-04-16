#!/usr/bin/env python3
"""
Crisis News Classifier Job

This batch job:
1. Reads cleaned articles from GCS for yesterday's date (or PROCESS_DATE env var)
2. Loads the crisis classification model
3. Classifies each article as crisis or non-crisis
4. Saves crisis articles to pending_review/ in the crisis bucket for admin review
"""

import os
import pickle
import logging
import sys
import re
import hashlib
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional, Tuple


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import query_latest_hash_from_neo4j_env, query_output_hash_from_neo4j_env

# Heavy ML imports — required for model loading
try:
    import numpy as np
    from sklearn.base import BaseEstimator, TransformerMixin

    # Required for unpickling the Gemma model
    class GemmaEmbeddingVectorizer(BaseEstimator, TransformerMixin):
        """Sklearn-compatible transformer that returns mean-pooled Gemma embeddings."""

        def __init__(self, model_name="google/embeddinggemma-300m",
                     batch_size=32, normalize=True, device=None):
            self.model_name = model_name
            self.batch_size = batch_size
            self.normalize = normalize
            self.device = device
            self.model_ = None

        def fit(self, X, y=None):
            from sentence_transformers import SentenceTransformer
            self.model_ = SentenceTransformer(self.model_name, device=self.device)
            return self

        def transform(self, X):
            if self.model_ is None:
                from sentence_transformers import SentenceTransformer
                hf_token = os.environ.get("HF_TOKEN")
                self.model_ = SentenceTransformer(self.model_name, device=self.device, token=hf_token)
            texts = list(X)
            token_embeddings = self.model_.encode(
                texts,
                output_value="token_embeddings",
                convert_to_numpy=False,
                normalize_embeddings=False,
                show_progress_bar=False,
                batch_size=self.batch_size,
            )
            matrices = list(token_embeddings)
            pooled = np.vstack([m.numpy().mean(axis=0) for m in matrices]).astype(np.float32)
            if self.normalize:
                norms = np.linalg.norm(pooled, axis=1, keepdims=True)
                norms[norms == 0.0] = 1.0
                pooled = pooled / norms
            return pooled

except ImportError:
    pass  # Will fail gracefully at model load time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "crisis_model.pkl")


def load_crisis_model(model_path: str):
    """Load the pre-trained crisis classification model."""
    logger.info("=" * 60)
    logger.info("LOADING CRISIS CLASSIFICATION MODEL")
    logger.info("=" * 60)
    logger.info(f"📦 Model path: {model_path}")

    try:
        import __main__
        __main__.GemmaEmbeddingVectorizer = GemmaEmbeddingVectorizer

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        logger.info("✅ Model loaded successfully")
        logger.info(f"   Model type: {type(model).__name__}")
        return model

    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")
        raise


def resolve_latest_hash_for_date(bucket, prefix_path: str, date_str: str) -> Optional[str]:
    """Resolve latest hash folder under prefix/date by blob update time."""
    pattern = re.compile(rf"^{re.escape(prefix_path)}/([^/]+)/{re.escape(date_str)}/")
    latest_by_hash = {}

    for blob in bucket.list_blobs(prefix=f"{prefix_path}/"):
        match = pattern.match(blob.name)
        if not match:
            continue
        hash_value = match.group(1)
        current = latest_by_hash.get(hash_value)
        updated = blob.updated or datetime.min
        if current is None or updated > current:
            latest_by_hash[hash_value] = updated

    if not latest_by_hash:
        return None

    return max(latest_by_hash.items(), key=lambda item: item[1])[0]


def build_pipeline_output_hash(source_hash: str, content_hash: str) -> str:
    """Build deterministic folder hash from upstream hash + current content hash."""
    content_hash = (content_hash or "unknown-hash").strip()
    source_hash = (source_hash or "").strip()

    if not source_hash:
        return content_hash

    return hashlib.sha256(f"{source_hash}:{content_hash}".encode("utf-8")).hexdigest()


def fetch_cleaned_articles(bucket_name: str, date_str: str,
                           prefix_path: str = "dvb_cleaned") -> Tuple[List[Dict], str]:
    """Fetch cleaned articles from GCS bucket for a specific date."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING CLEANED ARTICLES FROM GCS")
    logger.info("=" * 60)
    logger.info(f"📦 Bucket: gs://{bucket_name}")
    logger.info(f"📅 Date: {date_str}")
    logger.info(f"📂 Prefix root: {prefix_path}/")
    logger.info("")

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        source_hash = os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        if not source_hash:
            # Query the exact output hash the cleaner wrote for this date
            source_hash = query_output_hash_from_neo4j_env(f"dvb_cleaned_output:{date_str}") or ""
        if not source_hash:
            # Fallback: scan bucket for most recently updated hash folder
            source_hash = resolve_latest_hash_for_date(bucket, prefix_path, date_str) or ""

        if source_hash:
            prefix = f"{prefix_path}/{source_hash}/{date_str}/"
        else:
            # Legacy fallback for older layout without hash folders.
            prefix = f"{prefix_path}/{date_str}/"

        logger.info(f"📂 Resolved source path: {prefix}")
        blobs = list(bucket.list_blobs(prefix=prefix))

        txt_blobs = [b for b in blobs
                     if b.name.endswith('.txt') and not b.name.endswith('_COMPLETE')]

        logger.info(f"📊 Found {len(blobs)} total files")
        logger.info(f"   - Text articles: {len(txt_blobs)}")
        logger.info("")

        if not txt_blobs:
            logger.warning("⚠️  No cleaned articles found!")
            return [], source_hash

        articles = []
        for blob in txt_blobs:
            articles.append({
                'blob_name': blob.name,
                'filename': os.path.basename(blob.name),
                'size': blob.size,
                'bucket': bucket_name,
                'date': date_str
            })

        logger.info(f"✅ Successfully fetched {len(articles)} article references")
        return articles, source_hash

    except Exception as e:
        logger.error(f"❌ Error fetching articles: {e}")
        raise


def read_article_from_gcs(bucket_name: str, blob_name: str) -> Optional[str]:
    """Read a single article text from GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_text()
    except Exception as e:
        logger.error(f"❌ Error reading {blob_name}: {e}")
        return None


def classify_text(model, text: str) -> tuple:
    """Classify text as crisis or non-crisis. Returns (is_crisis, confidence)."""
    try:
        prediction = model.predict([text])[0]
        proba = model.predict_proba([text])[0]
        confidence = max(proba)
        is_crisis = bool(prediction == 'crisis')
        return is_crisis, confidence
    except Exception as e:
        logger.error(f"❌ Error during classification: {e}")
        raise


def upload_article(content: str, bucket_name: str, destination_path: str) -> bool:
    """Upload article to GCS."""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_path)
        blob.upload_from_string(content, content_type='text/plain')
        return True
    except Exception as e:
        logger.error(f"❌ Error uploading to {destination_path}: {e}")
        return False


def process_and_classify_articles(source_bucket: str, crisis_bucket: str,
                                  model, date_str: str,
                                  prefix_path: str = "dvb_cleaned") -> Dict[str, int]:
    """
    Fetch, classify, and save crisis articles to pending_review/.
    Admin must confirm/reject from the admin portal before articles move to crisis_articles/.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("CLASSIFYING ARTICLES")
    logger.info("=" * 60)
    logger.info(f"📥 Source root:  gs://{source_bucket}/{prefix_path}/")
    logger.info("")

    articles, source_hash = fetch_cleaned_articles(source_bucket, date_str, prefix_path)
    output_hash = build_pipeline_output_hash(
        source_hash,
        os.environ.get('CONTENT_HASH', 'unknown-hash').strip(),
    )

    if source_hash:
        logger.info(f"🔎 Source hash: {source_hash}")
    else:
        logger.info("🔎 Source hash: legacy/non-hash path")

    logger.info(f"🧬 Output hash: {output_hash}")
    logger.info(f"⏳ Pending: gs://{crisis_bucket}/pending_review/{output_hash}/{date_str}/")

    if not articles:
        return {"total": 0, "crisis": 0, "errors": 0}

    stats = {"total": len(articles), "crisis": 0, "errors": 0}

    logger.info(f"Processing {stats['total']} articles...")
    logger.info("")

    for i, article in enumerate(articles, 1):
        filename = article['filename']
        logger.info(f"[{i}/{stats['total']}] {filename}")

        content = read_article_from_gcs(source_bucket, article['blob_name'])

        if content is None:
            stats['errors'] += 1
            logger.error("  ❌ Failed to read")
            continue

        try:
            is_crisis, confidence = classify_text(model, content)

            if is_crisis:
                destination_path = f"pending_review/{output_hash}/{date_str}/{filename}"
                success = upload_article(content, crisis_bucket, destination_path)

                if success:
                    stats['crisis'] += 1
                    logger.info(f"  CRISIS (confidence: {confidence:.2%}) - Saved to pending_review")
                else:
                    stats['errors'] += 1
                    logger.error("  CRISIS but upload failed")
            else:
                logger.info(f"  Non-crisis (confidence: {confidence:.2%}) - Skipped")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"  ❌ Classification error: {e}")

    return stats


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Crisis Classifier Job Starting...")
    logger.info("=" * 60)

    # Get date to process (default: yesterday)
    date_str = os.environ.get('PROCESS_DATE')
    if not date_str:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y-%m-%d')

    source_bucket = os.environ.get('GCS_BUCKET')
    crisis_bucket = os.environ.get('CRISIS_BUCKET')

    if not source_bucket or not crisis_bucket:
        logger.error("❌ Missing required env vars: GCS_BUCKET, CRISIS_BUCKET")
        sys.exit(1)

    logger.info(f"📅 Processing date: {date_str}")
    logger.info(f"📦 Source bucket:   {source_bucket}")
    logger.info(f"📦 Crisis bucket:   {crisis_bucket}")

    # Skip if already classified
    storage_client = storage.Client()
    crisis_bkt = storage_client.bucket(crisis_bucket)
    already_classified = (
        any(True for _ in crisis_bkt.list_blobs(prefix="pending_review/")
            if re.match(rf"^pending_review/[^/]+/{re.escape(date_str)}/", _.name)) or
        any(True for _ in crisis_bkt.list_blobs(prefix="crisis_articles/")
            if re.match(rf"^crisis_articles/[^/]+/{re.escape(date_str)}/", _.name)) or
        any(True for _ in crisis_bkt.list_blobs(prefix=f"pending_review/{date_str}/", max_results=1)) or
        any(True for _ in crisis_bkt.list_blobs(prefix=f"crisis_articles/{date_str}/", max_results=1))
    )
    if already_classified:
        logger.info(f"⏭️  Already classified for {date_str}, skipping.")
        sys.exit(0)

    # Load model
    model = load_crisis_model(MODEL_PATH)

    # Classify
    stats = process_and_classify_articles(source_bucket, crisis_bucket, model, date_str)

    logger.info("")
    logger.info("=" * 60)
    logger.info("CLASSIFICATION COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"📊 Total: {stats['total']}  |  Crisis: {stats['crisis']}  |  Errors: {stats['errors']}")
    if stats['total'] > 0:
        crisis_rate = stats['crisis'] / stats['total'] * 100
        logger.info(f"   Crisis rate: {stats['crisis']}/{stats['total']} ({crisis_rate:.1f}%)")
        output_hash = build_pipeline_output_hash(
            os.environ.get('SOURCE_CONTENT_HASH', '').strip(),
            os.environ.get('CONTENT_HASH', 'unknown-hash').strip(),
        )
        logger.info(f"   Pending review: gs://{crisis_bucket}/pending_review/{output_hash}/{date_str}/")
