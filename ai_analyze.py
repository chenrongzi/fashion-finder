import base64
import json
import os
from openai import OpenAI

try:
    from config import API_KEY, BASE_URL, MODEL  # type: ignore
except ImportError:
    API_KEY  = os.environ.get("API_KEY",  "")
    BASE_URL = os.environ.get("BASE_URL", "https://x666.me/v1")
    MODEL    = os.environ.get("MODEL",    "gemini-3-flash-preview")

PROMPT = """你是专业女装设计师助手。分析这张服装图片，只返回一行紧凑JSON，不要换行不要空格不要代码块：
{"tags":["标签1","标签2","标签3"],"style":"风格描述15字内","color":"主色调","category":"品类","notes":"设计亮点40字内","fabric":"面料材质（如棉麻/针织/丝绸/雪纺/牛仔/皮革，不确定写空字符串）","silhouette":"版型（如A字/H型/修身/宽松/oversize/收腰，不确定写空字符串）","details":["设计细节1","设计细节2"]}
品类只能是：上衣/连衣裙/裤子/半裙/外套/套装/配饰/其他
details举例：钩花镂空/泡泡袖/开叉/抽绳/扎染/蕾丝边/立体花/压褶/拼接/开襟/收褶/系带"""


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
        content = content[start:] + '"}'

    try:
        result = json.loads(content)
        # 兼容旧格式：确保新字段存在
        result.setdefault("fabric", "")
        result.setdefault("silhouette", "")
        result.setdefault("details", [])
        return result
    except Exception:
        return {
            "tags": [], "style": content[:30] if content else "分析失败",
            "color": "", "category": "", "notes": "",
            "fabric": "", "silhouette": "", "details": [],
        }
