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
        self.feat_coll = self.db.feature_definitions

    async def get_all_templates(self):
        """Lấy danh sách các mẫu dataset có sẵn"""
        cursor = self.tpl_coll.find()
        return [DatasetTemplate(**doc) for doc in cursor]

    async def get_dataset(self, dataset_id: str):
        return self.ds_coll.find_one({"_id": ObjectId(dataset_id)})

    async def analyze_csv_mapping(self, file_path: str, template_id: str):
        """
        Core Logic: Đọc CSV và gợi ý mapping dựa trên Template đã chọn.
        """
        # 1. Lấy thông tin Template
        template_data = self.tpl_coll.find_one({"_id": ObjectId(template_id)})
        if not template_data:
            raise ValueError("Template not found")
        template = DatasetTemplate(**template_data)

        # 2. Đọc Headers của CSV
        try:
            df = pd.read_csv(file_path, nrows=5)
            csv_columns = df.columns.tolist()
        except Exception:
            raise ValueError("Cannot read CSV file")

        # 3. Lấy định nghĩa chi tiết các Features có trong Template
        features_cursor = self.feat_coll.find({"key": {"$in": template.feature_keys}})
        features = [doc for doc in features_cursor]

        suggestions = []

        # 4. GỢI Ý MAPPING (Thuật toán chính)
        for feat_data in features:
            feat = Feature(**feat_data)

            mapping = FieldMapping(
                feature_key=feat.key,
                source_type=feat.default_source,  # Mặc định lấy theo config của Feature
            )

            # Kiểm tra xem Template có gợi ý tên cột CSV không?
            suggested_csv_col = template.default_mapping.get(feat.key)

            if suggested_csv_col and suggested_csv_col in csv_columns:
                # Case 1: Tìm thấy cột CSV đúng tên gợi ý (Perfect Match)
                mapping.source_type = FeatureSourceType.MANUAL_UPLOAD
                mapping.csv_column = suggested_csv_col

            elif feat.key in csv_columns:
                # Case 2: Tên feature trùng tên cột CSV (Name Match)
                mapping.source_type = FeatureSourceType.MANUAL_UPLOAD
                mapping.csv_column = feat.key

            else:
                # Case 3: Không tìm thấy trong CSV -> Đề xuất hệ thống tự tính (Extract)
                # Giữ nguyên source_type mặc định (VD: GIT_HISTORY)
                pass

            suggestions.append(
                {
                    "feature": feat.model_dump(),
                    "mapping_suggestion": mapping.model_dump(),
                }
            )

        # 5. Gợi ý cột Identity (Repo & Commit)
        # Tìm cột có tên chứa 'repo', 'project', 'slug'...
        repo_col = next(
            (
                col
                for col in csv_columns
                if any(x in col.lower() for x in ["repo", "project", "slug"])
            ),
            None,
        )
        commit_col = next(
            (
                col
                for col in csv_columns
                if any(x in col.lower() for x in ["commit", "sha", "hash"])
            ),
            None,
        )

        return {
            "csv_headers": csv_columns,
            "repo_column_suggestion": repo_col,
            "commit_column_suggestion": commit_col,
            "feature_mappings": suggestions,
        }
