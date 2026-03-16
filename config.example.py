import os

# ── 本地开发：直接修改这里 ───────────────────────────────
# 部署到云端：通过环境变量注入，不需要改此文件

API_KEY  = os.environ.get("API_KEY",  "在这里填你的API Key")
BASE_URL = os.environ.get("BASE_URL", "https://x666.me/v1")
MODEL    = os.environ.get("MODEL",    "gemini-3-flash-preview")

# Serper.dev API Key（用于以图搜图 / 延展找图）
# 注册地址：https://serper.dev，免费 2500 次/月
SERPER_KEY = os.environ.get("SERPER_KEY", "在这里填你的Serper Key")

# 数据目录（本地默认当前目录，云端通过环境变量 DATA_DIR 指定）
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
