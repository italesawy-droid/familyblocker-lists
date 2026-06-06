#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]

FINAL_FILE = ROOT / "blocked_titles.txt"
MANUAL_FILE = ROOT / "blocked_titles_manual.txt"
AUTO_FILE = ROOT / "blocked_titles_auto.txt"
BY_GENRE_FILE = ROOT / "blocked_titles_by_genre.txt"
SOURCES_FILE = ROOT / "blocked_titles_sources.tsv"
GENRE_LOG_FILE = ROOT / "blocked_titles_auto_genres.txt"
ALLOWLIST_FILE = ROOT / "blocked_titles_allowlist.txt"
GENRES_ENABLED_FILE = ROOT / "blocked_genres_enabled.txt"
GENRES_DISABLED_FILE = ROOT / "blocked_genres_disabled.txt"

DEFAULT_GENRES: List[Tuple[str, str]] = [
    ("Q185529", "pornographic film"),
    ("Q599558", "erotic film"),
    ("Q2275499", "sex film"),
    ("Q2292320", "sexploitation film"),
    ("Q2991560", "sex comedy"),
    ("Q2991565", "commedia sexy all'italiana"),
    ("Q1194365", "pink film / pinku eiga"),
    ("Q4047254", "Pornochanchada"),
    ("Q5769572", "Mexican sex comedy"),
    ("Q120205248", "Comedia picaresca"),
    ("Q16254232", "pornographic parody film"),
    ("Q128145358", "gay pornographic film"),
    ("Q125719481", "lesbian pornographic film"),
    ("Q114051112", "POV pornographic film"),
    ("Q48743992", "gay pornographic video"),
]

# Dynamic discovery expands coverage, but still avoids generic comedy/drama/romance.
SEXUAL_GENRE_LABEL_REGEX = (
    r"(^|[^a-z])("
    r"erotic|"
    r"erotica|"
    r"sex|"
    r"sexy|"
    r"sexploitation|"
    r"porn|"
    r"pornographic|"
    r"pornography|"
    r"softcore|"
    r"soft-core|"
    r"hardcore|"
    r"hard-core|"
    r"nudist|"
    r"nudie|"
    r"pinku"
    r")([^a-z]|$)"
)

EXCLUDED_GENRE_LABEL_REGEX = (
    r"sex education|"
    r"sexual education|"
    r"sexual orientation|"
    r"gender|"
    r"romantic comedy|"
    r"romance film|"
    r"comedy film$|"
    r"drama film$"
)

REQUIRE_YEAR_FOR = {
    "love",
    "after",
    "q",
    "crash",
    "bound",
    "shame",
    "secretary",
    "romance",
    "desire",
    "damage",
    "adore",
    "chloe",
    "the lover",
    "the key",
    "intimacy",
    "paprika",
    "miranda",
    "monamour",
    "seduction",
    "obsession",
    "malizia",
    "malicious",
}

AUTO_SKIP_EXACT = {
    "",
    "sex",
    "love",
    "after",
    "q",
    "romance",
    "adult",
    "erotic",
    "comedy",
    "drama",
}


def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = value.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"[\s\-_–—:;,.!?()\[\]{}'\"/\\|]+", " ", value)
    return value.strip()


def clean_value(value: str) -> str:
    value = (value or "").strip()
    value = value.replace("\u00a0", " ")
    value = value.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"\s+", " ", value).strip()
    return value


def read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def write_lines(path: Path, header: Iterable[str], lines: Iterable[str]) -> None:
    unique: List[str] = []
    seen = set()

    for line in lines:
        line = clean_value(line)
        key = normalize_key(line)
        if not line or key in seen:
            continue
        seen.add(key)
        unique.append(line)

    text = "\n".join([*header, *unique]).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def parse_qid_line(line: str) -> Tuple[str, str] | None:
    line = line.strip()
    match = re.match(r"^(Q\d+)(?:\s*[-–—]\s*(.+))?$", line)
    if not match:
        return None
    return match.group(1), clean_value(match.group(2) or match.group(1))


