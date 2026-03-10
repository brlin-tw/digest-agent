"""文章列表頁面 - 瀏覽、篩選、管理、手動發佈."""

import asyncio
import json
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(page_title="文章列表 - Digest Agent", page_icon="📰", layout="wide")

from src.models.database import ArticleDB, SessionLocal  # noqa: E402
from src.orchestrator import DigestOrchestrator  # noqa: E402


# ── DB helpers ───────────────────────────────────────────────

def load_articles(status_filter=None, tag_filter=None, sort_by="created_at", sort_order="desc"):
    db = SessionLocal()
    try:
        query = db.query(ArticleDB)
        if status_filter and status_filter != "全部":
            query = query.filter(ArticleDB.publish_status == status_filter)

        col = getattr(ArticleDB, sort_by, ArticleDB.created_at)
        query = query.order_by(col.desc() if sort_order == "desc" else col.asc())
        articles = query.all()

        if tag_filter and tag_filter != "全部":
            articles = [a for a in articles if tag_filter in json.loads(a.tags or "[]")]

        return articles
    finally:
        db.close()


def collect_all_tags():
    db = SessionLocal()
    try:
        rows = db.query(ArticleDB.tags).all()
        tags = set()
        for (t,) in rows:
            try:
                tags.update(json.loads(t or "[]"))
            except Exception:
                pass
        return sorted(tags)
    finally:
        db.close()


def update_article_status(article_id: str, new_status: str):
    db = SessionLocal()
    try:
        a = db.query(ArticleDB).filter(ArticleDB.id == article_id).first()
        if a:
            a.publish_status = new_status
            db.commit()
    finally:
        db.close()


def _article_to_dict(a: ArticleDB) -> dict:
    try:
        summary_data = json.loads(a.summary or "{}")
    except Exception:
        summary_data = {}
    return {
        "id": a.id,
        "title": summary_data.get("title_zh") or a.title,
        "summary": summary_data.get("summary_zh", ""),
        "url": a.source_url or "",
        "source": a.source or "",
        "tags": json.loads(a.tags or "[]"),
    }


def publish_articles(article_ids: list, channels: list) -> tuple[int, list]:
    """Publish selected articles and update DB status. Returns (success_count, errors)."""
    db = SessionLocal()
    try:
        rows = db.query(ArticleDB).filter(ArticleDB.id.in_(article_ids)).all()
        if not rows:
            return 0, ["找不到文章"]

        article_dicts = [_article_to_dict(a) for a in rows]
        orch = DigestOrchestrator()
        result = asyncio.run(orch.run_publish_pipeline(articles=article_dicts, channels=channels))

        new_status = "published" if result.success else "failed"
        for a in rows:
            a.publish_status = new_status
            a.published_at_channels = json.dumps({
                ch: datetime.now(timezone.utc).isoformat() for ch in channels
            })
        db.commit()
        return result.published_count, result.errors
    finally:
        db.close()


# ── Session state init ────────────────────────────────────────

if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = set()


# ── UI ───────────────────────────────────────────────────────

st.title("📰 文章列表")

# ── Filters ──────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
with col1:
    status_filter = st.selectbox("狀態篩選", ["全部", "pending", "summarized", "published", "failed"])
with col2:
    tag_filter = st.selectbox("Tag 篩選", ["全部"] + collect_all_tags())
with col3:
    sort_options = {"建立時間": "created_at", "發佈時間": "published_at", "標題": "title"}
    sort_by = sort_options[st.selectbox("排序欄位", list(sort_options.keys()))]
with col4:
    sort_order = st.radio("順序", ["desc", "asc"], format_func=lambda x: "↓ 新→舊" if x == "desc" else "↑ 舊→新")

per_page = st.selectbox("每頁筆數", [20, 50, 100], index=0)

# ── Load ──────────────────────────────────────────────────────
articles = load_articles(status_filter, tag_filter, sort_by, sort_order)
total = len(articles)

# ── Toolbar ──────────────────────────────────────────────────
toolbar_left, toolbar_right = st.columns([3, 2])
with toolbar_left:
    selected_count = len(st.session_state.selected_ids)
    st.caption(f"共 {total} 篇文章（篩選後）｜已選 **{selected_count}** 篇")

if not articles:
    st.info("沒有符合條件的文章。請先到「發佈控制」頁面 Fetch 文章。")
