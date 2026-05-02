import os
import logging
import sys
import re
from flask import Flask, request, jsonify, redirect, render_template
from google.cloud import storage
import google.auth
from google.auth.transport.requests import AuthorizedSession
from typing import List, Dict, Optional


if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.neo4j_utils import (
    query_latest_folder_hash_from_neo4j_env,
    write_folder_hash_to_neo4j_env,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Keep this module local so content hashing captures admin runtime updates (rev2).


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


def trigger_cloud_run_job(job_name: str) -> None:
    """Trigger a Cloud Run job asynchronously from admin actions."""
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
        response = authed_session.post(url, json={})
        if 200 <= response.status_code < 300:
            logger.info("🚀 Triggered Cloud Run job: %s", job_name)
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


def list_pending_articles(crisis_bucket: str) -> List[Dict]:
    # Use only the system DB (Neo4j) FolderHash. If missing or there are no
    # blobs for the stored hash, show empty (do NOT fall back to scanning GCS).
    folder_hash = query_latest_folder_hash_from_neo4j_env("pending_review/", crisis_bucket)

    if not folder_hash:
        return []

    client = storage.Client()
    bucket = client.bucket(crisis_bucket)

    prefix = f"pending_review/{folder_hash}/"
    has_any = any(True for _ in bucket.list_blobs(prefix=prefix, max_results=1))
    if not has_any:
        return []

    return list_stage_articles(crisis_bucket, "pending_review", selected_hash=folder_hash)


def list_pending_annotation_articles(crisis_bucket: str) -> List[Dict]:
    # Use only the system DB (Neo4j) FolderHash. If missing or there are no
    # blobs for the stored hash, show empty (do NOT fall back to scanning GCS).
    folder_hash = query_latest_folder_hash_from_neo4j_env("pending_review_annotation/", crisis_bucket)

    if not folder_hash:
        return []

    client = storage.Client()
    bucket = client.bucket(crisis_bucket)

    prefix = f"pending_review_annotation/{folder_hash}/"
    has_any = any(True for _ in bucket.list_blobs(prefix=prefix, max_results=1))
    if not has_any:
        return []

    return list_stage_articles(
        crisis_bucket,
        "pending_review_annotation",
        selected_hash=folder_hash,
    )


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
    """Validate that the blob's hash matches the latest hash from Neo4j.
    
    Returns True if valid (blob hash == latest hash), False otherwise.
    """
    latest_hash = query_latest_folder_hash_from_neo4j_env(f"{stage_prefix}/", crisis_bucket)
    if not latest_hash:
        return False
    
    # Extract hash from blob path: {stage_prefix}/{hash}/{date}/{filename}
    hash_match = re.match(rf"^{re.escape(stage_prefix)}/([^/]+)/", blob_name)
    blob_hash = hash_match.group(1) if hash_match else None
    
    return blob_hash == latest_hash


def get_review_actions(blob_name: str) -> Dict[str, str]:
    """Return the correct confirm/reject actions for a blob path."""
    if blob_name.startswith("pending_review_annotation/"):
        return {
            "confirm_action": "/admin/confirm_annotation",
            "reject_action": "/admin/reject_annotation",
        }

    return {
        "confirm_action": "/admin/confirm",
        "reject_action": "/admin/reject",
    }


@app.route("/admin", methods=["GET"])
def admin_page():
    """Admin HTML page for reviewing pending and annotated crisis queues."""
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    try:
        pending_articles = list_pending_articles(crisis_bucket) if crisis_bucket else []
        pending_annotation_articles = list_pending_annotation_articles(crisis_bucket) if crisis_bucket else []
        hash_statuses = [
            get_stage_hash_status_view(get_stage_hash_status("pending_review", crisis_bucket)),
            get_stage_hash_status_view(get_stage_hash_status("pending_review_annotation", crisis_bucket)),
        ] if crisis_bucket else []
        logger.info( hash_statuses )
    except Exception as e:
        pending_articles = []
        pending_annotation_articles = []
        hash_statuses = []
        logger.error(f"Error listing pending articles: {e}")

    return render_template(
        "admin.html",
        pending_articles_count=len(pending_articles),
        pending_annotation_articles_count=len(pending_annotation_articles),
        pending_grouped=group_articles_by_date(pending_articles),
        annotation_grouped=group_articles_by_date(pending_annotation_articles),
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
        error_msg = "Cannot confirm article: not from latest hash version"
        logger.warning(f"⚠️  {error_msg} - blob: {blob_name}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": error_msg}), 403
        return error_msg, 403

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review/{hash}/{date}/{filename} -> crisis_articles/{same_hash}/{date}/{filename}
        # Use the pending_review hash directly so that crisis_articles/ stays version-chain aligned.
        pending_hash_match = re.match(r'^pending_review/([^/]+)/', blob_name)
        pending_review_hash = pending_hash_match.group(1) if pending_hash_match else ""
        output_hash = pending_review_hash or "unknown"
        date_match = re.match(r'^pending_review/[^/]+/([0-9]{4}-[0-9]{2}-[0-9]{2})/', blob_name)
        date_str = date_match.group(1) if date_match else "unknown"
        filename = blob_name.split('/')[-1]
        destination_name = f'crisis_articles/{output_hash}/{date_str}/{filename}'
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()

        if pending_review_hash:
            if write_folder_hash_to_neo4j_env(
                folder_path='crisis_articles/',
                hash_value=pending_review_hash,
                bucket_name=crisis_bucket,
                producer_component_key='service:crisis-admin',
                source_folder_path='pending_review/',
                source_folder_hash=pending_review_hash,
            ):
                logger.info(f"✅ Folder hash saved to Neo4j: crisis_articles/ → {pending_review_hash}")
            else:
                logger.warning("⚠️  Neo4j folder hash write skipped (not configured or failed)")

        trigger_cloud_run_job("dvb-annotator-job")

        logger.info(f"✅ Confirmed: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Confirm failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Confirmed: {blob_name}"}), 200
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
    return redirect('/admin')


