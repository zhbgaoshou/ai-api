from pydantic import BaseModel


class MessageIn(BaseModel):
    model: str
    content: str
    history: list | None = []
    role: str | None = "user"
    temperature: float | None = 0.2
    max_tokens: int | None = 1024