else:
    page_count = (total + per_page - 1) // per_page
    page = st.number_input("頁碼", min_value=1, max_value=max(1, page_count), value=1, step=1) - 1
    page_articles = articles[page * per_page:(page + 1) * per_page]
    page_ids = {a.id for a in page_articles}

    # ── Batch operations ──────────────────────────────────────
    with st.expander("🔧 批次操作", expanded=selected_count > 0):
        b_channels = st.multiselect(
            "發佈渠道",
            ["telegram", "email", "line", "discord"],
            default=["telegram"],
            key="batch_channels",
        )

        bc1, bc2, bc3, bc4, bc5 = st.columns(5)

        with bc1:
            if st.button("☑️ 全選本頁", use_container_width=True):
                st.session_state.selected_ids |= page_ids
                st.rerun()
        with bc2:
            if st.button("☐ 取消全選", use_container_width=True):
                st.session_state.selected_ids -= page_ids
                st.rerun()
        with bc3:
            if st.button("⏳ 標記 pending", use_container_width=True):
                for a in page_articles:
                    update_article_status(a.id, "pending")
                st.rerun()
        with bc4:
            if st.button("✅ 標記 published", use_container_width=True):
                for a in page_articles:
                    update_article_status(a.id, "published")
                st.rerun()
        with bc5:
            publish_target = (
                st.session_state.selected_ids
                if selected_count > 0
                else page_ids
            )
            label = f"📤 發佈選取 ({len(publish_target)}篇)" if selected_count > 0 else f"📤 發佈全頁 ({len(page_ids)}篇)"
            if st.button(label, use_container_width=True, type="primary", disabled=not b_channels):
                with st.spinner(f"發佈 {len(publish_target)} 篇 → {b_channels}..."):
                    ok, errors = publish_articles(list(publish_target), b_channels)
                    if errors:
                        st.error(f"❌ 發佈失敗：{errors}")
                    else:
                        st.toast(f"✅ 發佈完成！{ok} 篇成功")
                    st.session_state.selected_ids.clear()
                    st.rerun()

    # ── Article rows ──────────────────────────────────────────
    STATUS_ICON = {"pending": "⏳", "summarized": "✅", "published": "📤", "failed": "⚠️"}

    for article in page_articles:
        tags = json.loads(article.tags or "[]")
        icon = STATUS_ICON.get(article.publish_status, "❓")
        is_checked = article.id in st.session_state.selected_ids

        with st.container():
            col_check, col_main, col_action = st.columns([0.4, 5, 1.6])

            with col_check:
                checked = st.checkbox("", value=is_checked, key=f"chk_{article.id}", label_visibility="collapsed")
                if checked and article.id not in st.session_state.selected_ids:
                    st.session_state.selected_ids.add(article.id)
                    st.rerun()
                elif not checked and article.id in st.session_state.selected_ids:
                    st.session_state.selected_ids.discard(article.id)
                    st.rerun()

            with col_main:
                st.markdown(f"**{icon} {article.title}**")
                meta_parts = [f"來源: {article.source or '—'}"]
                if article.published_at and hasattr(article.published_at, "strftime"):
                    meta_parts.append(article.published_at.strftime("%Y-%m-%d %H:%M"))
                meta_parts.append(f"`{article.publish_status}`")
                if tags:
                    meta_parts.append(" ".join(f"`{t}`" for t in tags[:5]))
                st.caption(" · ".join(meta_parts))

                if article.summary:
                    with st.expander("摘要"):
                        try:
                            d = json.loads(article.summary)
                            if isinstance(d, dict):
                                st.write(d.get("summary_zh", article.summary))
                                for pt in d.get("key_points", []):
                                    st.write(f"• {pt}")
                            else:
                                st.write(article.summary)
                        except Exception:
                            st.write(article.summary)

            with col_action:
                # Status dropdown
                status_opts = ["pending", "summarized", "published", "failed"]
                cur_idx = status_opts.index(article.publish_status) if article.publish_status in status_opts else 0
                new_status = st.selectbox("狀態", status_opts, index=cur_idx,
                                          key=f"status_{article.id}", label_visibility="collapsed")
                if new_status != article.publish_status:
                    update_article_status(article.id, new_status)
                    st.rerun()

                # Single publish button (only show if summarized)
                if article.publish_status == "summarized":
                    if st.button("📤", key=f"pub_{article.id}", help="立即發佈此篇",
                                 use_container_width=True):
                        ch = st.session_state.get("batch_channels") or ["telegram"]
                        with st.spinner("發佈中..."):
                            ok, errors = publish_articles([article.id], ch)
                            if errors:
                                st.error(f"❌ 發佈失敗：{errors}")
                            else:
                                st.toast("✅ 已發佈")
                            st.rerun()

                if article.source_url:
                    st.link_button("🔗", article.source_url, use_container_width=True)

            st.divider()
