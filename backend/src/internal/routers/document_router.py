from fastapi import APIRouter, HTTPException, UploadFile, File
from starlette.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT

from db.models import ParsedDocument
from db.repositories.document_repo import ParsedDocumentRepository
from internal.dependencies import Db, CtxUser
from internal.schemas.documents import DocumentResponse, ExpandedDocumentResponse
from services.document_processing.pipeline import DocumentExistsError
from services.document_service import process_document


router = APIRouter(prefix="/document", tags=["document"])


@router.get("", response_model=list[DocumentResponse])
async def get_documents_for_user(db: Db, user: CtxUser) -> list[DocumentResponse]:
    docs = await ParsedDocumentRepository(db).get_all_for_user(user)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get("/{document_id}", response_model=ExpandedDocumentResponse)
async def get_document(
    db: Db, user: CtxUser, document_id: int
) -> ExpandedDocumentResponse:
    if (
        not (doc := await ParsedDocumentRepository(db).get_one_by_id(document_id))
        or doc.user != user
    ):
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Document not found")

    return ExpandedDocumentResponse.model_validate(doc)


@router.post("", response_model=DocumentResponse)
async def upload_document(
    db: Db, user: CtxUser, file: UploadFile = File(...)
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail="File must have a name"
        )

    try:
        saved_doc = await process_document(file, db, user)
    except DocumentExistsError:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail="Document already exists for this user",
        )

    return DocumentResponse.model_validate(saved_doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(db: Db, user: CtxUser, document_id: int) -> None:
    repo = ParsedDocumentRepository(db)
    doc = await repo.get_one_by_id(document_id)

    if not doc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.user_id is None or doc.user != user:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await repo.delete(ParsedDocument.document_id == document_id)
