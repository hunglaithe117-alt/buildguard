"""Base repository providing common MongoDB CRUD helpers."""

from abc import ABC
from enum import Enum
from types import SimpleNamespace
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel
from pymongo.collection import Collection
from pymongo.database import Database


class CollectionName(str, Enum):
    AVAILABLE_REPOSITORIES = "available_repositories"
    REPOSITORIES = "repositories"
    IMPORTED_REPOSITORIES = "imported_repositories"  # legacy name
    USERS = "users"
    OAUTH_IDENTITIES = "oauth_identities"
    GITHUB_INSTALLATIONS = "github_installations"
    GITHUB_PUBLIC_TOKENS = "github_public_tokens"
    GITHUB_STATES = "github_states"
    BUILD_SAMPLES = "build_samples"
    WORKFLOW_RUNS = "workflow_runs"
    SCAN_JOBS = "scan_jobs"
    SCAN_RESULTS = "scan_results"
    FAILED_SCANS = "failed_scans"
    REPOSITORY_SCANS = "repository_scans"
    FAILED_COMMITS = "failed_commits"
    PROJECTS = "projects"


T = TypeVar("T", bound=BaseModel)


class BaseRepository(ABC, Generic[T]):
    """Base repository providing common CRUD operations for MongoDB collections."""

    def __init__(
        self,
        db: Database,
        collection_name: Union[CollectionName, str],
        model_class: Type[T],
    ):
        self.db = db
        self.collection_name: str = (
            collection_name.value
            if isinstance(collection_name, CollectionName)
            else collection_name
        )
        self.collection: Collection = db[self.collection_name]
        self.model_class = model_class

    def find_by_id(self, entity_id: Union[str, ObjectId]) -> Optional[T]:
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
        self, entity_id: Union[str, ObjectId], update_data: Dict[str, Any]
    ) -> Optional[T]:
        identifier = self._to_object_id(entity_id)
        if identifier is None:
            return None
        self.collection.update_one({"_id": identifier}, {"$set": update_data})
        return self.find_by_id(identifier)

    def update_one(
        self, entity_id: Union[str, ObjectId], update_data: Dict[str, Any]
    ) -> Optional[T]:
        # Alias for update to match some usages
        return self.update(entity_id, update_data)

    def delete(self, entity_id: Union[str, ObjectId]) -> bool:
        identifier = self._to_object_id(entity_id)
        if identifier is None:
            return False
        result = self.collection.delete_one({"_id": identifier})
        return result.deleted_count > 0

    def _to_model(self, doc: Optional[Dict[str, Any]]) -> Optional[T]:
        if not doc:
            return None
        return self.model_class.model_validate(doc)

    def _to_object_id(
        self, entity_id: Union[str, ObjectId, None]
    ) -> Optional[ObjectId]:
        if entity_id is None:
            return None
        if isinstance(entity_id, ObjectId):
            return entity_id
        try:
            return ObjectId(entity_id)
        except (InvalidId, TypeError):
            return None


class MongoRepositoryBase:
    """
    Lightweight base used by legacy pipeline repositories that work directly
    with collection names rather than Pydantic models.
    """

    def __init__(self, db: Database, collections: Optional[Any] = None):
        self.db = db
        default = {
            "projects_collection": CollectionName.REPOSITORIES.value,
            "scan_jobs_collection": CollectionName.SCAN_JOBS.value,
            "scan_results_collection": CollectionName.SCAN_RESULTS.value,
            "failed_commits_collection": CollectionName.FAILED_COMMITS.value,
            "build_samples_collection": CollectionName.BUILD_SAMPLES.value,
        }
        if collections:
            if hasattr(collections, "model_dump"):
                default.update(collections.model_dump())
            elif isinstance(collections, dict):
                default.update(collections)
            else:
                default.update(vars(collections))
        self.collections = SimpleNamespace(**default)

    def _serialize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        data = dict(doc)
        if "_id" in data:
            data["id"] = str(data.pop("_id"))
        return data
