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
import time
from datetime import timedelta
from functools import wraps
from typing import Optional
from urllib.parse import urlencode, quote

from quart import (
    Blueprint,
    current_app,
    redirect,
    render_template_string,
    request,
    session,
    jsonify,
    websocket,
)

logger = logging.getLogger(__name__)

# ── Invite-code helpers ─────────────────────────────────────────────────

_INVITE_CODE_VAR = "SCIAGENT_INVITE_CODE"


def _is_invite_authenticated() -> bool:
    """Return True if the current session was authenticated via invite code."""
    invite_code = os.environ.get(_INVITE_CODE_VAR)
    if not invite_code:
        return False
    return session.get("invite_authenticated", False)

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

# Session and token validation timing
_SESSION_LIFETIME_HOURS = 1  # Sessions expire after 1 hour
_TOKEN_REVALIDATION_MINUTES = 15  # Re-validate token every 15 minutes


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

    Activates when OAuth **or** invite-code auth is configured.
    """
    if not is_oauth_configured() and not os.environ.get(_INVITE_CODE_VAR):
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
    # Sessions expire after configured lifetime (requires session.permanent = True)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=_SESSION_LIFETIME_HOURS)


# ── Auth blueprint ──────────────────────────────────────────────────────


def create_auth_blueprint() -> Blueprint:
    """Return a ``/auth`` blueprint with ``login``, ``callback``, ``logout``."""
    auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

    @auth_bp.route("/login")
    async def login():
        """Show an informational landing page before GitHub OAuth."""
        return_to = request.args.get("return_to", "/public/")
        invite_available = bool(os.environ.get(_INVITE_CODE_VAR))
        return await render_template_string(
            _LOGIN_PAGE_HTML,
            return_to=return_to,
            invite_available=invite_available,
        )

    @auth_bp.route("/login/github")
    async def login_github():
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
        session.permanent = True  # Enable PERMANENT_SESSION_LIFETIME
        session["github_token"] = access_token
        session["github_login"] = github_login
        session["token_validated_at"] = time.time()  # Track last validation

        return redirect(return_to)

    @auth_bp.route("/logout")
    async def logout():
        """Clear the session and redirect to the public page."""
        return_to = request.args.get("return_to", "/public/")
        session.clear()
        resp = redirect(return_to)
        # Explicitly delete the session cookie so the browser stops
        # sending the old signed session on subsequent requests.
        cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
        resp.delete_cookie(
            cookie_name,
            path=current_app.config.get("SESSION_COOKIE_PATH", "/"),
        )
        return resp

    @auth_bp.route("/status")
    async def status():
        """Return current auth status (for JS to check)."""
        if session.get("github_token"):
            return jsonify({
                "authenticated": True,
                "login": session.get("github_login", ""),
            })
        if _is_invite_authenticated():
            return jsonify({
                "authenticated": True,
                "login": "guest (invite)",
            })
        return jsonify({"authenticated": False})

    # ── Invite-code routes ────────────────────────────────────────

    @auth_bp.route("/invite")
    async def invite_form():
        """Show a simple invite-code entry form."""
        invite_code = os.environ.get(_INVITE_CODE_VAR)
        if not invite_code:
            return jsonify({"error": "Invite codes are not enabled."}), 404

        # If already authenticated via invite, redirect
        if _is_invite_authenticated():
            return redirect(request.args.get("return_to", "/public/"))

        return await render_template_string(
            _INVITE_PAGE_HTML,
            return_to=request.args.get("return_to", "/public/"),
            oauth_available=is_oauth_configured(),
        )

    @auth_bp.route("/invite/verify", methods=["POST"])
    async def invite_verify():
        """Verify the submitted invite code."""
        invite_code = os.environ.get(_INVITE_CODE_VAR)
        if not invite_code:
            return jsonify({"error": "Invite codes are not enabled."}), 404

        form = await request.form
        submitted = form.get("code", "").strip()
        return_to = form.get("return_to", "/public/")

        if submitted and hmac.compare_digest(submitted, invite_code):
            session["invite_authenticated"] = True
            logger.info("Invite-code authentication successful")
            return redirect(return_to)

        logger.warning("Invalid invite code attempt")
        return await render_template_string(
            _INVITE_PAGE_HTML,
            return_to=return_to,
            error="Invalid invite code. Please try again.",
        )

    return auth_bp


# ── Token validation helper ─────────────────────────────────────────────


async def _validate_token_if_needed() -> bool:
    """Re-validate the GitHub token if it hasn't been checked recently.

    Returns True if the token is valid, False if invalid/expired.
    Automatically clears the session if the token is no longer valid.
    """
    token = session.get("github_token")
    if not token:
        return False

    last_validated = session.get("token_validated_at", 0)
    now = time.time()

    # Skip validation if checked within the revalidation window
    if now - last_validated < (_TOKEN_REVALIDATION_MINUTES * 60):
        return True

    # Re-validate by calling GitHub /user API
    import httpx  # lazy import

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if resp.status_code == 200:
            session["token_validated_at"] = now
            logger.debug("Token re-validated for user: %s", session.get("github_login"))
            return True

        # Token is invalid or expired
        logger.warning(
            "Token validation failed for user %s (HTTP %d)",
            session.get("github_login"),
            resp.status_code,
        )
    except Exception as e:
        logger.warning("Token validation request failed: %s", e)
        # On network errors, allow the request (don't lock out users)
        # but don't update the validation timestamp
        return True

    # Clear invalid session
    session.clear()
    return False


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
        # Allow invite-code authenticated sessions through
        if _is_invite_authenticated():
            return await f(*args, **kwargs)

        if is_oauth_configured():
            # Check if user has a token and if it's still valid
            has_valid_token = session.get("github_token") and await _validate_token_if_needed()
            if not has_valid_token:
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
        # Allow invite-code authenticated sessions through
        if _is_invite_authenticated():
            return await f(*args, **kwargs)

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
    or the service token for invite-code users, or ``None``.

    **Never log the return value.**
    """
    if is_oauth_configured():
        token = session.get("github_token")
        if token:
            return token
    # Fallback: invite-code users get the service token
    if _is_invite_authenticated():
        return os.environ.get("SCIAGENT_SERVICE_TOKEN")
    return None


