import json
from pathlib import Path

import pytest

from app import create_app
from db import get_db, import_law_version


@pytest.fixture()
def app(tmp_path: Path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3")})


@pytest.fixture()
def client(app):
    return app.test_client()


def test_home_and_library(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "法律查询助手" in response.get_data(as_text=True)
    library = client.get("/laws")
    assert library.status_code == 200
    assert "中华人民共和国民法典" in library.get_data(as_text=True)


def test_number_search_redirects_to_law_scoped_url(client):
    response = client.get("/?q=545")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/laws/civil-code/articles/545")


def test_legacy_article_url_remains_compatible(client):
    response = client.get("/article/545")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/laws/civil-code/articles/545")


def test_keyword_search(client):
    response = client.get("/?q=债权转让")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "民法典" in body
    assert "第 545 条" in body


def test_save_note(client):
    response = client.post(
        "/laws/civil-code/articles/545/note",
        data={"content": "债权转让无需债务人同意。"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "债权转让无需债务人同意" in response.get_data(as_text=True)


def test_article_keyboard_navigation(client):
    body = client.get("/laws/civil-code/articles/546").get_data(as_text=True)
    assert 'data-previous-url="/laws/civil-code/articles/545"' in body
    assert 'data-next-url="/laws/civil-code/articles/547"' in body
    assert "article-navigation.js" in body
    assert "键盘左右键切换条文" in body


def test_favorites_history_and_topics(client):
    client.get("/laws/civil-code/articles/545")
    response = client.post(
        "/laws/civil-code/articles/545/favorite", follow_redirects=True
    )
    assert "已加入收藏" in response.get_data(as_text=True)
    workspace = client.get("/workspace").get_data(as_text=True)
    assert "民法典第545条" in workspace
    assert "浏览" in workspace
    topics = client.get("/topics").get_data(as_text=True)
    assert "闲置土地认定与处置" in topics
    topic = client.get("/topics/idle-land").get_data(as_text=True)
    assert "处置方案" in topic
    assert "主要法律依据" in topic
    assert client.get("/updates").status_code == 200


def test_import_second_law_and_compare_versions(app, client, tmp_path: Path):
    articles_v1 = tmp_path / "demo-v1.json"
    articles_v2 = tmp_path / "demo-v2.json"
    metadata_v1 = tmp_path / "demo-v1-meta.json"
    metadata_v2 = tmp_path / "demo-v2-meta.json"
    articles_v1.write_text(json.dumps([
        {"article_no": 1, "content": "第一版第一条。"},
        {"article_no": 2, "content": "第一版第二条。"},
    ], ensure_ascii=False), encoding="utf-8")
    articles_v2.write_text(json.dumps([
        {"article_no": 1, "content": "第二版修改后的第一条。依照《中华人民共和国民法典》第五百四十五条处理。"},
        {"article_no": 3, "content": "第二版新增第三条。"},
    ], ensure_ascii=False), encoding="utf-8")
    common = {
        "slug": "demo-law", "title": "示例法律", "short_name": "示例法",
        "issuing_authority": "示例机关", "category": "法律", "status": "effective",
    }
    metadata_v1.write_text(json.dumps({
        **common, "version_label": "2020版", "version_status": "repealed",
        "effective_date": "2020-01-01", "expiry_date": "2024-12-31",
    }, ensure_ascii=False), encoding="utf-8")
    metadata_v2.write_text(json.dumps({
        **common, "version_label": "2025版", "version_status": "effective",
        "effective_date": "2025-01-01",
    }, ensure_ascii=False), encoding="utf-8")

    with app.app_context():
        import_law_version(metadata_v1, articles_v1, make_current=False)
        import_law_version(metadata_v2, articles_v2, make_current=True)
        versions = get_db().execute(
            "SELECT id FROM law_versions WHERE law_id=(SELECT id FROM laws WHERE slug='demo-law') ORDER BY effective_date"
        ).fetchall()
        from_id, to_id = versions[0][0], versions[1][0]

    library_body = client.get("/laws").get_data(as_text=True)
    assert "示例法律" in library_body
    assert "2 个版本" in library_body
    search_body = client.get("/?q=第二版修改&law=demo-law").get_data(as_text=True)
    assert "第二版修改后的第一条" in search_body
    compare_body = client.get(
        f"/laws/demo-law/compare?from={from_id}&to={to_id}"
    ).get_data(as_text=True)
    assert "修改 1" in compare_body
    assert "新增 1" in compare_body
    assert "删除 1" in compare_body
    assert "<del>" in compare_body
    assert "<ins>" in compare_body

    historical = client.get("/?q=第一版第一条&law=demo-law&as_of=2023-06-01")
    assert "2020版" in historical.get_data(as_text=True)
    dated_article = client.get("/laws/demo-law/articles/1?as_of=2023-06-01")
    dated_body = dated_article.get_data(as_text=True)
    assert "2023-06-01" in dated_body
    assert "时适用" in dated_body
    current_article = client.get("/laws/demo-law/articles/1")
    current_body = current_article.get_data(as_text=True)
    assert 'class="citation-link"' in current_body
    assert "/laws/civil-code/articles/545" in current_body
