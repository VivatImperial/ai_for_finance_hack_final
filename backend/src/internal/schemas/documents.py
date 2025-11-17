from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: int
    minio_url: str
    filename: str
    created_at: datetime
    is_general: bool

    class Config:
        from_attributes = True


class ExpandedDocumentResponse(DocumentResponse):
    document_length: int
