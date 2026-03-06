# 找图助手

女装设计师找图 + AI 风格分析工具。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 API Key
export API_KEY=sk-你的key

# 3. 启动
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. 打开浏览器（手机访问同一 WiFi 下的 IP）
# 电脑：http://localhost:8000
# 手机：http://电脑局域网IP:8000
```

## 状态说明

| 状态 | 含义 |
|------|------|
| 待审核 | 刚上传，还没发给老板娘 |
| 已发老板娘 | 发出去了，等反馈 |
| 通过 ✅ | 老板娘喜欢 |
| 拒绝 ❌ | 老板娘不喜欢 |

状态可以随时手动修改。

## 文件结构

```
fashion-finder/
├── main.py          # FastAPI 后端
├── database.py      # SQLite 数据库
├── ai_analyze.py    # AI 图片分析
├── requirements.txt
├── fashion.db       # 数据库文件（自动生成）
├── uploads/         # 上传的图片（自动生成）
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```