# ── Internal helpers ────────────────────────────────────────────────────


def _build_callback_url() -> str:
    """Build the absolute callback URL from the current request.

    Respects X-Forwarded-Proto header for SSL-terminating proxies.
    """
    # Check for forwarded scheme from reverse proxy (Railway, Heroku, nginx, etc.)
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.host
    return f"{scheme}://{host}/auth/callback"


# ── Invite page HTML ───────────────────────────────────────────────────

_INVITE_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SciAgent — Enter Invite Code</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117; color: #c9d1d9;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh;
  }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 2.5rem; max-width: 420px; width: 100%; text-align: center;
  }
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #f0f6fc; }
  p  { font-size: 0.9rem; margin-bottom: 1.5rem; color: #8b949e; }
  .error { color: #f85149; font-size: 0.85rem; margin-bottom: 1rem; }
  input[type="text"] {
    width: 100%; padding: 0.75rem 1rem; font-size: 1rem;
    background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    color: #f0f6fc; margin-bottom: 1rem; text-align: center;
    letter-spacing: 0.1em;
  }
  input:focus { outline: none; border-color: #58a6ff; }
  button {
    width: 100%; padding: 0.75rem; font-size: 1rem; font-weight: 600;
    background: #238636; color: #fff; border: none; border-radius: 8px;
    cursor: pointer; transition: background 0.2s;
  }
  button:hover { background: #2ea043; }
  .divider { margin: 1.5rem 0; color: #484f58; font-size: 0.8rem; }
  a { color: #58a6ff; text-decoration: none; font-size: 0.9rem; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <h1>SciAgent Builder</h1>
  <p>Enter your invite code to continue</p>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST" action="/auth/invite/verify">
    <input type="hidden" name="return_to" value="{{ return_to }}">
    <input type="text" name="code" placeholder="Enter invite code" autocomplete="off" autofocus required>
    <button type="submit">Continue</button>
  </form>
  {% if oauth_available %}
  <div class="divider">— or —</div>
  <a href="/auth/login/github?return_to={{ return_to }}">Sign in with GitHub</a>
  {% endif %}
</div>
</body>
</html>
"""

# ── Login landing page HTML ─────────────────────────────────────────────

_LOGIN_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SciAgent — Sign In</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117; color: #c9d1d9;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh;
  }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 2.5rem; max-width: 480px; width: 100%; text-align: center;
  }
  h1 { font-size: 1.6rem; margin-bottom: 0.3rem; color: #f0f6fc; }
  .subtitle { font-size: 0.95rem; color: #8b949e; margin-bottom: 2rem; }

  .info-section {
    text-align: left; background: #0d1117; border: 1px solid #30363d;
    border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.75rem;
  }
  .info-section h3 {
    font-size: 0.9rem; color: #f0f6fc; margin-bottom: 0.35rem;
    display: flex; align-items: center; gap: 0.5rem;
  }
  .info-section p {
    font-size: 0.85rem; color: #8b949e; line-height: 1.5;
  }
  .info-section a { color: #58a6ff; text-decoration: none; }
  .info-section a:hover { text-decoration: underline; }

  .github-btn {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 0.6rem; width: 100%; padding: 0.8rem; font-size: 1rem;
    font-weight: 600; background: #238636; color: #fff; border: none;
    border-radius: 8px; cursor: pointer; transition: background 0.2s;
    text-decoration: none; margin-top: 1.5rem;
  }
  .github-btn:hover { background: #2ea043; }
  .github-btn svg { fill: #fff; flex-shrink: 0; }

  .divider { margin: 1.25rem 0; color: #484f58; font-size: 0.8rem; }
  .alt-link { color: #58a6ff; text-decoration: none; font-size: 0.9rem; }
  .alt-link:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
  <h1>&#129497; SciAgent</h1>
  <p class="subtitle">Sign in to start building your scientific agent</p>

  <div class="info-section">
    <h3>&#128273; Why sign in?</h3>
    <p>
      SciAgent uses <strong>your GitHub Copilot subscription</strong> to power
      AI requests. Signing in with GitHub lets us route LLM calls through
      your existing plan &mdash; no extra API keys or charges from us.
    </p>
  </div>

  <div class="info-section">
    <h3>&#128274; Your privacy</h3>
    <p>
      We <strong>do not retrieve, store, or share</strong> any of your personal
      data, code, or conversation history. Your GitHub token is held only in a
      secure, short-lived session cookie and is never persisted.
    </p>
  </div>

  <div class="info-section">
    <h3>&#127891; PhD student?</h3>
    <p>
      If you&rsquo;re a PhD student without a Copilot subscription, reach out
      for <strong>free access</strong>. Email
      <a href="mailto:smestern@uwo.ca">smestern@uwo.ca</a>
      with your university email and we&rsquo;ll get you set up.
    </p>
  </div>

  <a class="github-btn" href="/auth/login/github?return_to={{ return_to }}">
    <svg height="20" width="20" viewBox="0 0 16 16">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
        0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
        -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
        .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
        -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.64 7.64 0 0 1 2-.27c.68 0
        1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82
        1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
        1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
    </svg>
    Sign in with GitHub
  </a>

  {% if invite_available %}
  <div class="divider">&mdash; or &mdash;</div>
  <a class="alt-link" href="/auth/invite?return_to={{ return_to }}">Have an invite code?</a>
  {% endif %}
</div>
</body>
</html>
"""
