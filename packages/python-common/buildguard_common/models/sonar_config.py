from datetime import datetime
from pydantic import BaseModel


class SonarConfig(BaseModel):
    filename: str
    file_path: str
    updated_at: datetime
