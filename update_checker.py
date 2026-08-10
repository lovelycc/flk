"""Read-only checks against the official source of each current law version."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


FLK_DETAIL_URL = "https://flk.npc.gov.cn/law-search/search/flfgDetails"
USER_AGENT = "Mozilla/5.0 Legal-Assistant/3.5"


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://flk.npc.gov.cn/"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def _fetch_page(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(512_000)
    text = raw.decode("utf-8", errors="replace")
    start = text.lower().find("<title>")
    end = text.lower().find("</title>", start + 7)
    title = text[start + 7:end].strip() if start >= 0 and end > start else ""
    return title, text


def check_official_sources(db) -> list[dict]:
    rows = db.execute(
        """
        SELECT l.title, l.slug, v.version_label, v.source_url, v.source_record_id,
               v.promulgation_date, v.effective_date
        FROM laws l JOIN law_versions v ON v.law_id=l.id
        WHERE v.is_current=1 ORDER BY l.title
        """
    ).fetchall()
    def check_one(row) -> dict:
        item = {
            "title": row["title"], "slug": row["slug"],
            "version_label": row["version_label"], "source_url": row["source_url"],
            "status": "ok", "message": "官方记录可访问，标题一致。",
        }
        try:
            if row["source_record_id"] and "flk.npc.gov.cn" in (row["source_url"] or ""):
                query = urllib.parse.urlencode({"bbbs": row["source_record_id"]})
                payload = _fetch_json(f"{FLK_DETAIL_URL}?{query}")
                details = payload.get("data") if payload.get("code") == 200 else None
                if not details:
                    raise ValueError(payload.get("msg") or "官方接口未返回记录")
                if details.get("title") != row["title"]:
                    item["status"] = "changed"
                    item["message"] = f"官方标题发生变化：{details.get('title') or '空'}"
                elif ((details.get("gbrq") or None) != row["promulgation_date"] or
                      (details.get("sxrq") or None) != row["effective_date"]):
                    item["status"] = "changed"
                    item["message"] = "官方公布日期或施行日期与本地记录不同，请人工复核。"
            elif row["source_url"]:
                page_title, page_text = _fetch_page(row["source_url"])
                expected = row["title"].replace("中华人民共和国", "")
                if (expected not in page_title and row["title"] not in page_title and
                        expected not in page_text and row["title"] not in page_text):
                    item["status"] = "changed"
                    item["message"] = f"官方页面标题未匹配：{page_title or '未读取到标题'}"
            else:
                item["status"] = "warning"
                item["message"] = "本地版本未登记官方来源地址。"
        except Exception as exc:  # Network and official-site failures must not mutate data.
            item["status"] = "error"
            item["message"] = f"检查失败：{exc}"
        return item

    with ThreadPoolExecutor(max_workers=min(6, len(rows) or 1)) as executor:
        results = list(executor.map(check_one, rows))
    return results
