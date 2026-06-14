import httpx
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timedelta
import urllib.parse

from app.core.config import settings

class YouTubeMusicService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.user_links = self.db["user_music_links"]
        self.shared_tracks = self.db["shared_tracks"]
        self.users = self.db["users"]

    def get_auth_url(self) -> str:
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube",
            "access_type": "offline",
            "prompt": "consent"
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return url

    async def exchange_code(self, user_id: str, code: str) -> None:
        url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            tokens = resp.json()
            
        expires_in = tokens.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        await self.user_links.update_one(
            {"user_id": user_id, "provider": "youtube"},
            {"$set": {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),  # May not be returned if not first prompt
                "expires_at": expires_at
            }},
            upsert=True
        )
        
        await self.ensure_playlist(user_id)

    async def _get_valid_token(self, user_id: str) -> str:
        link = await self.user_links.find_one({"user_id": user_id, "provider": "youtube"})
        if not link:
            raise Exception("User has not linked YouTube account")
            
        if datetime.utcnow() >= link["expires_at"] - timedelta(minutes=5):
            # Refresh token
            if not link.get("refresh_token"):
                raise Exception("Token expired and no refresh token available. Re-authenticate.")
                
            url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "refresh_token": link["refresh_token"],
                "grant_type": "refresh_token"
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=data)
                resp.raise_for_status()
                tokens = resp.json()
                
            expires_in = tokens.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            await self.user_links.update_one(
                {"_id": link["_id"]},
                {"$set": {
                    "access_token": tokens["access_token"],
                    "expires_at": expires_at
                }}
            )
            return tokens["access_token"]
            
        return link["access_token"]

    async def ensure_playlist(self, user_id: str) -> str:
        link = await self.user_links.find_one({"user_id": user_id, "provider": "youtube"})
        if link and link.get("playlist_id"):
            return link["playlist_id"]
            
        token = await self._get_valid_token(user_id)
        
        # Check if they already have one named "Songs for us."
        url = "https://www.googleapis.com/youtube/v3/playlists"
        params = {
            "part": "snippet",
            "mine": "true",
            "maxResults": 50
        }
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                playlists = resp.json().get("items", [])
                for pl in playlists:
                    if pl["snippet"]["title"] == "Songs for us.":
                        pl_id = pl["id"]
                        await self.user_links.update_one(
                            {"_id": link["_id"]},
                            {"$set": {"playlist_id": pl_id}}
                        )
                        return pl_id
                        
            # Create it
            data = {
                "snippet": {
                    "title": "Songs for us.",
                    "description": "Synced across our accounts by Aligned app."
                },
                "status": {
                    "privacyStatus": "private"
                }
            }
            resp = await client.post(f"{url}?part=snippet,status", json=data, headers=headers)
            resp.raise_for_status()
            pl_id = resp.json()["id"]
            
            await self.user_links.update_one(
                {"_id": link["_id"]},
                {"$set": {"playlist_id": pl_id}}
            )
            return pl_id

    async def search_tracks(self, query: str) -> List[Dict[str, Any]]:
        # Using API Key for search to save user tokens, or use user token if available. 
        # Using API Key is simpler.
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query + " music",
            "type": "video",
            "videoCategoryId": "10", # Music
            "maxResults": 10,
            "key": settings.YOUTUBE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            
        results = []
        for item in items:
            snippet = item["snippet"]
            results.append({
                "id": item["id"]["videoId"],
                "title": snippet["title"],
                "artist": snippet["channelTitle"],
                "cover_url": snippet["thumbnails"]["high"]["url"],
                "provider": "youtube"
            })
        return results

    async def add_track(self, user_id: str, track_id: str, title: str, artist: str, cover_url: str) -> None:
        # Save to shared_tracks
        new_track = {
            "youtube_video_id": track_id,
            "title": title,
            "artist": artist,
            "cover_url": cover_url,
            "added_by": user_id,
            "provider": "youtube",
            "created_at": datetime.utcnow()
        }
        await self.shared_tracks.insert_one(new_track)
        
        # Add to user's playlist
        await self._add_to_youtube_playlist(user_id, track_id)
        
        # Add to partner's playlist if linked
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("partner"):
            partner_id = user["partner"]["user_id"]
            try:
                await self._add_to_youtube_playlist(partner_id, track_id)
            except Exception:
                pass # Ignore if partner hasn't linked youtube

    async def _add_to_youtube_playlist(self, user_id: str, video_id: str) -> None:
        token = await self._get_valid_token(user_id)
        playlist_id = await self.ensure_playlist(user_id)
        
        url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet"
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=headers)
            resp.raise_for_status()

    async def get_shared_playlist(self, user_id: str) -> List[Dict[str, Any]]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        partner_id = None
        partner_name = "Partner"
        user_name = user.get("name", "Me") if user else "Me"
        
        if user and user.get("partner"):
            partner_id = user["partner"]["user_id"]
            partner_name = user["partner"].get("name", "Partner")
            
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)
            
        cursor = self.shared_tracks.find({"added_by": {"$in": user_ids}}).sort("created_at", -1)
        docs = await cursor.to_list(length=None)
        
        results = []
        for doc in docs:
            is_partner = doc["added_by"] != user_id
            author = partner_name if is_partner else user_name
            results.append({
                "id": doc.get("youtube_video_id", str(doc["_id"])),
                "title": doc["title"],
                "artist": doc["artist"],
                "cover_url": doc.get("cover_url"),
                "added_by": doc["added_by"],
                "added_by_name": author,
                "is_partner": is_partner,
                "provider": doc.get("provider", "youtube")
            })
            
        return results

youtube_service = YouTubeMusicService()
