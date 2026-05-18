#!/usr/bin/env python3
"""Build data/policy_frontier.json for the economics policy frontier tracker."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "policy_frontier.json"
TRACKER_KEY = "policy_frontier_tracker"

CONTACT_EMAIL = os.getenv("TRACKER_CONTACT_EMAIL", "jincaiqi@ucass.edu.cn")
HEADERS = {
    "User-Agent": f"econ-policy-frontier-tracker/1.0 (mailto:{CONTACT_EMAIL})",
    "Accept": "application/json, text/html;q=0.9, text/plain;q=0.9, */*;q=0.8",
}
TIMEOUT = int(os.getenv("POLICY_FRONTIER_TIMEOUT_SECONDS", "25"))

KIMI_API_BASE = os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1").rstrip("/")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "").strip()
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
KIMI_MIN_INTERVAL_SECONDS = float(os.getenv("KIMI_MIN_INTERVAL_SECONDS", "1.6"))
MAX_ABSTRACT_TRANSLATE_CHARS = int(os.getenv("MAX_ABSTRACT_TRANSLATE_CHARS", "2500"))
MAX_PAPERS_PER_SOURCE = int(os.getenv("MAX_POLICY_FRONTIER_PAPERS_PER_SOURCE", "12"))
MAX_NBER_RECENT_PAPERS = int(os.getenv("MAX_NBER_RECENT_PAPERS", "220"))
MAX_TRACKED_JOURNALS = int(os.getenv("MAX_TRACKED_JOURNALS", "0"))
ENABLE_OPENALEX_ABSTRACT_LOOKUP = os.getenv("ENABLE_OPENALEX_ABSTRACT_LOOKUP", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}
LOAD_NBER_PROGRAMS = os.getenv("LOAD_NBER_PROGRAMS", "0").strip().lower() in {"1", "true", "yes"}

NBER_TSV_BASE = "https://data.nber.org/nber_paper_chapter_metadata/tsv"

JOURNALS: List[Dict[str, str]] = [
    {
        "name": "American Economic Review",
        "issn": "0002-8282",
        "category": "Top 5",
        "issue_url": "https://www.aeaweb.org/journals/aer",
    },
    {
        "name": "Quarterly Journal of Economics",
        "issn": "0033-5533",
        "category": "Top 5",
        "issue_url": "https://academic.oup.com/qje",
    },
    {
        "name": "Journal of Political Economy",
        "issn": "0022-3808",
        "category": "Top 5",
        "issue_url": "https://www.journals.uchicago.edu/journals/jpe",
    },
    {
        "name": "Econometrica",
        "issn": "0012-9682",
        "category": "Top 5",
        "issue_url": "https://onlinelibrary.wiley.com/journal/14680262",
    },
    {
        "name": "Review of Economic Studies",
        "issn": "0034-6527",
        "category": "Top 5",
        "issue_url": "https://academic.oup.com/restud",
    },
    {
        "name": "American Economic Journal: Applied Economics",
        "issn": "1945-7782",
        "category": "AEJ / applied",
        "issue_url": "https://www.aeaweb.org/journals/app",
    },
    {
        "name": "American Economic Journal: Economic Policy",
        "issn": "1945-7731",
        "category": "AEJ / policy",
        "issue_url": "https://www.aeaweb.org/journals/pol",
    },
    {
        "name": "American Economic Journal: Microeconomics",
        "issn": "1945-7669",
        "category": "AEJ / micro",
        "issue_url": "https://www.aeaweb.org/journals/mic",
    },
    {
        "name": "Review of Economics and Statistics",
        "issn": "0034-6535",
        "category": "General field",
        "issue_url": "https://direct.mit.edu/rest",
    },
    {
        "name": "Journal of Public Economics",
        "issn": "0047-2727",
        "category": "Public economics",
        "issue_url": "https://www.sciencedirect.com/journal/journal-of-public-economics",
    },
    {
        "name": "Journal of Development Economics",
        "issn": "0304-3878",
        "category": "Development",
        "issue_url": "https://www.sciencedirect.com/journal/journal-of-development-economics",
    },
    {
        "name": "Journal of International Economics",
        "issn": "0022-1996",
        "category": "International",
        "issue_url": "https://www.sciencedirect.com/journal/journal-of-international-economics",
    },
    {
        "name": "Journal of Industrial Economics",
        "issn": "0022-1821",
        "category": "Industrial organization",
        "issue_url": "https://onlinelibrary.wiley.com/journal/14676451",
    },
    {
        "name": "RAND Journal of Economics",
        "issn": "0741-6261",
        "category": "Industrial organization",
        "issue_url": "https://onlinelibrary.wiley.com/journal/17562171",
    },
    {
        "name": "International Journal of Industrial Organization",
        "issn": "0167-7187",
        "category": "Industrial organization",
        "issue_url": "https://www.sciencedirect.com/journal/international-journal-of-industrial-organization",
    },
    {
        "name": "Research Policy",
        "issn": "0048-7333",
        "category": "Innovation",
        "issue_url": "https://www.sciencedirect.com/journal/research-policy",
    },
    {
        "name": "Industrial and Corporate Change",
        "issn": "0960-6491",
        "category": "Innovation",
        "issue_url": "https://academic.oup.com/icc",
    },
    {
        "name": "Management Science",
        "issn": "0025-1909",
        "category": "Innovation / AI",
        "issue_url": "https://pubsonline.informs.org/journal/mnsc",
    },
    {
        "name": "Journal of Environmental Economics and Management",
        "issn": "0095-0696",
        "category": "Environment",
        "issue_url": "https://www.sciencedirect.com/journal/journal-of-environmental-economics-and-management",
    },
    {
        "name": "Review of Environmental Economics and Policy",
        "issn": "1750-6816",
        "category": "Environment",
        "issue_url": "https://academic.oup.com/reep",
    },
    {
        "name": "Energy Economics",
        "issn": "0140-9883",
        "category": "Environment / energy",
        "issue_url": "https://www.sciencedirect.com/journal/energy-economics",
    },
    {
        "name": "Resource and Energy Economics",
        "issn": "0928-7655",
        "category": "Environment / energy",
        "issue_url": "https://www.sciencedirect.com/journal/resource-and-energy-economics",
    },
]

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "产业政策": [
        "industrial policy",
        "industry policy",
        "sectoral policy",
        "manufacturing policy",
        "place-based policy",
        "place based policy",
        "regional policy",
        "cluster policy",
        "industrial cluster",
        "industrial park",
        "special economic zone",
        "export promotion",
        "import substitution",
        "state aid",
        "production subsidy",
        "subsidy",
        "subsidies",
        "tax incentive",
        "investment incentive",
        "government procurement",
        "public procurement",
        "local content",
        "development bank",
        "directed credit",
        "targeted credit",
        "tariff protection",
        "infant industry",
        "strategic industry",
        "产业政策",
        "制造业政策",
        "产业补贴",
        "政府补贴",
        "税收激励",
        "开发区",
        "产业园",
        "产业集群",
        "政府采购",
        "地方保护",
    ],
    "创新": [
        "innovation",
        "innovative",
        "invention",
        "inventor",
        "patent",
        "patents",
        "research and development",
        "r&d",
        "technology adoption",
        "technology diffusion",
        "technology transfer",
        "knowledge spillover",
        "science policy",
        "research subsidy",
        "research grant",
        "startup",
        "start-up",
        "entrepreneurship",
        "productivity growth",
        "技术创新",
        "企业创新",
        "研发",
        "专利",
        "创业",
        "技术扩散",
        "知识溢出",
    ],
    "绿色发展": [
        "green development",
        "green growth",
        "green innovation",
        "clean technology",
        "clean energy",
        "climate policy",
        "climate change",
        "carbon",
        "carbon tax",
        "carbon pricing",
        "cap-and-trade",
        "cap and trade",
        "emission",
        "emissions",
        "pollution",
        "environmental regulation",
        "renewable energy",
        "energy transition",
        "decarbonization",
        "sustainable development",
        "esg",
        "绿色发展",
        "绿色创新",
        "气候政策",
        "碳排放",
        "碳税",
        "碳交易",
        "环境规制",
        "污染",
        "可再生能源",
        "能源转型",
    ],
    "人工智能": [
        "artificial intelligence",
        "ai",
        "generative ai",
        "machine learning",
        "deep learning",
        "large language model",
        "large language models",
        "llm",
        "algorithmic",
        "algorithm",
        "automation",
        "robot",
        "robots",
        "robotics",
        "digital technology",
        "digital transformation",
        "data economy",
        "platform algorithm",
        "人工智能",
        "机器学习",
        "深度学习",
        "大语言模型",
        "算法",
        "自动化",
        "机器人",
        "数字技术",
        "数字化转型",
    ],
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_text(" ".join(self.parts))


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def strip_html_text(text: str) -> str:
    if not text:
        return ""
    parser = TextExtractor()
    try:
        parser.feed(unescape(text))
        return parser.text()
    except Exception:
        return normalize_text(re.sub(r"<[^>]+>", " ", unescape(text)))


def normalize_name_key(text: str) -> str:
    s = normalize_text(text).lower()
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)
    return normalize_text(s)


def trim_for_translation(text: str, max_chars: int = MAX_ABSTRACT_TRANSLATE_CHARS) -> str:
    s = normalize_text(text)
    if len(s) <= max_chars:
        return s
    return s[:max_chars].rsplit(" ", 1)[0] + " ..."


def clean_translation_output(text: str) -> str:
    s = normalize_text(text)
    if not s:
        return ""
    s = re.sub(r"^type\s*:\s*.*?text\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"^(translation|译文|翻译)\s*:\s*", "", s, flags=re.I)
    return normalize_text(s.strip("\"'` "))


def request_with_retries(method: str, url: str, **kwargs: Any) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            resp = requests.request(method, url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
            if resp.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"{method.upper()} failed for {url}: {last_error}")


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = request_with_retries("get", url, params=params)
    return resp.json()


def fetch_text(url: str) -> str:
    resp = request_with_retries("get", url)
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def safe_title(item: Dict[str, Any]) -> str:
    title = item.get("title", "")
    if isinstance(title, list):
        return normalize_text(title[0] if title else "")
    return normalize_text(title)


def date_tuple_from_crossref(item: Dict[str, Any]) -> Tuple[int, int, int]:
    fields = [
        "published-print",
        "published-online",
        "published",
        "issued",
        "created",
        "deposited",
    ]
    for key in fields:
        node = item.get(key, {})
        if not isinstance(node, dict):
            continue
        date_parts = node.get("date-parts")
        if not isinstance(date_parts, list) or not date_parts:
            continue
        first = date_parts[0]
        if not isinstance(first, list) or not first:
            continue
        try:
            year = int(first[0])
            month = int(first[1]) if len(first) > 1 else 1
            day = int(first[2]) if len(first) > 2 else 1
            return (year, month, day)
        except Exception:
            continue
    return (0, 0, 0)


def date_string_from_tuple(value: Tuple[int, int, int]) -> str:
    year, month, day = value
    if year <= 0:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def score_journal_candidate(query_name: str, candidate_title: str) -> int:
    query = normalize_name_key(query_name)
    candidate = normalize_name_key(candidate_title)
    if not query or not candidate:
        return -1
    if query == candidate:
        return 1000

    score = 0
    if query in candidate or candidate in query:
        score += 500

    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    score += len(query_tokens & candidate_tokens) * 80
    score -= abs(len(query_tokens) - len(candidate_tokens)) * 6
    return score


def resolve_crossref_journal(journal: Dict[str, str]) -> Tuple[str, str, Optional[str]]:
    query_name = normalize_text(journal.get("query_name") or journal.get("name"))
    issn_hint = normalize_text(journal.get("issn"))
    issn_lookup_error = ""

    if issn_hint:
        try:
            payload = fetch_json(f"https://api.crossref.org/journals/{issn_hint}")
            message = payload.get("message", {}) if isinstance(payload, dict) else {}
            title = normalize_text(message.get("title")) or query_name
            return issn_hint, title, None
        except Exception as exc:
            issn_lookup_error = str(exc)

    try:
        payload = fetch_json(
            "https://api.crossref.org/journals",
            params={"query.title": query_name, "rows": 8},
        )
    except Exception as exc:
        return "", query_name, str(exc)

    items = payload.get("message", {}).get("items", [])
    if not items:
        return "", query_name, "No Crossref journal match found."

    best = max(items, key=lambda row: score_journal_candidate(query_name, normalize_text(row.get("title", ""))))
    issn_list = best.get("ISSN", [])
    if not isinstance(issn_list, list):
        issn_list = []
    resolved_issn = normalize_text(issn_list[0] if issn_list else "")
    resolved_title = normalize_text(best.get("title")) or query_name

    if not resolved_issn:
        return "", resolved_title, "Crossref result has no ISSN."

    if issn_lookup_error:
        return resolved_issn, resolved_title, f"ISSN lookup failed; title fallback used: {issn_lookup_error}"

    return resolved_issn, resolved_title, None


def determine_latest_issue(items: List[Dict[str, Any]]) -> Tuple[str, str, Tuple[int, int, int]]:
    article_items = [item for item in items if item.get("type") == "journal-article"]
    if not article_items:
        return "", "", (0, 0, 0)

    candidates: List[Tuple[Tuple[int, int, int], str, str]] = []
    for item in article_items:
        volume = normalize_text(item.get("volume"))
        issue = normalize_text(item.get("issue"))
        if volume and issue:
            candidates.append((date_tuple_from_crossref(item), volume, issue))

    if candidates:
        latest_date, volume, issue = max(candidates, key=lambda row: (row[0], row[1], row[2]))
        return volume, issue, latest_date

    latest_date = max((date_tuple_from_crossref(item) for item in article_items), default=(0, 0, 0))
    return "", "", latest_date


def in_latest_issue(
    item: Dict[str, Any],
    latest_volume: str,
    latest_issue: str,
    latest_date: Tuple[int, int, int],
) -> bool:
    if latest_volume and latest_issue:
        return normalize_text(item.get("volume")) == latest_volume and normalize_text(item.get("issue")) == latest_issue

    year, month, _ = latest_date
    if year <= 0:
        return True

    item_year, item_month, _ = date_tuple_from_crossref(item)
    return item_year == year and item_month == month


def doi_from_crossref_item(item: Dict[str, Any]) -> str:
    doi = normalize_text(item.get("DOI"))
    if doi:
        return doi
    url = normalize_text(item.get("URL", ""))
    match = re.search(r"https?://(?:dx\.)?doi\.org/(.+)", url, flags=re.I)
    return match.group(1).strip() if match else ""


def openalex_abstract_from_doi(doi: str) -> str:
    if not doi:
        return ""

    api_url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        payload = fetch_json(api_url)
    except Exception:
        return ""

    inverted = payload.get("abstract_inverted_index")
    if not isinstance(inverted, dict) or not inverted:
        return ""

    words: Dict[int, str] = {}
    max_position = -1
    for token, positions in inverted.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            try:
                index = int(position)
            except Exception:
                continue
            words[index] = token
            max_position = max(max_position, index)

    if max_position < 0:
        return ""

    return normalize_text(" ".join(words.get(index, "") for index in range(max_position + 1)))


def format_crossref_authors(item: Dict[str, Any]) -> str:
    authors = item.get("author")
    if not isinstance(authors, list):
        return ""

    names: List[str] = []
    for author in authors[:8]:
        if not isinstance(author, dict):
            continue
        family = normalize_text(author.get("family"))
        given = normalize_text(author.get("given"))
        name = normalize_text(" ".join(part for part in [given, family] if part))
        if name:
            names.append(name)

    if len(authors) > 8:
        names.append("et al.")
    return ", ".join(names)


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def contains_keyword(haystack: str, keyword: str) -> bool:
    term = normalize_text(keyword).lower()
    if not term:
        return False
    if has_cjk(term):
        return term in haystack
    if re.fullmatch(r"[a-z0-9&.+-]+", term):
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    if term[0].isalnum() and term[-1].isalnum():
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    return term in haystack


def detect_topics(title: str, abstract: str) -> List[str]:
    haystack = normalize_text(f"{title} {abstract}").lower()
    if not haystack:
        return []

    matched: List[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(contains_keyword(haystack, keyword) for keyword in keywords):
            matched.append(topic)
    return matched


class KimiTranslator:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.enabled = bool(api_key)
        self.cache: Dict[str, str] = {}
        self.success_count = 0
        self.fail_count = 0
        self.fail_samples: List[str] = []
        self._last_call_ts = 0.0

    def warmup_cache(self, old_data: Dict[str, Any]) -> None:
        tracker = old_data.get(TRACKER_KEY, {}) if isinstance(old_data, dict) else {}
        sources = tracker.get("sources", [])
        if not isinstance(sources, list):
            sources = []

        for source in sources:
            for paper in source.get("papers", []) if isinstance(source, dict) else []:
                title_en = normalize_text(paper.get("title_en") or paper.get("title"))
                title_zh = normalize_text(paper.get("title_zh"))
                if title_en and title_zh:
                    self.cache[title_en] = title_zh

                abstract_en = normalize_text(paper.get("abstract_en"))
                abstract_zh = normalize_text(paper.get("abstract_zh"))
                if abstract_en and abstract_zh:
                    self.cache[abstract_en] = abstract_zh

    def _record_failure(self, source: str, message: str) -> None:
        self.fail_count += 1
        if len(self.fail_samples) < 8:
            self.fail_samples.append(f"{source[:90]} :: {message[:180]}")

    def _respect_rate_limit(self) -> None:
        if KIMI_MIN_INTERVAL_SECONDS <= 0:
            return
        now = time.time()
        wait_seconds = KIMI_MIN_INTERVAL_SECONDS - (now - self._last_call_ts)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def translate(self, text: str, kind: str = "text") -> str:
        source = normalize_text(text)
        if not source:
            return ""
        if source in self.cache:
            return self.cache[source]
        if not self.enabled:
            return ""

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional translator for economics research. "
                        "Translate into concise Simplified Chinese and keep field terms precise."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Translate the following English economics research content into Simplified Chinese. "
                        "Keep terms such as industrial policy, innovation, green development, and AI precise. "
                        "Output translation only.\n\n"
                        f"Type: {kind}\n"
                        f"Text:\n{source}"
                    ),
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for attempt in range(4):
            try:
                self._respect_rate_limit()
                resp = requests.post(
                    f"{KIMI_API_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90,
                )
                self._last_call_ts = time.time()
                if resp.status_code >= 400:
                    raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:220]}")

                data = resp.json()
                translated = clean_translation_output(data["choices"][0]["message"]["content"])
                if not translated:
                    raise ValueError("Empty translation")

                self.cache[source] = translated
                self.success_count += 1
                return translated
            except Exception as exc:
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                else:
                    self.cache[source] = ""
                    self._record_failure(source, str(exc))
                    return ""

        return ""


def translate_paper_fields(
    title_en: str,
    abstract_en: str,
    translator: KimiTranslator,
) -> Tuple[str, str]:
    title_zh = translator.translate(title_en, kind="title")
    abstract_zh = (
        translator.translate(trim_for_translation(abstract_en), kind="abstract")
        if abstract_en
        else ""
    )
    return title_zh, abstract_zh


def build_journal_block(journal: Dict[str, str], translator: KimiTranslator) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "source_type": "journal",
        "name": journal.get("name"),
        "query_name": journal.get("query_name") or journal.get("name"),
        "category": journal.get("category", ""),
        "issn": normalize_text(journal.get("issn")),
        "resolved_name": journal.get("name"),
        "issue_title": "Latest issue (Crossref)",
        "issue_url": journal.get("issue_url", ""),
        "matched_count": 0,
        "total_in_issue": 0,
        "papers": [],
        "error": None,
    }

    resolved_issn, resolved_name, resolve_error = resolve_crossref_journal(journal)
    if resolved_name:
        result["resolved_name"] = resolved_name
    if resolved_issn:
        result["issn"] = resolved_issn

    if not resolved_issn:
        result["error"] = resolve_error or "Unable to resolve journal ISSN from Crossref."
        return result

    try:
        payload = fetch_json(
            f"https://api.crossref.org/journals/{resolved_issn}/works",
            params={
                "sort": "published",
                "order": "desc",
                "rows": 240,
                "select": (
                    "DOI,title,URL,volume,issue,type,abstract,author,"
                    "published-print,published-online,published,issued"
                ),
            },
        )
        items = payload.get("message", {}).get("items", [])
        latest_volume, latest_issue, latest_date = determine_latest_issue(items)

        if latest_volume and latest_issue:
            result["issue_title"] = f"Volume {latest_volume}, Issue {latest_issue}"
        elif latest_date[0] > 0:
            result["issue_title"] = f"Published {latest_date[0]:04d}-{latest_date[1]:02d}"

        picked: List[Dict[str, Any]] = []
        total_in_issue = 0

        for item in items:
            if item.get("type") != "journal-article":
                continue

            title_en = safe_title(item)
            url = normalize_text(item.get("URL", ""))
            if not title_en or not url:
                continue

            if not in_latest_issue(item, latest_volume, latest_issue, latest_date):
                continue

            total_in_issue += 1
            abstract_en = strip_html_text(item.get("abstract", ""))
            if not abstract_en and ENABLE_OPENALEX_ABSTRACT_LOOKUP:
                abstract_en = openalex_abstract_from_doi(doi_from_crossref_item(item))
            abstract_en = normalize_text(abstract_en)

            matched_topics = detect_topics(title_en, abstract_en)
            if not matched_topics:
                continue

            title_zh, abstract_zh = translate_paper_fields(title_en, abstract_en, translator)
            date_display = date_string_from_tuple(date_tuple_from_crossref(item))

            picked.append(
                {
                    "title_en": title_en,
                    "title_zh": title_zh,
                    "url": url,
                    "authors": format_crossref_authors(item),
                    "date": date_display,
                    "abstract_en": abstract_en,
                    "abstract_zh": abstract_zh,
                    "matched_topics": matched_topics,
                }
            )

            if len(picked) >= MAX_PAPERS_PER_SOURCE:
                break

        result["papers"] = picked
        result["matched_count"] = len(picked)
        result["total_in_issue"] = total_in_issue
        if resolve_error:
            result["error"] = f"ISSN fallback used: {resolve_error}"

    except Exception as exc:
        result["error"] = str(exc)

    return result


def normalize_tsv_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(key or "").lower())


def normalize_tsv_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {normalize_tsv_key(key): normalize_text(value) for key, value in row.items()}


def row_value(row: Dict[str, str], candidates: Iterable[str]) -> str:
    for key in candidates:
        value = normalize_text(row.get(normalize_tsv_key(key)))
        if value:
            return value
    return ""


def fetch_tsv_rows(filename: str) -> List[Dict[str, str]]:
    text = fetch_text(f"{NBER_TSV_BASE}/{filename}")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter="\t")
    return [normalize_tsv_row(row) for row in reader]


def fetch_tsv_rows_optional(filename: str) -> List[Dict[str, str]]:
    try:
        return fetch_tsv_rows(filename)
    except Exception:
        return []


def paper_number_key(paper_id: str) -> int:
    match = re.search(r"\d+", paper_id)
    return int(match.group(0)) if match else 0


def parse_date_flexible(value: str) -> Tuple[int, int, int]:
    s = normalize_text(value)
    if not s:
        return (0, 0, 0)

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(s, fmt)
            return (parsed.year, parsed.month, parsed.day)
        except ValueError:
            continue

    match = re.search(r"(19|20)\d{2}[-/](\d{1,2})(?:[-/](\d{1,2}))?", s)
    if match:
        return (int(match.group(0)[:4]), int(match.group(2)), int(match.group(3) or 1))

    match = re.search(r"(19|20)\d{2}", s)
    if match:
        return (int(match.group(0)), 1, 1)

    return (0, 0, 0)


def nber_paper_url(paper_id: str) -> str:
    return f"https://www.nber.org/papers/{paper_id}"


def build_nber_raw_papers() -> List[Dict[str, Any]]:
    ref_rows = fetch_tsv_rows("ref.tsv")
    abs_rows = fetch_tsv_rows_optional("abs.tsv")
    prog_rows = fetch_tsv_rows_optional("prog.tsv") if LOAD_NBER_PROGRAMS else []

    abstracts: Dict[str, str] = {}
    for row in abs_rows:
        paper_id = row_value(row, ["paper", "paper_id", "paperid", "id"]).lower()
        abstract = row_value(row, ["abstract", "paper_abstract", "paperabstract", "text"])
        if paper_id and abstract:
            abstracts[paper_id] = abstract

    programs: Dict[str, List[str]] = {}
    for row in prog_rows:
        paper_id = row_value(row, ["paper", "paper_id", "paperid", "id"]).lower()
        program = row_value(row, ["program", "prog", "nber_program", "nberprogram"])
        if paper_id and program and program not in programs.get(paper_id, []):
            programs.setdefault(paper_id, []).append(program)

    papers: Dict[str, Dict[str, Any]] = {}
    for row in ref_rows:
        paper_id = row_value(row, ["paper", "paper_id", "paperid", "paper_number", "papernumber", "id"]).lower()
        if not paper_id or not paper_id.startswith("w"):
            continue

        paper = papers.setdefault(
            paper_id,
            {
                "paper_id": paper_id,
                "title_en": "",
                "authors": [],
                "date_raw": "",
                "doi": "",
            },
        )

        title = row_value(row, ["title", "paper_title", "papertitle"])
        if title:
            paper["title_en"] = title

        author = row_value(row, ["author", "authors", "author_name", "authorname", "name"])
        if author and author not in paper["authors"]:
            paper["authors"].append(author)

        date_raw = row_value(row, ["issue_date", "issuedate", "paper_date", "paperdate", "date", "publication_date", "publicationdate"])
        if date_raw:
            paper["date_raw"] = date_raw

        doi = row_value(row, ["doi", "paper_doi", "paperdoi"])
        if doi:
            paper["doi"] = doi

    for paper_id, paper in papers.items():
        paper["abstract_en"] = abstracts.get(paper_id, "")
        paper["programs"] = programs.get(paper_id, [])
        paper["date_tuple"] = parse_date_flexible(paper.get("date_raw", ""))

    return list(papers.values())


def format_nber_authors(authors: List[str]) -> str:
    if not authors:
        return ""
    if len(authors) <= 8:
        return ", ".join(authors)
    return ", ".join(authors[:8] + ["et al."])


def build_nber_block(translator: KimiTranslator) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "source_type": "nber",
        "name": "NBER Working Papers",
        "category": "Working papers",
        "issue_title": "Recent NBER Working Papers",
        "issue_url": "https://www.nber.org/papers",
        "matched_count": 0,
        "total_recent_considered": 0,
        "papers": [],
        "error": None,
    }

    try:
        raw_papers = build_nber_raw_papers()
        raw_papers.sort(key=lambda row: (row.get("date_tuple", (0, 0, 0)), paper_number_key(row["paper_id"])), reverse=True)
        recent = raw_papers[:MAX_NBER_RECENT_PAPERS]
        result["total_recent_considered"] = len(recent)

        if recent:
            latest_date = date_string_from_tuple(recent[0].get("date_tuple", (0, 0, 0)))
            if latest_date:
                result["issue_title"] = f"Recent NBER Working Papers through {latest_date}"

        picked: List[Dict[str, Any]] = []
        for paper in recent:
            title_en = normalize_text(paper.get("title_en"))
            abstract_en = normalize_text(paper.get("abstract_en"))
            if not title_en:
                continue

            matched_topics = detect_topics(title_en, abstract_en)
            if not matched_topics:
                continue

            title_zh, abstract_zh = translate_paper_fields(title_en, abstract_en, translator)
            paper_id = paper["paper_id"]
            doi = normalize_text(paper.get("doi"))
            url = nber_paper_url(paper_id)
            if doi and doi.startswith("10."):
                url = f"https://doi.org/{doi}"

            picked.append(
                {
                    "title_en": title_en,
                    "title_zh": title_zh,
                    "url": url,
                    "authors": format_nber_authors(paper.get("authors", [])),
                    "date": date_string_from_tuple(paper.get("date_tuple", (0, 0, 0))) or paper.get("date_raw", ""),
                    "abstract_en": abstract_en,
                    "abstract_zh": abstract_zh,
                    "matched_topics": matched_topics,
                    "paper_id": paper_id,
                    "programs": paper.get("programs", []),
                }
            )

            if len(picked) >= MAX_PAPERS_PER_SOURCE:
                break

        result["papers"] = picked
        result["matched_count"] = len(picked)

    except Exception as exc:
        result["error"] = str(exc)

    return result


def build_tracker_block(translator: KimiTranslator) -> Dict[str, Any]:
    journals = JOURNALS[:MAX_TRACKED_JOURNALS] if MAX_TRACKED_JOURNALS > 0 else JOURNALS
    journal_blocks = [build_journal_block(journal, translator) for journal in journals]
    nber_block = build_nber_block(translator)
    sources = journal_blocks + [nber_block]
    total_matches = sum(len(source.get("papers", [])) for source in sources)

    return {
        "name": "经济学产业政策前沿追踪",
        "topics": list(TOPIC_KEYWORDS.keys()),
        "topic_keywords": TOPIC_KEYWORDS,
        "max_papers_per_source": MAX_PAPERS_PER_SOURCE,
        "nber_recent_papers_considered": MAX_NBER_RECENT_PAPERS,
        "sources": sources,
        "journals": journal_blocks,
        "nber": nber_block,
        "total_matches": total_matches,
        "note": (
            "Latest issue TOCs from economics top journals and field-top journals plus recent "
            "NBER Working Papers, filtered by title/abstract keywords for industrial policy, "
            "innovation, green development, and artificial intelligence."
        ),
    }


def load_previous_data() -> Dict[str, Any]:
    if not OUTPUT.exists():
        return {}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    previous = load_previous_data()
    translator = KimiTranslator(api_key=KIMI_API_KEY, model=KIMI_MODEL)
    translator.warmup_cache(previous)
    tracker = build_tracker_block(translator)

    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "schema_version": 1,
        "translation": {
            "engine": "kimi",
            "model": KIMI_MODEL,
            "enabled": translator.enabled,
            "success_count": translator.success_count,
            "fail_count": translator.fail_count,
            "failed_examples": translator.fail_samples,
            "note": "Set KIMI_API_KEY to enable Chinese translation.",
        },
        TRACKER_KEY: tracker,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {OUTPUT}")
    print(
        "Translation stats: "
        f"enabled={translator.enabled}, success={translator.success_count}, fail={translator.fail_count}"
    )
    print(
        "Sources tracked: "
        f"{len(tracker.get('sources', []))}, total matched papers={tracker.get('total_matches', 0)}"
    )


if __name__ == "__main__":
    main()
