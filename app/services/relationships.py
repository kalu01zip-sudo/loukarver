import random
import string
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.schemas.relationships import RelationshipCreate

class RelationshipService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.collection = self.db["users"]

    async def get_all_relationships(self) -> List[Dict[str, Any]]:
        """Retrieves all registered relationships from the MongoDB collection."""
        try:
            cursor = self.collection.find({})
            results = await cursor.to_list(length=None)
            # Convert ObjectId _id to string for JSON serialization compatibility
            for result in results:
                if "_id" in result:
                    result["id"] = str(result["_id"])
                    result["_id"] = str(result["_id"])
            return results
        except Exception as e:
            raise e

    async def generate_unique_secret_key(self) -> str:
        """Generates a unique 16-character secret key like ALIGNED-Y8BSV1AB."""
        while True:
            random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            secret_key = f"ALIGNED-{random_part}"
            
            # Check uniqueness in MongoDB
            existing = await self.collection.find_one({"secret_key": secret_key})
            if not existing:
                return secret_key

    async def save_relationship(self, relationship: RelationshipCreate) -> Dict[str, Any]:
        """Saves a new relationship to MongoDB with a unique secret key."""
        secret_key = await self.generate_unique_secret_key()
        
        new_data = {
            "name": relationship.name,
            "city_name": relationship.city_name,
            "relationship_start_date": relationship.relationship_start_date,
            "is_long_distance": relationship.is_long_distance,
            "secret_key": secret_key,
            "is_aligned": False,
            "partner": None
        }
        
        await self.collection.insert_one(new_data)
        
        # Convert ObjectId _id to string for serializability
        if "_id" in new_data:
            new_data["id"] = str(new_data["_id"])
            new_data["_id"] = str(new_data["_id"])
            
        return new_data

    async def align_users(self, user_id: str, partner_secret_key: str) -> Dict[str, Any]:
        """Connects the initiating user with another user using the partner's secret key."""
        from bson import ObjectId
        
        # 1. Fetch initiator
        initiator = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not initiator:
            raise ValueError("User not found.")
            
        # 2. Fetch partner using secret key
        partner = await self.collection.find_one({"secret_key": partner_secret_key})
        if not partner:
            raise ValueError("Partner with specified secret key not found.")
            
        # 3. Check already aligned state
        if initiator.get("is_aligned"):
            raise ValueError("You are already connected to a partner.")
        if partner.get("is_aligned"):
            raise ValueError("The partner is already connected to another user.")
            
        # 4. Check if self-connect attempt
        if str(initiator["_id"]) == str(partner["_id"]):
            raise ValueError("Cannot connect to your own secret key.")
            
        # 5. Connect initiator to partner
        await self.collection.update_one(
            {"_id": initiator["_id"]},
            {
                "$set": {
                    "is_aligned": True,
                    "secret_key": None, # Disable secret key
                    "partner": {
                        "user_id": str(partner["_id"]),
                        "name": partner["name"],
                        "city_name": partner["city_name"],
                        "relationship_start_date": partner["relationship_start_date"],
                        "is_long_distance": partner["is_long_distance"]
                    }
                }
            }
        )
        
        # 6. Connect partner to initiator
        await self.collection.update_one(
            {"_id": partner["_id"]},
            {
                "$set": {
                    "is_aligned": True,
                    "secret_key": None, # Disable secret key
                    "partner": {
                        "user_id": str(initiator["_id"]),
                        "name": initiator["name"],
                        "city_name": initiator["city_name"],
                        "relationship_start_date": initiator["relationship_start_date"],
                        "is_long_distance": initiator["is_long_distance"]
                    }
                }
            }
        )
        
        # Fetch and return updated initiator data
        updated_initiator = await self.collection.find_one({"_id": initiator["_id"]})
        if updated_initiator and "_id" in updated_initiator:
            updated_initiator["id"] = str(updated_initiator["_id"])
            updated_initiator["_id"] = str(updated_initiator["_id"])
            
        return updated_initiator

    async def update_relationship_profile(self, user_id: str, relationship: RelationshipCreate) -> Dict[str, Any]:
        """Updates an existing user's profile with relationship details."""
        from bson import ObjectId
        
        # Verify user exists
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found.")
            
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "name": relationship.name,
                    "city_name": relationship.city_name,
                    "relationship_start_date": relationship.relationship_start_date,
                    "is_long_distance": relationship.is_long_distance
                }
            }
        )
        
        updated = await self.collection.find_one({"_id": ObjectId(user_id)})
        if updated and "_id" in updated:
            updated["id"] = str(updated["_id"])
            updated["_id"] = str(updated["_id"])
            
        return updated

    async def break_alignment(self, user_id: str) -> Dict[str, Any]:
        """Breaks the connection for the user and their partner."""
        from bson import ObjectId
        
        # 1. Fetch initiator
        initiator = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not initiator:
            raise ValueError("User not found.")
            
        if not initiator.get("is_aligned"):
            raise ValueError("You are not connected to anyone.")
            
        partner_id = initiator.get("partner", {}).get("user_id")
        
        # 2. Update initiator
        updates = {
            "$set": {
                "is_aligned": False,
                "partner": None
            }
        }
        
        # If secret_key doesn't exist (e.g. older user who had it deleted), generate a new one
        if not initiator.get("secret_key"):
            secret_key = await self.generate_unique_secret_key()
            updates["$set"]["secret_key"] = secret_key
            
        await self.collection.update_one(
            {"_id": initiator["_id"]},
            updates
        )
        
        # 3. Update partner if exists
        if partner_id:
            partner = await self.collection.find_one({"_id": ObjectId(partner_id)})
            if partner:
                partner_updates = {
                    "$set": {
                        "is_aligned": False,
                        "partner": None
                    }
                }
                if not partner.get("secret_key"):
                    partner_secret = await self.generate_unique_secret_key()
                    partner_updates["$set"]["secret_key"] = partner_secret
                    
                await self.collection.update_one(
                    {"_id": partner["_id"]},
                    partner_updates
                )
            
        # 4. Fetch and return updated initiator data
        updated_initiator = await self.collection.find_one({"_id": initiator["_id"]})
        if updated_initiator and "_id" in updated_initiator:
            updated_initiator["id"] = str(updated_initiator["_id"])
            updated_initiator["_id"] = str(updated_initiator["_id"])
            
        return updated_initiator

    async def align_users_mutually(self, user_id: str, partner_id: str) -> bool:
        """Directly aligns two users (mutually). Clears secret keys for both."""
        from bson import ObjectId
        
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        partner = await self.collection.find_one({"_id": ObjectId(partner_id)})
        
        if not user or not partner:
            return False
            
        if user.get("is_aligned") or partner.get("is_aligned"):
            # If already aligned with the SAME partner, it's fine (idempotent)
            if user.get("partner", {}).get("user_id") == partner_id:
                return True
            return False

        # Connect both
        await self.collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "is_aligned": True,
                "secret_key": None,
                "partner": {
                    "user_id": str(partner["_id"]),
                    "name": partner["name"],
                    "city_name": partner["city_name"],
                    "relationship_start_date": partner["relationship_start_date"],
                    "is_long_distance": partner["is_long_distance"]
                }
            }}
        )
        await self.collection.update_one(
            {"_id": partner["_id"]},
            {"$set": {
                "is_aligned": True,
                "secret_key": None,
                "partner": {
                    "user_id": str(user["_id"]),
                    "name": user["name"],
                    "city_name": user["city_name"],
                    "relationship_start_date": user["relationship_start_date"],
                    "is_long_distance": user["is_long_distance"]
                }
            }}
        )
        return True

    async def get_relationship_profile(self, user_id: str) -> Dict[str, Any]:
        """Retrieves a user's relationship profile."""
        from bson import ObjectId
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found.")
            
        if "_id" in user:
            user["id"] = str(user["_id"])
            user["_id"] = str(user["_id"])
            
        return user

relationship_service = RelationshipService()
