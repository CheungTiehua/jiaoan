"""LeKai 后端配置"""

import os
from pathlib import Path

# 版本（统一源）
VERSION = "1.0.0"

# 项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
CACHE_DIR = PROJECT_ROOT / ".cache"


def _load_dotenv() -> None:
    """Load simple KEY=VALUE lines from project .env for local uvicorn runs."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# DeepSeek API
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_FAST_MODEL = os.environ.get("DEEPSEEK_FAST_MODEL", "deepseek-v4-flash")
DEEPSEEK_REASONING_EFFORT = os.environ.get("DEEPSEEK_REASONING_EFFORT", "")
DEEPSEEK_THINKING = os.environ.get("DEEPSEEK_THINKING", "")
DEEPSEEK_MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8192") or "8192")

# ChromaDB
CHROMA_COLLECTION = "lesson_plans"

# PDF OCR ingestion
PDF_OCR_MAX_PAGES = int(os.environ.get("PDF_OCR_MAX_PAGES", "80") or "80")
PDF_OCR_DPI_SCALE = float(os.environ.get("PDF_OCR_DPI_SCALE", "2.0") or "2.0")
PDF_OCR_LANG = os.environ.get("PDF_OCR_LANG", "chi_sim+eng")
PDF_UPLOAD_MAX_MB = int(os.environ.get("PDF_UPLOAD_MAX_MB", "1024") or "1024")

# Embedded DEE evidence base
# DEE is not a separate service in this project. Its EvidenceObject fields are
# preserved in LeKai's local index so page, bbox, hash and source provenance can
# be rendered by the teaching system itself.

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
