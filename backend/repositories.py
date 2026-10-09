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
        results = []
        for item in cursor:
            response = serialise(item)
            response["id"] = str(item["_id"])
            results.append(response)
        return results

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

    def rename_conversation(self, owner_id: str, conversation_id: str, title: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(conversation_id):
            return None
        result = self.store.collection("conversations").find_one_and_update(
            {"_id": ObjectId(conversation_id), "owner_id": owner_id},
            {"$set": {"title": title.strip()[:160] or "New conversation", "updated_at": utc_now()}},
            return_document=True,
        )
        if result is None:
            return None
        response = serialise(result)
        response["id"] = conversation_id
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
        return serialise(item or {"owner_id": owner_id, "runtime": "local-firebox", "web_search_enabled": False})

    def update_settings(self, owner_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: value for key, value in values.items() if key in {"web_search_enabled"}}
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
        results = []
        for item in cursor:
            response = serialise(item)
            response["id"] = str(item["_id"])
            response.pop("storage_key", None)
            results.append(response)
        return results

    def delete_document(self, owner_id: str, document_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(document_id):
            return None
        collection = self.store.collection("documents")
        document = collection.find_one_and_delete({"_id": ObjectId(document_id), "owner_id": owner_id})
        if document is None:
            return None
        self.store.collection("document_chunks").delete_many({"document_id": document_id, "owner_id": owner_id})
        return serialise(document)

    def insert_training_record(self, collection: str, owner_id: str, values: dict[str, Any]) -> dict[str, Any]:
        document = {"owner_id": owner_id, "created_at": utc_now(), **values}
        result = self.store.collection(collection).insert_one(document)
        document["id"] = str(result.inserted_id)
        return serialise(document)

    def list_training_records(self, collection: str, owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.store.collection(collection).find({"owner_id": owner_id}).sort("created_at", -1).limit(limit)
        return [serialise({**item, "id": item["_id"]}) for item in cursor]

    def append_training_metric(self, owner_id: str, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return self.insert_training_record("training_metrics", owner_id, {"run_id": run_id, **values})

    def add_knowledge_item(self, owner_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return self.insert_training_record("knowledge_items", owner_id, {"approved": False, **values})

    def list_teacher_reviews(self, owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_training_records("teacher_reviews", owner_id, limit)

    def approve_teacher_review(self, owner_id: str, review_id: str) -> bool:
        if not ObjectId.is_valid(review_id):
            return False
        result = self.store.collection("teacher_reviews").update_one(
            {"_id": ObjectId(review_id), "owner_id": owner_id},
            {"$set": {"approved": True, "approved_at": utc_now()}},
        )
        return result.modified_count == 1

    def approved_teacher_dataset(self, owner_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        items = self.store.collection("teacher_reviews").find({"owner_id": owner_id, "approved": True}).sort("created_at", 1).limit(limit)
        return [
            {
                "instruction": item.get("prompt", ""),
                "context": item.get("context", ""),
                "response": item.get("response", ""),
            }
            for item in items
            if item.get("prompt") and item.get("response")
        ]

    def approve_knowledge_item(self, owner_id: str, item_id: str) -> bool:
        if not ObjectId.is_valid(item_id):
            return False
        result = self.store.collection("knowledge_items").update_one(
            {"_id": ObjectId(item_id), "owner_id": owner_id},
            {"$set": {"approved": True, "approved_at": utc_now()}},
        )
        return result.modified_count == 1
