# 找图助手

女装设计师找图 + AI 风格分析工具。

## 快速启动（本地）

**第一步：安装依赖**
```bash
pip install -r requirements.txt
```

**第二步：配置 API Key**

复制模板文件，重命名为 `config.py`：
```bash
cp config.example.py config.py
```

用任意编辑器打开 `config.py`，填入你的信息：
```python
API_KEY  = "sk-你的key"          # API Key
BASE_URL = "https://x666.me/v1"  # 中转站地址
MODEL    = "gemini-3-flash-preview"  # 使用的模型
```

> `config.py` 已加入 `.gitignore`，不会被提交到 GitHub，安全。

**第三步：启动**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**第四步：访问**
- 电脑：http://localhost:8000
- 手机（同一 WiFi）：http://电脑局域网IP:8000

---

## 部署到 Zeabur（推荐）

1. 在 [zeabur.com](https://zeabur.com) 新建 Project
2. Add Service → Git → 选择本仓库
3. 启动命令：`uvicorn main:app --host 0.0.0.0 --port 8080`
4. Storage → Add Volume，Mount Path：`/data`
5. Variables 添加环境变量：

| 变量名   | 值                        |
|----------|---------------------------|
| DATA_DIR | /data                     |
| API_KEY  | 你的 API Key              |
| BASE_URL | https://x666.me/v1        |
| MODEL    | gemini-3-flash-preview    |

---

## 状态说明

| 状态 | 含义 |
|------|------|
| 待审核 | 刚上传，还没发给老板娘 |
| 已发老板娘 | 发出去了，等反馈 |
| 通过 ✅ | 老板娘喜欢 |
| 拒绝 ❌ | 老板娘不喜欢 |

状态可以随时手动修改。

---

## 文件结构

```
fashion-finder/
├── main.py            # FastAPI 后端
├── database.py        # SQLite 数据库
├── ai_analyze.py      # AI 图片分析
├── config.py          # 本地配置（不提交）
├── config.example.py  # 配置模板
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```
