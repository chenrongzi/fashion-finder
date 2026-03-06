import base64
import json
import os
from openai import OpenAI

API_KEY  = os.environ.get("API_KEY",  "")
BASE_URL = os.environ.get("BASE_URL", "https://x666.me/v1")
MODEL    = os.environ.get("MODEL",    "gemini-3-flash-preview")

PROMPT = """你是专业女装设计师助手。分析这张服装图片，只返回一行紧凑JSON，不要换行不要空格不要代码块：
{"tags":["标签1","标签2","标签3"],"style":"风格描述15字内","color":"主色调","category":"品类","notes":"设计亮点40字内"}
品类只能是：上衣/连衣裙/裤子/半裙/外套/套装/配饰/其他"""


def get_client():
    return OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )


def analyze_image(image_data: bytes, filename: str) -> dict:
    client = get_client()

    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpg"
    mime = "image/png" if suffix == "png" else "image/jpeg"
    b64 = base64.b64encode(image_data).decode()

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        max_tokens=1024,
    )

    content = resp.choices[0].message.content.strip()
    # 清理 markdown 代码块
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    # 找到第一个 { 和最后一个 }，容错截断
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end+1]
    elif start != -1:
        # JSON 被截断，尝试补全
        content = content[start:] + '"}'

    try:
        return json.loads(content)
    except Exception:
        return {"tags": [], "style": content[:30] if content else "分析失败", "color": "", "category": "", "notes": ""}
