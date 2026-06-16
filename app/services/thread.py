import os
import uuid
import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from fastapi import UploadFile

from app.core.config import settings
from app.schemas.thread import (
    ThreadCategory, PromptType, PromptQuestionCreate,
    LetterCreate, PhotoCreate, PromptAskCreate, AppreciationCreate, CheckInThreadCreate
)

DEFAULT_ROMANTIC_QUESTIONS = [
    {"category": "Emotional", "rating": "●●○○○", "text": "What's one thing I did recently that made you feel deeply loved?", "type": PromptType.ROMANTIC},
    {"category": "Emotional", "rating": "●○○○○", "text": "Describe the moment you knew this was something real.", "type": PromptType.ROMANTIC},
    {"category": "Desire", "rating": "●●●○○", "text": "If we had one uninterrupted hour right now, how would you want to spend it?", "type": PromptType.ROMANTIC},
    {"category": "Growth", "rating": "●○○○○", "text": "What part of our relationship are you most proud of?", "type": PromptType.ROMANTIC},
    {"category": "Depth", "rating": "●●○○○", "text": "Tell me something you've been holding in — good or complicated.", "type": PromptType.ROMANTIC},
    {"category": "Memory", "rating": "●●○○○", "text": "If you could relive one moment with me, which would it be?", "type": PromptType.ROMANTIC},
    {"category": "Growth", "rating": "●●○○○", "text": "What's your love language and how can I speak it better?", "type": PromptType.ROMANTIC},
    {"category": "Future", "rating": "●●○○○", "text": "What are you looking forward to most in our future?", "type": PromptType.ROMANTIC},
    {"category": "Emotional", "rating": "●○○○○", "text": "What do I do that makes you feel most seen?", "type": PromptType.ROMANTIC},
    {"category": "Adventure", "rating": "●●○○○", "text": "What's a dream date you've never told me about?", "type": PromptType.ROMANTIC},
]

DEFAULT_DESIRED_QUESTIONS = [
    {"category": "Intense", "rating": "●●●●●", "text": "Tell me exactly what you'd do if I was there right now.", "type": PromptType.DESIRED},
    {"category": "Daring", "rating": "●●●●●", "text": "What's the boldest thing you want to try together?", "type": PromptType.DESIRED},
    {"category": "Memory", "rating": "●●●●○", "text": "Describe your favorite memory of us in full detail.", "type": PromptType.DESIRED},
    {"category": "Vulnerable", "rating": "●●●●○", "text": "What's something you've been too shy to ask for?", "type": PromptType.DESIRED},
    {"category": "Intense", "rating": "●●●●●", "text": "If you could have me any way you wanted tonight, what would you choose?", "type": PromptType.DESIRED},
    {"category": "Desire", "rating": "●●●●○", "text": "What do you think about when you close your eyes and think of me?", "type": PromptType.DESIRED},
    {"category": "Intimate", "rating": "●●●●○", "text": "What's one thing about your body you want me to pay more attention to?", "type": PromptType.DESIRED},
    {"category": "Daring", "rating": "●●●●●", "text": "Tell me a fantasy you've never spoken out loud.", "type": PromptType.DESIRED},
]

