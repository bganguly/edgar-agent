import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
