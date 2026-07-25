from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from app.middleware.auth import AuthenticatedCaller, get_current_caller
from app.services.document_ingestion import ingest_document

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    caller: AuthenticatedCaller = Depends(get_current_caller),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    return ingest_document(content, file.filename or "upload.bin")
