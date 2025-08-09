from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from routers import elevator
from auth import auth_router
import pandas as pd
from pathlib import Path
import os

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
app.include_router(elevator.router)
app.include_router(auth_router.router)

templates = Jinja2Templates(directory="templates")

# ====================== 共通：エレベーター一覧 ======================
ELEVATOR_CSV = Path("data") / "エレベーター一覧.csv"
def load_elevator_df() -> pd.DataFrame:
    for enc in ("cp932", "utf-8-sig"):
        try:
            df = pd.read_csv(ELEVATOR_CSV, encoding=enc)
            if "削除" in df.columns:
                df = df[df["削除"] != "削除"]
            return df
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return pd.DataFrame()
    return pd.DataFrame()

@app.get("/")
async def root(request: Request):
    if "user" in request.session:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": request.session["user"]})
    else:
        return RedirectResponse(url="/login")

@app.get("/inspection/select", response_class=HTMLResponse)
async def inspection_select(request: Request, kanri: str = ""):
    df = load_elevator_df()
    genba = "不明"
    if not df.empty and "管理番号" in df.columns and "現場名" in df.columns and kanri:
        hit = df[df["管理番号"] == kanri]
        if not hit.empty:
            genba = str(hit.iloc[0]["現場名"])
    return templates.TemplateResponse("inspection_select.html", {"request": request, "kanri": kanri, "genba": genba})

@app.get("/inspection/contact", response_class=HTMLResponse)
async def contact_maker_select(request: Request, kanri: str = ""):
    df = load_elevator_df()
    genba = "不明"
    if not df.empty and "管理番号" in df.columns and "現場名" in df.columns and kanri:
        hit = df[df["管理番号"] == kanri]
        if not hit.empty:
            genba = str(hit.iloc[0]["現場名"])
    return templates.TemplateResponse("contact_maker_select.html", {"request": request, "kanri": kanri, "genba": genba})

# ====================== 東芝：電磁接触器（既存フロー） ======================
TOSHIBA_CSV = os.path.join("data", "東芝", "東芝電磁接触器判定表.csv")
def load_toshiba_df():
    try:
        return pd.read_csv(TOSHIBA_CSV, encoding="utf-8-sig", dtype=str, low_memory=False)
    except FileNotFoundError:
        return pd.DataFrame()

# 画面では選択させず、結果だけに出す列（既存）
RESULT_FIELDS_AFTER = [
    "主回路電磁接触器フェールセーフ該当有無",
    "電動機主回路用接触器判定基準用コメント",
    "電動機主回路用接触器判定基準",
    "ブレーキ電磁接触器フェールセーフ該当有無",
    "ブレーキ用接触器判定基準",
    "ブレーキ電磁接触器②フェールセーフ該当有無",
    "ブレーキ用接触器②判定基準",
    "備考",
]
COMMENT_FIELDS_AFTER = [
    "電動機主回路用接触器目視確認可否コメント",
    "ブレーキ用接触器目視確認可否コメント",
    "ブレーキ用接触器②目視確認可否コメント",
]

@app.get("/inspection/contact/toshiba", response_class=HTMLResponse)
async def toshiba_selector_page(request: Request, kanri: str = ""):
    df_elev = load_elevator_df()
    genba = "不明"
    if not df_elev.empty and "管理番号" in df_elev.columns and "現場名" in df_elev.columns and kanri:
        hit = df_elev[df_elev["管理番号"] == kanri]
        if not hit.empty:
            genba = str(hit.iloc[0]["現場名"])
    return templates.TemplateResponse("toshiba_electromagnetic_selector.html", {"request": request, "kanri": kanri, "genba": genba})

