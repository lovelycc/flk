import json
import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g


BASE_DIR = Path(__file__).resolve().parent
CIVIL_CODE = {
    "slug": "civil-code",
    "title": "中华人民共和国民法典",
    "short_name": "民法典",
    "issuing_authority": "全国人民代表大会",
    "jurisdiction": "中国",
    "category": "法律",
    "status": "effective",
    "promulgation_date": "2020-05-28",
    "effective_date": "2021-01-01",
    "expiry_date": None,
    "source_url": "https://flk.npc.gov.cn/detail?id=ff808081729d1efe01729d50b5c500bf",
    "description": "中华人民共和国民事领域的基础性、综合性法律。",
    "version_label": "2020年通过版（现行）",
    "version_status": "effective",
    "source_record_id": "ff808081729d1efe01729d50b5c500bf",
    "source_hash": "6926a597a66c5aad4803591ce9a51a8eebe847260f5ba2805210b608ded78353",
}
VALID_STATUSES = {"effective", "not_effective", "expired", "repealed", "unknown"}


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def table_columns(db: sqlite3.Connection, name: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({name})")}


def ensure_civil_code(db: sqlite3.Connection) -> tuple[int, int]:
    law = CIVIL_CODE
    db.execute(
        """
        INSERT INTO laws
            (slug, title, short_name, issuing_authority, jurisdiction, category,
             status, promulgation_date, effective_date, expiry_date, source_url, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title=excluded.title, short_name=excluded.short_name,
            issuing_authority=excluded.issuing_authority,
            jurisdiction=excluded.jurisdiction, category=excluded.category,
            status=excluded.status, promulgation_date=excluded.promulgation_date,
            effective_date=excluded.effective_date, expiry_date=excluded.expiry_date,
            source_url=excluded.source_url, description=excluded.description,
            updated_at=CURRENT_TIMESTAMP
        """,
        tuple(law[key] for key in (
            "slug", "title", "short_name", "issuing_authority", "jurisdiction",
            "category", "status", "promulgation_date", "effective_date",
            "expiry_date", "source_url", "description",
        )),
    )
    law_id = db.execute("SELECT id FROM laws WHERE slug=?", (law["slug"],)).fetchone()[0]
    version = db.execute(
        "SELECT id FROM law_versions WHERE law_id=? AND version_label=?",
        (law_id, law["version_label"]),
    ).fetchone()
    if version is None:
        db.execute("UPDATE law_versions SET is_current=0 WHERE law_id=?", (law_id,))
        cursor = db.execute(
            """
            INSERT INTO law_versions
                (law_id, version_label, status, promulgation_date, effective_date,
                 expiry_date, source_url, source_record_id, source_hash, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                law_id, law["version_label"], law["version_status"],
                law["promulgation_date"], law["effective_date"], law["expiry_date"],
                law["source_url"], law["source_record_id"], law["source_hash"],
            ),
        )
        version_id = cursor.lastrowid
    else:
        version_id = version[0]
        db.execute("UPDATE law_versions SET is_current=0 WHERE law_id=? AND id<>?", (law_id, version_id))
        db.execute(
            """
            UPDATE law_versions SET status=?, promulgation_date=?, effective_date=?,
                expiry_date=?, source_url=?, source_record_id=?, source_hash=?, is_current=1
            WHERE id=?
            """,
            (
                law["version_status"], law["promulgation_date"], law["effective_date"],
                law["expiry_date"], law["source_url"], law["source_record_id"],
                law["source_hash"], version_id,
            ),
        )
    return law_id, version_id


def migrate_legacy_schema(db: sqlite3.Connection, schema: str) -> None:
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    for index_name in ("idx_articles_title", "idx_articles_book", "idx_articles_chapter"):
        db.execute(f"DROP INDEX IF EXISTS {index_name}")
    db.execute("ALTER TABLE articles RENAME TO legacy_articles")
    if table_exists(db, "notes"):
        db.execute("ALTER TABLE notes RENAME TO legacy_notes")
    db.executescript(schema)
    law_id, version_id = ensure_civil_code(db)
    db.execute(
        """
        INSERT INTO articles
            (law_version_id, article_no, title, content, book, chapter, keywords,
             related_articles, created_at, updated_at)
        SELECT ?, article_no, title, content, book, chapter, keywords,
               related_articles, created_at, updated_at
        FROM legacy_articles
        """,
        (version_id,),
    )
    if table_exists(db, "legacy_notes"):
        db.execute(
            """
            INSERT INTO notes(law_id, article_no, content, updated_at)
            SELECT ?, article_no, content, updated_at FROM legacy_notes
            """,
            (law_id,),
        )
        db.execute("DROP TABLE legacy_notes")
    db.execute("DROP TABLE legacy_articles")
    db.commit()
    db.execute("PRAGMA foreign_keys = ON")


def init_db() -> None:
    db = get_db()
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    if table_exists(db, "articles") and "law_version_id" not in table_columns(db, "articles"):
        migrate_legacy_schema(db, schema)
    else:
        db.executescript(schema)
        ensure_civil_code(db)
        db.commit()


def normalize_related(value: Any) -> str:
    values = value if isinstance(value, list) else str(value or "").replace("，", ",").split(",")
    result: list[str] = []
    for item in values:
        text = str(item).strip().replace("第", "").replace("条", "")
        if text.isdigit() and text not in result:
            result.append(text)
    return ",".join(result)


def normalize_keywords(value: Any) -> str:
    values = value if isinstance(value, list) else str(value or "").replace("，", ",").split(",")
    return ",".join(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def load_article_rows(json_path: Path) -> list[dict]:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        rows = []
        for article_no, article in raw.items():
            item = dict(article)
            item.setdefault("article_no", article_no)
            rows.append(item)
        return rows
    if isinstance(raw, list):
        return raw
    raise ValueError("JSON 顶层必须是数组或以条文号为键的对象")


def get_version(db: sqlite3.Connection, law_slug: str, version_label: str | None = None) -> sqlite3.Row:
    if version_label:
        row = db.execute(
            """
            SELECT v.*, l.slug, l.title AS law_title FROM law_versions v
            JOIN laws l ON l.id=v.law_id WHERE l.slug=? AND v.version_label=?
            """,
            (law_slug, version_label),
        ).fetchone()
    else:
        row = db.execute(
            """
            SELECT v.*, l.slug, l.title AS law_title FROM law_versions v
            JOIN laws l ON l.id=v.law_id WHERE l.slug=? AND v.is_current=1
            """,
            (law_slug,),
        ).fetchone()
    if row is None:
        raise ValueError(f"没有找到法律版本：{law_slug} / {version_label or '现行版本'}")
    return row


def import_articles(json_path: Path, law_slug: str = "civil-code", version_label: str | None = None) -> int:
    rows = load_article_rows(json_path)
    db = get_db()
    version = get_version(db, law_slug, version_label)
    count = 0
    for item in rows:
        article_no = int(item.get("article_no") or item.get("number"))
        content = str(item.get("content") or item.get("text") or "").strip()
        if article_no < 1:
            raise ValueError(f"条文号无效：{article_no}")
        if not content:
            raise ValueError(f"第 {article_no} 条缺少条文内容")
        db.execute(
            """
            INSERT INTO articles
                (law_version_id, article_no, title, content, book, chapter, keywords, related_articles)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(law_version_id, article_no) DO UPDATE SET
                title=CASE WHEN excluded.title<>'' THEN excluded.title ELSE articles.title END,
                content=excluded.content, book=excluded.book, chapter=excluded.chapter,
                keywords=CASE WHEN excluded.keywords<>'' THEN excluded.keywords ELSE articles.keywords END,
                related_articles=CASE WHEN excluded.related_articles<>'' THEN excluded.related_articles ELSE articles.related_articles END,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                version["id"], article_no, str(item.get("title") or "").strip(), content,
                str(item.get("book") or "").strip(), str(item.get("chapter") or "").strip(),
                normalize_keywords(item.get("keywords")),
                normalize_related(item.get("related_articles") or item.get("related")),
            ),
        )
        count += 1
    db.commit()
    return count


