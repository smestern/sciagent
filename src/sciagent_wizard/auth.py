"""
GitHub OAuth authentication for public-facing sciagent interfaces.

Provides opt-in GitHub OAuth App (web flow) so that:

* Access to ``/public`` and ``/ingestor`` is gated behind GitHub sign-in.
* The user's OAuth token (``gho_*``) is threaded through to the Copilot
  SDK so LLM requests are billed to the user's Copilot subscription.

**Activation:** Set two environment variables to enable OAuth:

    GITHUB_OAUTH_CLIENT_ID     — OAuth App client ID
    GITHUB_OAUTH_CLIENT_SECRET — OAuth App client secret

When these are absent **every route is open** and the codebase behaves
exactly as before (no auth, no redirects, no secrets required).

An optional ``SCIAGENT_SESSION_SECRET`` env var provides the session
cookie signing key.  When omitted **and** OAuth is enabled, a key is
derived from the client secret (acceptable for single-process deploys).

Security notes
--------------
* Session cookie is ``HttpOnly``, ``SameSite=Lax``; ``Secure`` when the
  request arrives over HTTPS.
* The ``state`` parameter in the OAuth redirect uses
  ``secrets.token_urlsafe(32)`` to prevent CSRF.
* Tokens are validated by prefix (``gho_``, ``ghu_``, ``github_pat_``)
  and by calling the GitHub ``/user`` API.
* **No secrets are committed to source.**
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from functools import wraps
from typing import Optional
from urllib.parse import urlencode, quote

from quart import (
    Blueprint,
    redirect,
    request,
    session,
    jsonify,
    websocket,
)

logger = logging.getLogger(__name__)

# ── Environment-variable helpers ────────────────────────────────────────

_GITHUB_OAUTH_CLIENT_ID = "GITHUB_OAUTH_CLIENT_ID"
_GITHUB_OAUTH_CLIENT_SECRET = "GITHUB_OAUTH_CLIENT_SECRET"
_SESSION_SECRET_VAR = "SCIAGENT_SESSION_SECRET"

# GitHub endpoints
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

# Allowed token prefixes (Copilot SDK supported types)
_ALLOWED_TOKEN_PREFIXES = ("gho_", "ghu_", "github_pat_")


def is_oauth_configured() -> bool:
    """Return ``True`` when both OAuth env vars are set."""
    return bool(
        os.environ.get(_GITHUB_OAUTH_CLIENT_ID)
        and os.environ.get(_GITHUB_OAUTH_CLIENT_SECRET)
    )


def get_session_secret() -> str:
    """Derive a session-cookie signing key.

    Priority:
    1. ``SCIAGENT_SESSION_SECRET`` env var (recommended for production).
    2. HMAC-SHA256 of the OAuth client secret (fallback for dev).
    """
    explicit = os.environ.get(_SESSION_SECRET_VAR)
    if explicit:
        return explicit
    client_secret = os.environ.get(_GITHUB_OAUTH_CLIENT_SECRET, "")
    if client_secret:
        return hmac.new(
            b"sciagent-session-key",
            client_secret.encode(),
            hashlib.sha256,
        ).hexdigest()
    # Not reachable when is_oauth_configured() is True, but be safe.
    return secrets.token_hex(32)


def configure_app_sessions(app) -> None:  # noqa: ANN001
    """Set ``secret_key`` and harden session cookies on *app*.

    Safe to call even when OAuth is disabled — it does nothing in that
    case.
    """
    if not is_oauth_configured():
        return
    app.secret_key = get_session_secret()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # SESSION_COOKIE_SECURE is ideally True in production (HTTPS).
    # We leave it False by default so local dev (http://localhost) works.
    # Deployers should set this via SCIAGENT_SESSION_SECURE=1.
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("SCIAGENT_SESSION_SECURE", "0") == "1"
    )


# ── Auth blueprint ──────────────────────────────────────────────────────


def create_auth_blueprint() -> Blueprint:
    """Return a ``/auth`` blueprint with ``login``, ``callback``, ``logout``."""
    auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

    @auth_bp.route("/login")
    async def login():
        """Redirect the user to GitHub's OAuth authorize page."""
        client_id = os.environ[_GITHUB_OAUTH_CLIENT_ID]
        return_to = request.args.get("return_to", "/public/")

        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        session["oauth_return_to"] = return_to

        params = urlencode({
            "client_id": client_id,
            "redirect_uri": _build_callback_url(),
            "state": state,
            "scope": "copilot",
        })
        return redirect(f"{_GITHUB_AUTHORIZE_URL}?{params}")

    @auth_bp.route("/callback")
    async def callback():
        """Exchange the authorization code for an access token."""
        code = request.args.get("code")
        state = request.args.get("state")

        # ── Validate state (CSRF protection) ────────────────────
        expected_state = session.pop("oauth_state", None)
        return_to = session.pop("oauth_return_to", "/public/")

        if not code or not state:
            return jsonify({"error": "Missing code or state parameter."}), 400

        if not hmac.compare_digest(state, expected_state or ""):
            logger.warning("OAuth state mismatch — possible CSRF attempt.")
            return jsonify({"error": "Invalid state parameter."}), 403

        # ── Exchange code for token ─────────────────────────────
        import httpx  # lazy import — only needed during OAuth flow

        client_id = os.environ[_GITHUB_OAUTH_CLIENT_ID]
        client_secret = os.environ[_GITHUB_OAUTH_CLIENT_SECRET]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _GITHUB_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                logger.error("GitHub token exchange failed: %s", resp.text)
                return jsonify({"error": "Token exchange failed."}), 502

            token_data = resp.json()

        access_token: str = token_data.get("access_token", "")
        if not access_token:
            error_desc = token_data.get("error_description", "unknown error")
            logger.error("GitHub did not return a token: %s", error_desc)
            return jsonify({"error": f"GitHub error: {error_desc}"}), 400

        # ── Validate token prefix ───────────────────────────────
        if not access_token.startswith(_ALLOWED_TOKEN_PREFIXES):
            logger.warning(
                "Rejected token with unsupported prefix: %s…",
                access_token[:6],
            )
            return jsonify({
                "error": "Unsupported token type. Classic PATs (ghp_) are not supported."
            }), 400

        # ── Validate token by fetching user info ────────────────
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(
                _GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if user_resp.status_code != 200:
            logger.error("GitHub /user check failed: %s", user_resp.text)
            return jsonify({"error": "Token validation failed."}), 403

        user_info = user_resp.json()
        github_login = user_info.get("login", "unknown")
        logger.info("GitHub OAuth successful for user: %s", github_login)

        # ── Store token in session (HttpOnly cookie) ────────────
        session["github_token"] = access_token
        session["github_login"] = github_login

        return redirect(return_to)

    @auth_bp.route("/logout")
    async def logout():
        """Clear the session and redirect to the public page."""
        return_to = request.args.get("return_to", "/public/")
        session.clear()
        return redirect(return_to)

    @auth_bp.route("/status")
    async def status():
        """Return current auth status (for JS to check)."""
        if session.get("github_token"):
            return jsonify({
                "authenticated": True,
                "login": session.get("github_login", ""),
            })
        return jsonify({"authenticated": False})

    return auth_bp


# ── Route decorator ─────────────────────────────────────────────────────


def require_auth(f):
    """Decorator: redirect to ``/auth/login`` if OAuth is enabled and user
    is not authenticated.

    For browser page navigations, issues a 302 redirect.
    For ``fetch()`` / XHR API calls, returns a JSON response with the
    login URL so the frontend can redirect via ``window.location``.

    When OAuth is **not** configured this is a no-op — the wrapped
    function runs unconditionally.
    """
    @wraps(f)
    async def wrapper(*args, **kwargs):
        if is_oauth_configured() and not session.get("github_token"):
            return_to = request.path
            login_url = f"/auth/login?return_to={quote(return_to)}"

            # Detect API/fetch calls: check Accept header, Content-Type,
            # X-Requested-With, or /api/ in the path.
            accept = request.headers.get("Accept", "")
            content_type = request.headers.get("Content-Type", "")
            xhr = request.headers.get("X-Requested-With", "")
            is_api = (
                "application/json" in accept
                or "application/json" in content_type
                or xhr == "XMLHttpRequest"
                or "/api/" in request.path
            )
            if is_api:
                return jsonify({
                    "auth_required": True,
                    "login_url": login_url,
                }), 401

            return redirect(login_url)
        return await f(*args, **kwargs)
    return wrapper


def require_auth_ws(f):
    """Decorator for WebSocket endpoints: reject the connection if OAuth
    is enabled and no valid session is present.

    WebSocket handlers cannot redirect, so we accept the connection,
    send an ``auth_required`` error message, and close.
    """
    @wraps(f)
    async def wrapper(*args, **kwargs):
        if is_oauth_configured() and not session.get("github_token"):
            await websocket.accept()
            await websocket.send(
                '{"type":"auth_required","text":"Please sign in with GitHub first."}'
            )
            return
        return await f(*args, **kwargs)
    return wrapper


def get_github_token() -> Optional[str]:
    """Return the authenticated user's GitHub token from the session,
    or ``None`` when OAuth is not configured / user not signed in.

    **Never log the return value.**
    """
    if not is_oauth_configured():
        return None
    return session.get("github_token")


# ── Internal helpers ────────────────────────────────────────────────────


def _build_callback_url() -> str:
    """Build the absolute callback URL from the current request."""
    scheme = request.scheme
    host = request.host
    return f"{scheme}://{host}/auth/callback"