class ThreadService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.messages_collection = self.db["thread_messages"]
        self.prompts_collection = self.db["thread_prompts"]
        self.users = self.db["users"]
        self.storage_path = "uploads"
        
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    async def init_indexes(self):
        await self.messages_collection.create_index([("creator_id", 1), ("partner_id", 1)])
        await self.messages_collection.create_index("created_at")
        await self.prompts_collection.create_index("type")

    async def _get_partner_id(self, user_id: str) -> Optional[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return user["partner"]["user_id"]
        return None

    async def _get_names(self, user_id: str, partner_id: str) -> Dict[str, str]:
        names = {user_id: "User", partner_id: "Partner"}
        async for user in self.users.find({"_id": {"$in": [ObjectId(user_id), ObjectId(partner_id)]}}):
            names[str(user["_id"])] = user.get("name", "User")
        return names

    async def get_categories(self, user_id: str) -> List[str]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id: user_ids.append(partner_id)
        
        # Return categories that have at least one message in this couple's thread
        pipeline = [
            {"$match": {"creator_id": {"$in": user_ids}}},
            {"$group": {"_id": "$category"}}
        ]
        cursor = self.messages_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return [r["_id"] for r in results]

    async def post_letter(self, user_id: str, payload: LetterCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        new_doc = {
            "category": ThreadCategory.LETTER,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {"text": payload.text},
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, payload.timezone, user_id)

    async def post_voice(self, user_id: str, file: UploadFile, timezone_str: str = "UTC") -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        local_path = os.path.join(self.storage_path, unique_filename)
        
        content = await file.read()
        with open(local_path, "wb") as f:
            f.write(content)
            
        file_url = f"/uploads/{unique_filename}"
        
        new_doc = {
            "category": ThreadCategory.VOICE,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {"file_url": file_url},
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, timezone_str, user_id)

    async def post_photo(self, user_id: str, file: UploadFile, caption: str, timezone_str: str = "UTC") -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        local_path = os.path.join(self.storage_path, unique_filename)
        
        content = await file.read()
        with open(local_path, "wb") as f:
            f.write(content)
            
        file_url = f"/uploads/{unique_filename}"
        
        new_doc = {
            "category": ThreadCategory.PHOTO,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {"file_url": file_url, "caption": caption},
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, timezone_str, user_id)

    async def ask_prompt(self, user_id: str, payload: PromptAskCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        new_doc = {
            "category": ThreadCategory.PROMPT,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {
                "prompt_type": payload.prompt_type,
                "question": payload.question_text,
                "type": payload.type,
                "answer": None,
                "status": "asked"
            },
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, payload.timezone, user_id)

    async def reply_to_prompt(self, user_id: str, message_id: str, answer: str, timezone_str: str = "UTC") -> Dict[str, Any]:
        doc = await self.messages_collection.find_one({"_id": ObjectId(message_id), "partner_id": user_id})
        if not doc:
            raise ValueError("Prompt not found or you are not the recipient.")
        
        if doc["content"].get("status") == "replied":
            raise ValueError("This prompt has already been replied to.")

        result = await self.messages_collection.find_one_and_update(
            {"_id": ObjectId(message_id)},
            {"$set": {
                "content.answer": answer,
                "content.status": "replied",
                "is_seen": True, # Replied implies seen
                "is_delivered": True,
                "updated_at": datetime.now(timezone.utc)
            }},
            return_document=True
        )
        return await self._map_message(result, timezone_str, user_id)

    async def post_appreciation(self, user_id: str, payload: AppreciationCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        new_doc = {
            "category": ThreadCategory.APPRECIATION,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {"text": payload.text},
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, payload.timezone, user_id)

    async def post_checkin(self, user_id: str, payload: CheckInThreadCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id: raise ValueError("Partner alignment required.")
        
        new_doc = {
            "category": ThreadCategory.CHECKIN,
            "creator_id": user_id,
            "partner_id": partner_id,
            "content": {
                "date": payload.date,
                "answer_1": payload.answer_1,
                "answer_2": payload.answer_2,
                "answer_3": payload.answer_3
            },
            "created_at": datetime.now(timezone.utc),
            "is_sent": True,
            "is_delivered": False,
            "is_seen": False
        }
        result = await self.messages_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_message(new_doc, payload.timezone, user_id)

    async def get_messages(self, user_id: str, page: int = 1, size: int = 20, timezone_str: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id: user_ids.append(partner_id)
        
        query = {"creator_id": {"$in": user_ids}}
        
        # Advanced Feature: Mark received messages as delivered & seen when fetched
        await self.messages_collection.update_many(
            {"partner_id": user_id, "is_seen": False},
            {"$set": {"is_delivered": True, "is_seen": True}}
        )

        skip = (page - 1) * size
        cursor = self.messages_collection.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.messages_collection.count_documents(query)
        
        return [await self._map_message(d, timezone_str, user_id) for d in docs], total

    async def delete_message(self, user_id: str, message_id: str) -> bool:
        doc = await self.messages_collection.find_one({"_id": ObjectId(message_id), "creator_id": user_id})
        if not doc:
            return False
            
        # Delete file if exists
        file_url = doc.get("content", {}).get("file_url")
        if file_url:
            local_path = file_url.lstrip("/")
            if os.path.exists(local_path):
                os.remove(local_path)
                
        result = await self.messages_collection.delete_one({"_id": ObjectId(message_id)})
        return result.deleted_count > 0

    async def update_message(self, user_id: str, message_id: str, updates: Dict[str, Any], file: Optional[UploadFile] = None, timezone_str: str = "UTC") -> Dict[str, Any]:
        doc = await self.messages_collection.find_one({"_id": ObjectId(message_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Message not found or permission denied.")

        category = doc["category"]
        content_updates = {}
        
        if category == ThreadCategory.LETTER:
            if "text" in updates: content_updates["text"] = updates["text"]
        elif category == ThreadCategory.APPRECIATION:
            if "text" in updates: content_updates["text"] = updates["text"]
        elif category == ThreadCategory.PHOTO:
            if "caption" in updates: content_updates["caption"] = updates["caption"]
            if file:
                # Delete old file
                old_file = doc["content"].get("file_url")
                if old_file:
                    lp = old_file.lstrip("/")
                    if os.path.exists(lp): os.remove(lp)
                
                ext = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                local_path = os.path.join(self.storage_path, unique_filename)
                with open(local_path, "wb") as f: f.write(await file.read())
                content_updates["file_url"] = f"/uploads/{unique_filename}"
        elif category == ThreadCategory.VOICE:
            if file:
                old_file = doc["content"].get("file_url")
                if old_file:
                    lp = old_file.lstrip("/")
                    if os.path.exists(lp): os.remove(lp)
                
                ext = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                local_path = os.path.join(self.storage_path, unique_filename)
                with open(local_path, "wb") as f: f.write(await file.read())
                content_updates["file_url"] = f"/uploads/{unique_filename}"
        elif category == ThreadCategory.PROMPT:
            if doc["content"].get("status") == "replied":
                raise ValueError("Cannot update a prompt that has already been replied to.")
            if "prompt_type" in updates: content_updates["prompt_type"] = updates["prompt_type"]
            if "question" in updates: content_updates["question"] = updates["question"]
            if "type" in updates: content_updates["type"] = updates["type"]
        elif category == ThreadCategory.CHECKIN:
            for k in ["answer_1", "answer_2", "answer_3", "date"]:
                if k in updates: content_updates[k] = updates[k]

        if not content_updates:
            return await self._map_message(doc, timezone_str, user_id)

        # Merge updates into content
        new_content = doc["content"].copy()
        new_content.update(content_updates)

        result = await self.messages_collection.find_one_and_update(
            {"_id": ObjectId(message_id)},
            {"$set": {"content": new_content, "updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_message(result, timezone_str, user_id)

    async def _map_message(self, d: Dict[str, Any], timezone_str: str, current_user_id: str) -> Dict[str, Any]:
        d["id"] = str(d["_id"]) if "_id" in d else d.get("id")
        if "_id" in d: del d["_id"]
        
        partner_id = await self._get_partner_id(d["creator_id"])
        names = await self._get_names(d["creator_id"], partner_id or "")
        
        # Identify Names
        u_name = names.get(current_user_id, "User")
        p_name = "Partner"
        for uid, name in names.items():
            if uid != current_user_id:
                p_name = name
                break

        d["user_name"] = u_name
        d["partner_name"] = p_name
        d["sender_name"] = names.get(d["creator_id"], "User")
        d["sender_id"] = d["creator_id"]
        
        # Status defaults for backward compatibility or safety
        d["is_sent"] = d.get("is_sent", True)
        d["is_delivered"] = d.get("is_delivered", False)
        d["is_seen"] = d.get("is_seen", False)

        try:
            tz = zoneinfo.ZoneInfo(timezone_str)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
            
        dt = d["created_at"]
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        d["created_at"] = dt.astimezone(tz)
        
        return d

    # --- Prompt Question CRUD ---
    async def get_prompt_questions(self, user_id: str, prompt_type: PromptType) -> List[Dict[str, Any]]:
        partner_id = await self._get_partner_id(user_id)
        creator_ids = [None, user_id]
        if partner_id: creator_ids.append(partner_id)
        
        query = {"type": prompt_type, "creator_id": {"$in": creator_ids}}
        cursor = self.prompts_collection.find(query)
        docs = await cursor.to_list(length=None)
        
        # Add defaults if not already in DB or for the first time
        if not docs:
            defaults = DEFAULT_ROMANTIC_QUESTIONS if prompt_type == PromptType.ROMANTIC else DEFAULT_DESIRED_QUESTIONS
            for q in defaults:
                q_copy = q.copy()
                q_copy["creator_id"] = None
                await self.prompts_collection.update_one(
                    {"text": q_copy["text"], "type": q_copy["type"], "creator_id": None},
                    {"$setOnInsert": q_copy},
                    upsert=True
                )
            cursor = self.prompts_collection.find(query)
            docs = await cursor.to_list(length=None)

        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
        return docs

    async def create_prompt_question(self, user_id: str, payload: PromptQuestionCreate) -> Dict[str, Any]:
        new_doc = payload.model_dump()
        new_doc["creator_id"] = user_id
        result = await self.prompts_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def update_prompt_question(self, user_id: str, question_id: str, payload: PromptQuestionCreate) -> Dict[str, Any]:
        result = await self.prompts_collection.find_one_and_update(
            {"_id": ObjectId(question_id), "creator_id": user_id},
            {"$set": payload.model_dump()},
            return_document=True
        )
        if not result: raise ValueError("Question not found or permission denied.")
        result["id"] = str(result["_id"])
        del result["_id"]
        return result

    async def delete_prompt_question(self, user_id: str, question_id: str) -> bool:
        result = await self.prompts_collection.delete_one({"_id": ObjectId(question_id), "creator_id": user_id})
        return result.deleted_count > 0

thread_service = ThreadService()