@app.post("/inspection/contact/toshiba/options")
async def toshiba_options(payload: dict):
    """
    電磁接触器：分類→制御盤型式→傾斜有無→CSV列順で一つずつ返す。
    コメントは comment、結果用列はスキップ、選択は options を返却。
    """
    df = load_toshiba_df()
    if df.empty:
        return JSONResponse({"error": "CSV not found"}, status_code=404)
    df = df.fillna("")

    selected: dict = payload.get("selected", {})

    # 1) 分類
    if "分類" not in selected:
        kinds = sorted(set(df.get("分類", [])) - {""})
        return {"field": "分類", "options": kinds}

    # 2) 制御盤型式
    if "制御盤型式" not in selected:
        subset = df[df.get("分類", "") == selected["分類"]]
        models = sorted(set(subset.get("制御盤型式", [])) - {""})
        return {"field": "制御盤型式", "options": models}

    # 3) 傾斜有無
    if "傾斜有無" not in selected:
        subset = df[
            (df.get("分類", "") == selected["分類"]) &
            (df.get("制御盤型式", "") == selected["制御盤型式"])
        ]
        slope_vals = sorted(set(subset.get("傾斜有無", [])) - {""})
        if not slope_vals:
            return {"field": "傾斜有無", "skip": True}
        elif len(slope_vals) == 1:
            return {"field": "傾斜有無", "options": slope_vals, "auto_select": True}
        else:
            return {"field": "傾斜有無", "options": slope_vals}

    # 以降：CSV左→右
    subset = df.copy()
    for col, val in selected.items():
        if col in subset.columns and val != "":
            subset = subset[subset[col] == val]

    cols = list(df.columns)
    try:
        start_idx = cols.index("傾斜有無") + 1
    except ValueError:
        start_idx = 0
    for col in cols[start_idx:]:
        if col not in subset.columns:
            continue
        if col in selected:
            if selected[col] != "":
                subset = subset[subset[col] == selected[col]]
            continue

        if col in COMMENT_FIELDS_AFTER:
            vals = sorted(set(subset[col]) - {""})
            text = vals[0] if len(vals) == 1 else (" / ".join(vals[:5]) if vals else "")
            return {"field": col, "comment": text}

        if col in RESULT_FIELDS_AFTER:
            continue

        vals = sorted(set(subset[col]) - {""})
        if not vals:
            return {"field": col, "skip": True}
        if len(vals) == 1:
            return {"field": col, "options": vals, "auto_select": True}
        return {"field": col, "options": vals}

    return {"done": True, "result_ready": True}

# ====================== 東芝：UPS 対応表（新規） ======================
UPS_CSV = os.path.join("data", "東芝", "東芝UPS対応表.csv")

def load_ups_df():
    try:
        return pd.read_csv(UPS_CSV, encoding="utf-8-sig", dtype=str, low_memory=False)
    except FileNotFoundError:
        return pd.DataFrame()

@app.post("/inspection/contact/toshiba/ups/options")
async def toshiba_ups_options(payload: dict):
    """
    UPS：分類はスキップ。最初に
    '主回路電磁接触器フェールセーフ該当有無' を
    東芝電磁接触器判定表.csv からサーバ側で導出し auto_fill（変更不可）、
    以降は UPS CSV を左→右で選択（空欄skip・1種auto）。
    """
    df_ups = load_ups_df()
    if df_ups.empty:
        return JSONResponse({"error": "UPS CSV not found"}, status_code=404)
    df_ups = df_ups.fillna("")

    base_selected: dict = payload.get("baseSelected", {})  # 画面の通常選択
    ups_selected: dict  = payload.get("upsSelected", {})   # UPS側の途中選択

    # --- 既に確定済みの UPS 列でフィルタ ---
    subset_ups = df_ups.copy()
    for col, val in ups_selected.items():
        if col in subset_ups.columns and val != "":
            subset_ups = subset_ups[subset_ups[col] == val]

    cols = list(df_ups.columns)
    try:
        start_idx = cols.index("分類") + 1   # 分類はUI非表示・スキップ
    except ValueError:
        start_idx = 0
    step_cols = cols[start_idx:]

    # --- 1手目：主回路電磁接触器フェールセーフ該当有無 をサーバ側で導出 ---
    FS_COL = "主回路電磁接触器フェールセーフ該当有無"
    if FS_COL not in ups_selected:
        # baseSelected には結果項目が入っていないので、東芝のメインCSVから導出する
        df_main = load_toshiba_df().fillna("")
        subset_main = df_main.copy()
        # 画面で選ばれた項目だけで絞り込む
        for col, val in base_selected.items():
            if col in subset_main.columns and val != "":
                subset_main = subset_main[subset_main[col] == val]
        # 該当列のユニーク値を取得（空は除外）
        vals = sorted(set(subset_main[FS_COL]) - {""}) if FS_COL in subset_main.columns else []
        auto_val = vals[0] if vals else ""  # 1件想定。無い場合は空（その場合はUPS側で全候補が出る）
        return {"field": FS_COL, "auto_fill": auto_val}

    # --- 以降：UPS CSV を左→右で選択。フェールセーフ列は除外（自動設定済） ---
    for col in step_cols:
        if col == FS_COL:
            continue
        if col not in subset_ups.columns:
            continue
        # 既に決定していれば前進
        if col in ups_selected:
            if ups_selected[col] != "":
                subset_ups = subset_ups[subset_ups[col] == ups_selected[col]]
            continue
        # 未決定：候補提示
        vals = sorted(set(subset_ups[col]) - {""})
        if not vals:
            return {"field": col, "skip": True}
        if len(vals) == 1:
            return {"field": col, "options": vals, "auto_select": True}
        return {"field": col, "options": vals}

    # 全列決定
    return {"upsDone": True}

