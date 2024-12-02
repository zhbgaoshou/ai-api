from fastapi import FastAPI
from routers import openai

app = FastAPI()

app.include_router(openai.router)
