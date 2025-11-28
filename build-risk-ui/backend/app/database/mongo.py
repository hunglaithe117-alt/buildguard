"""
MongoDB connection helpers.
"""
from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client


def get_database() -> Database:
    client = get_client()
    return client[settings.MONGODB_DB_NAME]


def get_db():
    db = get_database()
    try:
        yield db
    finally:
        # PyMongo manages connection pooling automatically; nothing to close here.
        pass
