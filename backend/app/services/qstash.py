"""
QStash service — publish background jobs and verify incoming webhook signatures.

QStash (Upstash) is used as the async job queue to trigger stock ingestion in
the background, decoupling the user-facing /meta endpoint from the slow yfinance
and Groq network calls.

Flow:
  1. User hits GET /meta for a new symbol
  2. /meta inserts a stub record (DISCOVERING) and fires a QStash message
     pointing at POST /api/v1/internal/ingest-background
  3. QStash calls our internal endpoint within seconds (retries on failure)
  4. Internal endpoint verifies the QStash signature, then runs the full pipeline:
     quick_discover → step1 history → step2 analytics → step3 briefing
  5. Frontend polls /status every 1.5s — sections appear as each stage completes
"""
import json
import logging
import time
import hmac
import hashlib
import base64
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("app.services.qstash")

# ── QStash REST API ───────────────────────────────────────────────────────────
# Base URL is region-specific (e.g. https://qstash-eu-central-1.upstash.io) —
# read from settings rather than hardcoding the default global endpoint.


async def publish_ingestion_job(symbol: str) -> bool:
    """
    Publish a background ingestion job to QStash.

    QStash will call POST /api/v1/internal/ingest-background with {"symbol": symbol}.
    Returns True if published successfully, False otherwise.

    If QStash is not configured (no QSTASH_TOKEN), returns False so the caller
    can fall back to the legacy synchronous quick_discover path.
    """
    if not settings.QSTASH_TOKEN:
        logger.warning("[QStash] QSTASH_TOKEN not set — falling back to sync discover")
        return False

    target_url = f"{settings.BACKEND_URL}/api/v1/internal/ingest-background"
    publish_base = (settings.QSTASH_URL or "https://qstash.upstash.io").rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{publish_base}/v2/publish/{target_url}",
                headers={
                    "Authorization": f"Bearer {settings.QSTASH_TOKEN}",
                    "Content-Type": "application/json",
                    "Upstash-Retries": "2",           # retry up to 2 times on failure
                    "Upstash-Timeout": "280s",         # allow up to 280s (within our 300s Fluid maxDuration — see backend/vercel.json)
                    "Upstash-Delay": "0s",             # fire immediately
                },
                content=json.dumps({"symbol": symbol}),
            )

        if resp.status_code in (200, 201, 202):
            msg_id = resp.json().get("messageId", "?")
            logger.info(f"[QStash] Published ingestion job for {symbol} → messageId={msg_id}")
            return True
        else:
            logger.error(f"[QStash] Publish failed for {symbol}: HTTP {resp.status_code} — {resp.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"[QStash] Publish exception for {symbol}: {e}")
        return False


async def publish_fund_ingestion_job(scheme_code: int, mode: str = "full") -> bool:
    """
    Publish a background fund-ingestion job to QStash.

    QStash will call POST /api/v1/internal/ingest-fund-background with
    {"scheme_code": scheme_code, "mode": mode}.

    mode:
      "full"            — full NAV ingest + rating recompute + AI summary
                           (mirrors the old funds.py `_ingest_and_brief`)
      "ai_summary_only" — regenerate just the AI summary for an already-ingested fund

    Returns True if published successfully, False otherwise. If QStash is not
    configured (no QSTASH_TOKEN), returns False so the caller can fall back to
    the legacy FastAPI BackgroundTasks path.
    """
    if not settings.QSTASH_TOKEN:
        logger.warning("[QStash] QSTASH_TOKEN not set — falling back to BackgroundTasks for fund ingestion")
        return False

    target_url = f"{settings.BACKEND_URL}/api/v1/internal/ingest-fund-background"
    publish_base = (settings.QSTASH_URL or "https://qstash.upstash.io").rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{publish_base}/v2/publish/{target_url}",
                headers={
                    "Authorization": f"Bearer {settings.QSTASH_TOKEN}",
                    "Content-Type": "application/json",
                    "Upstash-Retries": "2",           # retry up to 2 times on failure
                    "Upstash-Timeout": "280s",         # allow up to 280s (within our 300s Fluid maxDuration)
                    "Upstash-Delay": "0s",             # fire immediately
                },
                content=json.dumps({"scheme_code": scheme_code, "mode": mode}),
            )

        if resp.status_code in (200, 201, 202):
            msg_id = resp.json().get("messageId", "?")
            logger.info(f"[QStash] Published fund ingestion job for {scheme_code} (mode={mode}) → messageId={msg_id}")
            return True
        else:
            logger.error(f"[QStash] Fund publish failed for {scheme_code}: HTTP {resp.status_code} — {resp.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"[QStash] Fund publish exception for {scheme_code}: {e}")
        return False


# ── Signature Verification ────────────────────────────────────────────────────

def _verify_jwt(token: str, signing_key: str, url: str, body: bytes) -> bool:
    """
    Verify a QStash JWT signature.

    QStash signs its webhooks with a JWT using HMAC-SHA256.
    The JWT payload includes:
      - iss: "Upstash"
      - sub: the destination URL
      - nbf: not before (unix timestamp)
      - exp: expiry (unix timestamp)
      - body: SHA-256 hash of the request body (base64url encoded, no padding)
    """
    try:
        # Split JWT into header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            return False

        header_b64, payload_b64, sig_b64 = parts

        # Decode payload (base64url, no padding)
        def _b64decode(s: str) -> bytes:
            # Add padding
            s += "=" * (-len(s) % 4)
            return base64.urlsafe_b64decode(s)

        payload_bytes = _b64decode(payload_b64)
        payload = json.loads(payload_bytes)

        # 1. Check expiry
        exp = payload.get("exp", 0)
        if exp and time.time() > exp:
            logger.warning("[QStash] JWT expired")
            return False

        # 2. Check issuer
        if payload.get("iss") != "Upstash":
            logger.warning(f"[QStash] JWT issuer mismatch: {payload.get('iss')}")
            return False

        # 3. Check subject (URL) — compare without trailing slashes
        sub = payload.get("sub", "").rstrip("/")
        expected_url = url.rstrip("/")
        if sub and sub != expected_url:
            logger.warning(f"[QStash] JWT sub mismatch: {sub} != {expected_url}")
            # Don't hard-fail on URL mismatch in case of proxy/load balancer differences
            # Log but continue to body hash check

        # 4. Verify body hash — QStash encodes this claim as base64url WITH
        # padding (unlike the JWT segments themselves), so compare against
        # both padded and unpadded forms rather than assuming one.
        body_hash_claim = payload.get("body")
        if body_hash_claim and body:
            actual_hash = hashlib.sha256(body).digest()
            actual_b64_padded = base64.urlsafe_b64encode(actual_hash).decode()
            actual_b64_unpadded = actual_b64_padded.rstrip("=")
            if body_hash_claim not in (actual_b64_padded, actual_b64_unpadded):
                logger.warning("[QStash] JWT body hash mismatch")
                return False

        # 5. Verify HMAC-SHA256 signature
        signing_input = f"{header_b64}.{payload_b64}".encode()
        key = signing_key.encode()
        expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

        sig_ok = hmac.compare_digest(expected_b64, sig_b64)
        if not sig_ok:
            logger.warning("[QStash] JWT HMAC signature invalid")
        return sig_ok

    except Exception as e:
        logger.error(f"[QStash] Signature verification error: {e}")
        return False


def verify_qstash_signature(
    signature: Optional[str],
    body: bytes,
    url: str,
) -> bool:
    """
    Verify QStash webhook signature using current and next signing keys.

    Tries current signing key first, then next signing key (for key rotation).
    Returns True if the signature is valid, False otherwise.

    If neither signing key is configured, returns False (fail closed — requires
    explicit configuration to allow requests).
    """
    if not signature:
        logger.warning("[QStash] Missing Upstash-Signature header")
        return False

    current_key = settings.QSTASH_CURRENT_SIGNING_KEY
    next_key = settings.QSTASH_NEXT_SIGNING_KEY

    if not current_key and not next_key:
        logger.error("[QStash] No signing keys configured — cannot verify signature")
        return False

    # Try current key first
    if current_key and _verify_jwt(signature, current_key, url, body):
        return True

    # Try next key (for key rotation window)
    if next_key and _verify_jwt(signature, next_key, url, body):
        logger.info("[QStash] Verified with next signing key (key rotation in progress)")
        return True

    logger.warning("[QStash] Signature verification failed with both keys")
    return False


def is_qstash_configured() -> bool:
    """Check if QStash is fully configured for use."""
    return bool(
        settings.QSTASH_TOKEN
        and settings.QSTASH_CURRENT_SIGNING_KEY
        and settings.BACKEND_URL
    )
