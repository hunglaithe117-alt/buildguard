"""Base repository providing common MongoDB CRUD helpers."""

from abc import ABC
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel
from pymongo.collection import Collection
from pymongo.database import Database

T = TypeVar("T", bound=BaseModel)


class BaseRepository(ABC, Generic[T]):
    """Base repository providing common CRUD operations for MongoDB collections."""

    def __init__(self, db: Database, collection_name: str, model_class: Type[T]):
        self.db = db
        self.collection: Collection = db[collection_name]
        self.model_class = model_class

    def find_by_id(self, entity_id: str | ObjectId) -> Optional[T]:
        identifier = self._to_object_id(entity_id)
        if identifier is None:
            return None
        doc = self.collection.find_one({"_id": identifier})
        return self._to_model(doc)

    def find_one(self, query: Dict[str, Any]) -> Optional[T]:
        doc = self.collection.find_one(query)
        return self._to_model(doc)

    def find_many(
        self,
        query: Dict[str, Any],
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[T]:
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [self._to_model(doc) for doc in cursor]

    def insert_one(self, entity: T) -> T:
        doc = entity.model_dump(by_alias=True, exclude_none=True)
        result = self.collection.insert_one(doc)
        return self.find_by_id(result.inserted_id)

    def update(
        self, entity_id: str | ObjectId, update_data: Dict[str, Any]
    ) -> T | None:
        identifier = self._to_object_id(entity_id)
        if identifier is None:
            return None
        self.collection.update_one({"_id": identifier}, {"$set": update_data})
        return self.find_by_id(identifier)

    def update_one(
        self, entity_id: str | ObjectId, update_data: Dict[str, Any]
    ) -> T | None:
        # Alias for update to match some usages
        return self.update(entity_id, update_data)

    def delete(self, entity_id: str | ObjectId) -> bool:
        identifier = self._to_object_id(entity_id)
        if identifier is None:
            return False
        result = self.collection.delete_one({"_id": identifier})
        return result.deleted_count > 0

    def _to_model(self, doc: Dict[str, Any] | None) -> Optional[T]:
        if not doc:
            return None
        return self.model_class.model_validate(doc)

    def _to_object_id(self, entity_id: str | ObjectId | None) -> Optional[ObjectId]:
        if entity_id is None:
            return None
        if isinstance(entity_id, ObjectId):
            return entity_id
        try:
            return ObjectId(entity_id)
        except (InvalidId, TypeError):
            return None
