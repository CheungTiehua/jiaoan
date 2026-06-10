"""LeKai 后端配置"""

import os
from pathlib import Path

# 版本（统一源）
VERSION = "1.0.0"

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
RETRIEVAL_TOP_K = 5
MAX_CONTEXT_LENGTH = 8000

# ─── MAC 地址授权（盒子部署用）─────────────────────────────
import uuid as _uuid
_lic_file = PROJECT_ROOT / ".license"
if _lic_file.exists():
    _allowed = set(_lic_file.read_text().strip().split())
    _my_mac = ":".join(f"{(_uuid.getnode() >> (8*i)) & 0xff:02x}" for i in range(5, -1, -1))
    if _my_mac not in _allowed and "any" not in _allowed:
        raise RuntimeError(f"未授权设备。MAC: {_my_mac}")

# 时间到期检查
_EXPIRE_DATE = os.getenv("LEKAI_EXPIRE_DATE", "")
if _EXPIRE_DATE:
    import datetime as _dt
    try:
        _expire = _dt.date.fromisoformat(_EXPIRE_DATE)
    except ValueError:
        raise RuntimeError("授权日期格式错误，应为 YYYY-MM-DD") from None
    if _dt.date.today() > _expire:
        raise RuntimeError("授权已到期，请联系 LeKai 续费。")


def get_device_mac() -> str:
    """获取设备 MAC 地址"""
    return ":".join(f"{(_uuid.getnode() >> (8*i)) & 0xff:02x}" for i in range(5, -1, -1))


# Prompt 配置文件路径
PROMPTS_FILE = PROJECT_ROOT / "data" / ".system_prompts"

# 验收模式开关（仅交付验收时临时开启，正式生产必须关闭）
LEKAI_ACCEPTANCE_MODE = os.getenv("LEKAI_ACCEPTANCE_MODE", "0") == "1"
