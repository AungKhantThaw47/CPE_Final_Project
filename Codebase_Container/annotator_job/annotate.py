import os
import re
import logging
import time
import sys
import hashlib
from datetime import datetime
from google.cloud import storage
from google import genai

if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import (
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_env,
    write_folder_hash_to_neo4j_env,
    create_main_pipeline_linkage_env,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ANNOTATION_PROMPT = """
1. Wrap each disaster event in the article with `<event>` and `</event>` tags.

2. Only add a tag when the text describes a real disaster event.

   The scope of disasters includes: **Fire, Airstrike, Armed Conflict, Natural Disaster, Attack, and Bombing**.

3. Consider multiple sentences as the **same event** and use a single tag if all of the following are true:

   * They refer to the same date,

   * They occur in the same location,

   * They describe the same disaster incident.

   The tag should cover all related information about that event on that day, such as damages, casualties, and response actions.

4. Create a new `<event>` tag when any of these change:

   * The date is different,

   * The location is different,(ignore the township level)

   * The incident is separate and unrelated to the previous one.

5. Do not create one tag per sentence. One disaster event should have only one continuous tag that spans all directly related text.


6. Do not tag only the disaster word (e.g., "fire" or "earthquake"). Tag the full span of text that describes the event and its immediate effects.


7. Do not tag events that happened in the past if they are mentioned only as background or historical context.


8. Only tag events that are reported as happening in the current report time, specifically when the article indicates timing such as **"today" or "yesterday."**

   If there is no clear current-day reference, do not tag the event. But tag if the event yesterday or today is connected to the same event.


9. If multiple descriptions refer to connected parts of the same ongoing disaster on the same day (for example, flooding affecting nearby areas as part of the same incident), group them under one `<event>` tag.


10. Use time expressions carefully to decide whether the text refers to:

* the same ongoing event (use one tag), or

* a different event in time or place (use a new tag).

* a same event connected in different location (use a new tag).

11. When annotating, it is **not necessary to include or mention displacement information** (e.g., people being evacuated or moved or soldiers being relocated or fleeing away) as part of deciding or defining the disaster event. But if it is happening in the same sentence together and connected with the event cosinder that sentence as the event together.

12. Also tag supporting details for that same event if it is disaster related.

13. Do not cut off from the middle of the sentence and always take from the begining of the event sentence.
"""


def compute_folder_hash(previous_folder_hash: str, content_hash: str) -> str:
    """Compute the next FolderHash from the previous folder hash and content hash.

    Matches the same formula used by the cleaner and classifier jobs: sha256("{previous}:{content}").
    """
    previous_folder_hash = (previous_folder_hash or "").strip()
    content_hash = (content_hash or "").strip()

    if not previous_folder_hash:
        return content_hash

    if not content_hash:
        return previous_folder_hash

    return hashlib.sha256(f"{previous_folder_hash}:{content_hash}".encode("utf-8")).hexdigest()


def resolve_latest_crisis_articles_hash(bucket) -> str:
    """Resolve the latest crisis_articles hash from Neo4j."""
    return query_latest_folder_hash_from_neo4j_env("crisis_articles/", bucket_name=bucket.name)


def annotate_article(article_text: str, gemini_client) -> str:
    """Annotate a single article using Gemini."""
    full_prompt = ANNOTATION_PROMPT + "\n\nArticle:\n" + article_text
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=full_prompt
    )
    return response.text


