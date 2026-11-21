"""Predictive Maintenance demo API.

Run (dev):  uvicorn app.main:app --reload --no-server-header
"""
from __future__ import annotations

import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .assistant import Assistant
from .config import Settings
from .fleet import Fleet
from .knowledge import KnowledgeBase
from .schemas import (DiagnoseRequest, DiagnoseResponse, EngineDetail, FleetResponse, WorkOrder,
                      WorkOrderCreate)
from .security import (CSRF_HEADER, BodySizeLimitMiddleware, RateLimiter, SecurityHeadersMiddleware,
                       client_ip, require_csrf_header, security_log)
from .workorders import WorkOrderStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    fleet = Fleet()
    kb = KnowledgeBase()
    assistant = Assistant(settings, fleet, kb)
    orders = WorkOrderStore()
    limiter = RateLimiter()

    app = FastAPI(
        title="Predictive Maintenance API",
        # API docs are exposed only in development (A05: smaller attack surface)
        docs_url="/api/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.is_dev else None,
    )

    # Middleware runs outermost-last: headers -> body limit -> trusted host -> CORS -> routes
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["content-type", CSRF_HEADER], max_age=600)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.enable_hsts)

    # ---------- Error handling: no stack traces or echoed input to clients (A05 / A09) ----------
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()][:10]
        security_log.info("validation_failed path=%s count=%d", request.url.path, len(exc.errors()))
        return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        ref = uuid.uuid4().hex[:8]
        log.error("unhandled_error ref=%s path=%s type=%s", ref, request.url.path, type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "ref": ref})

    def rate_limit(bucket: str, limit: int):
        def dependency(request: Request) -> None:
            ip = client_ip(request, settings.trust_proxy_headers)
            if not limiter.check(ip, bucket, limit):
                security_log.warning("rate_limited bucket=%s", bucket)
                raise HTTPException(status_code=429, detail="Too many requests, please slow down",
                                    headers={"Retry-After": "60"})
        return dependency

    def get_engine(engine_id: int):
        engine = fleet.get(engine_id)
        if engine is None:
            raise HTTPException(status_code=404, detail="Engine not found")
        return engine

    read_limit = Depends(rate_limit("read", 600))

    # ---------- Routes ----------
    @app.get("/api/health", dependencies=[read_limit])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/fleet", response_model=FleetResponse, dependencies=[read_limit])
    def get_fleet(clock: int = Query(1, ge=1, le=400)) -> FleetResponse:
        return fleet.fleet(min(clock, fleet.max_clock))

    @app.get("/api/engines/{engine_id}", response_model=EngineDetail, dependencies=[read_limit])
    def get_engine_detail(engine_id: int, clock: int = Query(1, ge=1, le=400)) -> EngineDetail:
        if not 1 <= engine_id <= 99:
            raise HTTPException(status_code=404, detail="Engine not found")
        return fleet.detail(get_engine(engine_id), min(clock, fleet.max_clock))

    @app.post("/api/assistant/diagnose", response_model=DiagnoseResponse,
              dependencies=[Depends(require_csrf_header),
                            Depends(rate_limit("assistant", settings.rate_limit_assistant))])
    def diagnose(body: DiagnoseRequest) -> DiagnoseResponse:
        engine = get_engine(body.engine_id)
        log.info("diagnose engine=%d clock=%d question_len=%d", body.engine_id, body.clock, len(body.question))
        return assistant.diagnose(engine, min(body.clock, fleet.max_clock), body.question)

    @app.get("/api/work-orders", response_model=list[WorkOrder], dependencies=[read_limit])
    def list_work_orders() -> list[WorkOrder]:
        return orders.list()

    @app.post("/api/work-orders", response_model=WorkOrder, status_code=201,
              dependencies=[Depends(require_csrf_header), Depends(rate_limit("write", settings.rate_limit_write))])
    def create_work_order(body: WorkOrderCreate) -> WorkOrder:
        get_engine(body.engine_id)
        order = orders.create(body)
        security_log.info("work_order_created id=%s engine=%d priority=%s", order.id, order.engine_id, order.priority)
        return order

    return app


app = create_app()
