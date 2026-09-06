from pydantic import BaseModel


class MessageOut(BaseModel):
    message: str


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int