"""背景排程器 - 讀取 ScheduleConfigDB 自動執行 Pipeline.

設計原則：
  - 只有 DB 中有任何 enabled=True 的排程時才啟動 APScheduler
  - 全部停用時自動 shutdown（不佔背景 thread）
  - module-level singleton：Python 同一 process import 只執行一次，
    不需要 @st.cache_resource，頁面切換不會重複建立

排程判斷邏輯（每分鐘 check 一次）：
  - interval 模式：now - last_run >= interval_hours
  - cron 模式：今天 time_of_day 已過 且 last_run 不是今天
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# ── module-level singleton ──────────────────────────────────
_scheduler: BackgroundScheduler | None = None


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def start_scheduler() -> BackgroundScheduler:
    """啟動背景排程器（若已在執行則直接回傳）。"""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_pipeline_job,
        trigger="interval",
        minutes=1,
        id="pipeline_check",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("[Scheduler] Background scheduler started (check every 1 min)")
    return _scheduler


def stop_scheduler():
    """停止背景排程器並釋放 thread。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")
    _scheduler = None


def sync_scheduler_state():
    """讀取 DB，有任何 enabled=True 就 start，全部 False 就 stop。
    在 app.py 啟動時 以及 每次儲存排程設定後 呼叫。
    """
    from src.models.database import ScheduleConfigDB, SessionLocal

    db = SessionLocal()
    try:
        any_enabled = (
            db.query(ScheduleConfigDB)
            .filter(ScheduleConfigDB.enabled.is_(True))
            .count() > 0
        )
    finally:
        db.close()

    if any_enabled and not is_running():
        start_scheduler()
    elif not any_enabled and is_running():
        stop_scheduler()


# ── helpers ─────────────────────────────────────────────────

def _should_run(enabled: bool, mode: str, interval_hours: int,
                time_of_day: str, tz_name: str, last_run: datetime | None) -> bool:
    if not enabled:
        return False
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name or "Asia/Taipei")
    except Exception:
        tz = timezone.utc

    now = datetime.now(tz)

    if mode == "interval":
        if last_run is None:
            return True
        return (now - last_run.astimezone(tz)) >= timedelta(hours=interval_hours)

    # cron: once per day at time_of_day
    try:
        h, m = map(int, (time_of_day or "08:00").split(":"))
    except ValueError:
        h, m = 8, 0
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < target:
        return False
    if last_run is None:
        return True
    return last_run.astimezone(tz).date() < now.date()


# ── main job ────────────────────────────────────────────────

def _run_pipeline_job():
    """APScheduler job：每分鐘被呼叫，依 DB config 決定是否執行 pipeline。"""
    from src.models.database import ArticleDB, ScheduleConfigDB, SessionLocal, SourceDB

    db = SessionLocal()
    try:
        fs_cfg = db.query(ScheduleConfigDB).filter(ScheduleConfigDB.id == "fetch_summarize").first()
        pub_cfg = db.query(ScheduleConfigDB).filter(ScheduleConfigDB.id == "publish").first()
    finally:
        db.close()

    run_fetch = fs_cfg and _should_run(
        fs_cfg.enabled, fs_cfg.mode, fs_cfg.interval_hours,
        fs_cfg.time_of_day, fs_cfg.timezone, fs_cfg.last_run,
    )
    run_publish = pub_cfg and _should_run(
        pub_cfg.enabled, pub_cfg.mode, pub_cfg.interval_hours,
        pub_cfg.time_of_day, pub_cfg.timezone, pub_cfg.last_run,
    )

    if not run_fetch and not run_publish:
        return

    logger.info("[Scheduler] Starting pipeline job (fetch=%s, publish=%s)", run_fetch, run_publish)

    from src.llm.gemini_summarizer import GeminiSummarizer
    from src.orchestrator import DigestOrchestrator

    orch = DigestOrchestrator()

    if run_fetch:
        try:
            db = SessionLocal()
            try:
                sources = [
                    {"id": s.id, "url": s.url, "name": s.name, "enabled": s.enabled}
                    for s in db.query(SourceDB).filter(SourceDB.enabled.is_(True)).all()
                ]
            finally:
                db.close()

            result = asyncio.run(orch.run_fetch_pipeline(sources=sources))
            logger.info("[Scheduler] Fetch done: %d articles", result.articles_fetched)

            summarizer = GeminiSummarizer()
            db = SessionLocal()
            count = 0
            try:
                pending = db.query(ArticleDB).filter(ArticleDB.publish_status == "pending").all()
                for article in pending:
                    res = asyncio.run(summarizer.summarize({
                        "title": article.title,
                        "content": article.content or "",
                    }))
                    article.summary = json.dumps({
                        "title_zh": res.title_zh,
                        "summary_zh": res.summary_zh,
                        "key_points": res.key_points,
                        "tags": res.tags,
                    })
                    article.tags = json.dumps(res.tags)
                    article.publish_status = "summarized"
                    article.summarized_at = datetime.now(timezone.utc)
                    db.commit()
                    count += 1
            finally:
                db.close()
            logger.info("[Scheduler] Summarize done: %d articles", count)

            db = SessionLocal()
            try:
                sc = db.query(ScheduleConfigDB).filter(
                    ScheduleConfigDB.id == "fetch_summarize"
                ).first()
                if sc:
                    sc.last_run = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

        except Exception:
            logger.exception("[Scheduler] Fetch+Summarize failed")

    if run_publish:
        try:
            channels = json.loads(pub_cfg.channels or '["telegram"]')
            db = SessionLocal()
            try:
                summarized = db.query(ArticleDB).filter(
                    ArticleDB.publish_status == "summarized"
                ).all()
                article_dicts = []
                for a in summarized:
                    try:
                        sd = json.loads(a.summary or "{}")
                    except Exception:
                        sd = {}
                    article_dicts.append({
                        "id": a.id,
                        "title": sd.get("title_zh") or a.title,
                        "summary": sd.get("summary_zh", ""),
                        "url": a.source_url or "",
                        "source": a.source or "",
                        "tags": json.loads(a.tags or "[]"),
                    })
            finally:
                db.close()

            if article_dicts:
                result = asyncio.run(orch.run_publish_pipeline(
                    articles=article_dicts, channels=channels,
                ))
                db = SessionLocal()
                try:
                    for ad in article_dicts:
                        row = db.query(ArticleDB).filter(ArticleDB.id == ad["id"]).first()
                        if row:
                            row.publish_status = "published" if result.success else "failed"
                            row.published_at_channels = json.dumps({
                                ch: datetime.now(timezone.utc).isoformat() for ch in channels
                            })
                    sc = db.query(ScheduleConfigDB).filter(
                        ScheduleConfigDB.id == "publish"
                    ).first()
                    if sc:
                        sc.last_run = datetime.now(timezone.utc)
                    db.commit()
                finally:
                    db.close()
                logger.info("[Scheduler] Publish done: %d articles to %s",
                            result.published_count, channels)

        except Exception:
            logger.exception("[Scheduler] Publish failed")