# ====================== 結果ページ ======================
@app.post("/inspection/contact/toshiba/result", response_class=HTMLResponse)
async def toshiba_show_result(request: Request, payload: dict):
    df = load_toshiba_df().fillna("")
    selected = payload.get("selected", {})      # 電磁接触器の全選択
    ups_sel  = payload.get("ups", {}) or {}     # UPSの全選択（あれば）

    # 電磁接触器の1行抽出（UPS列で絞らない）
    subset = df.copy()
    for col, val in selected.items():
        if col in subset.columns and val != "":
            subset = subset[subset[col] == val]
    row = subset.iloc[0].to_dict() if not subset.empty else {}

    # 「該当型式無」→ 現地型式 を優先表示するためのマッピング
    LOCAL_MODEL_KEYS = {
        "電動機主回路用接触器型式": "電動機主回路用接触器型式_現地型式",
        "ブレーキ用接触器型式": "ブレーキ用接触器型式_現地型式",
        "ブレーキ用接触器型式②": "ブレーキ用接触器型式②_現地型式",
    }

    # 値取得ヘルパ（row→selected→ups_sel の順で補完。型式は現地型式を優先）
    def val_of(colname: str) -> str:
        v = row.get(colname, "")
        if colname in LOCAL_MODEL_KEYS and (v == "" or v == "該当型式無"):
            local = selected.get(LOCAL_MODEL_KEYS[colname], "")
            if local:
                return local
        if v not in (None, ""):
            return v
        v2 = selected.get(colname, "")
        if v2 not in (None, ""):
            return v2
        return ups_sel.get(colname, "")

    # 既存3グループ
    RESULT_GROUPS = {
        "電動機用接触器": [
            ("名称", "電動機主回路用接触器名称"),
            ("フェールセーフ", "主回路電磁接触器フェールセーフ該当有無"),
            ("型式", "電動機主回路用接触器型式"),
            ("判定結果", "電動機主回路用接触器目視確認判定結果"),
            ("判定基準用コメント", "電動機主回路用接触器判定基準用コメント"),
            ("判定基準", "電動機主回路用接触器判定基準"),
        ],
        "ブレーキ用接触器①": [
            ("名称", "ブレーキ用接触器名称"),
            ("フェールセーフ", "ブレーキ電磁接触器フェールセーフ該当有無"),
            ("型式", "ブレーキ用接触器型式"),
            ("判定結果", "ブレーキ用接触器目視確認判定結果"),
            ("判定基準用コメント", "ブレーキ用接触器判定基準用コメント"),
            ("判定基準", "ブレーキ用接触器判定基準"),
        ],
        "ブレーキ用接触器②": [
            ("名称", "ブレーキ用接触器名称②"),
            ("フェールセーフ", "ブレーキ電磁接触器②フェールセーフ該当有無"),
            ("型式", "ブレーキ用接触器型式②"),
            ("判定結果", "ブレーキ用接触器②目視確認判定結果"),
            ("判定基準用コメント", "ブレーキ用接触器②判定基準用コメント"),
            ("判定基準", "ブレーキ用接触器②判定基準"),
        ],
    }

    grouped = []
    for title, pairs in RESULT_GROUPS.items():
        rows = [{"label": lbl, "value": (val_of(col) or "—")} for (lbl, col) in pairs]
        grouped.append({"title": title, "rows": rows})

    # ★ UPSグループ（UPS有りのときだけ追加）
    if selected.get("停電時自動着床装置の有無") == "有" and ups_sel:
        ups_rows = [
            ("名称", "電動機主回路用接触器名称"),
            ("フェールセーフ", "UPS主回路電磁接触器フェールセーフ該当有無"),
            ("型式", "電動機主回路用接触器型式"),
            ("判定結果", "電動機主回路用接触器目視確認可否"),
            ("判定基準", "電動機主回路用接触器判定基準"),
        ]
        rows = [{"label": lbl, "value": (val_of(col) or "—")} for (lbl, col) in ups_rows]
        grouped.insert(1, {"title": "停電時自動着床装置用接触器", "rows": rows})  # 電動機の下に差し込む

    choices = {**selected, **ups_sel}
    return templates.TemplateResponse(
        "toshiba_electromagnetic_result.html",
        {"request": request, "choices": choices, "grouped": grouped}
    )
