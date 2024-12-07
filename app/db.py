from sqlmodel import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("MYSQL_URL")
engine = create_engine(DATABASE_URL)
