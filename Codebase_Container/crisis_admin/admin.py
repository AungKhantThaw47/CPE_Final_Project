import os
import logging
import sys
import re
from datetime import datetime
from flask import Flask, request, jsonify, redirect, render_template
from google.cloud import storage
import google.auth
from google.auth.transport.requests import AuthorizedSession
from typing import List, Dict, Optional


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import (
    query_folder_hashes_from_neo4j_env,
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_source_hash_env,
    query_moving_target_hash_from_source_hash_env,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Keep this module local so content hashing captures admin runtime updates (rev2).

ANNOTATION_STAGE_PREFIXES = ("pending_review_annotation",)


@app.route("/", methods=["GET"])
def root():
    return redirect("/admin")


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


def extract_event_blocks(text: str) -> List[str]:
    """Extract text contained in <event>...</event> tags."""
    if not text:
        return []
    return [match.strip() for match in re.findall(r"<event>(.*?)</event>", text, flags=re.DOTALL | re.IGNORECASE)]


def resolve_latest_folder_hash_from_gcs(stage_prefix: str, bucket_name: str) -> Optional[str]:
    """Scan GCS under `stage_prefix/` and return the hash with the most-recent blob timestamp.

    This is a fallback when Neo4j has no FolderHash for the stage.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{stage_prefix}/")

        latest_by_hash = {}
        for blob in blobs:
            # Expect paths: {stage_prefix}/{hash}/{date}/... or legacy {stage_prefix}/{date}/...
            m = re.match(rf"^{re.escape(stage_prefix)}/([^/]+)/", blob.name)
            if not m:
                continue
            h = m.group(1)
            updated = getattr(blob, 'updated', None) or getattr(blob, 'time_created', None)
            if updated is None:
                continue
            # Use updated timestamp for ordering
            ts = updated.timestamp() if hasattr(updated, 'timestamp') else 0
            prev = latest_by_hash.get(h)
            if not prev or ts > prev[0]:
                latest_by_hash[h] = (ts, blob.name)

        if not latest_by_hash:
            return None

        # Return the hash with the newest timestamp
        latest_hash = max(latest_by_hash.items(), key=lambda kv: kv[1][0])[0]
        return latest_hash
    except Exception as e:
        logger.warning(f"⚠️  Failed to scan GCS for latest folder hash: {e}")
        return None


def trigger_cloud_run_job(job_name: str, file_location: str = "") -> None:
    """Trigger a Cloud Run job asynchronously from admin actions with optional file location."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
    region = os.environ.get("GCP_REGION", "asia-southeast1")
    if not project_id:
        logger.warning("⚠️  GOOGLE_CLOUD_PROJECT(_ID) not set; skipping job trigger for %s", job_name)
        return

    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        authed_session = AuthorizedSession(credentials)
        url = (
            f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/"
            f"namespaces/{project_id}/jobs/{job_name}:run"
        )
        payload = {}
        if file_location:
            payload["overrides"] = {
                "containerOverrides": [{
                    "env": [{"name": "ADMIN_TRIGGER_FILE_LOCATION", "value": file_location}]
                }]
            }
        response = authed_session.post(url, json=payload)
        if 200 <= response.status_code < 300:
            logger.info("🚀 Triggered Cloud Run job: %s%s", job_name, f" (file: {file_location})" if file_location else "")
        else:
            logger.error("❌ Failed to trigger job %s: %s %s", job_name, response.status_code, response.text)
    except Exception as exc:
        logger.error("❌ Error triggering job %s: %s", job_name, exc)


def list_stage_articles(
    crisis_bucket: str,
    stage_prefix: str,
    selected_hash: Optional[str] = None,
) -> List[Dict]:
    """List stage articles strictly from latest Neo4j hash; no GCS fallback."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)

    selected_hash = (selected_hash or "").strip()

    if not selected_hash:
        return []

    blobs = list(bucket.list_blobs(prefix=f"{stage_prefix}/{selected_hash}/"))

    articles = []
    for blob in blobs:
        if blob.name.endswith('.txt'):
            # hashed: {stage_prefix}/{hash}/{date}/{filename}
            # legacy: {stage_prefix}/{date}/{filename}
            hash_match = re.match(rf"^{re.escape(stage_prefix)}/([^/]+)/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})/(.+\.txt)$", blob.name)
            legacy_match = re.match(rf"^{re.escape(stage_prefix)}/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})/(.+\.txt)$", blob.name)

            if hash_match:
                hash_value = hash_match.group(1)
                date = hash_match.group(2)
                filename = hash_match.group(3)
            elif legacy_match:
                hash_value = "legacy"
                date = legacy_match.group(1)
                filename = legacy_match.group(2)
            else:
                continue

            articles.append({
                'blob_name': blob.name,
                'filename': filename,
                'date': date,
                'hash': hash_value,
                'size': blob.size,
            })
    return articles


def list_all_hashes_in_stage(crisis_bucket: str, stage_prefix: str) -> List[str]:
    """List all hashes present in a stage folder, ordered by most recent first."""
    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        
        hash_times = {}
        for blob in bucket.list_blobs(prefix=f"{stage_prefix}/"):
            # Extract hash from path: {stage_prefix}/{hash}/{date}/{filename}
            m = re.match(rf"^{re.escape(stage_prefix)}/([^/]+)/", blob.name)
            if not m:
                continue
            h = m.group(1)
            updated = blob.updated or datetime.min
            if h not in hash_times or updated > hash_times[h]:
                hash_times[h] = updated
        
        # Sort by most recent first
        return sorted(hash_times.keys(), key=lambda h: hash_times[h], reverse=True)
    except Exception as e:
        logger.warning(f"⚠️  Error listing hashes in {stage_prefix}: {e}")
        return []


def list_pending_articles_all_hashes(crisis_bucket: str) -> List[Dict]:
    """List all pending_review articles from all hashes, grouped by hash."""
    hashes = list_all_hashes_in_stage(crisis_bucket, "pending_review")
    
    result = []
    for h in hashes:
        articles = list_stage_articles(crisis_bucket, "pending_review", selected_hash=h)
        if articles:
            result.append({"hash": h, "articles": articles})
    
    return result


def list_pending_annotation_articles_all_hashes(crisis_bucket: str) -> List[Dict]:
    """List all pending_review_annotation articles from all hashes, grouped by hash."""
    ordered_hashes: List[str] = []
    articles_by_hash: Dict[str, Dict[str, Dict]] = {}

    for stage_prefix in ANNOTATION_STAGE_PREFIXES:
        neo4j_hashes = query_folder_hashes_from_neo4j_env(f"{stage_prefix}/", bucket_name=crisis_bucket)
        gcs_hashes = list_all_hashes_in_stage(crisis_bucket, stage_prefix)
        for h in neo4j_hashes + gcs_hashes:
            if h not in ordered_hashes:
                ordered_hashes.append(h)

            articles = list_stage_articles(crisis_bucket, stage_prefix, selected_hash=h)
            if not articles:
                continue

            bucket = articles_by_hash.setdefault(h, {})
            for article in articles:
                bucket[article["blob_name"]] = article

    result = []
    for h in ordered_hashes:
        merged_articles = list(articles_by_hash.get(h, {}).values())
        if merged_articles:
            merged_articles.sort(key=lambda a: (a.get("date", ""), a.get("filename", ""), a.get("blob_name", "")))
            result.append({"hash": h, "articles": merged_articles})

    return result


def list_pending_articles(crisis_bucket: str) -> List[Dict]:
    """Legacy function for backwards compatibility. Returns all hashes grouped."""
    return list_pending_articles_all_hashes(crisis_bucket)


def list_pending_annotation_articles(crisis_bucket: str) -> List[Dict]:
    """Legacy function for backwards compatibility. Returns all hashes grouped."""
    return list_pending_annotation_articles_all_hashes(crisis_bucket)


def get_stage_hash_status(stage_prefix: str, crisis_bucket: str) -> Dict[str, str]:
    """Return Neo4j status for a review stage FolderHash."""
    system_db_hash = query_latest_folder_hash_from_neo4j_env(f"{stage_prefix}/", crisis_bucket)
    status = "available" if system_db_hash else "empty"

    return {
        "stage_prefix": stage_prefix,
        "status": status,
        "system_db_hash": system_db_hash or "-",
    }


def get_stage_hash_status_view(status: Dict[str, str]) -> Dict[str, str]:
    """Add template-friendly label and class for a Neo4j stage hash status."""
    label = status["stage_prefix"].replace("_", " ").title()

    if status["status"] == "available":
        text = f"{label}: Neo4j hash available"
        class_name = "ok"
    else:
        text = f"{label}: no hash available in Neo4j"
        class_name = "muted"

    return {
        **status,
        "label": label,
        "text": text,
        "class_name": class_name,
        "system_hash_id": f"{status['stage_prefix']}-system-hash",
    }


def resolve_moving_hash(
    source_folder_path: str,
    target_folder_path: str,
    source_hash: str,
    crisis_bucket: str,
) -> str:
    """Resolve the target-stage hash that moves with a source hash via Neo4j.
    
    Tries DEPENDS_ON_DATA_FROM first (primary method), then falls back to DERIVED_FROM.
    """
    source_hash = (source_hash or "").strip()
    if not source_hash or not crisis_bucket:
        return "-"

    # Try DEPENDS_ON_DATA_FROM first (primary method used in deployment)
    # Don't filter by bucket - the target folder might be empty but still valid
    mapped = query_moving_target_hash_from_source_hash_env(
        source_folder_path=source_folder_path,
        target_folder_path=target_folder_path,
        source_hash=source_hash,
        bucket_name="",
    )
    if mapped:
        return mapped
    
    # Fall back to DERIVED_FROM if DEPENDS_ON_DATA_FROM doesn't find anything
    mapped = query_folder_hash_derived_from_source_hash_env(
        target_folder_path=target_folder_path,
        source_folder_path=source_folder_path,
        source_hash=source_hash,
        bucket_name="",
    )
    return mapped or "-"


def group_articles_by_date(articles: List[Dict]) -> List[Dict]:
    """Group articles by date for template rendering."""
    grouped: Dict[str, List[Dict]] = {}
    for article in articles:
        grouped.setdefault(article["date"], []).append(article)

    result = []
    for date in sorted(grouped.keys()):
        result.append({"date": date, "articles": grouped[date]})
    return result


def validate_blob_is_latest_hash(blob_name: str, stage_prefix: str, crisis_bucket: str) -> bool:
    """Validate that the blob belongs to the requested stage and exists.

    Admin actions are allowed for any versioned hash, not just the latest Neo4j hash.
    This only rejects malformed paths or missing blobs.
    """

    # Extract hash from blob path: {stage_prefix}/{hash}/{date}/{filename}
    stage_prefixes = (stage_prefix,)
    hash_match = None
    for candidate_prefix in stage_prefixes:
        hash_match = re.match(rf"^{re.escape(candidate_prefix)}/([^/]+)/", blob_name)
        if hash_match:
            break
    if not hash_match:
        return False

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        return bucket.blob(blob_name).exists(client)
    except Exception as exc:
        logger.warning(f"⚠️  Failed to validate blob {blob_name}: {exc}")
        return False


def get_review_actions(blob_name: str) -> Dict[str, str]:
    """Return the correct confirm/reject actions for a blob path."""
    if any(blob_name.startswith(f"{prefix}/") for prefix in ANNOTATION_STAGE_PREFIXES):
        return {
            "confirm_action": "/admin/confirm_annotation",
            "reject_action": "/admin/reject_annotation",
        }

    return {
        "confirm_action": "/admin/confirm",
        "reject_action": "/admin/reject",
    }


def find_next_blob_after(blob_name: str, stage_prefix: str, crisis_bucket: str) -> Optional[str]:
    """Return the next blob name in the same stage/hash group or None.

    Lists articles for the same folder-hash and returns the subsequent blob
    after `blob_name` in the stable ordering used by `list_stage_articles()`.
    """
    # Extract hash from blob path: {stage_prefix}/{hash}/{date}/{filename}
    stage_prefixes = (stage_prefix,)
    selected_hash = None
    actual_stage_prefix = None
    for candidate_prefix in stage_prefixes:
        m = re.match(rf'^{re.escape(candidate_prefix)}/([^/]+)/', blob_name)
        if m:
            selected_hash = m.group(1)
            actual_stage_prefix = candidate_prefix
            break
    if not selected_hash or not actual_stage_prefix:
        return None

    try:
        articles = list_stage_articles(crisis_bucket, actual_stage_prefix, selected_hash=selected_hash)
        # stable sort by date then filename to provide deterministic "next"
        def keyfn(a):
            return (a.get('date',''), a.get('filename',''))
        articles_sorted = sorted(articles, key=keyfn)
        blob_names = [a['blob_name'] for a in articles_sorted]
        if blob_name in blob_names:
            idx = blob_names.index(blob_name)
            if idx + 1 < len(blob_names):
                return blob_names[idx + 1]
    except Exception:
        return None
    return None


@app.route("/admin", methods=["GET"])
def admin_page():
    """Admin HTML page for reviewing pending and annotated crisis queues."""
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    try:
        # Get articles grouped by hash (each hash group has articles list)
        pending_by_hash = list_pending_articles(crisis_bucket) if crisis_bucket else []
        pending_annotation_by_hash = list_pending_annotation_articles(crisis_bucket) if crisis_bucket else []
        
        # For each hash group, further group articles by date
        pending_grouped_with_dates = []
        for hash_group in pending_by_hash:
            dated_articles = group_articles_by_date(hash_group.get('articles', []))
            pending_grouped_with_dates.append({
                'hash': hash_group['hash'],
                'moving_hash': resolve_moving_hash(
                    source_folder_path='pending_review/',
                    target_folder_path='crisis_articles/',
                    source_hash=hash_group['hash'],
                    crisis_bucket=crisis_bucket,
                ),
                'date_groups': dated_articles
            })
        
        annotation_grouped_with_dates = []
        for hash_group in pending_annotation_by_hash:
            dated_articles = group_articles_by_date(hash_group.get('articles', []))
            annotation_grouped_with_dates.append({
                'hash': hash_group['hash'],
                'moving_hash': resolve_moving_hash(
                    source_folder_path='pending_review_annotation/',
                    target_folder_path='annotated_articles/',
                    source_hash=hash_group['hash'],
                    crisis_bucket=crisis_bucket,
                ),
                'date_groups': dated_articles
            })
        
        # Count total articles across all hashes
        total_pending_count = sum(len(hg.get('articles', [])) for hg in pending_by_hash)
        total_annotation_count = sum(len(hg.get('articles', [])) for hg in pending_annotation_by_hash)
        
        hash_statuses = [
            get_stage_hash_status_view(get_stage_hash_status("pending_review", crisis_bucket)),
            get_stage_hash_status_view(get_stage_hash_status("pending_review_annotation", crisis_bucket)),
        ] if crisis_bucket else []
        logger.info(hash_statuses)
    except Exception as e:
        pending_grouped_with_dates = []
        annotation_grouped_with_dates = []
        total_pending_count = 0
        total_annotation_count = 0
        hash_statuses = []
        logger.error(f"Error listing pending articles: {e}")

    return render_template(
        "admin.html",
        pending_articles_count=total_pending_count,
        pending_annotation_articles_count=total_annotation_count,
        pending_grouped=pending_grouped_with_dates,
        annotation_grouped=annotation_grouped_with_dates,
        hash_statuses=hash_statuses,
    )


@app.route("/admin/view", methods=["GET"])
def admin_view_article():
    """View raw content of a pending article."""
    blob_name = request.args.get('blob', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400
    try:
        content = read_article_from_gcs(crisis_bucket, blob_name)
        if content is None:
            return "Article not found", 404
        review_actions = get_review_actions(blob_name)
        return render_template(
            "article_view.html",
            blob_name=blob_name,
            content=content,
            confirm_action=review_actions["confirm_action"],
            reject_action=review_actions["reject_action"],
        )
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/admin/view_event_tags", methods=["GET"])
def admin_view_event_tags():
    """View extracted <event> blocks from a pending annotated article."""
    blob_name = request.args.get('blob', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        content = read_article_from_gcs(crisis_bucket, blob_name)
        if content is None:
            return "Article not found", 404

        event_blocks = extract_event_blocks(content)
        review_actions = get_review_actions(blob_name)
        return render_template(
            "event_tags.html",
            blob_name=blob_name,
            event_blocks=event_blocks,
            confirm_action=review_actions["confirm_action"],
            reject_action=review_actions["reject_action"],
        )
    except Exception as e:
        return f"Error: {e}", 500


@app.route("/admin/confirm", methods=["POST"])
def admin_confirm():
    """Move a pending article to crisis_articles/ and trigger annotation job."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Missing parameters"}), 400
        return "Missing parameters", 400

    # Validate blob is from latest hash
    if not validate_blob_is_latest_hash(blob_name, "pending_review", crisis_bucket):
        error_msg = "Cannot confirm article: invalid or missing blob"
        logger.warning(f"⚠️  {error_msg} - blob: {blob_name}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": error_msg}), 403
        return error_msg, 403

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review/{hash}/{date}/{filename} -> crisis_articles/{mapped_hash}/{date}/{filename}
        # Prefer a previously-created crisis_articles hash that was DERIVED_FROM this pending_review hash
        # If none exists, fallback to using the pending_review hash itself so the move remains version-aligned.
        pending_hash_match = re.match(r'^pending_review/([^/]+)/', blob_name)
        pending_review_hash = pending_hash_match.group(1) if pending_hash_match else ""
        # Prefer a previously-created crisis_articles hash that maps from this pending_review hash.
        # Use the general resolver which prefers DEPENDS_ON_DATA_FROM then falls back to DERIVED_FROM.
        output_hash = pending_review_hash or "unknown"
        if pending_review_hash:
            mapped = resolve_moving_hash(
                source_folder_path='pending_review/',
                target_folder_path='crisis_articles/',
                source_hash=pending_review_hash,
                crisis_bucket=crisis_bucket,
            )
            if mapped and mapped != "-":
                output_hash = mapped
                logger.info(f"✅ Using Neo4j mapping for crisis_articles/ → {output_hash}")
            else:
                logger.info("ℹ️ No Neo4j mapping found; falling back to pending_review hash")
        date_match = re.match(r'^pending_review/[^/]+/([0-9]{4}-[0-9]{2}-[0-9]{2})/', blob_name)
        date_str = date_match.group(1) if date_match else "unknown"
        filename = blob_name.split('/')[-1]
        destination_name = f'crisis_articles/{output_hash}/{date_str}/{filename}'
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()

        logger.info(f"✅ File saved to gs://{crisis_bucket}/{destination_name}")

        if pending_review_hash:
            logger.info(f"✅ Using Neo4j mapping for crisis_articles/ → {output_hash}")

        trigger_cloud_run_job("dvb-annotator-job", file_location=f"crisis_articles/{output_hash}/{date_str}/")

        logger.info(f"✅ Confirmed: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Confirm failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Confirmed: {blob_name}"}), 200

    # Non-AJAX: redirect to next article in the same pending_review hash if available
    next_blob = find_next_blob_after(blob_name, 'pending_review', crisis_bucket)
    if next_blob:
        return redirect(f'/admin/view?blob={next_blob}')
    return redirect('/admin')


