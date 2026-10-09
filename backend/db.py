"""MongoDB connection and collection/index management for FIREBOX AI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

logger = logging.getLogger("firebox.mongo")


@dataclass
class MongoStore:
    """Owns the MongoDB client and exposes a small, testable database boundary."""

    uri: str
    database_name: str
    client: MongoClient | None = None
    database: Any | None = None
    connected: bool = False
    last_error: str | None = None

    @classmethod
    def from_environment(cls) -> "MongoStore":
        return cls(
            uri=os.getenv("MONGODB_URI", "").strip(),
            database_name=os.getenv("MONGODB_DB_NAME", "firebox_ai").strip() or "firebox_ai",
        )

    def connect(self) -> bool:
        """Connect and verify MongoDB. Failure is recorded, never hidden."""
        if not self.uri:
            self.last_error = "MONGODB_URI is not configured"
            self.connected = False
            logger.warning(self.last_error)
            return False

        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=3500,
                connectTimeoutMS=3500,
                socketTimeoutMS=5000,
                appname="firebox-ai",
            )
            self.client.admin.command("ping")
            self.database = self.client[self.database_name]
            self._ensure_indexes()
            self.connected = True
            self.last_error = None
            logger.info("MongoDB connected: database=%s", self.database_name)
            return True
        except PyMongoError as exc:
            self.connected = False
            self.last_error = f"MongoDB connection failed: {exc.__class__.__name__}"
            logger.exception("MongoDB connection failed")
            self.close()
            return False

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.database = None
        self.connected = False

    def collection(self, name: str) -> Collection:
        if not self.connected or self.database is None:
            raise RuntimeError("MongoDB is unavailable; the requested data was not saved")
        return self.database[name]

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "database": self.database_name,
            "error": self.last_error,
        }

    def _ensure_indexes(self) -> None:
        assert self.database is not None
        self.database.conversations.create_index([("owner_id", ASCENDING), ("updated_at", DESCENDING)])
        self.database.messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
        self.database.settings.create_index("owner_id", unique=True)
        self.database.documents.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.documents.create_index([("owner_id", ASCENDING), ("status", ASCENDING)])
        self.database.document_chunks.create_index([("document_id", ASCENDING), ("chunk_index", ASCENDING)])
        self.database.document_chunks.create_index([("owner_id", ASCENDING), ("document_id", ASCENDING)])
        self.database.web_research_cache.create_index("expires_at", expireAfterSeconds=0)
        self.database.training_runs.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.training_metrics.create_index([("run_id", ASCENDING), ("epoch", ASCENDING)])
        self.database.training_feedback.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.training_lessons.create_index([("owner_id", ASCENDING), ("topic", ASCENDING)])
        self.database.evaluation_cases.create_index([("owner_id", ASCENDING), ("category", ASCENDING)])
        self.database.evaluation_results.create_index([("run_id", ASCENDING), ("created_at", DESCENDING)])
        self.database.knowledge_items.create_index([("owner_id", ASCENDING), ("approved", ASCENDING)])


def mongo_error_message(exc: Exception) -> str:
    """Return a safe error message without exposing a connection string."""
    if isinstance(exc, RuntimeError):
        return str(exc)
    return "MongoDB is unavailable; the operation was not completed"
