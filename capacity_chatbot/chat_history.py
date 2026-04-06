"""Chat history metadata storage for conversation listing."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def ensure_chat_history_table(pool) -> None:
    """Create chat_history table if it doesn't exist."""
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                thread_id VARCHAR(255) PRIMARY KEY,
                user_uuid VARCHAR(255) NOT NULL,
                dealer_uuid VARCHAR(255) NOT NULL,
                department_uuid VARCHAR(255) NOT NULL,
                first_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                message_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(user_uuid);
            CREATE INDEX IF NOT EXISTS idx_chat_history_dealer ON chat_history(dealer_uuid);
        """)


async def save_thread_metadata(
    pool,
    thread_id: str,
    user_uuid: str,
    dealer_uuid: str,
    department_uuid: str,
    first_message: str,
    message_count: int = 1,
) -> bool:
    """Upsert thread metadata. Called after each message exchange."""
    try:
        now = datetime.now(timezone.utc)
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO chat_history
                    (thread_id, user_uuid, dealer_uuid, department_uuid, first_message, created_at, updated_at, message_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (thread_id)
                DO UPDATE SET updated_at = %s, message_count = %s
                """,
                (
                    thread_id, user_uuid, dealer_uuid, department_uuid,
                    first_message[:200], now, now, message_count,
                    now, message_count,
                ),
            )
        return True
    except Exception as e:
        logger.exception("Failed to save thread metadata: %s", e)
        return False


async def get_threads_for_user(pool, user_uuid: str, limit: int = 50) -> list[dict]:
    """Get conversation list for a user, sorted by most recent."""
    try:
        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT thread_id, first_message, created_at, updated_at, message_count
                FROM chat_history
                WHERE user_uuid = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_uuid, limit),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "thread_id": row["thread_id"],
                    "first_message": row["first_message"] or "",
                    "created_at": row["created_at"].isoformat() if row["created_at"] else "",
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
                    "message_count": row["message_count"] or 0,
                }
                for row in rows
            ]
    except Exception as e:
        logger.exception("Failed to get threads: %s", e)
        return []


async def verify_thread_ownership(pool, thread_id: str, user_uuid: str) -> bool:
    """Check if a thread belongs to the given user.

    Fail-closed: returns False (deny) when ownership cannot be confirmed.
    Only skips check when auth is explicitly disabled via ENABLE_MKID_AUTH=false.
    """
    import os
    auth_disabled = os.getenv("ENABLE_MKID_AUTH", "true").lower() == "false"

    if auth_disabled:
        return True  # Auth explicitly disabled — local dev, allow

    if not pool or not user_uuid:
        logger.warning("Cannot verify thread ownership: pool=%s, user_uuid=%s", bool(pool), bool(user_uuid))
        return False  # Fail closed — pool missing or empty user in auth-enabled mode

    try:
        async with pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT user_uuid FROM chat_history WHERE thread_id = %s",
                (thread_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return False  # No metadata — deny (fail closed)
            return row["user_uuid"] == user_uuid
    except Exception as e:
        logger.warning("Could not verify thread ownership: %s", e)
        return False  # DB error — deny (fail closed)
