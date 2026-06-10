#!/usr/bin/env python3
"""
LeKai 离线 Embedding 模型预置脚本

用法:
  python scripts/prepare_offline_model.py
  LEKAI_MODEL_DIR=/opt/lekai/models/bge-small-zh-v1.5 python scripts/prepare_offline_model.py

功能:
  1. 检查指定目录或默认缓存目录中 BAAI/bge-small-zh-v1.5 模型是否已就绪
  2. 如未就绪，尝试从 HuggingFace 下载
  3. 下载失败时给出明确的人工操作提示
"""

import os
import sys
from pathlib import Path

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_model_dir() -> Path:
    """确定模型目录"""
    env_dir = os.environ.get("LEKAI_MODEL_DIR", "")
    if env_dir:
        return Path(env_dir)
    return PROJECT_ROOT / ".cache" / "models" / MODEL_NAME.replace("/", "--")


def check_model_ready(model_dir: Path) -> bool:
    """检查模型目录是否包含必要文件"""
    required_files = ["config.json", "tokenizer.json", "special_tokens_map.json"]
    # pytorch_model.bin 或 model.safetensors
    weight_files = ["pytorch_model.bin", "model.safetensors"]

    if not model_dir.exists():
        return False

    for f in required_files:
        if not (model_dir / f).exists():
            return False

    has_weights = any((model_dir / f).exists() for f in weight_files)
    return has_weights


def download_model(model_dir: Path) -> bool:
    """尝试从 HuggingFace 下载模型"""
    try:
        from sentence_transformers import SentenceTransformer
        print(f"正在下载模型 {MODEL_NAME} ...")
        model = SentenceTransformer(MODEL_NAME, cache_folder=str(model_dir.parent.parent))
        # SentenceTransformer 会下载到 cache_folder，尝试保存到指定目录
        target = model_dir
        if target.exists() and check_model_ready(target):
            print(f"模型已下载到缓存目录")
            return True
        # 尝试保存到指定目录
        model.save(str(model_dir))
        print(f"模型已保存到: {model_dir}")
        return True
    except Exception as e:
        print(f"自动下载失败: {e}")
        return False


def main():
    model_dir = get_model_dir()
    print(f"模型名称: {MODEL_NAME}")
    print(f"模型目录: {model_dir}")

    if check_model_ready(model_dir):
        print("状态: 已就绪")
        print("OFFLINE MODEL READY")
        return 0

    print("状态: 模型缺失，尝试自动下载...")

    if download_model(model_dir):
        if check_model_ready(model_dir):
            print("状态: 已就绪")
            print("OFFLINE MODEL READY")
            return 0

    # 下载失败，输出人工操作提示
    print()
    print("=" * 60)
    print("模型未能自动下载，请执行以下任一操作：")
    print()
    print("方式 1（推荐）— 在有网络的机器上下载后拷贝：")
    print(f"  git clone https://huggingface.co/{MODEL_NAME}")
    print(f"  scp -r {MODEL_NAME.split('/')[-1]}/ root@<服务器IP>:{model_dir}")
    print()
    print("方式 2 — 手动下载 zip：")
    print(f"  https://huggingface.co/{MODEL_NAME}/resolve/main/pytorch_model.bin")
    print(f"  下载后放置到: {model_dir}")
    print()
    print("方式 3 — 设置 LEKAI_MODEL_DIR 指向已有模型：")
    print(f"  LEKAI_MODEL_DIR=/path/to/model python scripts/prepare_offline_model.py")
    print("=" * 60)
    print()
    print("OFFLINE MODEL NOT READY")
    return 1


if __name__ == "__main__":
    sys.exit(main())
