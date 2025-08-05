from fastapi import APIRouter, Query, HTTPException
import pandas as pd
import os

router = APIRouter()

CSV_PATH = os.path.join("data", "エレベーター一覧.csv")

# CSV読み込み（エラー時は空のDataFrame）
try:
    elevator_df = pd.read_csv(CSV_PATH, encoding="cp932")
except Exception as e:
    print(f"CSV読み込みエラー: {e}")
    elevator_df = pd.DataFrame()

@router.get("/api/elevator")
def get_elevator_info(kanri: str = Query(..., alias="kanri")):
    row = elevator_df[elevator_df["管理番号"] == kanri]
    if row.empty:
        raise HTTPException(status_code=404, detail="管理番号が見つかりません")
    return {
        "genba": row.iloc[0]["現場名"],
        "maker": row.iloc[0]["メーカー"],
        "model": row.iloc[0]["機種"]
    }

@router.get("/api/elevator/list")
def list_kanri_bangou():
    return elevator_df["管理番号"].dropna().unique().tolist()
