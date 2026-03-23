from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from contextlib import asynccontextmanager
import os

from app.database import init_db
from app.routers import auth, admin, user


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Atlas Valley Portal", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(user.router, prefix="/api")


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/")
async def home(request: Request):
    from app.services.auth import get_current_user_from_request
    user = get_current_user_from_request(request)
    if user:
        if user.get("is_admin"):
            return RedirectResponse(url="/admin", status_code=302)
        return RedirectResponse(url="/portal", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/portal")
async def portal(request: Request):
    from app.services.auth import get_current_user_from_request
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    if user.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("portal.html", {"request": request, "user": user})


@app.get("/admin")
async def admin_panel(request: Request):
    from app.services.auth import get_current_user_from_request
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    if not user.get("is_admin"):
        return RedirectResponse(url="/portal", status_code=302)
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})
