import os
import json
import io
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

PROMPT = """
あなたはリサイクルショップの仕入れ伝票を読み取るAIアシスタントです。
この画像は仕入れ市場で発行された「買伝票」です。

以下のルールに従って、全商品をJSON配列形式で返してください。

【品名の読み取りルール】
- 「2 22' バナニ槽式洗濯機 5kg」の場合
  → 先頭の数字(2)は管理番号なので除外
  → 「22'」は年式なので除外
  → item_name = 「バナニ槽式洗濯機」
  → features = 「5kg」
- 色・サイズ・容量など特徴はfeaturesに入れること
- 「×2」「x2」「×8」などの数量表記はfeaturesに入れること
- 年式（22'など）は出力しないこと

【その他のルール】
- purchase_dateとlocationはヘッダーから読み取ること
- 仕入先は市場名のみ（「株式会社」などは省略）
- 型番（登録番号）はTから始まる英数字が多い。なければnull
- 読み取れない場合はnullを返すこと
- 合計金額行・税金行・参加費行は商品として含めないこと

返答は以下のJSON形式のみ（説明文不要）:
[
  {
    "purchase_date": "YYYY/MM/DD",
    "location": "市場名",
    "item_name": "品目名",
    "features": "特徴" または null,
    "model_number": "型番" または null,
    "purchase_price": 仕入れ値（整数）または null
  }
]
"""

MAX_SIZE = 1600


def preprocess_image(uploaded_file) -> bytes:
    """画像を最大1600pxに縮小してJPEG形式で返す"""
    img = Image.open(uploaded_file)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > MAX_SIZE:
        ratio = MAX_SIZE / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def extract_items(image_bytes: bytes) -> list[dict]:
    """Gemini APIに画像を送信してアイテムリストを返す"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "GEMINI_API_KEY に無効な文字が含まれています。\n"
            ".env ファイルの GEMINI_API_KEY=... の部分を実際の API キーに書き換えてください。"
        )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            PROMPT,
        ],
    )

    raw_text = response.text.strip()

    # ```json ... ``` ブロックを除去
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)

    try:
        items = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSONのパースに失敗しました: {e}\n\nAPIの返答:\n{raw_text}")

    if not isinstance(items, list):
        raise ValueError("APIの返答がリスト形式ではありません。")

    return items
