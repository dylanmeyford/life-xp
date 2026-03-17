"""Generic token refresh for API sensors.

Supports multiple auth strategies: OAuth 2.0 refresh_token, JWT client
credentials, and custom token endpoints.  Called proactively by the
scheduler (before expiry) and reactively by APISensor on 401 responses.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx

from life_xp.database import fetch_one, update

logger = logging.getLogger(__name__)

REFRESHABLE_AUTH_TYPES = {"oauth", "jwt", "custom"}


def token_needs_refresh(config: dict, buffer_seconds: int = 300) -> bool:
    """Return True if the token is near expiry (within *buffer_seconds*)."""
    expires_at = config.get("token_expires_at")
    if expires_at is None:
        return False
    return time.time() + buffer_seconds >= float(expires_at)


def parse_token_expiry(response_json: dict, config: dict) -> float | None:
    """Extract a token_expires_at epoch from a token endpoint response.

    Checks ``expires_in`` (seconds from now) first, then falls back to the
    ``exp`` claim (epoch timestamp, common in JWT responses).
    """
    expires_in = response_json.get("expires_in")
    if expires_in is not None:
        return time.time() + int(expires_in)

    exp = response_json.get("exp")
    if exp is not None:
        return float(exp)

    return None


async def refresh_token_for_sensor(db, sensor_id: int) -> bool:
    """Refresh the access token for a sensor.  Returns True on success."""
    row = await fetch_one(db, "SELECT * FROM sensor_configs WHERE id = ?", (sensor_id,))
    if not row:
        return False

    config: dict = json.loads(row["config"])
    auth_type = config.get("auth_type", "")

    if auth_type not in REFRESHABLE_AUTH_TYPES:
        return False

    token_url = config.get("token_url")
    if not token_url:
        logger.warning("Sensor %d has auth_type=%s but no token_url", sensor_id, auth_type)
        return False

    try:
        if auth_type == "oauth":
            return await _refresh_oauth(db, sensor_id, config, token_url)
        elif auth_type == "jwt":
            return await _refresh_jwt(db, sensor_id, config, token_url)
        elif auth_type == "custom":
            return await _refresh_custom(db, sensor_id, config, token_url)
    except Exception as exc:
        logger.error("Token refresh failed for sensor %d (%s): %s", sensor_id, auth_type, exc)
        return False

    return False


# ── Strategy implementations ──────────────────────────────────────────


async def _refresh_oauth(db, sensor_id: int, config: dict, token_url: str) -> bool:
    """OAuth 2.0 refresh_token grant."""
    refresh_token = config.get("refresh_token")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")

    if not refresh_token or not client_id or not client_secret:
        logger.warning("Sensor %d missing OAuth credentials for refresh", sensor_id)
        return False

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    if resp.status_code != 200:
        logger.error("OAuth refresh for sensor %d returned %d: %s", sensor_id, resp.status_code, resp.text[:200])
        return False

    tokens = resp.json()
    return await _apply_token_response(db, sensor_id, config, tokens, rotate_refresh=True)


async def _refresh_jwt(db, sensor_id: int, config: dict, token_url: str) -> bool:
    """JWT / client_credentials style refresh."""
    body = config.get("refresh_body")
    if body is None:
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        body = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(token_url, json=body)

    if resp.status_code != 200:
        logger.error("JWT refresh for sensor %d returned %d: %s", sensor_id, resp.status_code, resp.text[:200])
        return False

    tokens = resp.json()
    return await _apply_token_response(db, sensor_id, config, tokens, rotate_refresh=False)


async def _refresh_custom(db, sensor_id: int, config: dict, token_url: str) -> bool:
    """Custom token endpoint with configurable body."""
    body = config.get("refresh_body", {})

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(token_url, json=body)

    if resp.status_code != 200:
        logger.error("Custom refresh for sensor %d returned %d: %s", sensor_id, resp.status_code, resp.text[:200])
        return False

    tokens = resp.json()
    return await _apply_token_response(db, sensor_id, config, tokens, rotate_refresh=False)


# ── Shared helpers ────────────────────────────────────────────────────


async def _apply_token_response(
    db,
    sensor_id: int,
    config: dict,
    tokens: dict,
    *,
    rotate_refresh: bool,
) -> bool:
    """Apply a token endpoint response to the sensor config and persist it."""
    token_path = config.get("token_response_path", "access_token")
    new_token = _extract_path(tokens, token_path)

    if not new_token:
        logger.error("No token found at path '%s' in response for sensor %d", token_path, sensor_id)
        return False

    header_name = config.get("token_header_name", "Authorization")
    header_prefix = config.get("token_header_prefix", "Bearer ")

    new_config = {**config}
    headers = {**new_config.get("headers", {})}
    headers[header_name] = f"{header_prefix}{new_token}"
    new_config["headers"] = headers

    # Update refresh token if provider rotates it
    if rotate_refresh and tokens.get("refresh_token"):
        new_config["refresh_token"] = tokens["refresh_token"]

    # Update expiry
    expires_at = parse_token_expiry(tokens, config)
    if expires_at is not None:
        new_config["token_expires_at"] = expires_at

    await update(db, "sensor_configs", sensor_id, {"config": json.dumps(new_config)})
    logger.info("Token refreshed for sensor %d (expires_at=%s)", sensor_id, expires_at)
    return True


def _extract_path(data: Any, path: str) -> Any:
    """Simple dot-path extraction (e.g. 'data.access_token')."""
    if not path:
        return data
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data
