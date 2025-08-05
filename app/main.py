from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from routers import elevator
from auth import auth_router

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

app.include_router(elevator.router)
app.include_router(auth_router.router)

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def root(request: Request):
    # セッションにユーザーがいるかを確認
    if "user" in request.session:
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": request.session["user"]})
    else:
        return RedirectResponse(url="/login")
