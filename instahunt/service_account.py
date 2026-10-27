"""
Optional Instagram Service Account Manager for InstaHunt.
Manages secondary burner account credentials for deep graph chaining,
comment authenticity auditing, and session token caching.
Completely optional and decoupled from the core discovery pipeline.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import instaloader

from instahunt.config import BASE_DIR, DATA_DIR


class ServiceAccountManager:
    SESSION_FILE = DATA_DIR / "session_service_account"
    COOKIE_FILE = BASE_DIR / "cookies.json"

    def __init__(self):
        self.username = os.getenv("Insta_svc_acc_username") or os.getenv("INSTAGRAM_SERVICE_USER")
        self.password = os.getenv("Insta_svc_acc_pwd") or os.getenv("INSTAGRAM_SERVICE_PASS")
        self.loader = instaloader.Instaloader(
            dirname_pattern=str(DATA_DIR / "tmp_downloads"),
            save_metadata=False,
            compress_json=False,
        )
        self.is_authenticated = False
        self._try_restore_session()

    def _try_restore_session(self):
        """Attempt to restore a previously validated session from disk."""
        if self.SESSION_FILE.exists() and self.username:
            try:
                self.loader.load_session_from_file(self.username, filename=str(self.SESSION_FILE))
                self.is_authenticated = True
            except Exception:
                self.is_authenticated = False

    def get_status(self) -> Dict:
        """Return diagnostic status of the service account integration."""
        return {
            "has_credentials": bool(self.username and self.password),
            "username": self.username or "None",
            "is_authenticated": self.is_authenticated,
            "session_file_exists": self.SESSION_FILE.exists(),
        }

    def attempt_login(self) -> Dict:
        """
        Attempt a non-blocking login check.
        Catches checkpoints, 2FA, and connection challenges gracefully.
        """
        if not self.username or not self.password:
            return {
                "success": False,
                "status": "missing_credentials",
                "message": "Insta_svc_acc_username / Insta_svc_acc_pwd not found in environment/vault.",
            }

        try:
            self.loader.login(self.username, self.password)
            self.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.loader.save_session_to_file(str(self.SESSION_FILE))
            self.is_authenticated = True

            # Also extract sessionid to cookies.json for web requests
            session_cookie = self.loader.context._session.cookies.get_dict().get("sessionid")
            if session_cookie:
                cookie_data = {"sessionid": session_cookie}
                with open(self.COOKIE_FILE, "w") as f:
                    json.dump(cookie_data, f, indent=2)

            return {
                "success": True,
                "status": "authenticated",
                "message": f"Successfully authenticated as @{self.username}. Session cached.",
            }

        except instaloader.TwoFactorAuthRequiredException:
            return {
                "success": False,
                "status": "2fa_required",
                "message": "Two-Factor Authentication is enabled on this account. Manual approval needed.",
            }

        except instaloader.BadCredentialsException:
            return {
                "success": False,
                "status": "bad_credentials",
                "message": "Invalid username or password.",
            }

        except instaloader.ConnectionException as ce:
            err_msg = str(ce)
            if "Checkpoint" in err_msg:
                return {
                    "success": False,
                    "status": "checkpoint_required",
                    "message": "Instagram requested a browser checkpoint verification (unrecognized IP).",
                }
            return {
                "success": False,
                "status": "connection_error",
                "message": f"Instagram connection issue: {err_msg[:120]}",
            }

        except Exception as e:
            return {
                "success": False,
                "status": "unknown_error",
                "message": f"Encountered {type(e).__name__}: {str(e)[:120]}",
            }

    def fetch_deep_chaining(self, username: str, max_results: int = 30) -> List[str]:
        """
        Fetch extended chaining/similar profiles using the authenticated session.
        Falls back to empty list if not authenticated or throttled.
        """
        if not self.is_authenticated:
            return []

        try:
            profile = instaloader.Profile.from_username(self.loader.context, username)
            similar = profile.get_similar()
            discovered = []
            for p in similar:
                discovered.append(p.username)
                if len(discovered) >= max_results:
                    break
            return discovered
        except Exception:
            return []