@app.route("/admin/reject", methods=["POST"])
def admin_reject():
    """Delete a pending article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Missing parameters"}), 400
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Reject failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Rejected: {blob_name}"}), 200

    # Non-AJAX: redirect to next article in the same pending_review hash if available
    next_blob = find_next_blob_after(blob_name, 'pending_review', crisis_bucket)
    if next_blob:
        return redirect(f'/admin/view?blob={next_blob}')
    return redirect('/admin')


@app.route("/admin/confirm_annotation", methods=["POST"])
def admin_confirm_annotation():
    """Move a pending annotated article to annotated_articles/ and trigger extraction."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Missing parameters"}), 400
        return "Missing parameters", 400

    # Validate blob is from an allowed annotation hash
    if not validate_blob_is_latest_hash(blob_name, "pending_review_annotation", crisis_bucket):
        error_msg = "Cannot confirm annotation: invalid or missing blob"
        logger.warning(f"⚠️  {error_msg} - blob: {blob_name}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": error_msg}), 403
        return error_msg, 403

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review_annotation/{hash}/{date}/{filename} -> annotated_articles/{same_hash}/{date}/{filename}
        # Use the annotation hash directly so that annotated_articles/ stays version-chain aligned.
        pending_ann_match = None
        for prefix in ANNOTATION_STAGE_PREFIXES:
            pending_ann_match = re.match(rf'^{re.escape(prefix)}/([^/]+)/', blob_name)
            if pending_ann_match:
                break
        pending_ann_hash = pending_ann_match.group(1) if pending_ann_match else ""
        output_hash = pending_ann_hash or "unknown"
        date_match = None
        for prefix in ANNOTATION_STAGE_PREFIXES:
            date_match = re.match(rf'^{re.escape(prefix)}/[^/]+/([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})/', blob_name)
            if date_match:
                break
        date_str = date_match.group(1) if date_match else "unknown"
        filename = blob_name.split('/')[-1]
        destination_name = f'annotated_articles/{output_hash}/{date_str}/{filename}'
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()

        logger.info(f"✅ File saved to gs://{crisis_bucket}/{destination_name}")

        logger.info(f"✅ Using existing Neo4j mapping for annotated_articles/ → {output_hash}")

        trigger_cloud_run_job("dvb-extractor-job", file_location=f"annotated_articles/{output_hash}/{date_str}/")

        logger.info(f"✅ Confirmed annotation: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Annotation confirm failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Confirmed annotation: {blob_name}"}), 200

    # Non-AJAX: redirect to next article in the same pending annotation hash if available
    next_blob = find_next_blob_after(blob_name, 'pending_review_annotation', crisis_bucket)
    if next_blob:
        return redirect(f'/admin/view?blob={next_blob}')
    return redirect('/admin')


@app.route("/admin/reject_annotation", methods=["POST"])
def admin_reject_annotation():
    """Delete a pending annotated article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Missing parameters"}), 400
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected annotation: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Annotation reject failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Rejected annotation: {blob_name}"}), 200

    # Non-AJAX: redirect to next article in the same pending annotation hash if available
    next_blob = find_next_blob_after(blob_name, 'pending_review_annotation', crisis_bucket)
    if next_blob:
        return redirect(f'/admin/view?blob={next_blob}')
    return redirect('/admin')


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
