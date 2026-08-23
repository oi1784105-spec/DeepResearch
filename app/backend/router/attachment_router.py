from fastapi import APIRouter, Depends, File, UploadFile, status

from backend.deps import current_user
from backend.schemas.attachment import AttachmentResponse
from backend.service.attachment_service import delete_attachment, save_attachments


router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])


@router.post("", response_model=list[AttachmentResponse], status_code=status.HTTP_201_CREATED)
async def upload_attachments(
    files: list[UploadFile] = File(...),
    user: dict = Depends(current_user),
) -> list[AttachmentResponse]:
    return await save_attachments(files, user["id"])


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attachment(attachment_id: str, user: dict = Depends(current_user)) -> None:
    delete_attachment(attachment_id, user["id"])

