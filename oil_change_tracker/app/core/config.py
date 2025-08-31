import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./oilchange.db")

PLATE_LOOKUP_PROVIDER = os.getenv("PLATE_LOOKUP_PROVIDER", "none").lower()
PLATE_LOOKUP_KEY = os.getenv("PLATE_LOOKUP_KEY", "")
PLATE_LOOKUP_REGION = os.getenv("PLATE_LOOKUP_REGION", "US")
