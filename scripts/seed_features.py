import os
from pymongo import MongoClient
from datetime import datetime

# URL Mongo local hoặc từ biến môi trường
MONGO_URI = os.getenv(
    "MONGO_URI", "mongodb://travis:travis@localhost:27017/?directConnection=true"
)
DB_NAME = "buildguard"


def seed():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("🌱 Bắt đầu seed Features và Templates...")

    # 1. Định nghĩa các Features chuẩn (Dictionary)
    features = [
        {
            "key": "gh_complexity",
            "name": "Cyclomatic Complexity",
            "description": "Độ phức tạp của code",
            "data_type": "integer",
            "default_source": "sonar",  # Mặc định lấy từ Sonar
            "is_active": True,
        },
        {
            "key": "gh_bugs",
            "name": "Bugs Count",
            "description": "Số lượng bugs phát hiện được",
            "data_type": "integer",
            "default_source": "sonar",
            "is_active": True,
        },
        {
            "key": "gh_diff_churn",
            "name": "Code Churn",
            "description": "Tổng số dòng code thêm/sửa/xóa",
            "data_type": "integer",
            "default_source": "git_extract",  # Mặc định tính từ Git
            "extraction_config": {
                "git_key": "git_diff_src_churn"
            },  # Map to GitFeatureExtractor output
            "is_active": True,
        },
        {
            "key": "gh_build_status",
            "name": "Build Status",
            "description": "Trạng thái build (0: Fail, 1: Pass)",
            "data_type": "integer",
            "default_source": "csv_mapped",  # Thường có sẵn trong CSV
            "is_active": True,
        },
    ]

    # Upsert Features (Nếu có rồi thì update, chưa có thì tạo)
    for f in features:
        db.feature_definitions.update_one(
            {"key": f["key"]},
            {"$set": {**f, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    # 2. Định nghĩa Template "TravisTorrent"
    # Đây là mapping chuẩn của dataset TravisTorrent
    travis_template = {
        "name": "TravisTorrent Standard",
        "description": "Bộ dữ liệu chuẩn TravisTorrent",
        "feature_keys": [
            "gh_complexity",
            "gh_bugs",
            "gh_diff_churn",
            "gh_build_status",
        ],
        # Mapping gợi ý: Key của mình -> Tên cột trong CSV TravisTorrent
        "default_mapping": {
            "gh_complexity": "gh_complexity",  # Trong CSV cũng tên là gh_complexity (ví dụ)
            "gh_bugs": "gh_bugs",
            "gh_diff_churn": "gh_diff_src_churn",  # Cột trong CSV tên khác
            "gh_build_status": "tr_status",
        },
    }

    db.dataset_templates.update_one(
        {"name": travis_template["name"]},
        {"$set": {**travis_template, "updated_at": datetime.utcnow()}},
        upsert=True,
    )

    print("✅ Seed dữ liệu thành công!")


if __name__ == "__main__":
    seed()
