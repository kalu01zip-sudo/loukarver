import zoneinfo
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.vibe_dates import VibeDateCreate, VibeDateUpdate, VibeDateRespondRequest, DateStatus
from app.services.vibe_check import vibe_check_service
from app.services.notification import notification_service
from app.schemas.notification import NotificationCreate, NotificationType

class VibeDateService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.dates = self.db["vibe_dates"]
        self.connections = self.db["vibe_check_connections"]
        self.profiles = self.db["vibe_check_profiles"]

    async def init_indexes(self):
        await self.dates.create_index("proposer_id")
        await self.dates.create_index("partner_id")

    async def _map_date(self, d: Dict[str, Any], user_timezone: str) -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        if "_id" in d: del d["_id"]

        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        for field in ["created_at", "updated_at"]:
            dt = d.get(field)
            if isinstance(dt, datetime):
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)

        return d

    async def propose_date(self, user_id: str, payload: VibeDateCreate) -> Dict[str, Any]:
        # 1. Verify partner connection
        is_connected = await self.connections.find_one({
            "user_id": user_id, 
            "partner_id": payload.partner_id
        })
        if not is_connected:
            raise ValueError("You can only propose dates to your Vibe partners.")

        # 2. Get names for convenience
        me = await vibe_check_service.get_profile(user_id)
        partner = await vibe_check_service.get_profile(payload.partner_id)
        
        now = datetime.now(timezone.utc)
        date_doc = payload.model_dump()
        date_doc.update({
            "proposer_id": user_id,
            "proposer_name": me["name"],
            "partner_name": partner["name"],
            "status": DateStatus.PENDING,
            "last_updated_by": user_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await self.dates.insert_one(date_doc)
        return await self._map_date(date_doc, payload.timezone)

    async def get_dates(self, user_id: str, user_timezone: str = "UTC", page: int = 1, size: int = 20) -> tuple[List[Dict[str, Any]], int]:
        query = {"$or": [{"proposer_id": user_id}, {"partner_id": user_id}]}
        skip = (page - 1) * size
        
        cursor = self.dates.find(query).sort("updated_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.dates.count_documents(query)
        
        results = [await self._map_date(d, user_timezone) for d in docs]
        return results, total

    async def get_date_by_id(self, date_id: str, user_id: str, user_timezone: str = "UTC") -> Dict[str, Any]:
        doc = await self.dates.find_one({"_id": ObjectId(date_id)})
        if not doc:
            raise ValueError("Date proposal not found.")
        if doc["proposer_id"] != user_id and doc["partner_id"] != user_id:
            raise PermissionError("You do not have permission to view this date.")
        return await self._map_date(doc, user_timezone)

    async def update_date(self, user_id: str, date_id: str, payload: VibeDateUpdate) -> Dict[str, Any]:
        date_doc = await self.get_date_by_id(date_id, user_id)
        
        if date_doc["proposer_id"] != user_id:
             raise PermissionError("Only the proposer can edit the date details directly.")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return date_doc

        now = datetime.now(timezone.utc)
        old_status = date_doc["status"]
        new_status = old_status

        # If already accepted, reset to pending and notify
        if old_status == DateStatus.ACCEPTED:
            new_status = DateStatus.PENDING
            await notification_service.schedule_notification(user_id, NotificationCreate(
                recipient_id=date_doc["partner_id"],
                type=NotificationType.VIBE_DATE,
                title="Date Proposal Updated",
                message=f"{date_doc['proposer_name']} updated the details for your date at {date_doc['where']}. Please re-confirm.",
                scheduled_for=now,
                timezone=date_doc["timezone"]
            ))

        updates.update({
            "status": new_status,
            "last_updated_by": user_id,
            "updated_at": now
        })
        
        await self.dates.update_one({"_id": ObjectId(date_id)}, {"$set": updates})
        return await self.get_date_by_id(date_id, user_id, payload.timezone or date_doc["timezone"])

    async def respond_to_date(self, user_id: str, date_id: str, payload: VibeDateRespondRequest) -> Dict[str, Any]:
        date_doc = await self.get_date_by_id(date_id, user_id)
        now = datetime.now(timezone.utc)
        me = await vibe_check_service.get_profile(user_id)

        is_proposer = date_doc["proposer_id"] == user_id
        is_partner = date_doc["partner_id"] == user_id

        if payload.action == DateStatus.ACCEPTED:
            # If partner accepts a PENDING or original proposer accepts PROPOSED_CHANGES
            if (is_partner and date_doc["status"] == DateStatus.PENDING) or \
               (is_proposer and date_doc["status"] == DateStatus.PROPOSED_CHANGES):
                
                await self.dates.update_one(
                    {"_id": ObjectId(date_id)},
                    {"$set": {
                        "status": DateStatus.ACCEPTED,
                        "updated_at": now,
                        "last_updated_by": user_id
                    }}
                )
                
                # Notify the other person
                recipient_id = date_doc["proposer_id"] if is_partner else date_doc["partner_id"]
                await notification_service.schedule_notification(user_id, NotificationCreate(
                    recipient_id=recipient_id,
                    type=NotificationType.VIBE_DATE,
                    title="Date Accepted!",
                    message=f"{me['name']} accepted the date proposal for {date_doc['where']}!",
                    scheduled_for=now,
                    timezone=date_doc["timezone"]
                ))
            else:
                raise ValueError("Invalid action for current date status.")

        elif payload.action == DateStatus.REJECTED:
            await self.dates.update_one(
                {"_id": ObjectId(date_id)},
                {"$set": {
                    "status": DateStatus.REJECTED,
                    "updated_at": now,
                    "last_updated_by": user_id
                }}
            )
            # Notify
            recipient_id = date_doc["proposer_id"] if is_partner else date_doc["partner_id"]
            await notification_service.schedule_notification(user_id, NotificationCreate(
                recipient_id=recipient_id,
                type=NotificationType.VIBE_DATE,
                title="Date Rejected",
                message=f"{me['name']} rejected/cancelled the date proposal.",
                scheduled_for=now,
                timezone=date_doc["timezone"]
            ))

        elif payload.action == DateStatus.PROPOSED_CHANGES:
            if not is_partner:
                raise PermissionError("Only the partner can recommend changes.")
            
            updates = payload.model_dump(exclude_unset=True, exclude={"action"})
            if not updates:
                 raise ValueError("Please provide at least one field to change.")
            
            updates.update({
                "status": DateStatus.PROPOSED_CHANGES,
                "last_updated_by": user_id,
                "updated_at": now
            })
            
            await self.dates.update_one({"_id": ObjectId(date_id)}, {"$set": updates})
            
            # Notify proposer
            await notification_service.schedule_notification(user_id, NotificationCreate(
                recipient_id=date_doc["proposer_id"],
                type=NotificationType.VIBE_DATE,
                title="Changes Proposed for Date",
                message=f"{me['name']} recommended some changes for the date at {date_doc['where']}.",
                scheduled_for=now,
                timezone=date_doc["timezone"]
            ))

        return await self.get_date_by_id(date_id, user_id, date_doc["timezone"])

    async def delete_date(self, user_id: str, date_id: str) -> bool:
        date_doc = await self.get_date_by_id(date_id, user_id)
        # Allow either party to delete/cancel? 
        # Usually only the proposer can fully delete, or partner can reject.
        # Let's allow either to delete for simplicity of CRUD.
        result = await self.dates.delete_one({"_id": ObjectId(date_id)})
        return result.deleted_count > 0

vibe_date_service = VibeDateService()
