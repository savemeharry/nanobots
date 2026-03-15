"""Telegram Mini App authentication."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, unquote
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class TelegramUser:
    """Authenticated Telegram user from initData."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: bool = False
    photo_url: Optional[str] = None


@dataclass
class AuthResult:
    """Result of authentication check."""
    valid: bool
    user: Optional[TelegramUser] = None
    error: Optional[str] = None


class TelegramAuth:
    """
    Validates Telegram Mini App initData.

    Based on official Telegram documentation:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """

    def __init__(self, bot_token: str, allow_from: list[str] = None, max_age_seconds: int = 86400):
        """
        Initialize authenticator.

        Args:
            bot_token: Telegram bot token from BotFather
            allow_from: List of allowed user IDs or usernames. Empty = allow all authenticated users.
            max_age_seconds: Maximum age of initData in seconds (default 24h)
        """
        self.bot_token = bot_token
        self.allow_from = allow_from or []
        self.max_age_seconds = max_age_seconds
        self._secret_key = self._compute_secret_key()

    def _compute_secret_key(self) -> bytes:
        """Compute HMAC secret key from bot token."""
        # secret_key = HMAC_SHA256("WebAppData", bot_token)
        return hmac.new(
            b"WebAppData",
            self.bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()

    def validate(self, init_data: str) -> AuthResult:
        """
        Validate Telegram initData string.

        Args:
            init_data: The initData string from Telegram.WebApp.initData

        Returns:
            AuthResult with validation status and user info
        """
        if not init_data:
            return AuthResult(valid=False, error="No initData provided")

        try:
            # Parse the query string
            parsed = parse_qs(init_data, keep_blank_values=True)

            # Extract and remove hash
            if 'hash' not in parsed:
                return AuthResult(valid=False, error="Missing hash in initData")

            received_hash = parsed.pop('hash')[0]

            # Build data-check-string: key=value pairs sorted alphabetically
            data_pairs = []
            for key, values in parsed.items():
                # parse_qs returns lists, take first value
                value = values[0] if values else ''
                data_pairs.append(f"{key}={value}")

            data_pairs.sort()
            data_check_string = '\n'.join(data_pairs)

            # Compute expected hash
            computed_hash = hmac.new(
                self._secret_key,
                data_check_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(computed_hash, received_hash):
                logger.warning("initData hash mismatch - possible tampering")
                return AuthResult(valid=False, error="Invalid signature")

            # Check auth_date freshness
            if 'auth_date' in parsed:
                auth_date = int(parsed['auth_date'][0])
                current_time = int(time.time())

                if current_time - auth_date > self.max_age_seconds:
                    return AuthResult(valid=False, error="initData expired")

            # Parse user data
            user = None
            if 'user' in parsed:
                try:
                    user_data = json.loads(unquote(parsed['user'][0]))
                    user = TelegramUser(
                        id=user_data.get('id'),
                        first_name=user_data.get('first_name', ''),
                        last_name=user_data.get('last_name'),
                        username=user_data.get('username'),
                        language_code=user_data.get('language_code'),
                        is_premium=user_data.get('is_premium', False),
                        photo_url=user_data.get('photo_url')
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse user data: {e}")
                    return AuthResult(valid=False, error="Invalid user data")

            if not user:
                return AuthResult(valid=False, error="No user in initData")

            # Check if user is in allow list
            if self.allow_from:
                user_id_str = str(user.id)
                username_str = user.username or ''

                allowed = (
                    user_id_str in self.allow_from or
                    username_str in self.allow_from or
                    f"@{username_str}" in self.allow_from
                )

                if not allowed:
                    logger.warning(f"User {user_id_str} (@{username_str}) not in allow list")
                    return AuthResult(valid=False, user=user, error="User not authorized")

            logger.debug(f"Authenticated user: {user.id} (@{user.username})")
            return AuthResult(valid=True, user=user)

        except Exception as e:
            logger.error(f"initData validation error: {e}")
            return AuthResult(valid=False, error=f"Validation error: {str(e)}")

    def is_user_allowed(self, user_id: int, username: str = None) -> bool:
        """
        Check if a specific user is allowed.

        Args:
            user_id: Telegram user ID
            username: Telegram username (without @)

        Returns:
            True if allowed
        """
        if not self.allow_from:
            return True  # No restrictions

        user_id_str = str(user_id)
        username_str = username or ''

        return (
            user_id_str in self.allow_from or
            username_str in self.allow_from or
            f"@{username_str}" in self.allow_from
        )
