from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.database import init_db
from src.api.routes import documents, domains, learning, modules


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="KGI Knowledge Shredder API",
    description="金融業微型學習平台 — 知識粉碎機",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(domains.router)
app.include_router(modules.router)
app.include_router(learning.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """確保所有未預期的 500 錯誤都以 JSON 格式回傳，前端可正確解析。"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"伺服器內部錯誤：{type(exc).__name__}: {str(exc)[:300]}"},
    )

_STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/static/trainer.html")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
