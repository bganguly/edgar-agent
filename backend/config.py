import os
from dotenv import load_dotenv

load_dotenv()

# Set MODEL_PROVIDER=nvidia to use NVIDIA NIM / Nemotron
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")

ANTHROPIC_MODEL = "claude-sonnet-5"

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-ultra-253b-v1")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
