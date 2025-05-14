import base64
import json
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv
from azure.core.pipeline.transport import RequestsTransport
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)
from azure.storage.queue import QueueClient

# ── .env 読み込み ───────────────────────────────
load_dotenv()

AZ_CONN_STR   = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZ_ACCOUNT    = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZ_CONTAINER  = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
QUEUE_NAME    = os.getenv("AZURE_QUEUE_NAME", "audio-processing")

# ── ロガー ─────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("storage")

# ── クライアント初期化（タイムアウト拡大） ───────
transport = RequestsTransport(connection_timeout=600, read_timeout=600)

blob_service_client = BlobServiceClient.from_connection_string(
    AZ_CONN_STR, transport=transport
)
container_client = blob_service_client.get_container_client(AZ_CONTAINER)
logger.info(f"Connected to Blob Storage: {AZ_ACCOUNT}/{AZ_CONTAINER}")

try:
    queue_client = QueueClient.from_connection_string(AZ_CONN_STR, QUEUE_NAME)
    logger.info(f"Connected to Queue Storage: {QUEUE_NAME}")
except Exception as e:
    logger.exception("Failed to connect to Azure Queue")
    raise

# ────────────────────────────────────────────────

def _normalize_blob_name(blob_name: str, *, force_audio_prefix: bool = False) -> str:
    if force_audio_prefix:
        if blob_name.startswith("audio/"):
            return blob_name
        if blob_name.startswith("word/") or blob_name.startswith("results/") or blob_name.startswith("settings/") or blob_name.startswith("processed/"):
            return blob_name  # ⛔ audio/word/... にならないよう除外
        return f"audio/{blob_name}"
    return blob_name  # ✅ False の場合はそのまま使用

def _extract_blob_name_from_url(blob_url: str) -> str:
    parsed = urlparse(blob_url)
    parts = parsed.path.lstrip("/").split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid blob URL: {blob_url}")
    return unquote(parts[1])

# ── Public API ─────────────────────────────────

def generate_blob_url(blob_name: str) -> str:
    return f"https://{AZ_ACCOUNT}.blob.core.windows.net/{AZ_CONTAINER}/{blob_name}"

def upload_to_blob(
    blob_name: str,
    file_stream,
    *,
    add_audio_prefix: bool = True,
    content_type: str = "application/octet-stream",
) -> str:
    blob_name = _normalize_blob_name(blob_name, force_audio_prefix=add_audio_prefix)
    blob_client = container_client.get_blob_client(blob_name)

    try:
        blob_client.upload_blob(
            file_stream,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
    except Exception:
        logger.exception(f"UPLOAD FAILED: {blob_name}")
        raise

    if not blob_client.exists():
        raise RuntimeError(f"Blob {blob_name} not found right after upload!")

    logger.info(f"Uploaded blob: {blob_name}")
    return generate_blob_url(blob_name)

def download_blob(blob_name_or_url: str, download_path: str):
    if blob_name_or_url.startswith("http"):
        blob_name = _extract_blob_name_from_url(blob_name_or_url)
    else:
        blob_name = blob_name_or_url

    blob_client = container_client.get_blob_client(blob_name)
    stream = blob_client.download_blob()

    with open(download_path, "wb") as fp:
        for chunk in stream.chunks():
            fp.write(chunk)

    logger.info(f"Downloaded blob {blob_name} → {download_path}")
    return download_path

def generate_upload_sas(blob_name: str, expiry_hours: int = 1) -> dict:
    blob_name = _normalize_blob_name(blob_name, force_audio_prefix=True)

    sas_token = generate_blob_sas(
        account_name=AZ_ACCOUNT,
        container_name=AZ_CONTAINER,
        blob_name=blob_name,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True, write=True, create=True),
        expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
    )
    base_url = generate_blob_url(blob_name)
    return {"uploadUrl": f"{base_url}?{sas_token}", "blobUrl": base_url}

def enqueue_processing(blob_url: str, template_blob_url: str, job_id: str) -> None:
    payload = json.dumps({
        "job_id": job_id,
        "blob_url": blob_url,
        "template_blob_url": template_blob_url
    })
    encoded_msg = base64.b64encode(payload.encode("utf-8")).decode("utf-8")
    queue_client.send_message(encoded_msg)
    logger.info(f"Enqueued job {job_id}")

# --- ワンショット util --------------------------------------

def upload_and_enqueue(local_path: str, blob_name: str, job_id: str) -> str:
    with open(local_path, "rb") as fp:
        blob_url = upload_to_blob(blob_name, fp)
    return blob_url
