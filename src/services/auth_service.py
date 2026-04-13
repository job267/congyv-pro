import base64
import hashlib
import hmac
import secrets
import time

from src.core.errors import AppError
from src.models import User
from src.schemas import AuthResponse, UserProfile
from src.store import InMemoryStore


class AuthService:
    def __init__(self, store: InMemoryStore, secret_key: str, token_ttl_seconds: int) -> None:
        self.store = store
        self.secret_key = secret_key.encode("utf-8")
        self.token_ttl_seconds = token_ttl_seconds

    def register(self, username: str, password: str) -> AuthResponse:
        normalized = self._normalize_username(username)
        self._validate_password(password)
        if self.store.get_user_by_username(normalized):
            raise AppError("USERNAME_EXISTS", "Username already exists.", status_code=409)

        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(password=password, salt=salt)
        user = self.store.create_user(
            username=normalized,
            password_hash=pwd_hash,
            password_salt=salt,
        )
        token = self.issue_token(user.user_id)
        return AuthResponse(token=token, user=UserProfile(user_id=user.user_id, username=user.username))

    def login(self, username: str, password: str) -> AuthResponse:
        normalized = self._normalize_username(username)
        user = self.store.get_user_by_username(normalized)
        if not user:
            raise AppError("INVALID_CREDENTIALS", "Username or password is incorrect.", status_code=401)

        expected = self._hash_password(password=password, salt=user.password_salt)
        if not hmac.compare_digest(expected, user.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Username or password is incorrect.", status_code=401)

        token = self.issue_token(user.user_id)
        return AuthResponse(token=token, user=UserProfile(user_id=user.user_id, username=user.username))

    def issue_token(self, user_id: str) -> str:
        exp = int(time.time()) + self.token_ttl_seconds
        payload = f"{user_id}.{exp}"
        signature = hmac.new(self.secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token_raw = f"{user_id}.{exp}.{signature}".encode("utf-8")
        return base64.urlsafe_b64encode(token_raw).decode("utf-8")

    def authenticate_token(self, token: str) -> User:
        try:
            raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            user_id, exp_str, signature = raw.split(".", 2)
        except Exception as exc:
            raise AppError("UNAUTHORIZED", "Invalid token.", status_code=401) from exc

        payload = f"{user_id}.{exp_str}"
        expected = hmac.new(self.secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise AppError("UNAUTHORIZED", "Invalid token signature.", status_code=401)

        try:
            exp = int(exp_str)
        except ValueError as exc:
            raise AppError("UNAUTHORIZED", "Invalid token expiration.", status_code=401) from exc
        if exp < int(time.time()):
            raise AppError("UNAUTHORIZED", "Token expired.", status_code=401)

        user = self.store.get_user_by_id(user_id)
        if not user:
            raise AppError("UNAUTHORIZED", "User not found.", status_code=401)
        return user

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = username.strip()
        if not normalized:
            raise AppError("INVALID_USERNAME", "Username cannot be empty.", status_code=400)
        if " " in normalized:
            raise AppError("INVALID_USERNAME", "Username cannot contain spaces.", status_code=400)
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 6:
            raise AppError("WEAK_PASSWORD", "Password must be at least 6 characters.", status_code=400)

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120_000,
        )
        return digest.hex()

