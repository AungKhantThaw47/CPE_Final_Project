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
from datetime import datetime, timedelta
from google.cloud import storage
from typing import List, Dict, Optional

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


def fetch_cleaned_articles(bucket_name: str, date_str: str,
                           prefix_path: str = "dvb_cleaned") -> List[Dict]:
    """Fetch cleaned articles from GCS bucket for a specific date."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING CLEANED ARTICLES FROM GCS")
    logger.info("=" * 60)
    logger.info(f"📦 Bucket: gs://{bucket_name}")
    logger.info(f"📅 Date: {date_str}")
    logger.info(f"📂 Prefix: {prefix_path}/{date_str}/")
    logger.info("")

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        prefix = f"{prefix_path}/{date_str}/"
        blobs = list(bucket.list_blobs(prefix=prefix))

        txt_blobs = [b for b in blobs
                     if b.name.endswith('.txt') and not b.name.endswith('_COMPLETE')]

        logger.info(f"📊 Found {len(blobs)} total files")
        logger.info(f"   - Text articles: {len(txt_blobs)}")
        logger.info("")

        if not txt_blobs:
            logger.warning("⚠️  No cleaned articles found!")
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

        logger.info(f"✅ Successfully fetched {len(articles)} article references")
        return articles

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
    logger.info(f"📥 Source:  gs://{source_bucket}/{prefix_path}/{date_str}/")
    logger.info(f"⏳ Pending: gs://{crisis_bucket}/pending_review/{date_str}/")
    logger.info("")

    articles = fetch_cleaned_articles(source_bucket, date_str, prefix_path)

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
                destination_path = f"pending_review/{date_str}/{filename}"
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
        logger.info(f"   Pending review: gs://{crisis_bucket}/pending_review/{date_str}/")
