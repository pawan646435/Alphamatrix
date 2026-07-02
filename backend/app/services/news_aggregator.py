"""
AlphaMatrix — Multi-Source Financial News Aggregator
======================================================
Aggregates financial news from multiple public RSS feeds.
Deduplicates stories, scores sources by credibility, and
classifies events (positive/negative/neutral).

Legal: All sources use publicly available RSS feeds.
No scraping. No paywalled content.
"""

import asyncio
import hashlib
import logging
import re
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("app.services.news_aggregator")

# ─────────────────────────────────────────────────────────────
# SOURCE REGISTRY
# ─────────────────────────────────────────────────────────────
INDIA_SOURCES = [
    {
        "name": "Economic Times Markets",
        "short": "ET Markets",
        "url": "https://economictimes.indiatimes.com/markets/rss.cms",
        "credibility": 0.82,
        "country": "IN",
    },
    {
        "name": "Moneycontrol",
        "short": "Moneycontrol",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml",
        "credibility": 0.80,
        "country": "IN",
    },
    {
        "name": "Business Standard Markets",
        "short": "Business Standard",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
        "credibility": 0.80,
        "country": "IN",
    },
    {
        "name": "Livemint",
        "short": "Livemint",
        "url": "https://www.livemint.com/rss/markets",
        "credibility": 0.78,
        "country": "IN",
    },
]

GLOBAL_SOURCES = [
    {
        "name": "Reuters Business",
        "short": "Reuters",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "credibility": 0.95,
        "country": "GLOBAL",
    },
    {
        "name": "CNBC Finance",
        "short": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "credibility": 0.85,
        "country": "GLOBAL",
    },
    {
        "name": "Yahoo Finance",
        "short": "Yahoo Finance",
        "url": "https://finance.yahoo.com/rss/topfinstories",
        "credibility": 0.70,
        "country": "GLOBAL",
    },
]

# ─────────────────────────────────────────────────────────────
# EVENT CLASSIFICATION
# ─────────────────────────────────────────────────────────────
POSITIVE_EVENTS = {
    "order_win":             ["order win", "bags order", "wins contract", "secures order", "order book", "new order"],
    "capacity_expansion":    ["capacity expansion", "new plant", "greenfield", "capex", "expansion plan", "facility"],
    "regulatory_approval":   ["fda approval", "sebi approval", "regulatory nod", "approved by", "gets approval", "nod from"],
    "product_launch":        ["product launch", "launches new", "unveils", "introduces", "new product"],
    "earnings_beat":         ["beats estimate", "profit jumps", "revenue surges", "net profit rises", "quarterly beat",
                              "record profit", "strong results", "earnings surge", "outperforms"],
    "upgrade":               ["upgrade", "target raised", "raised target", "overweight", "buy rating"],
    "dividend":              ["dividend", "buyback", "bonus shares", "special dividend"],
    "foreign_investment":    ["fii buying", "fpi investment", "foreign inflow", "fdi"],
}

NEGATIVE_EVENTS = {
    "earnings_miss":         ["misses estimate", "profit falls", "revenue drops", "net loss", "quarterly miss",
                              "profit declines", "below estimate", "disappoints"],
    "promoter_selling":      ["promoter selling", "promoter stake sale", "insider selling", "founders sell"],
    "debt_concern":          ["debt burden", "default", "npa rises", "bad loans", "rating downgrade",
                              "high debt", "leveraged", "liquidity concern"],
    "investigation":         ["sebi probe", "cbi raid", "income tax", "ed probe", "investigated", "fraud",
                              "scam", "penalty imposed", "fine", "show cause"],
    "downgrade":             ["downgrade", "sell rating", "reduce rating", "target cut", "underperform"],
    "regulatory_penalty":    ["penalty", "banned", "suspended", "recall", "regulatory action"],
}

NEUTRAL_EVENTS = {
    "general_coverage":      ["market update", "weekly roundup", "outlook", "analysis", "forecast"],
    "corporate_action":      ["board meeting", "agm", "egm", "rights issue"],
    "macro":                 ["gdp", "inflation", "rbi policy", "repo rate", "budget", "trade data"],
}


