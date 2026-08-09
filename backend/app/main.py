import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .audit import safe_request_id
from .database import Base, SessionLocal, engine
from .routers import applications, auth, business_data, credentials, dashboard, legal, media, merchants, onboarding, resources, system, users
from .seed import seed_database

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("wanzhou")
upload_dir = Path(get_settings().upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().environment != "production":
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(
    title=get_settings().app_name,
    version="1.0.0",
    description="万州中小商户数字化助手平台 API",
    lifespan=lifespan,
    docs_url=None if get_settings().environment == "production" else "/api/docs",
    openapi_url=(
        None
        if get_settings().environment == "production"
        else "/api/openapi.json"
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = safe_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    request.state.user_id = None
    started = time.perf_counter()
    response_status = 500
    try:
        response = await call_next(request)
        response_status = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/api/v1/") and not request.url.path.startswith(
            "/api/v1/health"
        ):
            response.headers.setdefault("Cache-Control", "no-store, private")
            response.headers.setdefault("Pragma", "no-cache")
    finally:
        logger.info(
            "request_id=%s user_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.state.user_id,
            request.method,
            request.url.path,
            response_status,
            (time.perf_counter() - started) * 1000,
        )
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "请求失败")
        data = exc.detail.get("data")
    else:
        message = str(exc.detail)
        data = None
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": message, "data": data},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first.get("loc", []) if item != "body")
    message = first.get("msg", "请求参数不正确")
    return JSONResponse(status_code=422, content={"code": 422, "message": f"{location}: {message}" if location else message, "data": None})


@app.get("/api/v1/health/live")
def health_live():
    return {"code": 0, "message": "healthy", "data": {"service": "wanzhou-api", "version": "1.0.0"}}


@app.get("/api/v1/health/ready")
def health_ready():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    if not upload_dir.is_dir() or not os.access(upload_dir, os.W_OK):
        raise HTTPException(status_code=503, detail="上传目录不可写")
    return {
        "code": 0,
        "message": "ready",
        "data": {"database": "healthy", "uploads": "writable"},
    }


@app.get("/api/v1/health")
def health():
    return health_live()


app.include_router(auth.router, prefix="/api/v1")
app.include_router(legal.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(merchants.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(credentials.router, prefix="/api/v1")
app.include_router(business_data.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(resources.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
