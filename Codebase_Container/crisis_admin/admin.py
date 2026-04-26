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

from utils.neo4j_utils import query_latest_hash_from_neo4j_env, query_latest_folder_hash_from_neo4j_env

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


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


def resolve_latest_hash(bucket, prefix: str) -> Optional[str]:
    """Resolve latest hash folder under prefix/ by blob update time."""
    pattern = re.compile(rf"^{re.escape(prefix)}/([^/]+)/")
    latest_by_hash = {}

    for blob in bucket.list_blobs(prefix=f"{prefix}/"):
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


def list_stage_articles(
    crisis_bucket: str,
    stage_prefix: str,
    latest_hash_key: str,
    preferred_hash: Optional[str] = None,
) -> List[Dict]:
    """List stage articles from latest hash folder (with legacy fallback)."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)
    latest_hash = (
        (preferred_hash or "").strip()
        or os.environ.get("SOURCE_CONTENT_HASH", "").strip()
        or query_latest_hash_from_neo4j_env(latest_hash_key)
        or resolve_latest_hash(bucket, stage_prefix)
    )
    if latest_hash:
        blobs = list(bucket.list_blobs(prefix=f"{stage_prefix}/{latest_hash}/"))
    else:
        blobs = list(bucket.list_blobs(prefix=f"{stage_prefix}/"))

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
    return list_stage_articles(crisis_bucket, "pending_review", "job:crisis-classifier-job")


def list_pending_annotation_articles(crisis_bucket: str) -> List[Dict]:
    folder_hash = query_latest_folder_hash_from_neo4j_env("pending_review_annotation/", crisis_bucket)
    return list_stage_articles(
        crisis_bucket,
        "pending_review_annotation",
        "job:dvb-annotator-job",
        preferred_hash=folder_hash,
    )


def get_pending_annotation_hash_status(crisis_bucket: str) -> Dict[str, str]:
    """Compare latest pending_review_annotation hash in GCS vs system DB FolderHash."""
    client = storage.Client()
    bucket = client.bucket(crisis_bucket)

    gcs_latest_hash = resolve_latest_hash(bucket, "pending_review_annotation")
    system_db_hash = query_latest_folder_hash_from_neo4j_env("pending_review_annotation/", crisis_bucket)

    if gcs_latest_hash and system_db_hash:
        status = "match" if gcs_latest_hash == system_db_hash else "mismatch"
    elif gcs_latest_hash and not system_db_hash:
        status = "missing_system_db"
    elif not gcs_latest_hash and system_db_hash:
        status = "missing_gcs"
    else:
        status = "empty"

    return {
        "status": status,
        "gcs_latest_hash": gcs_latest_hash or "-",
        "system_db_hash": system_db_hash or "-",
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
        pending_annotation_hash_status = (
            get_pending_annotation_hash_status(crisis_bucket) if crisis_bucket else {
                "status": "empty",
                "gcs_latest_hash": "-",
                "system_db_hash": "-",
            }
        )
    except Exception as e:
        pending_articles = []
        pending_annotation_articles = []
        pending_annotation_hash_status = {
            "status": "error",
            "gcs_latest_hash": "-",
            "system_db_hash": "-",
        }
        logger.error(f"Error listing pending articles: {e}")

    latest_pending_annotation_hash = pending_annotation_hash_status["gcs_latest_hash"]
    if latest_pending_annotation_hash and latest_pending_annotation_hash != "-":
        pending_annotation_articles = [
            article for article in pending_annotation_articles if article.get("hash") == latest_pending_annotation_hash
        ]

    hash_status = pending_annotation_hash_status.get("status", "empty")
    if hash_status == "match":
        hash_status_text = "System DB hash matches latest GCS pending annotation hash"
        hash_status_class = "ok"
    elif hash_status == "mismatch":
        hash_status_text = "System DB hash does NOT match latest GCS pending annotation hash"
        hash_status_class = "warn"
    elif hash_status == "missing_system_db":
        hash_status_text = "System DB hash missing for pending annotation folder"
        hash_status_class = "warn"
    elif hash_status == "missing_gcs":
        hash_status_text = "No pending annotation data in GCS, but system DB has a hash"
        hash_status_class = "warn"
    elif hash_status == "error":
        hash_status_text = "Unable to verify pending annotation hash consistency"
        hash_status_class = "warn"
    else:
        hash_status_text = "No pending annotation hashes available yet"
        hash_status_class = "muted"

    return render_template(
        "admin.html",
        pending_articles_count=len(pending_articles),
        pending_annotation_articles_count=len(pending_annotation_articles),
        pending_grouped=group_articles_by_date(pending_articles),
        annotation_grouped=group_articles_by_date(pending_annotation_articles),
        hash_status_class=hash_status_class,
        hash_status_text=hash_status_text,
        pending_annotation_hash_status=pending_annotation_hash_status,
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
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review/{hash}/{date}/{filename} -> crisis_articles/{hash}/{date}/{filename}
        destination_name = blob_name.replace('pending_review/', 'crisis_articles/', 1)
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()
        trigger_cloud_run_job("dvb-annotator-job")

        logger.info(f"✅ Confirmed: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Confirm failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/admin/reject", methods=["POST"])
def admin_reject():
    """Delete a pending article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Reject failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/admin/confirm_annotation", methods=["POST"])
def admin_confirm_annotation():
    """Move a pending annotated article to annotated_articles/ and trigger extractor job."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        source_blob = bucket.blob(blob_name)

        # pending_review_annotation/{hash}/{date}/{filename} -> annotated_articles/{hash}/{date}/{filename}
        destination_name = blob_name.replace('pending_review_annotation/', 'annotated_articles/', 1)
        bucket.copy_blob(source_blob, bucket, destination_name)
        source_blob.delete()
        trigger_cloud_run_job("dvb-extractor-job")

        logger.info(f"✅ Confirmed annotation: {blob_name} -> {destination_name}")
    except Exception as e:
        logger.error(f"❌ Annotation confirm failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/admin/reject_annotation", methods=["POST"])
def admin_reject_annotation():
    """Delete a pending annotated article (reject it)."""
    blob_name = request.form.get('blob_name', '')
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    if not blob_name or not crisis_bucket:
        return "Missing parameters", 400

    try:
        client = storage.Client()
        bucket = client.bucket(crisis_bucket)
        bucket.blob(blob_name).delete()
        logger.info(f"🗑️  Rejected annotation: {blob_name}")
    except Exception as e:
        logger.error(f"❌ Annotation reject failed: {e}")
        return f"Error: {e}", 500

    return redirect('/admin')


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
