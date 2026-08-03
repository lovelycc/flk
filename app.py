import os
import difflib
import json
import re
from datetime import date
from pathlib import Path

import click
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from db import (
    get_db,
    import_articles,
    import_law_version,
    init_app as init_db_app,
    init_db,
)
from topics import TOPICS, TOPIC_BY_SLUG
from update_checker import check_official_sources


BASE_DIR = Path(__file__).resolve().parent
STATUS_LABELS = {
    "effective": "现行有效",
    "not_effective": "尚未生效",
    "expired": "已失效",
    "repealed": "已废止",
    "unknown": "效力待核",
}

CHINESE_ARTICLE_NUMBER = re.compile(r"[〇零一二三四五六七八九十百千万两0-9]+")


def chinese_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3,
              "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = section = number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if unit == 10000:
                total += (section + number) * unit
                section = number = 0
            else:
                section += (number or 1) * unit
                number = 0
        else:
            raise ValueError(value)
    return total + section + number


def highlighted_diff(old_text: str, new_text: str) -> tuple[Markup, Markup]:
    old_parts: list[str] = []
    new_parts: list[str] = []
    matcher = difflib.SequenceMatcher(None, old_text or "", new_text or "", autojunk=False)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_piece = escape((old_text or "")[old_start:old_end])
        new_piece = escape((new_text or "")[new_start:new_end])
        if tag == "equal":
            old_parts.append(str(old_piece)); new_parts.append(str(new_piece))
        elif tag == "delete":
            old_parts.append(f"<del>{old_piece}</del>")
        elif tag == "insert":
            new_parts.append(f"<ins>{new_piece}</ins>")
        else:
            old_parts.append(f"<del>{old_piece}</del>")
            new_parts.append(f"<ins>{new_piece}</ins>")
    return Markup("".join(old_parts)), Markup("".join(new_parts))


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("MFD_SECRET_KEY", "dev-change-this-key"),
        DATABASE=str(Path(app.instance_path) / "mfd.sqlite3"),
        MAX_NOTE_LENGTH=10_000,
        AUTO_BOOTSTRAP_OFFICIAL=True,
    )
    if test_config:
        app.config.update(test_config)
        if app.config.get("TESTING") and "AUTO_BOOTSTRAP_OFFICIAL" not in test_config:
            app.config["AUTO_BOOTSTRAP_OFFICIAL"] = False

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db_app(app)

    with app.app_context():
        init_db()
        current_count = get_db().execute(
            """
            SELECT COUNT(*) FROM articles a
            JOIN law_versions v ON v.id=a.law_version_id
            JOIN laws l ON l.id=v.law_id
            WHERE l.slug='civil-code' AND v.is_current=1
            """
        ).fetchone()[0]
        if current_count == 0:
            civil_source = BASE_DIR / "data" / "sample_articles.json"
            official_civil_source = BASE_DIR / "data" / "civil_code_1260_official.json"
            if app.config["AUTO_BOOTSTRAP_OFFICIAL"] and official_civil_source.exists():
                civil_source = official_civil_source
            import_articles(civil_source)

        if app.config["AUTO_BOOTSTRAP_OFFICIAL"]:
            manifest_path = BASE_DIR / "data" / "legal_collection" / "manifest.json"
            law_count = get_db().execute("SELECT COUNT(*) FROM laws").fetchone()[0]
            if law_count == 1 and manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for item in manifest:
                    metadata_path = BASE_DIR / str(item["metadata"]).replace("\\", "/")
                    articles_path = BASE_DIR / str(item["articles"]).replace("\\", "/")
                    import_law_version(
                        metadata_path, articles_path, make_current=bool(item.get("current"))
                    )

    @app.template_filter("related_list")
    def related_list(value: str) -> list[str]:
        return [part.strip() for part in (value or "").split(",") if part.strip()]

    @app.template_filter("status_label")
    def status_label(value: str) -> str:
        return STATUS_LABELS.get(value, STATUS_LABELS["unknown"])

    @app.template_filter("date_or_dash")
    def date_or_dash(value: str | None) -> str:
        return value or "—"

    def valid_as_of(value: str) -> str:
        if not value:
            return ""
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return ""

    def article_query(as_of: str = "") -> tuple[str, list[str]]:
        join = "JOIN law_versions v ON v.id=(SELECT id FROM law_versions WHERE law_id=l.id AND is_current=1)"
        params: list[str] = []
        if as_of:
            join = """
                JOIN law_versions v ON v.id=(
                    SELECT v2.id FROM law_versions v2
                    WHERE v2.law_id=l.id
                      AND (v2.effective_date IS NULL OR v2.effective_date<=?)
                      AND (v2.expiry_date IS NULL OR v2.expiry_date>=?)
                    ORDER BY COALESCE(v2.effective_date, '0000-00-00') DESC, v2.id DESC
                    LIMIT 1
                )
            """
            params = [as_of, as_of]
        return f"""
            SELECT a.*, l.id AS law_id, l.slug AS law_slug, l.title AS law_title,
                   l.short_name AS law_short_name, l.status AS law_status,
                   v.id AS version_id, v.version_label, v.status AS version_status,
                   v.effective_date AS version_effective_date
            FROM laws l {join}
            JOIN articles a ON a.law_version_id=v.id
            WHERE 1=1
        """, params

    def linked_article_text(article, as_of: str = "") -> Markup:
        db = get_db()
        laws = db.execute("SELECT slug, title, short_name FROM laws").fetchall()
        name_map: dict[str, str] = {"本法": article["law_slug"]}
        for law in laws:
            name_map[law["title"]] = law["slug"]
            if law["short_name"]:
                name_map.setdefault(law["short_name"], law["slug"])
            if law["title"].startswith("中华人民共和国"):
                name_map.setdefault(law["title"].removeprefix("中华人民共和国"), law["slug"])
        names = sorted(name_map, key=len, reverse=True)
        if not names:
            return Markup(escape(article["content"]))
        pattern = re.compile(
            rf"(?:《(?P<bracket>{'|'.join(map(re.escape, names))})》|(?P<plain>{'|'.join(map(re.escape, names))}))"
            rf"第(?P<number>{CHINESE_ARTICLE_NUMBER.pattern})条"
        )
        output: list[str] = []
        cursor = 0
        for match in pattern.finditer(article["content"]):
            output.append(str(escape(article["content"][cursor:match.start()])))
            law_name = match.group("bracket") or match.group("plain")
            number = chinese_number(match.group("number"))
            slug = name_map[law_name]
            query: dict[str, object] = {}
            if as_of:
                query["as_of"] = as_of
            elif slug == article["law_slug"] and not article["is_current"]:
                query["version"] = article["version_id"]
            destination = url_for("article_detail", law_slug=slug, article_no=number, **query)
            output.append(f'<a class="citation-link" href="{escape(destination)}">{escape(match.group(0))}</a>')
            cursor = match.end()
        output.append(str(escape(article["content"][cursor:])))
        return Markup("".join(output))

    @app.get("/")
    def index():
        db = get_db()
        query = request.args.get("q", "").strip()
        law_filter = request.args.get("law", "").strip()
        raw_as_of = request.args.get("as_of", "").strip()
        as_of = valid_as_of(raw_as_of)
        if raw_as_of and not as_of:
            flash("日期格式无效，请使用 YYYY-MM-DD。", "error")
        results = []
        laws = db.execute(
            """
            SELECT l.*, COUNT(a.id) AS article_count
            FROM laws l
            LEFT JOIN law_versions v ON v.law_id=l.id AND v.is_current=1
            LEFT JOIN articles a ON a.law_version_id=v.id
            GROUP BY l.id ORDER BY l.category, l.title
            """
        ).fetchall()
        article_count = sum(row["article_count"] for row in laws)

        if query:
            article_number = query
            if query.startswith("第") and query.endswith("条"):
                article_number = query[1:-1].strip()
            sql, params = article_query(as_of)
            if law_filter:
                sql += " AND l.slug=?"
                params.append(law_filter)
            if article_number.isdigit():
                sql += " AND a.article_no=? ORDER BY l.title"
                params.append(int(article_number))
            else:
                terms = [term for term in re.split(r"[\s，,]+", query) if term] or [query]
                searchable = """(a.title LIKE ? OR a.content LIKE ? OR a.keywords LIKE ?
                    OR a.book LIKE ? OR a.chapter LIKE ? OR l.title LIKE ? OR l.short_name LIKE ?)"""
                sql += " AND (" + " OR ".join(searchable for _ in terms) + ")"
                for term in terms:
                    params.extend([f"%{term}%"] * 7)
                sql += " ORDER BY l.title, a.article_no LIMIT 100"
            results = db.execute(sql, params).fetchall()
            if article_number.isdigit() and len(results) == 1:
                row = results[0]
                return redirect(url_for(
                    "article_detail", law_slug=row["law_slug"], article_no=row["article_no"],
                    as_of=as_of or None,
                ))

        return render_template(
            "index.html", query=query, results=results, article_count=article_count,
            laws=laws, law_filter=law_filter, as_of=as_of,
        )

    @app.get("/laws")
    def law_library():
        laws = get_db().execute(
            """
            SELECT l.*, v.id AS version_id, v.version_label, v.status AS version_status,
                   v.effective_date AS version_effective_date,
                   COUNT(a.id) AS article_count,
                   (SELECT COUNT(*) FROM law_versions all_v WHERE all_v.law_id=l.id) AS version_count
            FROM laws l
            LEFT JOIN law_versions v ON v.law_id=l.id AND v.is_current=1
            LEFT JOIN articles a ON a.law_version_id=v.id
            GROUP BY l.id ORDER BY l.category, l.title
            """
        ).fetchall()
        return render_template("laws.html", laws=laws)

    @app.get("/laws/<law_slug>")
    def law_detail(law_slug: str):
        db = get_db()
        law = db.execute("SELECT * FROM laws WHERE slug=?", (law_slug,)).fetchone()
        if law is None:
            abort(404)
        versions = db.execute(
            """
            SELECT v.*, COUNT(a.id) AS article_count
            FROM law_versions v LEFT JOIN articles a ON a.law_version_id=v.id
            WHERE v.law_id=? GROUP BY v.id
            ORDER BY v.is_current DESC, COALESCE(v.effective_date, '') DESC, v.id DESC
            """,
            (law["id"],),
        ).fetchall()
        as_of = valid_as_of(request.args.get("as_of", "").strip())
        effective_version = None
        if as_of:
            effective_version = db.execute(
                """
                SELECT * FROM law_versions
                WHERE law_id=? AND (effective_date IS NULL OR effective_date<=?)
                  AND (expiry_date IS NULL OR expiry_date>=?)
                ORDER BY COALESCE(effective_date,'0000-00-00') DESC, id DESC LIMIT 1
                """,
                (law["id"], as_of, as_of),
            ).fetchone()
        return render_template(
            "law_detail.html", law=law, versions=versions, today=date.today().isoformat(),
            as_of=as_of, effective_version=effective_version,
        )

    @app.get("/laws/<law_slug>/versions/<int:version_id>")
    def version_articles(law_slug: str, version_id: int):
        db = get_db()
        version = db.execute(
            """
            SELECT v.*, l.slug AS law_slug, l.title AS law_title, l.short_name AS law_short_name
            FROM law_versions v JOIN laws l ON l.id=v.law_id
            WHERE l.slug=? AND v.id=?
            """,
            (law_slug, version_id),
        ).fetchone()
        if version is None:
            abort(404)
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = 100
        total = db.execute("SELECT COUNT(*) FROM articles WHERE law_version_id=?", (version_id,)).fetchone()[0]
        articles = db.execute(
            """
            SELECT * FROM articles WHERE law_version_id=?
            ORDER BY article_no LIMIT ? OFFSET ?
            """,
            (version_id, per_page, (page - 1) * per_page),
        ).fetchall()
        return render_template(
            "version_articles.html", version=version, articles=articles, page=page,
            per_page=per_page, total=total,
        )

    @app.get("/laws/<law_slug>/compare")
    def compare_versions(law_slug: str):
        db = get_db()
        law = db.execute("SELECT * FROM laws WHERE slug=?", (law_slug,)).fetchone()
        if law is None:
            abort(404)
        versions = db.execute(
            "SELECT * FROM law_versions WHERE law_id=? ORDER BY COALESCE(effective_date,'') DESC, id DESC",
            (law["id"],),
        ).fetchall()
        from_id = request.args.get("from", type=int)
        to_id = request.args.get("to", type=int)
        changes = []
        summary = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
        selected_from = selected_to = None
        if from_id and to_id and from_id != to_id:
            selected_from = next((row for row in versions if row["id"] == from_id), None)
            selected_to = next((row for row in versions if row["id"] == to_id), None)
            if selected_from is None or selected_to is None:
                abort(404)
            old_rows = {
                row["article_no"]: row for row in db.execute(
                    "SELECT * FROM articles WHERE law_version_id=?", (from_id,)
                )
            }
            new_rows = {
                row["article_no"]: row for row in db.execute(
                    "SELECT * FROM articles WHERE law_version_id=?", (to_id,)
                )
            }
            for number in sorted(set(old_rows) | set(new_rows)):
                old = old_rows.get(number)
                new = new_rows.get(number)
                if old is None:
                    change_type = "added"
                elif new is None:
                    change_type = "removed"
                elif old["content"] != new["content"] or old["title"] != new["title"]:
                    change_type = "modified"
                else:
                    summary["unchanged"] += 1
                    continue
                summary[change_type] += 1
                old_html, new_html = highlighted_diff(
                    old["content"] if old else "", new["content"] if new else ""
                )
                changes.append({
                    "article_no": number, "type": change_type, "old": old, "new": new,
                    "old_html": old_html, "new_html": new_html,
                })
        return render_template(
            "compare.html", law=law, versions=versions, selected_from=selected_from,
            selected_to=selected_to, changes=changes, summary=summary,
        )

    @app.get("/article/<int:article_no>")
    def legacy_article_detail(article_no: int):
        return redirect(url_for("article_detail", law_slug="civil-code", article_no=article_no), code=301)

    @app.get("/laws/<law_slug>/articles/<int:article_no>")
    def article_detail(law_slug: str, article_no: int):
        db = get_db()
        requested_version = request.args.get("version", type=int)
        as_of = valid_as_of(request.args.get("as_of", "").strip())
        params: list = [law_slug, article_no]
        version_condition = "v.is_current=1"
        if requested_version:
            version_condition = "v.id=?"
            params.append(requested_version)
            as_of = ""
        elif as_of:
            version_condition = """v.id=(
                SELECT v2.id FROM law_versions v2
                WHERE v2.law_id=l.id
                  AND (v2.effective_date IS NULL OR v2.effective_date<=?)
                  AND (v2.expiry_date IS NULL OR v2.expiry_date>=?)
                ORDER BY COALESCE(v2.effective_date,'0000-00-00') DESC, v2.id DESC LIMIT 1
            )"""
            params.extend([as_of, as_of])
        article = db.execute(
            f"""
            SELECT a.*, l.id AS law_id, l.slug AS law_slug, l.title AS law_title,
                   l.short_name AS law_short_name, l.status AS law_status,
                   l.source_url AS law_source_url, v.id AS version_id,
                   v.version_label, v.status AS version_status,
                   v.promulgation_date AS version_promulgation_date,
                   v.effective_date AS version_effective_date,
                   v.expiry_date AS version_expiry_date, v.source_url AS version_source_url,
                   v.is_current
            FROM articles a JOIN law_versions v ON v.id=a.law_version_id
            JOIN laws l ON l.id=v.law_id
            WHERE l.slug=? AND a.article_no=? AND {version_condition}
            """,
            params,
        ).fetchone()
        if article is None:
            abort(404)
        db.execute(
            """
            INSERT INTO browsing_history(law_id, article_no, view_count, viewed_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(law_id, article_no) DO UPDATE SET
                view_count=browsing_history.view_count+1, viewed_at=CURRENT_TIMESTAMP
            """,
            (article["law_id"], article_no),
        )
        db.commit()
        note = db.execute(
            "SELECT * FROM notes WHERE law_id=? AND article_no=?",
            (article["law_id"], article_no),
        ).fetchone()
        related_numbers = related_list(article["related_articles"])
        related = []
        if related_numbers:
            placeholders = ",".join("?" for _ in related_numbers)
            related = db.execute(
                f"""
                SELECT article_no, title FROM articles
                WHERE law_version_id=? AND article_no IN ({placeholders})
                """,
                (article["version_id"], *(int(number) for number in related_numbers)),
            ).fetchall()
        related_by_number = {str(row["article_no"]): row for row in related}
        adjacent = db.execute(
            """
            SELECT
                (SELECT MAX(article_no) FROM articles WHERE law_version_id=? AND article_no<?) AS previous_no,
                (SELECT MIN(article_no) FROM articles WHERE law_version_id=? AND article_no>?) AS next_no
            """,
            (article["version_id"], article_no, article["version_id"], article_no),
        ).fetchone()
        is_favorite = db.execute(
            "SELECT 1 FROM favorites WHERE law_id=? AND article_no=?",
            (article["law_id"], article_no),
        ).fetchone() is not None
        return render_template(
            "article.html", article=article, note=note, related_numbers=related_numbers,
            related_by_number=related_by_number, adjacent=adjacent, as_of=as_of,
            linked_content=linked_article_text(article, as_of), is_favorite=is_favorite,
        )

    @app.post("/laws/<law_slug>/articles/<int:article_no>/note")
    def save_note(law_slug: str, article_no: int):
        db = get_db()
        law = db.execute("SELECT id FROM laws WHERE slug=?", (law_slug,)).fetchone()
        if law is None:
            abort(404)
        exists = db.execute(
            """
            SELECT 1 FROM articles a JOIN law_versions v ON v.id=a.law_version_id
            WHERE v.law_id=? AND a.article_no=?
            """,
            (law["id"], article_no),
        ).fetchone()
        if not exists:
            abort(404)
        content = request.form.get("content", "").strip()
        if len(content) > app.config["MAX_NOTE_LENGTH"]:
            flash("笔记过长，请控制在 10000 字以内。", "error")
            return redirect(url_for("article_detail", law_slug=law_slug, article_no=article_no))
        db.execute(
            """
            INSERT INTO notes(law_id, article_no, content, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(law_id, article_no) DO UPDATE SET
                content=excluded.content, updated_at=CURRENT_TIMESTAMP
            """,
            (law["id"], article_no, content),
        )
        db.commit()
        flash("笔记已保存到本地数据库。", "success")
        return redirect(url_for(
            "article_detail", law_slug=law_slug, article_no=article_no,
            version=request.form.get("version") or None, as_of=request.form.get("as_of") or None,
        ))

    @app.post("/laws/<law_slug>/articles/<int:article_no>/favorite")
    def toggle_favorite(law_slug: str, article_no: int):
        db = get_db()
        law = db.execute("SELECT id FROM laws WHERE slug=?", (law_slug,)).fetchone()
        if law is None:
            abort(404)
        existing = db.execute(
            "SELECT 1 FROM favorites WHERE law_id=? AND article_no=?", (law["id"], article_no)
        ).fetchone()
        if existing:
            db.execute("DELETE FROM favorites WHERE law_id=? AND article_no=?", (law["id"], article_no))
            flash("已取消收藏。", "success")
        else:
            db.execute("INSERT INTO favorites(law_id, article_no) VALUES (?, ?)", (law["id"], article_no))
            flash("已加入收藏。", "success")
        db.commit()
        return redirect(url_for(
            "article_detail", law_slug=law_slug, article_no=article_no,
            version=request.form.get("version") or None, as_of=request.form.get("as_of") or None,
        ))

    @app.get("/workspace")
    def personal_workspace():
        db = get_db()
        favorites = db.execute(
            """
            SELECT f.created_at, f.article_no, l.slug AS law_slug, l.title AS law_title,
                   l.short_name AS law_short_name, a.title, a.content
            FROM favorites f JOIN laws l ON l.id=f.law_id
            LEFT JOIN law_versions v ON v.law_id=l.id AND v.is_current=1
            LEFT JOIN articles a ON a.law_version_id=v.id AND a.article_no=f.article_no
            ORDER BY f.created_at DESC
            """
        ).fetchall()
        history = db.execute(
            """
            SELECT h.viewed_at, h.view_count, h.article_no, l.slug AS law_slug,
                   l.title AS law_title, l.short_name AS law_short_name, a.title, a.content
            FROM browsing_history h JOIN laws l ON l.id=h.law_id
            LEFT JOIN law_versions v ON v.law_id=l.id AND v.is_current=1
            LEFT JOIN articles a ON a.law_version_id=v.id AND a.article_no=h.article_no
            ORDER BY h.viewed_at DESC LIMIT 100
            """
        ).fetchall()
        return render_template("workspace.html", favorites=favorites, history=history)

    @app.post("/workspace/history/clear")
    def clear_history():
        db = get_db()
        db.execute("DELETE FROM browsing_history")
        db.commit()
        flash("浏览历史已清空。", "success")
        return redirect(url_for("personal_workspace"))

    @app.get("/topics")
    def topic_library():
        return render_template("topics.html", topics=TOPICS)

    @app.get("/topics/<topic_slug>")
    def topic_detail(topic_slug: str):
        topic = TOPIC_BY_SLUG.get(topic_slug)
        if topic is None:
            abort(404)
        placeholders = ",".join("?" for _ in topic["laws"])
        laws = get_db().execute(
            f"SELECT * FROM laws WHERE slug IN ({placeholders}) ORDER BY category, title",
            topic["laws"],
        ).fetchall()
        return render_template("topic_detail.html", topic=topic, laws=laws)

    @app.get("/updates")
    def update_center():
        row = get_db().execute("SELECT * FROM update_checks ORDER BY id DESC LIMIT 1").fetchone()
        results = json.loads(row["details"]) if row and row["details"] else []
        return render_template("updates.html", check=row, results=results)

    @app.post("/updates/check")
    def run_update_check():
        db = get_db()
        results = check_official_sources(db)
        changed = sum(item["status"] == "changed" for item in results)
        failed = sum(item["status"] == "error" for item in results)
        status = "attention" if changed or failed else "ok"
        summary = f"已检查 {len(results)} 个现行版本：需复核 {changed}，连接失败 {failed}。"
        db.execute(
            "INSERT INTO update_checks(status, summary, details) VALUES (?, ?, ?)",
            (status, summary, json.dumps(results, ensure_ascii=False)),
        )
        db.commit()
        flash(summary, "error" if status == "attention" else "success")
        return redirect(url_for("update_center"))

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        click.echo("数据库结构已初始化。")

    @app.cli.command("import-json")
    @click.argument("json_file", type=click.Path(exists=True, path_type=Path))
    @click.option("--law", "law_slug", default="civil-code", show_default=True)
    @click.option("--version", "version_label", default=None)
    def import_json_command(json_file: Path, law_slug: str, version_label: str | None):
        count = import_articles(json_file, law_slug, version_label)
        click.echo(f"已导入或更新 {count} 条条文。")

    @app.cli.command("import-law")
    @click.argument("metadata_file", type=click.Path(exists=True, path_type=Path))
    @click.argument("articles_file", type=click.Path(exists=True, path_type=Path))
    @click.option("--historical", is_flag=True, help="导入为历史版本，不设为现行版本。")
    def import_law_command(metadata_file: Path, articles_file: Path, historical: bool):
        title, version, count = import_law_version(metadata_file, articles_file, not historical)
        click.echo(f"已导入《{title}》{version}：{count} 条。")

    return app


app = create_app()


if __name__ == "__main__":
    run_host = os.environ.get("MFD_HOST", "127.0.0.1")
    try:
        run_port = int(os.environ.get("MFD_PORT", "5000"))
    except ValueError as exc:
        raise SystemExit("MFD_PORT 必须是有效端口号。") from exc
    run_debug = os.environ.get("MFD_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=run_host, port=run_port, debug=run_debug)
