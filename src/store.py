import hashlib
import sqlite3
import threading
import uuid
from pathlib import Path

from src.models import Conversation, Message, Skill, User
from src.utils import utc_now


class InMemoryStore:
    """
    Backward-compatible store name.
    Data is persisted in SQLite for users/conversations/messages.
    Skills remain in-memory because they are loaded from files.
    """

    def __init__(self, database_path: str = "data/app.db") -> None:
        self._lock = threading.RLock()
        self._skills: dict[str, Skill] = {}

        db_path = Path(database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_map (
                    channel TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    PRIMARY KEY (channel, external_id)
                )
                """
            )

    def health(self) -> bool:
        try:
            self._conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    # ---------- Skill ----------
    def upsert_skill(self, skill: Skill) -> None:
        with self._lock:
            self._skills[skill.skill_id] = skill

    def list_skills(self) -> list[Skill]:
        with self._lock:
            return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Skill | None:
        with self._lock:
            return self._skills.get(skill_id)

    # ---------- User ----------
    def create_user(self, username: str, password_hash: str, password_salt: str) -> User:
        with self._lock:
            user_id = f"u_{uuid.uuid4().hex[:12]}"
            now = utc_now()
            try:
                with self._conn:
                    self._conn.execute(
                        """
                        INSERT INTO users(user_id, username, password_hash, password_salt, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, username, password_hash, password_salt, now.isoformat()),
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError("USERNAME_EXISTS") from exc

            return User(
                user_id=user_id,
                username=username,
                password_hash=password_hash,
                password_salt=password_salt,
                created_at=now,
            )

    def get_user_by_username(self, username: str) -> User | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT user_id, username, password_hash, password_salt, created_at
                FROM users WHERE username = ?
                """,
                (username,),
            ).fetchone()
            return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT user_id, username, password_hash, password_salt, created_at
                FROM users WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            return self._row_to_user(row) if row else None

    # ---------- Conversation ----------
    def create_conversation(self, user_id: str, skill_id: str, channel: str) -> Conversation:
        with self._lock:
            conversation_id = f"c_{uuid.uuid4().hex[:12]}"
            now = utc_now()
            title = "New conversation"
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO conversations(
                        conversation_id, user_id, skill_id, title, channel, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (conversation_id, user_id, skill_id, title, channel, now.isoformat(), now.isoformat()),
                )

            return Conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                skill_id=skill_id,
                title=title,
                channel=channel,
                created_at=now,
                updated_at=now,
            )

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT conversation_id, user_id, skill_id, title, channel, created_at, updated_at
                FROM conversations WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            return self._row_to_conversation(row) if row else None

    def touch_conversation(self, conversation_id: str) -> None:
        with self._lock:
            now = utc_now().isoformat()
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE conversations SET updated_at = ?
                    WHERE conversation_id = ?
                    """,
                    (now, conversation_id),
                )

    def list_conversations_by_user(self, user_id: str) -> list[Conversation]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT conversation_id, user_id, skill_id, title, channel, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [self._row_to_conversation(row) for row in rows]

    # ---------- Message ----------
    def append_message(self, conversation_id: str, role: str, content: str, token_count: int) -> Message:
        with self._lock:
            message_id = f"m_{uuid.uuid4().hex[:12]}"
            now = utc_now()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO messages(message_id, conversation_id, role, content, token_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, conversation_id, role, content, token_count, now.isoformat()),
                )
                self._conn.execute(
                    """
                    UPDATE conversations SET updated_at = ?
                    WHERE conversation_id = ?
                    """,
                    (now.isoformat(), conversation_id),
                )

            return Message(
                message_id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                token_count=token_count,
                created_at=now,
            )

    def get_messages(self, conversation_id: str) -> list[Message]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT message_id, conversation_id, role, content, token_count, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
            return [self._row_to_message(row) for row in rows]

    # ---------- External user mapping ----------
    def resolve_user_id(self, channel: str, external_id: str) -> str:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT user_id FROM user_map
                WHERE channel = ? AND external_id = ?
                """,
                (channel, external_id),
            ).fetchone()
            if row:
                return str(row["user_id"])

            digest = hashlib.sha1(f"{channel}:{external_id}".encode("utf-8")).hexdigest()
            user_id = f"u_{digest[:12]}"
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO user_map(channel, external_id, user_id)
                    VALUES (?, ?, ?)
                    """,
                    (channel, external_id, user_id),
                )
            return user_id

    # ---------- Row conversions ----------
    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            password_salt=str(row["password_salt"]),
            created_at=self._parse_dt(str(row["created_at"])),
        )

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        return Conversation(
            conversation_id=str(row["conversation_id"]),
            user_id=str(row["user_id"]),
            skill_id=str(row["skill_id"]),
            title=str(row["title"]),
            channel=str(row["channel"]),
            created_at=self._parse_dt(str(row["created_at"])),
            updated_at=self._parse_dt(str(row["updated_at"])),
        )

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            message_id=str(row["message_id"]),
            conversation_id=str(row["conversation_id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            token_count=int(row["token_count"]),
            created_at=self._parse_dt(str(row["created_at"])),
        )

    @staticmethod
    def _parse_dt(value: str):
        from datetime import datetime

        return datetime.fromisoformat(value)

