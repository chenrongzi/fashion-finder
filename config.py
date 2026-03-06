import os

# ── 本地开发直接改这里 ───────────────────────────────────

API_KEY  = os.environ.get("API_KEY",  "sk-gqlYnF9vIbhFGxACwyU6OyA8Qqx3aLfmDGbI0RQS4uOf7Rdg")
BASE_URL = os.environ.get("BASE_URL", "https://x666.me/v1")
MODEL    = os.environ.get("MODEL",    "gemini-3-flash-preview")

# 数据目录（本地默认当前目录，云端通过环境变量 DATA_DIR 指定）
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
