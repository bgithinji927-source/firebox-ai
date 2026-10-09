"""Persistence operations kept separate from HTTP routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from .db import MongoStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialise(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialise(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, list):
        return [serialise(item) for item in value]
    return value


class Repositories:
    def __init__(self, store: MongoStore) -> None:
        self.store = store

    def create_conversation(self, owner_id: str, title: str) -> dict[str, Any]:
        now = utc_now()
        document = {"owner_id": owner_id, "title": title.strip()[:160] or "New conversation", "created_at": now, "updated_at": now}
        result = self.store.collection("conversations").insert_one(document)
        document["id"] = str(result.inserted_id)
        return serialise(document)

    def list_conversations(self, owner_id: str) -> list[dict[str, Any]]:
        cursor = self.store.collection("conversations").find({"owner_id": owner_id}).sort("updated_at", -1).limit(100)
        return [serialise(item) for item in cursor]

    def get_conversation(self, owner_id: str, conversation_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(conversation_id):
            return None
        conversation = self.store.collection("conversations").find_one({"_id": ObjectId(conversation_id), "owner_id": owner_id})
        if conversation is None:
            return None
        messages = self.store.collection("messages").find({"conversation_id": conversation_id, "owner_id": owner_id}).sort("created_at", 1)
        response = serialise(conversation)
        response["id"] = conversation_id
        response["messages"] = [serialise(message) for message in messages]
        return response

    def append_message(self, owner_id: str, conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if role not in {"user", "assistant", "system"} or not ObjectId.is_valid(conversation_id):
            return None
        conversation_filter = {"_id": ObjectId(conversation_id), "owner_id": owner_id}
        now = utc_now()
        if self.store.collection("conversations").find_one(conversation_filter, {"_id": 1}) is None:
            return None
        message = {"conversation_id": conversation_id, "owner_id": owner_id, "role": role, "content": content, "metadata": metadata or {}, "created_at": now}
        result = self.store.collection("messages").insert_one(message)
        self.store.collection("conversations").update_one(conversation_filter, {"$set": {"updated_at": now}})
        message["id"] = str(result.inserted_id)
        return serialise(message)

    def delete_conversation(self, owner_id: str, conversation_id: str) -> bool:
        if not ObjectId.is_valid(conversation_id):
            return False
        conversation_filter = {"_id": ObjectId(conversation_id), "owner_id": owner_id}
        result = self.store.collection("conversations").delete_one(conversation_filter)
        if result.deleted_count:
            self.store.collection("messages").delete_many({"conversation_id": conversation_id, "owner_id": owner_id})
            return True
        return False

    def get_settings(self, owner_id: str) -> dict[str, Any]:
        item = self.store.collection("settings").find_one({"owner_id": owner_id})
        return serialise(item or {"owner_id": owner_id, "model_name": "Firebox Small · Local", "web_search_enabled": False})

    def update_settings(self, owner_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: value for key, value in values.items() if key in {"model_name", "web_search_enabled"}}
        allowed["owner_id"] = owner_id
        allowed["updated_at"] = utc_now()
        self.store.collection("settings").update_one({"owner_id": owner_id}, {"$set": allowed, "$setOnInsert": {"created_at": utc_now()}}, upsert=True)
        return self.get_settings(owner_id)

    def insert_document(self, document: dict[str, Any]) -> dict[str, Any]:
        result = self.store.collection("documents").insert_one(document)
        document["id"] = str(result.inserted_id)
        return serialise(document)

    def list_documents(self, owner_id: str) -> list[dict[str, Any]]:
        cursor = self.store.collection("documents").find({"owner_id": owner_id}).sort("created_at", -1)
        return [serialise(item) for item in cursor]

    def delete_document(self, owner_id: str, document_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(document_id):
            return None
        collection = self.store.collection("documents")
        document = collection.find_one_and_delete({"_id": ObjectId(document_id), "owner_id": owner_id})
        if document is None:
            return None
        self.store.collection("document_chunks").delete_many({"document_id": document_id, "owner_id": owner_id})
        return serialise(document)