def classify_event(title: str) -> Dict[str, str]:
    """
    Classifies a news title into event type, direction, and impact.
    Returns dict with: event_type, event_direction, impact_level
    """
    title_lower = title.lower()

    for event_type, keywords in POSITIVE_EVENTS.items():
        if any(kw in title_lower for kw in keywords):
            return {
                "event_type": event_type,
                "event_direction": "POSITIVE",
                "impact_level": "HIGH" if event_type in ("earnings_beat", "order_win", "regulatory_approval") else "MEDIUM",
            }

    for event_type, keywords in NEGATIVE_EVENTS.items():
        if any(kw in title_lower for kw in keywords):
            return {
                "event_type": event_type,
                "event_direction": "NEGATIVE",
                "impact_level": "HIGH" if event_type in ("earnings_miss", "investigation", "debt_concern") else "MEDIUM",
            }

    for event_type, keywords in NEUTRAL_EVENTS.items():
        if any(kw in title_lower for kw in keywords):
            return {
                "event_type": event_type,
                "event_direction": "NEUTRAL",
                "impact_level": "LOW",
            }

    # Fallback impact from keywords
    high_words = ["rbi", "fed", "interest rate", "budget", "gdp", "inflation", "crash", "policy", "sebi", "tariffs"]
    med_words  = ["earnings", "results", "quarterly", "ipo", "profit", "launch", "nifty", "sensex"]
    if any(w in title_lower for w in high_words):
        return {"event_type": "macro", "event_direction": "NEUTRAL", "impact_level": "HIGH"}
    if any(w in title_lower for w in med_words):
        return {"event_type": "general_coverage", "event_direction": "NEUTRAL", "impact_level": "MEDIUM"}

    return {"event_type": "general_coverage", "event_direction": "NEUTRAL", "impact_level": "LOW"}


# ─────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────
def _title_fingerprint(title: str) -> str:
    """Creates a normalized fingerprint for deduplication."""
    # Remove punctuation, lowercase, strip common stop words
    clean = re.sub(r"[^\w\s]", "", title.lower())
    tokens = [t for t in clean.split() if len(t) > 3]
    return " ".join(sorted(tokens[:12]))  # order-independent bag of key words


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two token sets."""
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def deduplicate_articles(articles: List[Dict[str, Any]], threshold: float = 0.65) -> List[Dict[str, Any]]:
    """
    Merges near-duplicate news articles.
    For clusters, keeps the highest-credibility source and adds source_count.
    """
    deduplicated: List[Dict[str, Any]] = []
    fingerprints: List[str] = []

    for article in articles:
        fp = _title_fingerprint(article["title"])
        merged = False
        for i, existing_fp in enumerate(fingerprints):
            if _jaccard_similarity(fp, existing_fp) >= threshold:
                # Merge into existing: prefer higher credibility source
                existing = deduplicated[i]
                existing["source_count"] = existing.get("source_count", 1) + 1
                existing["additional_sources"] = existing.get("additional_sources", [])
                existing["additional_sources"].append(article["publisher"])
                if article.get("credibility_score", 0) > existing.get("credibility_score", 0):
                    # Upgrade to higher-credibility source
                    existing["title"]             = article["title"]
                    existing["link"]              = article["link"]
                    existing["publisher"]         = article["publisher"]
                    existing["source_short"]      = article.get("source_short", article["publisher"])
                    existing["credibility_score"] = article.get("credibility_score", 0.5)
                merged = True
                break
        if not merged:
            article["source_count"] = 1
            article["additional_sources"] = []
            deduplicated.append(article)
            fingerprints.append(fp)

    return deduplicated


# ─────────────────────────────────────────────────────────────
# RSS PARSER
# ─────────────────────────────────────────────────────────────
def _parse_rss_xml(xml_text: str, source_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parses RSS XML and extracts articles."""
    articles = []
    try:
        # Extract all <item> blocks
        items = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
        for item in items[:30]:  # cap per-source at 30
            def get_tag(tag):
                m = re.search(rf"<{tag}[^>]*><!\[CDATA\[(.*?)\]\]></{tag}>", item, re.DOTALL)
                if m:
                    return m.group(1).strip()
                m2 = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", item, re.DOTALL)
                return m2.group(1).strip() if m2 else ""

            title = get_tag("title")
            link  = get_tag("link") or get_tag("guid")
            pub_date_str = get_tag("pubDate") or get_tag("dc:date")

            if not title or len(title) < 10:
                continue

            # Parse timestamp
            timestamp = None
            if pub_date_str:
                for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        dt = datetime.strptime(pub_date_str.strip(), fmt)
                        timestamp = int(dt.timestamp())
                        break
                    except Exception:
                        continue

            event_info = classify_event(title)

            articles.append({
                "title":            title,
                "publisher":        source_meta["name"],
                "source_short":     source_meta["short"],
                "link":             link,
                "credibility_score": source_meta["credibility"],
                "timestamp":        timestamp or int(time.time()) - 3600,
                **event_info,
            })
    except Exception as e:
        logger.error(f"RSS parse error for {source_meta['name']}: {e}")
    return articles


