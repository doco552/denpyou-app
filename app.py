import io
import openpyxl
from openpyxl.styles import Alignment
import streamlit as st
import pandas as pd
from extractor import preprocess_image, extract_items

st.set_page_config(page_title="仕入れ伝票 自動読み取りアプリ", layout="centered")
st.title("🧾 仕入れ伝票 自動読み取りアプリ")

# --- 画像アップロード ---
uploaded_file = st.file_uploader(
    "画像をアップロード（JPG / PNG）",
    type=["jpg", "jpeg", "png"],
)

if uploaded_file:
    st.image(uploaded_file, caption="アップロードされた画像", use_container_width=True)

    if st.button("読み取り開始", type="primary"):
        with st.spinner("読み取り中..."):
            try:
                image_bytes = preprocess_image(uploaded_file)
                items = extract_items(image_bytes)
            except ValueError as e:
                st.error(f"エラー: {e}")
                st.stop()
            except Exception as e:
                st.error(f"予期しないエラーが発生しました: {e}")
                st.stop()

        if not items:
            st.warning("商品データが見つかりませんでした。")
            st.stop()

        # --- ヘッダー情報 ---
        purchase_date = items[0].get("purchase_date") or ""
        location = items[0].get("location") or ""
        st.subheader("読み取り結果")
        col1, col2 = st.columns(2)
        col1.metric("仕入日", purchase_date)
        col2.metric("仕入先", location)

        # --- テーブル表示（品目・特徴・仕入値の3列）---
        DISPLAY_COLUMNS = {
            "item_name": "品目",
            "features": "特徴",
            "purchase_price": "仕入値",
        }
        df = pd.DataFrame(items)
        for col in DISPLAY_COLUMNS:
            if col not in df.columns:
                df[col] = None

        display_df = df[list(DISPLAY_COLUMNS.keys())].rename(columns=DISPLAY_COLUMNS)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # --- 合計仕入れ額 ---
        total = pd.to_numeric(df.get("purchase_price", pd.Series(dtype=float)), errors="coerce").fillna(0)
        total_amount = int(total.sum())
        st.markdown(f"**合計仕入れ額: ¥{total_amount:,}**")

        # --- Excel生成 ---
        wb = openpyxl.Workbook()
        ws = wb.active
        headers = ["年月日", "場所", "品目", "特徴", "型番 年式", "仕入値", "売値", "差額", "売却日", "in", "out", "差額合計"]
        ws.append(headers)

        for item in items:
            price = item.get("purchase_price")
            price_val = int(price) if price is not None else None
            ws.append([
                item.get("purchase_date") or "",
                item.get("location") or "",
                item.get("item_name") or "",
                item.get("features") or "",
                "",          # 型番 年式：常に空白
                price_val,
                "",          # 売値：空白（手入力）
                "",          # 差額：空白（手入力）
                "",          # 売却日：空白（手入力）
                "",          # in：空白（手入力）
                "",          # out：空白（手入力）
                "",          # 差額合計：空白（手入力）
            ])

        center = Alignment(horizontal="center", vertical="center")
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = center

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        excel_bytes = excel_buf.getvalue()

        # ファイル名: 20260323_サンプル市場.xlsx
        date_str = purchase_date.replace("/", "") if purchase_date else "unknown"
        location_str = location if location else "unknown"
        filename = f"{date_str}_{location_str}.xlsx"

        st.download_button(
            label="Excelダウンロード",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("JPG・PNG 形式の仕入れ伝票画像をアップロードしてください。")
