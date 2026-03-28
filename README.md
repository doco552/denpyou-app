# 仕入れ伝票 自動読み取りアプリ

仕入れ市場の買伝票を撮影した画像から商品データを自動で読み取り、Excelファイルとして出力するツールです。

## セットアップ

### 1. 依存ライブラリのインストール

```bash
cd densho-app
pip install -r requirements.txt
```

### 2. APIキーの設定

`.env` ファイルにGemini APIキーを記述します。

```
GEMINI_API_KEY=your_api_key_here
```

Google AI Studio（https://aistudio.google.com/）でAPIキーを取得できます。

### 3. アプリの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

## 使い方

1. 仕入れ伝票の画像（JPG / PNG）をアップロード
2. 「読み取り開始」ボタンをクリック
3. 解析結果をテーブルで確認
4. 「Excelダウンロード」ボタンでファイルを保存

## 出力ファイル

- ファイル名: `YYYYMMDD_市場名.xlsx`（例: `20260323_石川道具市場.xlsx`）
- 列構成: 年月日、場所、品目、特徴、型番、仕入値
- 年月日は YYYY/MM/DD 形式、仕入値は数値型で出力
