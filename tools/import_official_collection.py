"""Download and import the natural-resources/legal-procedure collection.

Sources are limited to the National Database of Laws and Regulations and the
official Ministry of Natural Resources rules catalogue. Every generated JSON
is rejected unless article numbers are continuous and article text is nonempty.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from import_official_civil_code import (
    BASE_URL,
    DOWNLOAD_URL,
    DETAIL_URL,
    ARTICLE_PATTERN,
    download_file,
    document_paragraphs,
    fetch_json,
    parse_articles,
)


COLLECTION = [
    {
        "slug": "civil-procedure-law",
        "title": "中华人民共和国民事诉讼法",
        "short_name": "民事诉讼法",
        "category": "法律",
        "description": "规范民事案件管辖、审判、执行及涉外民事诉讼程序的基本法律。",
        "versions": [
            {"id": "ff8081818a21dc13018b425303b7086d", "label": "2023年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "criminal-law",
        "title": "中华人民共和国刑法",
        "short_name": "刑法",
        "category": "法律",
        "description": "国家法律法规数据库2020年公布的刑法整合文本（含刑法修正案十一）；查询2024年3月1日后的案件还应结合刑法修正案十二适用。",
        "versions": [
            {"id": "ff808181796a636a0179822a19640c92", "label": "2020年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "criminal-procedure-law",
        "title": "中华人民共和国刑事诉讼法",
        "short_name": "刑事诉讼法",
        "category": "法律",
        "description": "规范刑事案件立案、侦查、起诉、审判和执行程序的基本法律。",
        "versions": [
            {"id": "ff8080816f135f46016f1d1b81b01351", "label": "2018年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "land-administration-law",
        "title": "中华人民共和国土地管理法",
        "short_name": "土地管理法",
        "category": "法律",
        "description": "土地所有权、用途管制、耕地保护、建设用地和监督检查的基础法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf62ce302f3", "label": "2004年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8080816f3cbb3c016f4626903427fc", "label": "2019年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "land-administration-law-regulations",
        "title": "中华人民共和国土地管理法实施条例",
        "short_name": "土地管理法实施条例",
        "category": "行政法规",
        "description": "土地管理法的配套行政法规。",
        "versions": [
            {"id": "ff8080816f3cbb3c016f40f5a2050e35", "label": "2014年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8081817b63b895017b7b071b6843c0", "label": "2021年修订版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "urban-rural-planning-law",
        "title": "中华人民共和国城乡规划法",
        "short_name": "城乡规划法",
        "category": "法律",
        "description": "城乡规划制定、实施、修改和监督检查的基础法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf7a26a07a3", "label": "2015年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8080816f135f46016f216129dd1a92", "label": "2019年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "administrative-licensing-law",
        "title": "中华人民共和国行政许可法",
        "short_name": "行政许可法",
        "category": "法律",
        "description": "行政许可设定、实施、监督检查和法律责任的基础法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf616a602c1", "label": "2003年通过版（历史）", "status": "repealed", "current": False},
            {"id": "ff8080816f135f46016f216bf96b1ae6", "label": "2019年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "administrative-penalty-law",
        "title": "中华人民共和国行政处罚法",
        "short_name": "行政处罚法",
        "category": "法律",
        "description": "行政处罚设定、实施机关、管辖适用及程序的基础法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf86fa90a7d", "label": "2017年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8080817703add20177373df6a43e33", "label": "2021年修订版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "administrative-reconsideration-law",
        "title": "中华人民共和国行政复议法",
        "short_name": "行政复议法",
        "category": "法律",
        "description": "行政复议申请、受理、审理和决定程序的基础法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf86f120a73", "label": "2017年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8081818a21e6c3018a508d491a0c98", "label": "2023年修订版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "administrative-litigation-law",
        "title": "中华人民共和国行政诉讼法",
        "short_name": "行政诉讼法",
        "category": "法律",
        "description": "人民法院审理行政案件的基本诉讼法律。",
        "versions": [
            {"id": "2c909fdd678bf17901678bf858550a0f", "label": "2017年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "interim-real-estate-registration-regulations",
        "title": "不动产登记暂行条例",
        "short_name": "不动产登记暂行条例",
        "category": "行政法规",
        "description": "不动产统一登记机构、登记簿、程序和信息共享的行政法规。",
        "versions": [
            {"id": "ff8080816f3cbb3c016f4127f0361a2d", "label": "2019年修正版（历史）", "status": "repealed", "current": False},
            {"id": "ff8081819c46fdc3019cd18cd0a71cd0", "label": "2024年修正版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "spc-administrative-litigation-interpretation",
        "title": "最高人民法院关于适用《中华人民共和国行政诉讼法》的解释",
        "short_name": "行政诉讼法司法解释",
        "category": "司法解释",
        "description": "最高人民法院关于行政诉讼法适用问题的综合司法解释。",
        "versions": [
            {"id": "2c90e5ba65c68cf70167f29d0e604ec4", "label": "2018年施行版（现行）", "status": "effective", "current": True},
        ],
    },
    {
        "slug": "spc-state-land-use-contract-interpretation",
        "title": "最高人民法院关于审理涉及国有土地使用权合同纠纷案件适用法律问题的解释",
        "short_name": "国有土地使用权合同司法解释",
        "category": "司法解释",
        "description": "国有土地使用权出让、转让及合作开发房地产合同纠纷的司法解释。",
        "versions": [
            {"id": "402881e45ffbbe41015ffc70b97a0d43", "label": "2005年施行版（历史）", "status": "repealed", "current": False},
            {
                "id": "ff808181799df4000179b09d7fb4181e",
                "label": "2020年修正版（现行）",
                "status": "effective",
                "current": True,
                # The database attachment is a legacy Word binary and its PDF is
                # image-only. The Supreme People's Court also publishes the exact
                # amended full text in this official decision page.
                "html_url": "https://www.court.gov.cn/zixun/xiangqing/282621.html",
                "html_start": "第一条本解释所称的土地使用权出让合同",
                "html_stop": "最高人民法院",
            },
        ],
    },
    {
        "slug": "spc-house-registration-provisions",
        "title": "最高人民法院关于审理房屋登记案件若干问题的规定",
        "short_name": "房屋登记案件规定",
        "category": "司法解释",
        "description": "人民法院审理房屋登记行政案件的专门司法解释。",
        "versions": [
            {"id": "402881e45ffbbe41015ffc53ea7e0a15", "label": "2010年施行版（现行）", "status": "effective", "current": True},
        ],
    },
]

MNR_RULES = [
    {
        "slug": "idle-land-disposal-measures",
        "title": "闲置土地处置办法",
        "short_name": "闲置土地处置办法",
        "category": "部门规章",
        "description": "闲置土地调查、认定、处置、预防和监管的部门规章。",
        "authority": "国土资源部",
        "url": "https://gk.mnr.gov.cn/zc/gz/201702/t20170206_1437100.html",
        "label": "2012年修订版（现行）",
        "promulgation_date": "2012-06-01",
        "effective_date": "2012-07-01",
    },
    {
        "slug": "natural-resources-administrative-penalty-measures",
        "title": "自然资源行政处罚办法",
        "short_name": "自然资源行政处罚办法",
        "category": "部门规章",
        "description": "自然资源违法案件行政处罚的管辖、调查、决定、执行和监督规则。",
        "authority": "自然资源部",
        "url": "https://gk.mnr.gov.cn/zc/gz/202402/t20240205_2837163.html",
        "label": "2024年修订版（现行）",
        "promulgation_date": "2024-01-31",
        "effective_date": "2024-05-01",
    },
]


class DocumentTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_doc = False
        self.doc_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if not self.in_doc and attributes.get("id") == "doccon":
            self.in_doc = True
            self.doc_depth = 1
            return
        if self.in_doc:
            if tag == "div":
                self.doc_depth += 1
            if tag in {"p", "div", "br"}:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if not self.in_doc:
            return
        if tag in {"p", "div"}:
            self.parts.append("\n")
        if tag == "div":
            self.doc_depth -= 1
            if self.doc_depth == 0:
                self.in_doc = False

    def handle_data(self, data):
        if self.in_doc:
            self.parts.append(data)

    def lines(self) -> list[str]:
        text = html.unescape("".join(self.parts)).replace("\xa0", " ")
        return [re.sub(r"[\t ]+", " ", line).strip() for line in text.splitlines() if line.strip()]


def expected_article_numbers(tree: dict | None) -> list[int]:
    if not isinstance(tree, dict):
        return []
    result: list[int] = []
    stack = [tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        match = ARTICLE_PATTERN.fullmatch(str(node.get("title") or "").strip())
        if match:
            from import_official_civil_code import chinese_number
            result.append(chinese_number(match.group(1)))
        stack.extend(reversed(node.get("children") or []))
    return sorted(set(result))


def validate_continuous(articles: list[dict], expected: list[int] | None = None) -> None:
    numbers = [row["article_no"] for row in articles]
    if not numbers:
        raise ValueError("No articles were parsed; refusing to create or import an empty version")
    continuous = list(range(1, max(numbers, default=0) + 1))
    if numbers != continuous:
        raise ValueError(f"Article numbers are not continuous: {numbers[:10]} ... {numbers[-10:]}")
    if expected and numbers != expected:
        raise ValueError(f"DOCX/tree mismatch: parsed={len(numbers)}, tree={len(expected)}")
    if any(not row["content"].strip() for row in articles):
        raise ValueError("One or more articles have empty text")


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", value).strip("_")


def pdf_paragraphs(pdf_path: Path) -> list[str]:
    from pypdf import PdfReader
    lines: list[str] = []
    for page in PdfReader(str(pdf_path)).pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
            line = re.sub(r"[\t ]+", " ", line).strip()
            if line:
                lines.append(line)
    return lines


def write_version(output_root: Path, law: dict, version: dict, articles: list[dict], metadata: dict) -> tuple[Path, Path]:
    folder = output_root / law["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    stem = safe_name(version["label"])
    article_path = folder / f"{stem}_articles.json"
    metadata_path = folder / f"{stem}_metadata.json"
    article_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path, article_path


def process_flk(output_root: Path) -> list[tuple[Path, Path, bool]]:
    generated = []
    for law in COLLECTION:
        for version in law["versions"]:
            folder = output_root / law["slug"]
            stem = safe_name(version["label"])
            cached_metadata = folder / f"{stem}_metadata.json"
            cached_articles = folder / f"{stem}_articles.json"
            if cached_metadata.exists() and cached_articles.exists():
                articles = json.loads(cached_articles.read_text(encoding="utf-8"))
                metadata = json.loads(cached_metadata.read_text(encoding="utf-8"))
                if metadata.get("title") == law["title"]:
                    try:
                        validate_continuous(articles)
                    except ValueError as exc:
                        print(f"INVALID CACHE {law['title']} | {version['label']} | {exc}; downloading again")
                    else:
                        generated.append((cached_metadata, cached_articles, version["current"]))
                        print(f"CACHED {law['title']} | {version['label']} | {len(articles)} articles")
                        continue
            details = fetch_json(DETAIL_URL, {"bbbs": version["id"]})
            if details.get("title") != law["title"]:
                raise ValueError(f"Unexpected title for {version['id']}: {details.get('title')}")
            source_url = f"{BASE_URL}/detail?id={version['id']}"
            source_database = "国家法律法规数据库"
            if version.get("html_url"):
                page, source_hash = fetch_html(version["html_url"])
                html_path = folder / f"{safe_name(version['label'])}_official.html"
                html_path.write_text(page, encoding="utf-8")
                articles = parse_articles(
                    sliced_html_paragraphs(page, version["html_start"], version["html_stop"])
                )
                source_url = version["html_url"]
                source_database = "中华人民共和国最高人民法院"
            else:
                download = fetch_json(DOWNLOAD_URL, {"bbbs": version["id"], "format": "docx"})
                docx_path = folder / f"{safe_name(version['label'])}_official.docx"
                source_hash = download_file(download["url"], docx_path)
                try:
                    articles = parse_articles(document_paragraphs(docx_path))
                except zipfile.BadZipFile:
                    pdf_download = fetch_json(DOWNLOAD_URL, {"bbbs": version["id"], "format": "pdf"})
                    pdf_path = folder / f"{safe_name(version['label'])}_official.pdf"
                    source_hash = download_file(pdf_download["url"], pdf_path)
                    articles = parse_articles(pdf_paragraphs(pdf_path))
            validate_continuous(articles, expected_article_numbers(details["content"]))
            metadata = {
                "slug": law["slug"], "title": law["title"], "short_name": law["short_name"],
                "issuing_authority": details.get("zdjgName") or "", "jurisdiction": "中国",
                "category": law["category"], "status": "effective",
                "version_label": version["label"], "version_status": version["status"],
                "promulgation_date": details.get("gbrq"), "effective_date": details.get("sxrq"),
                "expiry_date": None, "source_url": source_url,
                "source_record_id": version["id"], "source_hash": source_hash,
                "description": law["description"], "article_count": len(articles),
                "source_database": source_database,
            }
            generated.append((*write_version(output_root, law, version, articles, metadata), version["current"]))
            print(f"OK {law['title']} | {version['label']} | {len(articles)} articles")
    return generated


def fetch_html(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(request, timeout=60).read()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def sliced_html_paragraphs(page: str, start: str, stop: str) -> list[str]:
    text = re.sub(r"<(?:br|/p|/div)\b[^>]*>", "\n", page, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [re.sub(r"[\t ]+", " ", html.unescape(line)).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    try:
        begin = next(index for index, line in enumerate(lines) if line.startswith(start))
    except StopIteration as exc:
        raise ValueError(f"Official court page did not contain start marker: {start}") from exc
    end = next((index for index in range(begin + 1, len(lines)) if lines[index] == stop), len(lines))
    return lines[begin:end]


def process_mnr(output_root: Path) -> list[tuple[Path, Path, bool]]:
    generated = []
    for rule in MNR_RULES:
        page, source_hash = fetch_html(rule["url"])
        title_match = re.search(r"<title>(.*?)</title>", page, re.I | re.S)
        if not title_match or title_match.group(1).strip() != rule["title"]:
            raise ValueError(f"Unexpected MNR page title: {title_match.group(1) if title_match else None}")
        parser = DocumentTextParser()
        parser.feed(page)
        articles = parse_articles(parser.lines())
        validate_continuous(articles)
        version = {"label": rule["label"]}
        metadata = {
            "slug": rule["slug"], "title": rule["title"], "short_name": rule["short_name"],
            "issuing_authority": rule["authority"], "jurisdiction": "中国",
            "category": rule["category"], "status": "effective",
            "version_label": rule["label"], "version_status": "effective",
            "promulgation_date": rule["promulgation_date"], "effective_date": rule["effective_date"],
            "expiry_date": None, "source_url": rule["url"], "source_record_id": "",
            "source_hash": source_hash, "description": rule["description"],
            "article_count": len(articles), "source_database": "自然资源部政府信息公开目录",
        }
        generated.append((*write_version(output_root, rule, version, articles, metadata), True))
        print(f"OK {rule['title']} | {rule['label']} | {len(articles)} articles")
    return generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/legal_collection"))
    parser.add_argument("--import-db", action="store_true")
    args = parser.parse_args()
    generated = process_flk(args.output) + process_mnr(args.output)
    manifest = [{
        "metadata": meta.as_posix(), "articles": articles.as_posix(), "current": current
    } for meta, articles, current in generated]
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.import_db:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app import app
        from db import import_law_version
        with app.app_context():
            for metadata, articles, current in generated:
                title, version, count = import_law_version(metadata, articles, make_current=current)
                print(f"IMPORTED {title} | {version} | {count}")
    print(f"Completed {len(generated)} verified versions across {len(COLLECTION) + len(MNR_RULES)} laws.")


if __name__ == "__main__":
    main()
