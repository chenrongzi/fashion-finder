import json
import os
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI

from ai_analyze import analyze_image, API_KEY, BASE_URL, MODEL
from database import get_db, init_db

try:
    from config import SERPER_KEY  # type: ignore
except ImportError:
    SERPER_KEY = os.environ.get("SERPER_KEY", "")

app = FastAPI(title="找图助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
DATA_DIR = os.environ.get("DATA_DIR", str(Path(__file__).parent))

UPLOAD_DIR = Path(DATA_DIR) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


# ── 上传图片文件 ──────────────────────────────────────────
@app.post("/api/images/upload")
async def upload_image(file: UploadFile = File(...), platform: str = "其他"):
    content = await file.read()
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    (UPLOAD_DIR / filename).write_bytes(content)

    try:
        analysis = analyze_image(content, filename)
    except Exception as e:
        analysis = {"tags": [], "style": "分析失败", "color": "", "category": "", "notes": str(e)}

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO images (filename, source_platform, ai_tags, ai_style, ai_color, ai_category, ai_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            filename, platform,
            json.dumps(analysis.get("tags", []), ensure_ascii=False),
            analysis.get("style", ""), analysis.get("color", ""),
            analysis.get("category", ""), analysis.get("notes", ""),
        ),
    )
    conn.commit()
    image_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone())
    row["ai_tags"] = json.loads(row["ai_tags"] or "[]")
    conn.close()
    return {"id": image_id, "filename": filename, "analysis": analysis, "image": row}


# ── 通过 URL 抓取图片 ────────────────────────────────────
class FetchUrlReq(BaseModel):
    url: str
    platform: str = "其他"


@app.post("/api/images/fetch-url")
async def fetch_url(req: FetchUrlReq):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Referer": req.url,
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        r = await client.get(req.url, headers=headers)
        if r.status_code != 200:
            raise HTTPException(400, f"无法获取图片：HTTP {r.status_code}")
        content = r.content

    filename = f"{uuid.uuid4()}.jpg"
    (UPLOAD_DIR / filename).write_bytes(content)

    try:
        analysis = analyze_image(content, filename)
    except Exception as e:
        analysis = {"tags": [], "style": "分析失败", "color": "", "category": "", "notes": str(e)}

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO images (filename, source_url, source_platform, ai_tags, ai_style, ai_color, ai_category, ai_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            filename, req.url, req.platform,
            json.dumps(analysis.get("tags", []), ensure_ascii=False),
            analysis.get("style", ""), analysis.get("color", ""),
            analysis.get("category", ""), analysis.get("notes", ""),
        ),
    )
    conn.commit()
    image_id = cur.lastrowid
    row = dict(conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone())
    row["ai_tags"] = json.loads(row["ai_tags"] or "[]")
    conn.close()
    return {"id": image_id, "filename": filename, "analysis": analysis, "image": row}


