"""API routes for StudyWise file uploads."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.attachments import save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
async def upload_attachment(
    file: UploadFile = File(...),
    student_id: str = Form(...),
    conversation_id: int = Form(...),
):
    """Upload a document or image to an existing conversation."""

    if not student_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Student ID is required.",
        )

    return await save_upload(
        file=file,
        student_id=student_id,
        conversation_id=conversation_id,
    )
