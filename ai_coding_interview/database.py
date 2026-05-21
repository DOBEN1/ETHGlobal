import threading
import uuid
import time
import random
import logging

logger = logging.getLogger("db")


class DatabaseError(Exception):
    pass


class Database:

    def __init__(self):
        self._lock = threading.Lock()
        self.users = {
            "user_1": {
                "id": "user_1",
                "email": "alex@example.com",
                "name": "Alex Chen",
                "plan": "free",
                "updated_at": None,
            }
        }
        self.outbox = []
        self._tx_log = []
        self._pending = {}
        self._fail_count = 0

    def begin_transaction(self) -> str:
        txn_id = f"txn_{uuid.uuid4().hex[:8]}"
        logger.info(f"BEGIN transaction {txn_id}")
        self._pending[txn_id] = {}
        return txn_id

    def update_user(self, txn_id: str, user_id: str, changes: dict):
        logger.info(f"[{txn_id}] UPDATE users SET {changes} WHERE id={user_id}")
        self._pending[txn_id]["user_update"] = {
            "user_id": user_id,
            "changes": changes,
        }

    def insert_outbox(self, txn_id: str, event: dict):
        logger.info(f"[{txn_id}] INSERT INTO outbox: {event.get('type', 'unknown')}")
        self._pending.setdefault(txn_id, {})
        self._pending[txn_id].setdefault("outbox_events", []).append(event)

    def commit(self, txn_id: str):
        if self._fail_count > 0:
            self._fail_count -= 1
            logger.error(f"[{txn_id}] COMMIT FAILED — connection timeout (retryable)")
            self.rollback(txn_id)
            raise DatabaseError(f"Transaction {txn_id} failed: connection timeout")

        if random.random() < 0.15:
            logger.error(f"[{txn_id}] COMMIT FAILED — deadlock detected (retryable)")
            self.rollback(txn_id)
            raise DatabaseError(f"Transaction {txn_id} failed: deadlock detected")

        with self._lock:
            pending = self._pending.pop(txn_id, {})

            if "user_update" in pending:
                uid = pending["user_update"]["user_id"]
                if uid in self.users:
                    self.users[uid].update(pending["user_update"]["changes"])
                    self.users[uid]["updated_at"] = time.time()

            for evt in pending.get("outbox_events", []):
                evt["created_at"] = time.time()
                evt["published"] = False
                self.outbox.append(evt)

            self._tx_log.append({"txn_id": txn_id, "status": "committed", "ts": time.time()})
            logger.info(f"[{txn_id}] COMMIT OK")

    def rollback(self, txn_id: str):
        self._pending.pop(txn_id, None)
        self._tx_log.append({"txn_id": txn_id, "status": "rolled_back", "ts": time.time()})
        logger.warning(f"[{txn_id}] ROLLBACK")

    def get_user(self, user_id: str) -> dict | None:
        return self.users.get(user_id)

    def get_pending_outbox(self) -> list:
        return [e for e in self.outbox if not e.get("published")]

    def mark_outbox_published(self, event_id: str):
        for e in self.outbox:
            if e.get("id") == event_id:
                e["published"] = True

    def force_fail_next_commits(self, count: int = 1):
        self._fail_count = count

    def reset(self):
        self.users = {
            "user_1": {
                "id": "user_1",
                "email": "alex@example.com",
                "name": "Alex Chen",
                "plan": "free",
                "updated_at": None,
            }
        }
        self.outbox = []
        self._tx_log = []
        self._pending = {}
        self._fail_count = 0