def import_law_version(metadata_path: Path, articles_path: Path, make_current: bool = True) -> tuple[str, str, int]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = ("slug", "title", "version_label")
    missing = [key for key in required if not str(metadata.get(key) or "").strip()]
    if missing:
        raise ValueError(f"元数据缺少字段：{', '.join(missing)}")
    law_status = metadata.get("status", "effective")
    version_status = metadata.get("version_status", law_status)
    if law_status not in VALID_STATUSES or version_status not in VALID_STATUSES:
        raise ValueError("status 必须是 effective/not_effective/expired/repealed/unknown")

    db = get_db()
    db.execute(
        """
        INSERT INTO laws
            (slug, title, short_name, issuing_authority, jurisdiction, category,
             status, promulgation_date, effective_date, expiry_date, source_url, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            title=excluded.title, short_name=excluded.short_name,
            issuing_authority=excluded.issuing_authority,
            jurisdiction=excluded.jurisdiction, category=excluded.category,
            status=excluded.status, promulgation_date=excluded.promulgation_date,
            effective_date=excluded.effective_date, expiry_date=excluded.expiry_date,
            source_url=excluded.source_url, description=excluded.description,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            metadata["slug"], metadata["title"], metadata.get("short_name", ""),
            metadata.get("issuing_authority", ""), metadata.get("jurisdiction", "中国"),
            metadata.get("category", "法律"), law_status, metadata.get("promulgation_date"),
            metadata.get("effective_date"), metadata.get("expiry_date"),
            metadata.get("source_url", ""), metadata.get("description", ""),
        ),
    )
    law_id = db.execute("SELECT id FROM laws WHERE slug=?", (metadata["slug"],)).fetchone()[0]
    if make_current:
        db.execute("UPDATE law_versions SET is_current=0 WHERE law_id=?", (law_id,))
    db.execute(
        """
        INSERT INTO law_versions
            (law_id, version_label, status, promulgation_date, effective_date,
             expiry_date, source_url, source_record_id, source_hash, is_current)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(law_id, version_label) DO UPDATE SET
            status=excluded.status, promulgation_date=excluded.promulgation_date,
            effective_date=excluded.effective_date, expiry_date=excluded.expiry_date,
            source_url=excluded.source_url, source_record_id=excluded.source_record_id,
            source_hash=excluded.source_hash,
            is_current=CASE WHEN excluded.is_current=1 THEN 1 ELSE law_versions.is_current END,
            imported_at=CURRENT_TIMESTAMP
        """,
        (
            law_id, metadata["version_label"], version_status,
            metadata.get("promulgation_date"), metadata.get("effective_date"),
            metadata.get("expiry_date"), metadata.get("source_url", ""),
            metadata.get("source_record_id", ""), metadata.get("source_hash", ""),
            1 if make_current else 0,
        ),
    )
    db.commit()
    count = import_articles(articles_path, metadata["slug"], metadata["version_label"])
    return metadata["title"], metadata["version_label"], count


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
