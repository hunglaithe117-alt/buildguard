from bson import ObjectId
import pandas as pd
from app.database.mongo import get_database
from buildguard_common.models.dataset_template import DatasetTemplate
from buildguard_common.models.features import Feature, FeatureSourceType
from buildguard_common.models.dataset import FieldMapping, TrainingDataset


class DatasetService:
    def __init__(self, db):
        self.db = db
        self.ds_coll = self.db.training_datasets
        self.tpl_coll = self.db.dataset_templates
        self.feat_coll = self.db.features

    async def get_all_templates(self):
        """Get list of available dataset templates."""
        cursor = self.tpl_coll.find()
        templates = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["feature_ids"] = [str(fid) for fid in doc.get("feature_ids", [])]
            templates.append(doc)
        return templates

    async def get_dataset(self, dataset_id: str):
        return self.ds_coll.find_one({"_id": ObjectId(dataset_id)})

    async def preview_csv_upload(self, file) -> dict:
        """
        Read first few lines of CSV to return preview.
        """
        try:
            # Read chunk to avoid loading large files into memory
            # We assume utf-8 encoding for now
            df = pd.read_csv(file.file, nrows=5)

            # Reset file pointer if we were to save it, but here we just preview
            # file.file.seek(0)

            headers = df.columns.tolist()
            sample_rows = df.to_dict(orient="records")

            return {
                "headers": headers,
                "sample_rows": sample_rows,
                "total_rows_estimate": 0,  # TODO: Estimate if needed, or just return 0
            }
        except Exception as e:
            raise ValueError(f"Invalid CSV file: {str(e)}")

    async def create_dataset(self, payload) -> ObjectId:
        """
        Create a new TrainingDataset record.
        """
        # Validate mandatory mapping if CSV upload
        if payload.source_type == "csv_upload":
            if not payload.config.file_path:
                # In a real flow, file should be uploaded first to a staging area,
                # and file_path provided here. Or we handle upload in this request (multipart).
                # For simplicity, we assume file_path is passed (e.g. from a previous upload step)
                # OR we might need to change the flow to upload file separately.
                # Let's assume the frontend uploads file to /upload endpoint first, gets a path/ID, then calls this.
                pass

            mapping = payload.config.mandatory_mapping
            if not mapping:
                raise ValueError("Mandatory mapping is required for CSV upload")

            required_keys = ["tr_build_id", "gh_project_name", "git_trigger_commit"]
            for key in required_keys:
                if key not in mapping:
                    raise ValueError(f"Missing mandatory mapping for: {key}")

        # Convert template_id to ObjectId if present
        tpl_id = ObjectId(payload.template_id) if payload.template_id else None

        dataset = TrainingDataset(
            name=payload.name,
            description=payload.description,
            source_type=payload.source_type,
            config=payload.config,
            template_id=tpl_id,
            mappings=[],  # Mappings will be populated in a separate step or we can accept them here
        )

        result = self.ds_coll.insert_one(dataset.to_mongo())
        return result.inserted_id
