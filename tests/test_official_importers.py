from tools.import_official_civil_code import parse_articles


def test_inserted_criminal_law_articles_are_retained_under_base_article():
    rows = parse_articles(
        [
            "第一百三十三条　主条正文。",
            "第一百三十三条之一　插入条文之一。",
            "第一百三十三条之二　插入条文之二。",
            "第一百三十四条　下一条正文。",
        ]
    )

    assert [row["article_no"] for row in rows] == [133, 134]
    assert "第一百三十三条之一" in rows[0]["content"]
    assert "第一百三十三条之二" in rows[0]["content"]
    assert rows[1]["content"] == "下一条正文。"
