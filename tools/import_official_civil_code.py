"""Download, verify, and convert the official Civil Code DOCX into import JSON.

Source: National Database of Laws and Regulations, maintained by the General
Office of the Standing Committee of the National People's Congress.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


BASE_URL = "https://flk.npc.gov.cn"
RECORD_ID = "ff808081729d1efe01729d50b5c500bf"
DETAIL_URL = f"{BASE_URL}/law-search/search/flfgDetails"
DOWNLOAD_URL = f"{BASE_URL}/law-search/download/pc"
USER_AGENT = "Mozilla/5.0 Civil-Code-Importer/3.1"
ARTICLE_PATTERN = re.compile(r"^第([〇零一二三四五六七八九十百千万两]+)条[\s　]*(.*)$")
BOOK_PATTERN = re.compile(r"^第[〇零一二三四五六七八九十百千万两]+编(?:\s+|　*)(.*)$")
CHAPTER_PATTERN = re.compile(r"^第[〇零一二三四五六七八九十百千万两]+章(?:\s+|　*)(.*)$")
SECTION_PATTERN = re.compile(r"^第[〇零一二三四五六七八九十百千万两]+节(?:\s+|　*)(.*)$")


def fetch_json(url: str, params: dict[str, str]) -> dict:
    request_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        request_url,
        headers={"User-Agent": USER_AGENT, "Referer": f"{BASE_URL}/"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if payload.get("code") != 200:
        raise RuntimeError(f"Official API returned an error: {payload.get('msg')}")
    return payload["data"]


def download_file(url: str, target: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def document_paragraphs(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:body/w:p", namespace):
        pieces: list[str] = []
        for node in paragraph.iter():
            local_name = node.tag.rsplit("}", 1)[-1]
            if local_name == "t" and node.text:
                pieces.append(node.text)
            elif local_name == "tab":
                pieces.append("\t")
            elif local_name == "br":
                pieces.append("\n")
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def chinese_number(value: str) -> int:
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                if number == 0:
                    number = 1
                section += number * unit
            number = 0
        else:
            raise ValueError(f"Unsupported Chinese numeral: {value}")
    return total + section + number


def parse_articles(paragraphs: list[str]) -> list[dict]:
    articles: list[dict] = []
    current: dict | None = None
    book = ""
    chapter = ""
    section = ""

    def finish_current() -> None:
        nonlocal current
        if current is not None:
            current["content"] = "\n".join(current.pop("_parts")).strip()
            articles.append(current)
            current = None

    for paragraph in paragraphs:
        compact = re.sub(r"[\t ]+", " ", paragraph).strip()
        article_match = ARTICLE_PATTERN.match(compact)
        if article_match:
            finish_current()
            article_no = chinese_number(article_match.group(1))
            first_content = article_match.group(2).strip()
            current = {
                "article_no": article_no,
                "content": "",
                "book": book,
                "chapter": " / ".join(part for part in (chapter, section) if part),
                "_parts": [first_content] if first_content else [],
            }
            continue

        book_match = BOOK_PATTERN.match(compact)
        if book_match:
            finish_current()
            book = compact
            chapter = ""
            section = ""
            continue
        chapter_match = CHAPTER_PATTERN.match(compact)
        if chapter_match:
            finish_current()
            chapter = compact
            section = ""
            continue
        section_match = SECTION_PATTERN.match(compact)
        if section_match:
            finish_current()
            section = compact
            continue

        if current is not None:
            current["_parts"].append(compact)

    finish_current()
    return articles


def validate_articles(articles: list[dict]) -> None:
    numbers = [article["article_no"] for article in articles]
    expected = list(range(1, 1261))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        duplicates = sorted(number for number in set(numbers) if numbers.count(number) > 1)
        raise ValueError(
            f"Validation failed: count={len(numbers)}, missing={missing[:20]}, "
            f"duplicates={duplicates[:20]}"
        )
    empty = [article["article_no"] for article in articles if not article["content"]]
    if empty:
        raise ValueError(f"Articles without text: {empty}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/civil_code_1260_official.json"))
    parser.add_argument("--docx", type=Path, default=Path("data/civil_code_official.docx"))
    parser.add_argument("--metadata", type=Path, default=Path("data/civil_code_source.json"))
    args = parser.parse_args()

    details = fetch_json(DETAIL_URL, {"bbbs": RECORD_ID})
    if details.get("title") != "中华人民共和国民法典":
        raise ValueError(f"Unexpected official record: {details.get('title')}")

    download = fetch_json(DOWNLOAD_URL, {"bbbs": RECORD_ID, "format": "docx"})
    sha256 = download_file(download["url"], args.docx)
    articles = parse_articles(document_paragraphs(args.docx))
    validate_articles(articles)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata = {
        "slug": "civil-code",
        "title": details["title"],
        "short_name": "民法典",
        "issuing_authority": "全国人民代表大会",
        "jurisdiction": "中国",
        "category": "法律",
        "status": "effective",
        "version_label": "2020年通过版（现行）",
        "version_status": "effective",
        "source_record_id": RECORD_ID,
        "source_url": f"{BASE_URL}/detail?id={RECORD_ID}",
        "official_database": "国家法律法规数据库",
        "maintainer": "全国人大常委会办公厅",
        "promulgation_date": details.get("gbrq"),
        "effective_date": details.get("sxrq"),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_hash": sha256,
        "article_count": len(articles),
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Validated {len(articles)} continuous articles (1-1260).")
    print(f"JSON: {args.output}")
    print(f"DOCX SHA-256: {sha256}")


if __name__ == "__main__":
    main()
