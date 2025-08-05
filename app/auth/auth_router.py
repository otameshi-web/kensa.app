from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import csv
import bcrypt

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        with open("data/users.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not row.get("email"):
                    continue

                if row["email"].strip() == email:
                    stored_hash = row["hashed_password"].strip().encode("utf-8")
                    if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                        user_name = row.get("name", "").strip()
                        request.session["user"] = user_name
                        return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "ログインに失敗しました"
        })
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"システムエラー: {str(e)}"
        })
