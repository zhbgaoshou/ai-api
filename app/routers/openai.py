from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse
import os
import json
import redis
from models.openai import MessageIn
from dotenv import load_dotenv

load_dotenv()

# 从环境变量加载 OpenAI API 密钥，避免硬编码
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# 创建 FastAPI 路由
router = APIRouter(prefix="/openai", tags=["openai"])

# 初始化 OpenAI 客户端
client = OpenAI(
    base_url="https://api.openai-proxy.org/v1",
    api_key=OPENAI_API_KEY,
)
redis_client = redis.StrictRedis(
    host="localhost", port=6379, db=0, decode_responses=True
)


# 生成事件流的异步生成器函数
async def generate_event_stream(completion):
    try:
        ai_content = ""
        for chunk in completion:
            delta = chunk.choices[0].delta
            if chunk.choices and delta.content:
                ai_content += delta.content
                yield delta.content
            else:
                print(f"Unexpected chunk structure: {chunk}")
    except Exception as e:
        print(f"Error during event streaming: {e}")
        raise HTTPException(status_code=500, detail="生成失败，请稍后再试")
    finally:
        if ai_content:  # 确保有生成的 AI 内容
            print(f"保存消息到 Redis: {ai_content}")


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
    print(message.history)

    # 后台任务
    # print("将content保存到db", message)

    # 返回 EventSourceResponse，异步生成数据
    return EventSourceResponse(generate_event_stream(completion))
