import json
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai_analyze import analyze_image
from database import get_db, init_db

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
def get_images(status: str = None, platform: str = None, limit: int = 50, offset: int = 0):
    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if platform:
        conditions.append("source_platform = ?")
        params.append(platform)

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
