"""LeKai 后端配置"""

import os
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
CACHE_DIR = PROJECT_ROOT / ".cache"

# DeepSeek API
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# ChromaDB
CHROMA_COLLECTION = "lesson_plans"

# RAG 参数
RETRIEVAL_TOP_K = 5     # 检索返回的教案数量
MAX_CONTEXT_LENGTH = 8000  # 检索上下文最大字符数
