from pydantic import BaseModel


class MessageOut(BaseModel):
    message: str


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    has_more: bool
