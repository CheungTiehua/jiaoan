# LeKai教案系统 — 离线模型预置指南

## 当前使用的 Embedding 模型

- **模型名称**：`BAAI/bge-small-zh-v1.5`
- **维度**：512 维
- **大小**：约 96MB
- **用途**：教案文本向量化，支持 ChromaDB 语义检索
- **来源**：[HuggingFace — BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)

## 在线下载方式

默认情况下，后端首次启动时自动从 HuggingFace 下载模型到 `.cache/models/` 目录。

```bash
# 启动服务，模型会自动下载
docker compose up -d

# 或手动触发下载
docker compose exec backend python -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='.cache/models')
"
```

## 离线预置方式

### 步骤一：在有网络的机器上下载模型

```bash
# 方式 1：用项目脚本
python scripts/prepare_offline_model.py

# 方式 2：用 Python
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='./models')
model.save('./models/bge-small-zh-v1.5')
"

# 方式 3：用 git clone
git clone https://huggingface.co/BAAI/bge-small-zh-v1.5
```

### 步骤二：拷贝到服务器

```bash
scp -r models/bge-small-zh-v1.5/ root@192.168.x.x:/opt/lekai/.cache/models/
```

### 步骤三：设置环境变量（可选）

在 `.env` 中添加：

```bash
LEKAI_MODEL_DIR=/app/.cache/models/bge-small-zh-v1.5
```

如果未设置 `LEKAI_MODEL_DIR`，后端会按以下优先级自动查找：
1. `$LEKAI_MODEL_DIR` 环境变量指定的目录
2. 项目默认目录 `.cache/models/bge-small-zh-v1.5`
3. 在线从 HuggingFace 下载

Docker Compose 中已通过 volume `model_cache:/app/.cache` 挂载，模型放在 `model_cache/models/` 下即可。

## 模型缓存目录说明

| 环境 | 默认路径 | 说明 |
|------|---------|------|
| Docker | `/app/.cache/models/` | 通过 named volume `model_cache` 持久化 |
| 本地开发 | `.cache/models/` | 项目根目录下的 `.cache/models/` |
| 自定义 | `$LEKAI_MODEL_DIR` | 环境变量指定的绝对路径 |

## 学校弱网/无公网环境部署建议

1. **提前下载模型**：在有网络的机器上完成模型下载
2. **打包到部署包中**：将 `.cache/models/` 目录包含在部署包内
3. **设置 `LEKAI_MODEL_DIR`**：指向预置的模型目录
4. **运行验证脚本**：

```bash
python scripts/prepare_offline_model.py
```

期望输出：

```text
模型目录: /app/.cache/models/bge-small-zh-v1.5
状态: 已就绪
OFFLINE MODEL READY
```

## 模型缺失时的错误排查

### 错误信息

```text
Embedding 模型加载失败，请检查 LEKAI_MODEL_DIR 或网络连接
```

### 排查步骤

1. 检查模型文件是否存在：

```bash
ls -la .cache/models/
# 或
ls -la $LEKAI_MODEL_DIR
```

2. 确认模型目录包含必要文件：
   - `config.json`
   - `pytorch_model.bin` 或 `model.safetensors`
   - `tokenizer.json`
   - `special_tokens_map.json`

3. 运行预置脚本：

```bash
python scripts/prepare_offline_model.py
```

4. 手动指定目录重试：

```bash
LEKAI_MODEL_DIR=/path/to/model python scripts/prepare_offline_model.py
```

5. 如果所有方式都失败：
   - 确认磁盘空间充足（模型约需 100MB）
   - 确认目录有读取权限
   - 尝试删除 `.cache/models/` 后重新下载
