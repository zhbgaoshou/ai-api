from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


# 消息输入
class MessageIn(SQLModel):
    model: str
    content: str
    history: list | None = []
    role: str | None = "user"
    temperature: float | None = 0.2
    max_tokens: int | None = 1024
    user_id: int
    session_id: int | None = None


# 模型输入
class ModelIn(SQLModel):
    name: str
    model: str
    desc: str
    supper: bool = False
    image: str | None = None
    active: bool = False


# 数据库模型基础
class DBBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S"),
        }


# 会话数据库
class SessionDB(DBBase, table=True):
    __tablename__ = "sessions"
    name: str
    active: bool = True
    user_id: int = Field(index=True)
    messages: list["MessageDB"] = Relationship(back_populates="session", cascade_delete=True)


class MessageDB(DBBase, table=True):
    __tablename__ = "messages"
    model: str
    content: str
    role: str
    user_id: int = Field(index=True)
    session_id: int = Field(index=True, foreign_key="sessions.id")
    session: SessionDB = Relationship(back_populates="messages")


# 模型
class ModelDB(DBBase, table=True):
    __tablename__ = "models"
    name: str
    model: str
    desc: str
    supper: bool = False
    image: str | None = None
    active: bool = False
