import random
import string
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from app.core.config import settings
from app.schemas.vibe_check import VibeCheckProfileCreate, VibeInviteResponse, VibeInviteValidateResponse, VibeInviteAcceptResponse

class VibeCheckService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.profiles = self.db["vibe_check_profiles"]
        self.connections = self.db["vibe_check_connections"]
        self.requests = self.db["vibe_check_requests"]
        self.invites = self.db["vibe_check_invites"]
        self.cumulative_scores = self.db["vibe_cumulative_scores"]
        self.user_streaks = self.db["vibe_user_streaks"]

    async def init_indexes(self):
        await self.profiles.create_index("user_id", unique=True)
        await self.profiles.create_index("vibe_key", unique=True)
        await self.connections.create_index([("user_id", 1), ("partner_id", 1)], unique=True)
        await self.requests.create_index([("sender_id", 1), ("recipient_id", 1)], unique=True)
        await self.requests.create_index("recipient_id")
        await self.invites.create_index("invite_code", unique=True)
        await self.invites.create_index("inviter_id")

    async def generate_unique_vibe_key(self) -> str:
        """Generates a unique 12-character vibe key like VIBE-X7R2P9."""
        while True:
            random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            vibe_key = f"VIBE-{random_part}"
            existing = await self.profiles.find_one({"vibe_key": vibe_key})
            if not existing:
                return vibe_key

    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        
        # Update user's last activity whenever they fetch their profile
        # This allows us to track "active" users
        doc = await self.profiles.find_one_and_update(
            {"user_id": user_id},
            {"$set": {"updated_at": now}},
            return_document=True
        )
        
        if doc:
            # AUTO-FIX: If vibe_key is missing for some reason, generate and save it
            if not doc.get("vibe_key"):
                vibe_key = await self.generate_unique_vibe_key()
                await self.profiles.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"vibe_key": vibe_key}}
                )
                doc["vibe_key"] = vibe_key
            
            # 1. Count connections (connect)
            connect_count = await self.connections.count_documents({"user_id": user_id})
            
            # 2. Categorize partners (active vs inactive) - Threshold: 15 minutes
            active_threshold = now - timedelta(minutes=15)
            
            # Fetch all partner IDs for this user
            cursor = self.connections.find({"user_id": user_id}, {"partner_id": 1})
            connection_docs = await cursor.to_list(length=None)
            partner_ids = [c["partner_id"] for c in connection_docs]
            
            active_users = []
            inactive_users = []
            
            if partner_ids:
                # Fetch all partner profiles
                partner_profiles_cursor = self.profiles.find({"user_id": {"$in": partner_ids}})
                partner_profiles = await partner_profiles_cursor.to_list(length=None)
                
                for p in partner_profiles:
                    p_id = p["user_id"]
                    
                    # 1. Determine activity
                    last_active = p.get("updated_at")
                    if last_active and last_active.tzinfo is None:
                        last_active = last_active.replace(tzinfo=timezone.utc)
                    
                    is_active = last_active and last_active >= active_threshold
                    
                    # 2. Get match percentage
                    score_doc = await self.cumulative_scores.find_one({
                        "user_id": user_id, 
                        "partner_id": p_id
                    })
                    match_percentage = round(score_doc["score"], 1) if score_doc else 0.0
                    
                    # 3. Get partner's streak
                    streak_doc = await self.user_streaks.find_one({"user_id": p_id})
                    streak_days = streak_doc["current_streak"] if streak_doc else 0
                    
                    stats = {
                        "name": p["name"],
                        "match_percentage": match_percentage,
                        "streak_days": streak_days
                    }
                    
                    if is_active:
                        active_users.append(stats)
                    else:
                        inactive_users.append(stats)
                
            doc["id"] = str(doc["_id"])
            doc["connect"] = connect_count
            doc["active"] = len(active_users)
            doc["active_users"] = active_users
            doc["inactive"] = len(inactive_users)
            doc["inactive_users"] = inactive_users
            return doc
        return None

    async def create_or_update_profile(self, user_id: str, payload: VibeCheckProfileCreate) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        existing = await self.profiles.find_one({"user_id": user_id})
        
        if existing:
            update_data = {"name": payload.name, "updated_at": now}
            if not existing.get("vibe_key"):
                update_data["vibe_key"] = await self.generate_unique_vibe_key()
                
            await self.profiles.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
        else:
            vibe_key = await self.generate_unique_vibe_key()
            doc = {
                "user_id": user_id,
                "name": payload.name,
                "vibe_key": vibe_key,
                "created_at": now,
                "updated_at": now
            }
            await self.profiles.insert_one(doc)

        return await self.get_profile(user_id)

    async def get_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """List all people this user is connected with in VibeCheck."""
        cursor = self.connections.find({"user_id": user_id})
        connection_docs = await cursor.to_list(length=None)
        
        partner_ids = [c["partner_id"] for c in connection_docs]
        partner_profiles = await self.profiles.find({"user_id": {"$in": partner_ids}}).to_list(length=None)
        profile_map = {p["user_id"]: p["name"] for p in partner_profiles}
        
        results = []
        for c in connection_docs:
            results.append({
                "user_id": c["partner_id"],
                "name": profile_map.get(c["partner_id"], "Unknown User"),
                "connected_at": c["connected_at"]
            })
        return results

    async def connect_with_partner(self, user_id: str, vibe_key: str) -> Dict[str, Any]:
        """Create a pending connection request using a Vibe Key."""
        # 1. Fetch initiator profile
        initiator = await self.profiles.find_one({"user_id": user_id})
        if not initiator:
            raise ValueError("Your VibeCheck profile is not setup.")

        # 2. Fetch target profile
        target = await self.profiles.find_one({"vibe_key": vibe_key})
        if not target:
            raise ValueError("User with this Vibe Key not found.")
            
        if target["user_id"] == user_id:
            raise ValueError("You cannot connect with yourself.")

        # 3. Check if already connected
        existing_conn = await self.connections.find_one({"user_id": user_id, "partner_id": target["user_id"]})
        if existing_conn:
            raise ValueError(f"You are already connected with {target['name']}.")

        now = datetime.now(timezone.utc)
        
        # 4. Create pending request
        await self.requests.update_one(
            {"sender_id": user_id, "recipient_id": target["user_id"]},
            {"$setOnInsert": {
                "sender_id": user_id, 
                "recipient_id": target["user_id"], 
                "sender_name": initiator["name"],
                "created_at": now
            }},
            upsert=True
        )

        return {"success": True, "message": f"Connection request sent to {target['name']}."}

    async def get_pending_requests(self, user_id: str) -> List[Dict[str, Any]]:
        """List all pending connection requests for this user."""
        cursor = self.requests.find({"recipient_id": user_id})
        docs = await cursor.to_list(length=None)
        
        results = []
        for d in docs:
            results.append({
                "request_id": str(d["_id"]),
                "sender_id": d["sender_id"],
                "sender_name": d["sender_name"],
                "created_at": d["created_at"]
            })
        return results

    async def respond_to_request(self, user_id: str, request_id: str, accept: bool) -> Dict[str, Any]:
        """Accept or reject a pending connection request."""
        request = await self.requests.find_one({"_id": ObjectId(request_id), "recipient_id": user_id})
        if not request:
            raise ValueError("Request not found.")

        if accept:
            now = datetime.now(timezone.utc)
            # Create mutual connections
            # Recipient -> Sender
            await self.connections.update_one(
                {"user_id": user_id, "partner_id": request["sender_id"]},
                {"$setOnInsert": {"user_id": user_id, "partner_id": request["sender_id"], "connected_at": now}},
                upsert=True
            )
            # Sender -> Recipient
            await self.connections.update_one(
                {"user_id": request["sender_id"], "partner_id": user_id},
                {"$setOnInsert": {"user_id": request["sender_id"], "partner_id": user_id, "connected_at": now}},
                upsert=True
            )
            message = "Connection accepted."
        else:
            message = "Connection request rejected."

        # Delete the request
        await self.requests.delete_one({"_id": ObjectId(request_id)})
        
        return {"success": True, "message": message}

    async def delete_connection(self, user_id: str, partner_id: str) -> bool:
        """Remove a mutual connection between two users."""
        # A -> B
        res1 = await self.connections.delete_one({"user_id": user_id, "partner_id": partner_id})
        # B -> A
        res2 = await self.connections.delete_one({"user_id": partner_id, "partner_id": user_id})
        return res1.deleted_count > 0 or res2.deleted_count > 0

    async def regenerate_vibe_key(self, user_id: str) -> str:
        """Generate a new unique vibe key for the user."""
        new_key = await self.generate_unique_vibe_key()
        result = await self.profiles.update_one(
            {"user_id": user_id},
            {"$set": {"vibe_key": new_key, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise ValueError("VibeCheck profile not found.")
        return new_key

    # --- Invite System ---

    async def generate_invite(self, user_id: str) -> VibeInviteResponse:
        """Generates a secure unique invite code and link."""
        # Check if user has a profile
        profile = await self.get_profile(user_id)
        if not profile:
            raise ValueError("Your VibeCheck profile is not setup.")

        # Rate limiting: Check if user has generated too many invites recently (optional, but requested)
        # For simplicity, let's just limit to 10 active invites per user
        active_count = await self.invites.count_documents({
            "inviter_id": user_id, 
            "status": "pending", 
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        if active_count >= 10:
            raise ValueError("You have too many active invites. Please wait for them to expire or be used.")

        while True:
            invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            existing = await self.invites.find_one({"invite_code": invite_code})
            if not existing:
                break
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)
        
        invite_doc = {
            "invite_code": invite_code,
            "inviter_id": user_id,
            "inviter_name": profile["name"],
            "created_at": now,
            "expires_at": expires_at,
            "status": "pending",
            "used_by": None,
            "used_at": None
        }
        await self.invites.insert_one(invite_doc)
        
        invite_link = f"{settings.FRONTEND_URL}/invite/{invite_code}"
        
        return VibeInviteResponse(invite_code=invite_code, invite_link=invite_link)

    async def validate_invite(self, invite_code: str) -> VibeInviteValidateResponse:
        """Verify invite exists and is not expired."""
        invite = await self.invites.find_one({"invite_code": invite_code})
        if not invite:
            return VibeInviteValidateResponse(valid=False, inviter_name="")
            
        now = datetime.now(timezone.utc)
        expires_at = invite["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if invite["status"] != "pending" or expires_at < now:
            return VibeInviteValidateResponse(valid=False, inviter_name=invite["inviter_name"])
            
        return VibeInviteValidateResponse(
            valid=True, 
            inviter_name=invite["inviter_name"],
            inviter_profile_picture=invite.get("inviter_profile_picture")
        )

    async def accept_invite(self, user_id: str, invite_code: str) -> VibeInviteAcceptResponse:
        """Accept an invite and create connection."""
        invite = await self.invites.find_one({"invite_code": invite_code})
        if not invite:
            raise ValueError("Invalid invite code.")
            
        if invite["inviter_id"] == user_id:
            raise ValueError("You cannot accept your own invite.")
            
        now = datetime.now(timezone.utc)
        expires_at = invite["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if invite["status"] != "pending" or expires_at < now:
            raise ValueError("Invite has expired or already been used.")
            
        # Ensure user has a profile
        me = await self.get_profile(user_id)
        if not me:
            raise ValueError("Your VibeCheck profile is not setup. Please setup your profile first.")

        # Ensure not already connected
        existing_conn = await self.connections.find_one({"user_id": user_id, "partner_id": invite["inviter_id"]})
        if existing_conn:
            # Mark invite as used anyway if they are already connected? 
            # Or just throw error. Usually better to throw error.
            raise ValueError("You are already connected with this user.")

        # Create mutual connections
        # Me -> Inviter
        await self.connections.update_one(
            {"user_id": user_id, "partner_id": invite["inviter_id"]},
            {"$setOnInsert": {"user_id": user_id, "partner_id": invite["inviter_id"], "connected_at": now}},
            upsert=True
        )
        # Inviter -> Me
        await self.connections.update_one(
            {"user_id": invite["inviter_id"], "partner_id": user_id},
            {"$setOnInsert": {"user_id": invite["inviter_id"], "partner_id": user_id, "connected_at": now}},
            upsert=True
        )
        
        # Mark invite as used
        await self.invites.update_one(
            {"invite_code": invite_code},
            {"$set": {
                "status": "used",
                "used_by": user_id,
                "used_at": now
            }}
        )
        
        return VibeInviteAcceptResponse(
            success=True, 
            message=f"You are now connected with {invite['inviter_name']}!",
            partner_id=invite["inviter_id"],
            partner_name=invite["inviter_name"]
        )

vibe_check_service = VibeCheckService()
