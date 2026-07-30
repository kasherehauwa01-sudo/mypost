import logging
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.config import settings
from app.db import SessionLocal
from app.mail_service import MailService
from app.repositories import AccountRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
scheduler = AsyncIOScheduler(); service = MailService()
async def sync_all():
    async with SessionLocal() as db:
        for account in await AccountRepository(db).list():
            if account.enabled: await service.sync(db, account)
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(sync_all, "interval", seconds=settings.sync_interval_seconds, max_instances=1, coalesce=True); scheduler.start()
    yield
    scheduler.shutdown(wait=False)
app = FastAPI(title="Моя почта API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
@app.get("/health")
async def health(): return {"status": "ok"}