@app.route("/admin/confirm_annotation", methods=["POST"])
def admin_confirm_annotation():
    """Move a pending annotated article to annotated_articles/ and trigger extractor job."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Missing parameters"}), 400
        return "Missing parameters", 400

    # Validate blob is from latest hash
    if not validate_blob_is_latest_hash(blob_name, "pending_review_annotation", crisis_bucket):
        error_msg = "Cannot confirm annotation: not from latest hash version"
        logger.warning(f"⚠️  {error_msg} - blob: {blob_name}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": error_msg}), 403
        return error_msg, 403

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review_annotation/{hash}/{date}/{filename} -> annotated_articles/{same_hash}/{date}/{filename}
        # Use the pending_review_annotation hash directly so that annotated_articles/ stays version-chain aligned.
        pending_ann_match = re.match(r'^pending_review_annotation/([^/]+)/', blob_name)
        pending_ann_hash = pending_ann_match.group(1) if pending_ann_match else ""
        output_hash = pending_ann_hash or "unknown"
        date_match = re.match(r'^pending_review_annotation/[^/]+/([0-9]{4}-[0-9]{2}-[0-9]{2})/', blob_name)
        date_str = date_match.group(1) if date_match else "unknown"
        filename = blob_name.split('/')[-1]
        destination_name = f'annotated_articles/{output_hash}/{date_str}/{filename}'
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()

        if write_folder_hash_to_neo4j_env(
            folder_path='annotated_articles/',
            hash_value=output_hash,
            bucket_name=crisis_bucket,
            producer_component_key='service:crisis-admin',
            source_folder_path='pending_review_annotation/',
            source_folder_hash=pending_ann_hash,
        ):
            logger.info(f"✅ Output folder hash saved to Neo4j: annotated_articles/ → {output_hash}")
        else:
            logger.warning("⚠️  Neo4j write skipped (not configured or failed)")

        trigger_cloud_run_job("dvb-extractor-job")

        logger.info(f"✅ Confirmed annotation: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Annotation confirm failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        return f"Error: {e}", 500

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Confirmed annotation: {blob_name}"}), 200
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
    return redirect('/admin')


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
