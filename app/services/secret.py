import os
import uuid
import shutil
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from fastapi import UploadFile

from app.core.config import settings

class SecretService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.secrets_collection = self.db["secrets"]
        self.users = self.db["users"]
        self.storage_path = "secrets_vault"
        
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    async def init_indexes(self):
        # Auto-delete secrets after 24 hours if not viewed
        await self.secrets_collection.create_index("created_at", expireAfterSeconds=86400)

    async def _get_partner_id(self, user_id: str) -> Optional[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return user["partner"]["user_id"]
        return None

    async def _get_names(self, user_id: str, partner_id: Optional[str]) -> Tuple[str, str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        u_name = user.get("name", "User") if user else "User"
        p_name = "Partner"
        if partner_id:
            pt = await self.users.find_one({"_id": ObjectId(partner_id)})
            if pt:
                p_name = pt.get("name", "Partner")
        return u_name, p_name

    async def save_secret(self, sender_id: str, file: UploadFile, prevent_screenshot: bool = True) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(sender_id)
        if not partner_id:
            raise ValueError("You must be aligned with a partner to send secrets.")

        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        full_path = os.path.join(self.storage_path, unique_filename)

        # Save file to disk
        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create database entry
        new_doc = {
            "sender_id": sender_id,
            "recipient_id": partner_id,
            "filename": file.filename,
            "stored_filename": unique_filename,
            "file_type": file.content_type,
            "size": os.path.getsize(full_path),
            "prevent_screenshot": prevent_screenshot,
            "created_at": datetime.now(timezone.utc),
            "is_viewed": False
        }
        
        result = await self.secrets_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def get_secrets_for_me(self, user_id: str, page: int = 1, size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        u_name, p_name = await self._get_names(user_id, partner_id)

        skip = (page - 1) * size
        query = {"recipient_id": user_id, "is_viewed": False}
        
        cursor = self.secrets_collection.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.secrets_collection.count_documents(query)

        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            d["user_name"] = u_name
            d["partner_name"] = p_name
            if "prevent_screenshot" not in d:
                d["prevent_screenshot"] = True
            results.append(d)
        return results, total

    async def get_sent_secrets(self, user_id: str, page: int = 1, size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        u_name, p_name = await self._get_names(user_id, partner_id)

        skip = (page - 1) * size
        query = {"sender_id": user_id, "is_viewed": False}
        
        cursor = self.secrets_collection.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.secrets_collection.count_documents(query)

        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            d["user_name"] = u_name
            d["partner_name"] = p_name
            if "prevent_screenshot" not in d:
                d["prevent_screenshot"] = True
            results.append(d)
        return results, total

    async def patch_screenshot_protection(self, secret_id: str, user_id: str, prevent: bool) -> bool:
        result = await self.secrets_collection.update_one(
            {"_id": ObjectId(secret_id), "sender_id": user_id, "is_viewed": False},
            {"$set": {"prevent_screenshot": prevent}}
        )
        return result.matched_count > 0

    async def get_secret_metadata(self, secret_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.secrets_collection.find_one({
            "_id": ObjectId(secret_id),
            "$or": [{"recipient_id": user_id}, {"sender_id": user_id}],
            "is_viewed": False
        })
        if not doc:
            raise ValueError("Secret not found or already viewed.")
        return doc

    async def mark_secret_viewed(self, secret_id: str):
        await self.secrets_collection.update_one(
            {"_id": ObjectId(secret_id)},
            {"$set": {"is_viewed": True, "viewed_at": datetime.now(timezone.utc)}}
        )

    def get_full_path(self, stored_filename: str) -> str:
        return os.path.join(self.storage_path, stored_filename)

    def delete_file(self, file_path: str):
        """Physical deletion of the file."""
        if os.path.exists(file_path):
            os.remove(file_path)

secret_service = SecretService()