# ─────────────────────────────────────────────────────────────
# MAIN FETCH FUNCTION
# ─────────────────────────────────────────────────────────────
async def _fetch_source(
    client: httpx.AsyncClient,
    source: Dict[str, Any],
    timeout: float = 4.0
) -> List[Dict[str, Any]]:
    """Fetches and parses one RSS source. Returns empty list on any failure."""
    try:
        resp = await client.get(
            source["url"],
            timeout=timeout,
            headers={"User-Agent": "AlphaMatrix/2.0 (institutional research; +https://alphamatrix.in)"},
            follow_redirects=True
        )
        if resp.status_code == 200:
            articles = _parse_rss_xml(resp.text, source)
            logger.info(f"Fetched {len(articles)} articles from {source['name']}")
            return articles
        else:
            logger.warning(f"HTTP {resp.status_code} from {source['name']}")
    except Exception as e:
        logger.warning(f"Failed to fetch {source['name']}: {e}")
    return []


async def fetch_india_news(category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches Indian financial news from all India sources concurrently.
    Deduplicates and returns sorted by timestamp descending.
    """
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_source(client, source) for source in INDIA_SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)

    # Sort by timestamp descending before dedup (so we keep newest per cluster)
    all_articles.sort(key=lambda a: a.get("timestamp", 0), reverse=True)
    deduped = deduplicate_articles(all_articles)

    if category_filter and category_filter != "all":
        deduped = _filter_by_category(deduped, category_filter)

    logger.info(f"India news: {len(all_articles)} raw → {len(deduped)} after dedup")
    return deduped[:80]


async def fetch_global_news(category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches global financial news from Reuters, CNBC, Yahoo Finance.
    """
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_source(client, source) for source in GLOBAL_SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)

    all_articles.sort(key=lambda a: a.get("timestamp", 0), reverse=True)
    deduped = deduplicate_articles(all_articles)

    if category_filter and category_filter != "all":
        deduped = _filter_by_category(deduped, category_filter)

    logger.info(f"Global news: {len(all_articles)} raw → {len(deduped)} after dedup")
    return deduped[:60]


def _filter_by_category(articles: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Client-side category filter by keyword matching on title."""
    CATEGORY_KEYWORDS = {
        "stocks":       ["stock", "share", "nifty", "sensex", "equity", "ipo", "listed", "bse", "nse"],
        "mutual_funds": ["mutual fund", "fund", "nav", "sip", "aum", "scheme", "mf"],
        "economy":      ["gdp", "economy", "inflation", "fiscal", "trade", "export", "import", "growth"],
        "policy":       ["rbi", "sebi", "government", "policy", "budget", "fed", "rate", "regulatory", "finance minister"],
        "earnings":     ["profit", "earnings", "revenue", "quarterly", "result", "q1", "q2", "q3", "q4", "annual"],
    }
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if not keywords:
        return articles
    return [a for a in articles if any(kw in a["title"].lower() for kw in keywords)]
