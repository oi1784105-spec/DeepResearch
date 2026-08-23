from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    kind: str
    is_image: bool

