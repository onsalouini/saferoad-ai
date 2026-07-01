# api/database.py
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "saferoad"

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        if not MONGO_URI:
            raise ValueError("MONGO_URI not set in .env file")
        cls.client = AsyncIOMotorClient(MONGO_URI)
        cls.db = cls.client[DB_NAME]
        print("✅ MongoDB connected successfully")

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            print("✅ MongoDB disconnected")

    @classmethod
    def get_collection(cls, name):
        return cls.db[name]