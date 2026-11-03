from dotenv import load_dotenv
import os
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    DJANGO_SECRET_KEY: str = os.getenv('DJANGO_SECRET_KEY')