def process_crisis_articles():
    """Batch process all files in crisis_articles/ folder and save annotated output."""
    logger.info("=" * 60)
    logger.info("BATCH ANNOTATION JOB STARTED")
    logger.info("=" * 60)
    
    crisis_bucket = os.environ.get('CRISIS_BUCKET')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    
    if not crisis_bucket or not gemini_api_key:
        logger.error("❌ Missing env vars: CRISIS_BUCKET, GEMINI_API_KEY")
        return False
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(crisis_bucket)
        gemini_client = genai.Client(api_key=gemini_api_key)

        # Annotate the latest classifier output in crisis_articles/.
        source_hash = resolve_latest_crisis_articles_hash(bucket)
        if not source_hash:
            logger.error("❌ No crisis_articles/ hash found in Neo4j")
            return False

        logger.info(f"🔎 Neo4j source hash: {source_hash}")

        # List only the latest classifier batch resolved from Neo4j.
        blobs = bucket.list_blobs(prefix=f'crisis_articles/{source_hash}/')
        
        processed_count = 0
        skipped_count = 0
        error_count = 0
        annotator_content_hash = os.environ.get("CONTENT_HASH", "").strip()
        output_hash = compute_folder_hash(source_hash, annotator_content_hash)
        
        for blob in blobs:
            # Skip directories and non-txt files
            if blob.name.endswith('/') or not blob.name.endswith('.txt'):
                continue
            
            try:
                # Parse source path
                # hashed: crisis_articles/{hash}/{date}/{filename}
                # legacy: crisis_articles/{date}/{filename}
                hash_match = re.match(r'crisis_articles/([^/]+)/(\d{4}-\d{2}-\d{2})/(.+\.txt)$', blob.name)
                legacy_match = re.match(r'crisis_articles/(\d{4}-\d{2}-\d{2})/(.+\.txt)$', blob.name)
                
                if hash_match:
                    blob_hash = hash_match.group(1)
                    date_str = hash_match.group(2)
                    filename = hash_match.group(3)
                elif legacy_match:
                    blob_hash = source_hash
                    date_str = legacy_match.group(1)
                    filename = legacy_match.group(2)
                else:
                    logger.warning(f"⏭️  Could not parse path: {blob.name}")
                    skipped_count += 1
                    continue

                if blob_hash != source_hash:
                    logger.warning(
                        "⚠️  Blob hash %s does not match Neo4j source hash %s; skipping %s",
                        blob_hash,
                        source_hash,
                        blob.name,
                    )
                    skipped_count += 1
                    continue
                
                annotated_blob_name = f"pending_annotation_review/{output_hash}/{date_str}/{filename}"
                
                # Check if already annotated
                annotated_blob = bucket.blob(annotated_blob_name)
                if annotated_blob.exists():
                    logger.info(f"⏭️  Already annotated: {annotated_blob_name}")
                    skipped_count += 1
                    blob.delete()
                    logger.info(f"🗑️  Deleted source: {blob.name}")
                    continue

                # Download and annotate
                logger.info(f"📄 Processing: {blob.name}")
                article_text = blob.download_as_text(encoding='utf-8')
                logger.info(f"✅ Downloaded ({len(article_text)} chars)")

                logger.info("🤖 Annotating with Gemini...")
                annotated_text = annotate_article(article_text, gemini_client)
                logger.info("✅ Annotation complete")

                # Save annotated output, then remove source
                annotated_blob.upload_from_string(annotated_text, content_type='text/plain; charset=utf-8')
                logger.info(f"✅ Saved to gs://{crisis_bucket}/{annotated_blob_name}")
                blob.delete()
                logger.info(f"🗑️  Deleted source: {blob.name}")

                processed_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error processing {blob.name}: {e}")
                error_count += 1
                continue
        
        logger.info("=" * 60)
        logger.info(f"BATCH COMPLETE: {processed_count} processed, {skipped_count} skipped, {error_count} errors")
        logger.info("=" * 60)

        if write_folder_hash_to_neo4j_env(
            folder_path="pending_annotation_review/",
            hash_value=output_hash,
            bucket_name=crisis_bucket,
            producer_component_key="job:dvb-annotator-job",
            source_folder_path="crisis_articles/",
            source_folder_hash=source_hash,
        ):
            logger.info(f"✅ Output folder hash saved to Neo4j: pending_annotation_review/ → {output_hash}")
            
            # Create DEPENDS_ON_DATA_FROM relationships between consecutive pipeline stages
            success, message = create_main_pipeline_linkage_env()
            if success:
                logger.info(f"✅ Pipeline linkages created: {message}")
            else:
                logger.warning(f"⚠️  Pipeline linkage creation incomplete: {message}")
        else:
            logger.warning("⚠️  Neo4j write skipped (not configured or failed)")
        
        return error_count == 0
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = process_crisis_articles()
    sys.exit(0 if success else 1)