# ── 图库列表 ─────────────────────────────────────────────
@app.get("/api/images")
def get_images(status: str = None, platform: str = None, favorite: int = None, limit: int = 50, offset: int = 0):
    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if platform:
        conditions.append("source_platform = ?")
        params.append(platform)
    if favorite is not None:
        conditions.append("is_favorite = ?")
        params.append(favorite)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM images {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    total = conn.execute(f"SELECT COUNT(*) FROM images {where}", params).fetchone()[0]
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["ai_tags"] = json.loads(d["ai_tags"] or "[]")
        except Exception:
            d["ai_tags"] = []
        result.append(d)
    return {"items": result, "total": total}


# ── 更改状态（可以随时改） ────────────────────────────────
VALID_STATUS = {"pending", "sent", "approved", "rejected"}


class UpdateStatusReq(BaseModel):
    status: str


@app.patch("/api/images/{image_id}/status")
def update_status(image_id: int, req: UpdateStatusReq):
    if req.status not in VALID_STATUS:
        raise HTTPException(400, f"无效状态，可选：{VALID_STATUS}")
    conn = get_db()
    conn.execute("UPDATE images SET status = ? WHERE id = ?", (req.status, image_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── 更新备注 ─────────────────────────────────────────────
class UpdateNotesReq(BaseModel):
    notes: str


@app.patch("/api/images/{image_id}/notes")
def update_notes(image_id: int, req: UpdateNotesReq):
    conn = get_db()
    conn.execute("UPDATE images SET user_notes = ? WHERE id = ?", (req.notes, image_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── 批量删除 ─────────────────────────────────────────────
class BatchDeleteReq(BaseModel):
    ids: list[int]


@app.delete("/api/images/batch")
def batch_delete(req: BatchDeleteReq):
    if not req.ids:
        return {"deleted": 0}
    conn = get_db()
    deleted = 0
    for image_id in req.ids:
        row = conn.execute("SELECT filename FROM images WHERE id = ?", (image_id,)).fetchone()
        if row:
            f = UPLOAD_DIR / row["filename"]
            if f.exists():
                f.unlink()
            conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
            deleted += 1
    conn.commit()
    conn.close()
    return {"deleted": deleted}


# ── 收藏 ─────────────────────────────────────────────────
class FavoriteReq(BaseModel):
    is_favorite: bool


@app.patch("/api/images/{image_id}/favorite")
def toggle_favorite(image_id: int, req: FavoriteReq):
    conn = get_db()
    conn.execute("UPDATE images SET is_favorite = ? WHERE id = ?",
                 (1 if req.is_favorite else 0, image_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── 延展找图（核心新功能）────────────────────────────────
CATEGORY_KEYWORDS = {
    "same":   "同款风格",
    "top":    "上衣",
    "pants":  "裤子",
    "skirt":  "半裙 裙子",
    "dress":  "连衣裙",
    "coat":   "外套",
    "suit":   "套装",
}

REFINE_KEYWORDS = {
    "premium": "高级感 质感 设计师款",
    "new":     "2024新款 流行前沿",
    "unique":  "小众 独特 设计感 不普通",
    "summer":  "夏季 轻薄 夏款",
}

KEYWORD_PROMPT = """你是专业女装设计师，帮设计师在Google图片上找参考图。

根据以下图片信息，生成4个搜索关键词组合，用于Google图片搜索。

要求：
1. 每组关键词要具体，包含【具体单品名称】+【氛围/风格词】，不要只写风格标签
2. 中英文混搭效果更好（比如"法式碎花连衣裙 editorial"比"法式风格"好得多）
3. 加上场景词/平台词：lookbook、outfit、editorial、ins风、穿搭、小红书风、
4. 品类要对上目标品类：{target_category}
5. 如果有调整方向"{refine}"，体现在关键词里（比如"设计师款""小众""2024新款"）
6. 禁止直接把风格描述原封不动写成关键词（"法式慵懒风"这种太宽泛，没用）

图片信息：
- 风格描述：{style}
- 标签：{tags}
- 品类：{category}
- 色调：{color}
- 设计亮点：{notes}

只返回JSON数组，4个元素，不要其他内容：
["关键词组1","关键词组2","关键词组3","关键词组4"]

示例（法式复古连衣裙，找同款）：
["法式复古碎花连衣裙 小众设计","vintage floral midi dress editorial","慵懒法式穿搭 氛围感outfit","French girl dress lookbook ins风"]"""


def generate_keywords(img: dict, target_category: str, refine: str) -> list[str]:
    """用AI根据图片分析结果生成搜索关键词"""
    cat_label = CATEGORY_KEYWORDS.get(target_category, "同风格服装")
    refine_label = REFINE_KEYWORDS.get(refine, "")

    prompt = KEYWORD_PROMPT.format(
        style=img.get("ai_style", ""),
        tags=", ".join(json.loads(img.get("ai_tags", "[]") or "[]")),
        category=img.get("ai_category", ""),
        color=img.get("ai_color", ""),
        notes=img.get("ai_notes", ""),
        target_category=cat_label,
        refine=refine_label or "无",
    )

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
    )
    content = resp.choices[0].message.content.strip()
    # 清理代码块
    if "```" in content:
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()
    start, end = content.find("["), content.rfind("]")
    if start != -1 and end != -1:
        content = content[start:end+1]
    try:
        keywords = json.loads(content)
        return keywords if isinstance(keywords, list) else []
    except Exception:
        return []


def serper_search(query: str, num: int = 10) -> list[dict]:
    """调用 Serper.dev Google Images API"""
    if not SERPER_KEY:
        return []
    try:
        resp = httpx.post(
            "https://google.serper.dev/images",
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num, "gl": "cn", "hl": "zh-cn"},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for item in data.get("images", []):
            results.append({
                "title": item.get("title", ""),
                "image_url": item.get("imageUrl", ""),
                "thumbnail": item.get("thumbnailUrl", ""),
                "source_url": item.get("link", ""),
                "keyword": query,
            })
        return results
    except Exception:
        return []


class ExtendReq(BaseModel):
    image_id: int
    category: str = "same"   # same/top/pants/skirt/dress/coat/suit
    refine: str = ""          # premium/new/unique/summer/""


@app.post("/api/search/extend")
def extend_search(req: ExtendReq):
    """以一张参考图为起点，延展找同氛围感候选图"""
    if not SERPER_KEY:
        raise HTTPException(400, "未配置 SERPER_KEY，请先设置环境变量")

    conn = get_db()
    row = conn.execute("SELECT * FROM images WHERE id = ?", (req.image_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "图片不存在")

    img = dict(row)

    # 生成搜索关键词
    keywords = generate_keywords(img, req.category, req.refine)
    if not keywords:
        # 兜底：直接用AI分析结果拼关键词
        cat_label = CATEGORY_KEYWORDS.get(req.category, "")
        style = img.get("ai_style", "")
        keywords = [f"{style} {cat_label}".strip()] if style else [cat_label]

    # 附加品类和refine修饰词
    refine_suffix = REFINE_KEYWORDS.get(req.refine, "")
    cat_suffix = CATEGORY_KEYWORDS.get(req.category, "")

    results = []
    seen_urls = set()
    for kw in keywords[:4]:  # 4个关键词，每个搜10张
        query = kw  # 关键词本身已包含品类和refine信息
        items = serper_search(query, num=10)
        for item in items:
            url = item["image_url"]
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(item)

    return {
        "seed_id": req.image_id,
        "seed_style": img.get("ai_style", ""),
        "keywords_used": keywords,
        "category": req.category,
        "refine": req.refine,
        "results": results[:24],  # 最多返回24张
    }


# ── 删除 ─────────────────────────────────────────────────
@app.delete("/api/images/{image_id}")
def delete_image(image_id: int):
    conn = get_db()
    row = conn.execute("SELECT filename FROM images WHERE id = ?", (image_id,)).fetchone()
    if row:
        f = UPLOAD_DIR / row["filename"]
        if f.exists():
            f.unlink()
        conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()
    conn.close()
    return {"ok": True}


# ── 静态文件 ─────────────────────────────────────────────
@app.get("/uploads/{filename}")
def get_upload(filename: str):
    f = UPLOAD_DIR / filename
    if not f.exists():
        raise HTTPException(404, "图片不存在")
    return FileResponse(f)


app.mount("/", StaticFiles(directory=str(Path(__file__).parent / "static"), html=True), name="static")
