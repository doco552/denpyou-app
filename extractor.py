import os
import json
import io
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

PROMPT = """
あなたはベテランの古物商および市場の鑑定士です。手書きの崩れ文字や、かすれた古い伝票を正確に読み取るプロフェッショナルです。
この画像は仕入れ市場で発行された「買伝票」です。

以下のルールに従って、全商品をJSON配列形式で返してください。

【絶対厳守：全行抽出ルール】
- 伝票内の商品行は絶対にスキップしないこと。1行も読み飛ばさないこと
- 「摘要」「お品代」「明細」「商品名」「品物」など、列の見出し表現が異なっていても「品名」として柔軟に解釈し、必ず全行を抽出すること
- 単価・金額が読めなくても、品名が読めるなら行ごと捨てずに「読めた部分だけ」を確実に出力すること（読めなかったフィールドはnullにする）
- 合計金額行・税金行・参加費行・小計行のみ除外すること（それ以外は必ず含める）

【推測・補完ルール】
- 多少の崩れ文字やかすれであっても、前後の文脈や一般的な単語（メーカー名、家電の種類など）から90%以上の確度で推測できる場合は、補完して出力してよい
- どうしても読めない箇所のみ「判読不可」とすること

【出力フォーマットルール】
- 金額や数量のデータにカンマ（,）や円記号（¥、円）が含まれている場合はそれらを取り除き、純粋な半角数字のみを出力すること
- 指定された出力フォーマット（JSON）を厳密に守り、余計な挨拶や説明は一切省くこと

【品名の読み取りルール】
- 「2 22' バナニ槽式洗濯機 5kg」の場合
  → 先頭の数字(2)は管理番号なので除外
  → 「22'」は年式なので除外
  → item_name = 「バナニ槽式洗濯機」
  → features = 「5kg」
- 色・サイズ・容量など特徴はfeaturesに入れること
- 「×2」「x2」「×8」などの数量表記はfeaturesに入れること
- 年式（22'など）は出力しないこと

【エアコン専用ルール】（伝票に「エアコン」「クーラー」「〇〇クーラー」と読み取れる商品に適用）
- item_name は必ず「エアコン」の1単語のみとする。メーカー名・能力・年式は一切含めないこと
  （例: 「ダイキンクーラー」「ダイキンエアコン」「エアコン」→ すべて item_name = 「エアコン」）
- features にはスペース区切りで次の3要素のみをまとめて入れること：
  1. メーカー名（例: パナソニック、ダイキン、日立 など）
  2. 能力値：「2.2」「2.8」など小数点を含む数字。後ろに「k」「kw」「px」などのかすれ文字が付いていても数字部分のみ採用すること
  3. 製造年（例: 21製 → 「2021年製」に変換して出力）
  → 出力例: features = 「パナソニック 2.8 2021年製」
  → 読み取れない要素はその要素だけ省略し、読み取れた要素のみ出力すること
- model_number は必ず null にすること
- 「配管折れ」「動作確認済」などの状態メモ、「px」などの判読不明文字は features にも model_number にも含めないこと（完全に無視）

【除外・無視ルール】
- 「T」から始まる13桁の番号（インボイス登録番号）は型番ではないため、model_number には含めずnullにすること
  （例: 「T1234567890123」のような13桁 → model_number = null）

【その他のルール】
- purchase_dateとlocationはヘッダーから読み取ること
- 仕入先は市場名のみ（「株式会社」などは省略）
- 型番（登録番号）はTから始まる英数字が多いが、13桁のインボイス番号は除く。なければnull

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