def ensure_file(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def ensure_base_files() -> None:
    ensure_file(
        GENRES_ENABLED_FILE,
        "# FamilyBlocker blocked_genres_enabled.txt\n"
        "# QCODE - genre name\n"
        "# All strict genres enabled by default.\n\n"
        + "\n".join(f"{qid} - {name}" for qid, name in DEFAULT_GENRES)
        + "\n",
    )

    ensure_file(
        GENRES_DISABLED_FILE,
        "# FamilyBlocker blocked_genres_disabled.txt\n"
        "# Add QCODEs here to disable whole automatic genres.\n\n",
    )

    ensure_file(
        ALLOWLIST_FILE,
        "# FamilyBlocker blocked_titles_allowlist.txt\n"
        "# Exact titles to exclude from automatic titles only.\n\n"
        "Love\nAfter\nQ\nCrash\nBound\nShame\nSecretary\nRomance\nDesire\nDamage\nAdore\nChloe\n"
        "The Key\nThe Lover\nIntimacy\nPaprika\nMiranda\nMonamour\nSeduction\nObsession\nComedy\nDrama\n",
    )

    if not MANUAL_FILE.exists():
        current = read_lines(FINAL_FILE)
        write_lines(
            MANUAL_FILE,
            [
                "# FamilyBlocker blocked_titles_manual.txt",
                "# Manual titles you trust. One title per line.",
                "",
            ],
            current,
        )


def read_enabled_genres() -> List[Tuple[str, str]]:
    ensure_base_files()
    output: List[Tuple[str, str]] = []
    seen: Set[str] = set()

    for line in read_lines(GENRES_ENABLED_FILE):
        parsed = parse_qid_line(line)
        if not parsed:
            continue
        qid, label = parsed
        if qid not in seen:
            seen.add(qid)
            output.append((qid, label))

    # If the file was accidentally emptied, fall back to default strict list.
    if not output:
        output = DEFAULT_GENRES[:]

    return output


def read_disabled_genres() -> Set[str]:
    disabled: Set[str] = set()
    for line in read_lines(GENRES_DISABLED_FILE):
        parsed = parse_qid_line(line)
        if parsed:
            disabled.add(parsed[0])
    return disabled


def sparql_request(query: str, timeout: int = 60) -> Dict:
    endpoint = "https://query.wikidata.org/sparql"
    url = endpoint + "?" + urllib.parse.urlencode({"query": query, "format": "json"})

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "FamilyBlocker-GitHubAction/3.0 (https://github.com/italesawy-droid/familyblocker-lists)",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_additional_genres(seed_genres: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seed_values = " ".join(f"wd:{qid}" for qid, _ in seed_genres)

    query = f"""
SELECT DISTINCT ?genre ?genreLabel WHERE {{
  {{
    VALUES ?seed {{ {seed_values} }}
    ?genre wdt:P279* ?seed.
  }}
  UNION
  {{
    ?genre wdt:P31/wdt:P279* wd:Q201658.
    ?genre rdfs:label ?genreLabel.
    FILTER(LANG(?genreLabel) = "en")
    FILTER(REGEX(LCASE(STR(?genreLabel)), "{SEXUAL_GENRE_LABEL_REGEX}"))
    FILTER(!REGEX(LCASE(STR(?genreLabel)), "{EXCLUDED_GENRE_LABEL_REGEX}"))
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
ORDER BY ?genreLabel
LIMIT 1000
"""

    payload = sparql_request(query)
    output: List[Tuple[str, str]] = []
    seen: Set[str] = set()

    for item in payload.get("results", {}).get("bindings", []):
        uri = item.get("genre", {}).get("value", "")
        label = item.get("genreLabel", {}).get("value", "")
        qid = uri.rsplit("/", 1)[-1].strip()

        if not qid.startswith("Q"):
            continue

        label_key = normalize_key(label)
        if re.search(EXCLUDED_GENRE_LABEL_REGEX, label_key):
            continue

        if qid not in seen:
            seen.add(qid)
            output.append((qid, label or qid))

    return output


def merge_genres(enabled: List[Tuple[str, str]], discovered: List[Tuple[str, str]], disabled: Set[str]) -> List[Tuple[str, str]]:
    output: List[Tuple[str, str]] = []
    seen: Set[str] = set()

    for qid, label in [*enabled, *discovered]:
        if qid in disabled:
            continue
        if qid not in seen:
            seen.add(qid)
            output.append((qid, label))

    return output


def chunked(values: List[Tuple[str, str]], size: int) -> Iterable[List[Tuple[str, str]]]:
    for idx in range(0, len(values), size):
        yield values[idx: idx + size]


def fetch_titles_for_genre_chunk(genres: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    values = " ".join(f"wd:{qid}" for qid, _ in genres)

    query = f"""
SELECT DISTINCT ?film ?filmLabel ?date ?genre ?genreLabel WHERE {{
  VALUES ?genre {{ {values} }}
  ?film wdt:P31/wdt:P279* wd:Q11424.
  ?film wdt:P136 ?genre.
  OPTIONAL {{ ?film wdt:P577 ?date. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
ORDER BY ?genreLabel ?filmLabel
LIMIT 10000
"""

    payload = sparql_request(query)
    rows: List[Dict[str, str]] = []

    for item in payload.get("results", {}).get("bindings", []):
        label = item.get("filmLabel", {}).get("value", "")
        date = item.get("date", {}).get("value", "")
        genre_uri = item.get("genre", {}).get("value", "")
        genre_label = item.get("genreLabel", {}).get("value", "")
        genre_qid = genre_uri.rsplit("/", 1)[-1].strip()
        year = ""
        match = re.match(r"^(\d{4})", date)
        if match:
            year = match.group(1)
        rows.append(
            {
                "title": label,
                "year": year,
                "genre_qid": genre_qid,
                "genre_label": genre_label,
            }
        )

    return rows


def should_require_year(title: str) -> bool:
    key = normalize_key(title)
    if key in REQUIRE_YEAR_FOR:
        return True
    if len(title) <= 5:
        return True
    return False


def candidate_title(raw_title: str, year: str) -> str | None:
    title = clean_value(raw_title)
    year = (year or "").strip()

    if not title:
        return None

    key = normalize_key(title)
    if key in AUTO_SKIP_EXACT:
        return None

    if key.startswith("q") and key[1:].isdigit():
        return None

    if should_require_year(title):
        if year:
            return f"{title} {year}"
        return None

    return title


def build_auto_data(genres: List[Tuple[str, str]]) -> Tuple[List[str], Dict[str, List[str]], Dict[str, Set[Tuple[str, str]]]]:
    rows: List[Dict[str, str]] = []
    for group in chunked(genres, 40):
        rows.extend(fetch_titles_for_genre_chunk(group))
        time.sleep(0.25)

    titles_by_genre: Dict[str, List[str]] = defaultdict(list)
    source_map: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
    all_titles: List[str] = []

    genre_labels = {qid: label for qid, label in genres}

    for row in rows:
        title = candidate_title(row.get("title", ""), row.get("year", ""))
        if not title:
            continue

        qid = row.get("genre_qid", "")
        label = clean_value(row.get("genre_label", "")) or genre_labels.get(qid, qid)

        titles_by_genre[qid].append(title)
        source_map[title].add((qid, label))
        all_titles.append(title)

    all_titles = sorted(set(all_titles), key=lambda x: normalize_key(x))

    for qid in list(titles_by_genre.keys()):
        titles_by_genre[qid] = sorted(set(titles_by_genre[qid]), key=lambda x: normalize_key(x))

    return all_titles, titles_by_genre, source_map


def merge_final(manual: List[str], auto: List[str], allowlist: List[str]) -> List[str]:
    allow_keys = {normalize_key(x) for x in allowlist}
    final: List[str] = []
    seen = set()

    for item in manual:
        key = normalize_key(item)
        if key and key not in seen:
            seen.add(key)
            final.append(item)

    for item in auto:
        key = normalize_key(item)
        if key and key not in seen and key not in allow_keys:
            seen.add(key)
            final.append(item)

    return final


def write_by_genre(genres: List[Tuple[str, str]], titles_by_genre: Dict[str, List[str]], now: str) -> None:
    lines: List[str] = [
        "# FamilyBlocker blocked_titles_by_genre.txt",
        "# Auto-generated grouped review file.",
        f"# Updated: {now}",
        "# To disable a whole genre, add its QCODE to blocked_genres_disabled.txt.",
        "# Do not edit this file manually.",
        "",
    ]

    total = 0
    for qid, label in genres:
        titles = titles_by_genre.get(qid, [])
        if not titles:
            continue
        total += len(titles)
        lines.append(f"# {qid} - {label}")
        lines.extend(titles)
        lines.append("")

    lines.append(f"# Total grouped rows: {total}")
    BY_GENRE_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_sources(source_map: Dict[str, Set[Tuple[str, str]]]) -> None:
    rows = ["Title\tGenreCodes\tGenreNames"]
    for title in sorted(source_map.keys(), key=lambda x: normalize_key(x)):
        sources = sorted(source_map[title], key=lambda x: x[0])
        codes = ", ".join(qid for qid, _ in sources)
        names = ", ".join(label for _, label in sources)
        safe_title = title.replace("\t", " ")
        rows.append(f"{safe_title}\t{codes}\t{names}")
    SOURCES_FILE.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    ensure_base_files()

    disabled = read_disabled_genres()
    enabled = read_enabled_genres()

    try:
        discovered = discover_additional_genres(enabled)
        genres = merge_genres(enabled, discovered, disabled)
        auto_titles, titles_by_genre, source_map = build_auto_data(genres)
    except Exception as exc:
        print(f"ERROR: Could not update automatic titles: {exc}", file=sys.stderr)
        print("Keeping existing blocked_titles.txt unchanged.", file=sys.stderr)
        return 1

    manual = read_lines(MANUAL_FILE)
    allowlist = read_lines(ALLOWLIST_FILE)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    write_lines(
        GENRE_LOG_FILE,
        [
            "# FamilyBlocker blocked_titles_auto_genres.txt",
            "# Genres used by scripts/update_titles.py.",
            f"# Updated: {now}",
            "# Disabled genres are not included here.",
            "",
        ],
        [f"{qid} - {label}" for qid, label in genres],
    )

    write_by_genre(genres, titles_by_genre, now)
    write_sources(source_map)

    write_lines(
        AUTO_FILE,
        [
            "# FamilyBlocker blocked_titles_auto.txt",
            "# Auto-generated flat automatic titles.",
            f"# Updated: {now}",
            "# Do not edit manually. Use blocked_titles_manual.txt, blocked_titles_allowlist.txt, or blocked_genres_disabled.txt.",
            "",
        ],
        auto_titles,
    )

    final = merge_final(manual, auto_titles, allowlist)

    write_lines(
        FINAL_FILE,
        [
            "# FamilyBlocker blocked_titles.txt",
            "# Final flat list used by the browser extension.",
            f"# Updated: {now}",
            "# Built from:",
            "# - blocked_titles_manual.txt",
            "# - blocked_titles_auto.txt",
            "# - blocked_titles_allowlist.txt applies to automatic titles only",
            "",
        ],
        final,
    )

    print(f"Enabled base genres: {len(enabled)}")
    print(f"Disabled genres: {len(disabled)}")
    print(f"Total active genres after discovery: {len(genres)}")
    print(f"Manual titles: {len(manual)}")
    print(f"Auto titles: {len(auto_titles)}")
    print(f"Allowlist titles: {len(allowlist)}")
    print(f"Final titles: {len(final)}")
    print(f"Grouped review file: {BY_GENRE_FILE.name}")
    print(f"Sources TSV file: {SOURCES_FILE.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
