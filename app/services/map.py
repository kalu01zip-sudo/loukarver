import os
import uuid
import zoneinfo
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from fastapi import UploadFile

from app.core.config import settings
from app.schemas.map import (
    PlaceCreate, PlaceUpdate, PlaceCategory, MomentCreate, MomentType
)

class MapService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.places_collection = self.db["map_places"]
        self.users = self.db["users"]
        self.storage_path = "uploads"
        
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    async def init_indexes(self):
        await self.places_collection.create_index([("creator_id", 1), ("partner_id", 1)])
        await self.places_collection.create_index("category")
        await self.places_collection.create_index("city")

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

    async def _geocode(self, city: str, country: str) -> Tuple[float, float]:
        """Extremely resilient geocoding with multiple providers and fallback logic."""
        if not city or not country:
            return 0.0, 0.0

        # Nominatim policy: 1 req/sec. We add a small artificial delay to be safe
        await asyncio.sleep(1.0) 

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AlignedTracker/1.0",
            "Accept-Language": "en"
        }

        providers = [
            # Provider 1: Nominatim (Primary)
            {
                "url": "https://nominatim.openstreetmap.org/search",
                "params": {"q": f"{city}, {country}", "format": "json", "limit": 1}
            },
            # Provider 2: geocode.maps.co (Secondary Fallback)
            {
                "url": "https://geocode.maps.co/search",
                "params": {"q": f"{city} {country}"}
            }
        ]

        async with httpx.AsyncClient(timeout=15.0, verify=False) as client: # verify=False for local testing if needed
            for provider in providers:
                try:
                    response = await client.get(provider["url"], params=provider["params"], headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            return float(data[0]["lat"]), float(data[0]["lon"])
                except Exception as e:
                    print(f"Geocoding provider {provider['url']} failed: {str(e)}")
                    continue
        
        return 0.0, 0.0

    async def create_place(self, user_id: str, payload: PlaceCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id:
            raise ValueError("Partner alignment required.")

        lat, lng = await self._geocode(payload.city, payload.country)
        
        new_doc = payload.model_dump()
        new_doc["creator_id"] = user_id
        new_doc["partner_id"] = partner_id
        new_doc["lat"] = lat
        new_doc["lng"] = lng
        new_doc["moments"] = []
        new_doc["created_at"] = datetime.now(timezone.utc)
        new_doc["updated_at"] = datetime.now(timezone.utc)

        result = await self.places_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_place(new_doc, payload.timezone, user_id)

    async def get_places(self, user_id: str, category: Optional[PlaceCategory] = None, search: Optional[str] = None, page: int = 1, size: int = 20, user_timezone: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        query = {"$or": [{"creator_id": user_id}, {"partner_id": user_id}]}
        
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"city": {"$regex": search, "$options": "i"}},
                {"country": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]

        skip = (page - 1) * size
        cursor = self.places_collection.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.places_collection.count_documents(query)

        results = []
        for d in docs:
            results.append(await self._map_place(d, user_timezone, user_id))
        return results, total

    async def get_place_by_id(self, place_id: str, user_id: str, user_timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        doc = await self.places_collection.find_one({
            "_id": ObjectId(place_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if doc:
            return await self._map_place(doc, user_timezone, user_id)
        return None

    async def update_place(self, place_id: str, user_id: str, payload: PlaceUpdate) -> Dict[str, Any]:
        doc = await self.places_collection.find_one({"_id": ObjectId(place_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Place not found or permission denied.")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return await self._map_place(doc, payload.timezone, user_id)

        if "city" in updates or "country" in updates:
            city = updates.get("city", doc["city"])
            country = updates.get("country", doc["country"])
            lat, lng = await self._geocode(city, country)
            updates["lat"] = lat
            updates["lng"] = lng

        updates["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.places_collection.find_one_and_update(
            {"_id": ObjectId(place_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_place(result, payload.timezone, user_id)

    async def delete_place(self, place_id: str, user_id: str) -> bool:
        result = await self.places_collection.delete_one({"_id": ObjectId(place_id), "creator_id": user_id})
        return result.deleted_count > 0

    # --- Moment Management ---

    async def add_moment(self, place_id: str, user_id: str, payload: MomentCreate, file: Optional[UploadFile] = None) -> Dict[str, Any]:
        doc = await self.places_collection.find_one({
            "_id": ObjectId(place_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if not doc:
            raise ValueError("Place not found.")

        content = payload.content
        if payload.type == MomentType.PHOTO and file:
            ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            local_path = os.path.join(self.storage_path, unique_filename)
            with open(local_path, "wb") as f:
                f.write(await file.read())
            content = f"/uploads/{unique_filename}"
        
        new_moment = {
            "id": str(uuid.uuid4()),
            "type": payload.type,
            "content": content,
            "caption": payload.caption,
            "creator_id": user_id,
            "created_at": datetime.now(timezone.utc)
        }

        result = await self.places_collection.find_one_and_update(
            {"_id": ObjectId(place_id)},
            {"$push": {"moments": new_moment}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_place(result, payload.timezone, user_id)

    # --- Stats & Overview ---

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id: user_ids.append(partner_id)
        
        query = {"creator_id": {"$in": user_ids}}
        
        places = await self.places_collection.find(query).to_list(length=None)
        
        countries = set(p["country"] for p in places)
        cities = set(p["city"] for p in places)
        
        together_count = sum(1 for p in places if p["category"] == PlaceCategory.TOGETHER)
        bucket_count = sum(1 for p in places if p["category"] == PlaceCategory.BUCKET)
        upcoming_count = sum(1 for p in places if p["category"] == PlaceCategory.UPCOMING)
        home_count = sum(1 for p in places if p["category"] == PlaceCategory.HOME)

        return {
            "total_countries": len(countries),
            "total_cities": len(cities),
            "together_count": together_count,
            "bucket_count": bucket_count,
            "upcoming_count": upcoming_count,
            "home_count": home_count
        }

    async def get_overview(self, user_id: str, user_timezone: str = "UTC") -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id: user_ids.append(partner_id)
        
        query = {"creator_id": {"$in": user_ids}}
        
        places_docs = await self.places_collection.find(query).sort("created_at", 1).to_list(length=None)
        
        places = []
        for d in places_docs:
            places.append(await self._map_place(d, user_timezone, user_id))
        
        # Calculate Routes: chronological connection of "Together" places
        together_places = [p for p in places if p["category"] == PlaceCategory.TOGETHER]
        # Sort by visit_date if present, else created_at
        def sort_key(p):
            if p.get("visit_date"):
                try:
                    return datetime.strptime(p["visit_date"], "%m.%d.%Y")
                except: pass
            return p["created_at"]
        
        together_places.sort(key=sort_key)
        
        routes = []
        if len(together_places) > 1:
            points = []
            for p in together_places:
                points.append({"lat": p["lat"], "lng": p["lng"], "city": p["city"]})
            
            routes.append({
                "name": "Our Journey Together",
                "points": points
            })
            
        stats = await self.get_stats(user_id)
        
        return {
            "places": places,
            "routes": routes,
            "stats": stats
        }

    async def _map_place(self, d: Dict[str, Any], user_timezone: str, current_user_id: str) -> Dict[str, Any]:
        place_id = str(d["_id"]) if "_id" in d else d.get("id")
        d["id"] = place_id
        if "_id" in d: del d["_id"]
        
        # --- AUTO-REPAIR LOGIC ---
        # If coordinates are missing (0,0), attempt to re-geocode and update the DB
        if d.get("lat") == 0.0 and d.get("lng") == 0.0:
            new_lat, new_lng = await self._geocode(d["city"], d["country"])
            if new_lat != 0.0 or new_lng != 0.0:
                await self.places_collection.update_one(
                    {"_id": ObjectId(place_id)},
                    {"$set": {"lat": new_lat, "lng": new_lng}}
                )
                d["lat"] = new_lat
                d["lng"] = new_lng
        
        partner_id = await self._get_partner_id(current_user_id)
        names = await self._get_names(current_user_id, partner_id or "")

        # Personalization: Add creator name
        d["creator_name"] = names.get(str(d.get("creator_id")), "User")

        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        # Convert timestamps
        for field in ["created_at", "updated_at"]:
            dt = d.get(field)
            if isinstance(dt, datetime):
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)

        # Map moments
        for m in d.get("moments", []):
            m["creator_name"] = names.get(str(m["creator_id"]), "User")
            dt = m.get("created_at")
            if isinstance(dt, datetime):
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                m["created_at"] = dt.astimezone(tz)

        return d

map_service = MapService()
