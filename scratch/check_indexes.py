import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.MONGO_DB_NAME]
    collection = db["ritual_completions"]
    indexes = await collection.index_information()
    print("Current indexes:", indexes)

if __name__ == "__main__":
    asyncio.run(main())
