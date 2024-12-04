from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse
import os
import json
import redis
from models.openai import MessageIn
from models.openai import ModelDB, ModelIn, SessionDB
from sqlmodel import Session, select
from db import engine
from dotenv import load_dotenv

load_dotenv()

# 从环境变量加载 OpenAI API 密钥，避免硬编码
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# 创建 FastAPI 路由
router = APIRouter(prefix="/openai", tags=["openai"])


def get_session():
    with Session(engine) as session:
        yield session


# 初始化 OpenAI 客户端
client = OpenAI(
    base_url="https://api.openai-proxy.org/v1",
    api_key=OPENAI_API_KEY,
)
redis_client = redis.StrictRedis(
    host="localhost", port=6379, db=0, decode_responses=True
)


# 创建会话依赖
def create_session(session: SessionDB, session_db: Session = Depends(get_session)):
    db_session = SessionDB.model_validate(session)
    session_db.add(db_session)
    session_db.commit()
    session_db.refresh(db_session)
    return db_session


# 生成事件流的异步生成器函数
def generate_event_stream(completion, message: MessageIn):

    if not message.session_id:
        with Session(engine) as session:
            true_session = session.exec(
                select(SessionDB).where(
                    SessionDB.active == True, SessionDB.user_id == message.user_id
                )
            ).all()
            for s in true_session:  # 关闭其他会话
                s.active = False
                session.add(s)
            new_session = SessionDB(
                name="默认会话", active=True, user_id=message.user_id
            )
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            message.session_id = new_session.id
            yield new_session
    try:
        ai_content = ""
        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:  # 确保有内容
                    ai_content += delta.content
                    yield delta.content
            else:
                print(f"Unexpected chunk structure:")
    except Exception as e:
        raise HTTPException(status_code=500, detail="生成失败，请稍后再试")
    finally:
        if ai_content:  # 确保有生成的 AI 内容
            print(f"保存消息到 Redis")


def generate_completion(message: MessageIn):
    try:
        # 创建 OpenAI 的 chat completions 流式请求
        completion = client.chat.completions.create(
            model=message.model,
            messages=[{"role": "system", "content": "You are a helpful assistant."}]
            + message.history,
            stream=True,
            temperature=message.temperature,
            max_tokens=message.max_tokens,
        )
        return completion
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建AI模型失败: {e}")


@router.post("")
async def stream_chat(
    response: Response, message: MessageIn, completion=Depends(generate_completion)
):
    # 设置响应头
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"

    # 后台任务
    # print("将content保存到db", message)

    # 返回 EventSourceResponse，异步生成数据
    return EventSourceResponse(generate_event_stream(completion, message))


@router.post("/model", response_model=ModelDB)
def create_model(model: ModelIn, session: Session = Depends(get_session)):
    if session.exec(select(ModelDB).where(ModelDB.model == model.model)).first():
        raise HTTPException(status_code=400, detail="模型已存在")
    db_model = ModelDB.model_validate(model)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)

    return db_model


@router.get("/model", response_model=list[ModelDB])
def get_models(session: Session = Depends(get_session)):
    return session.exec(select(ModelDB)).all()


# 切换模型
@router.get("/toggle/{model_id}")
def toggle_model(model_id: int, session: Session = Depends(get_session)):
    all_modles = session.exec(select(ModelDB).where(ModelDB.active == True)).all()
    for m in all_modles:
        m.active = False
        session.add(m)
    model = session.get(ModelDB, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    model.active = True
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


# 创建会话
@router.post("/session", response_model=SessionDB)
def create_session(session=Depends(create_session)):
    return session


@router.get("/session/{user_id}", response_model=list[SessionDB])
def get_sessions(*, session: Session = Depends(get_session), user_id: int):
    return session.exec(select(SessionDB).where(SessionDB.user_id == user_id)).all()
