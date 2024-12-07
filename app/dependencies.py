from db import engine
from sqlmodel import Session
from fastapi import Query


def get_session():
    with Session(engine) as session:
        yield session


def get_page_params(limit: int = Query(default=1, alias='page'), offset: int = Query(default=10, alias='page_size', le=100)):
    return {'limit': limit, 'offset': offset}
