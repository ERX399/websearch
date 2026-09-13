import asyncio
import html
import re
import time
import urllib.parse

import aiohttp

from .textutil import UA, clean_text, strip_tracking, url_key

COOLDOWN_SECONDS = 300
STUB_BYTES = 12000

ENGINE_ALIASES = {
    "bing": "bing",
    "cn.bing": "bing",
    "必应": "bing",
    "bing_rss": "bing_rss",
    "rss": "bing_rss",
}

BLOCKED_UNTIL = {}

BING_URL = "https://www.bing.com/search?"

BING_LI_RE = re.compile(r'<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', re.S)
BING_H2_RE = re.compile(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
BING_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
BING_AD_MARK_RE = re.compile(
    r'b_adlabel|class="[^"]*\bb_ad\b|data-ad[a-z-]*=|>\s*广告\s*<|>\s*Sponsored\s*<',
    re.I,
)
BING_AD_PATH_RE = re.compile(r"/aclick|/ads?\b", re.I)

RSS_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
RSS_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
RSS_LINK_RE = re.compile(r"<link>(.*?)</link>", re.S)
RSS_DESC_RE = re.compile(r"<description>(.*?)</description>", re.S)
RSS_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.S)
RSS_CN_DATE_RE = re.compile(r"(\d{1,2})\s*(\d{1,2})\s*月\s*(\d{4})")
RSS_EN_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})")
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

TIME_FILTERS = {"day": "ez1", "week": "ez2", "month": "ez3", "year": "ez4"}


def _headers(user_agent, market="zh-CN"):
    return {
        "User-Agent": user_agent or UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": f"{market},zh;q=0.9,en;q=0.8",
    }


def resolve_engine(name):
    key = str(name or "").strip().lower()
    return ENGINE_ALIASES.get(key, key if key in KNOWN_ENGINES else "")


def cooling(engine):
    return BLOCKED_UNTIL.get(engine, 0) > time.time()


def _cool(engine):
    BLOCKED_UNTIL[engine] = time.time() + COOLDOWN_SECONDS


def _stub_page(results, ads, page):
    return not results and not ads and len(page or "") < STUB_BYTES


STUB_ERROR = "被拦截或该查询无结果，已冷却"


async def _get(session, engine, url, user_agent, timeout, proxy, market):
    try:
        async with session.get(
            url,
            headers=_headers(user_agent, market),
            timeout=aiohttp.ClientTimeout(total=timeout),
            proxy=proxy,
            allow_redirects=True,
        ) as resp:
            if resp.status in (202, 403, 429):
                _cool(engine)
                return None, f"被限流({resp.status})"
            if resp.status != 200:
                return None, f"HTTP {resp.status}"
            return await resp.text(errors="ignore"), ""
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _item(engine, rank, title, url, snippet, date=""):
    url = strip_tracking(html.unescape(url or ""))
    return {
        "title": clean_text(title) or url,
        "url": url,
        "snippet": clean_text(snippet),
        "date": date,
        "key": url_key(url),
        "engines": [engine],
        "ranks": {engine: rank},
    }


def _rss_date(raw):
    text = clean_text(raw)
    hit = RSS_CN_DATE_RE.search(text)
    if hit:
        return f"{hit.group(3)} 年 {hit.group(2)} 月 {hit.group(1)} 日"
    hit = RSS_EN_DATE_RE.search(text)
    if hit:
        month = MONTHS.get(hit.group(2).lower())
        if month:
            return f"{hit.group(3)} 年 {month} 月 {hit.group(1)} 日"
    return ""


def parse_bing_rss(page):
    results = []
    rank = 0
    for block in RSS_ITEM_RE.findall(page or ""):
        lm = RSS_LINK_RE.search(block)
        if not lm:
            continue
        url = lm.group(1).strip()
        if not url.startswith("http"):
            continue
        tm = RSS_TITLE_RE.search(block)
        dm = RSS_DESC_RE.search(block)
        pm = RSS_DATE_RE.search(block)
        rank += 1
        results.append(
            _item(
                "bing_rss",
                rank,
                tm.group(1) if tm else "",
                url,
                dm.group(1) if dm else "",
                _rss_date(pm.group(1) if pm else ""),
            )
        )
    return results


def _is_bing_ad(url, block):
    if BING_AD_MARK_RE.search(block or ""):
        return True
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    if host == "go.microsoft.com" or host.endswith(".go.microsoft.com"):
        return True
    if (host == "bing.com" or host.endswith(".bing.com")) and BING_AD_PATH_RE.search(
        url
    ):
        return True
    return False


def parse_bing(page, filter_ads=True):
    results = []
    ads = 0
    rank = 0
    for block in BING_LI_RE.findall(page):
        hit = BING_H2_RE.search(block)
        if not hit:
            continue
        url = hit.group(1)
        if _is_bing_ad(url, block) and filter_ads:
            ads += 1
            continue
        snippet = ""
        sm = BING_P_RE.search(block)
        if sm:
            snippet = sm.group(1)
        rank += 1
        results.append(_item("bing", rank, hit.group(2), url, snippet))
    if not results and not ads:
        rank = 0
        for hit in BING_H2_RE.finditer(page):
            url = hit.group(1)
            if not url.startswith("http"):
                continue
            rank += 1
            results.append(_item("bing", rank, hit.group(2), url, ""))
    return results, ads


async def search_engine(
    session,
    engine,
    query,
    count,
    user_agent,
    timeout,
    proxy,
    market,
    time_range="",
    filter_ads=True,
):
    tr = (time_range or "").strip().lower()
    if cooling(engine):
        return {
            "engine": engine,
            "ok": False,
            "error": "冷却中",
            "results": [],
            "ads": 0,
        }
    if engine == "bing_rss":
        params = {
            "q": query,
            "format": "rss",
            "count": str(count + 6),
            "mkt": market,
        }
        url = BING_URL + urllib.parse.urlencode(params)
        page, err = await _get(session, engine, url, user_agent, timeout, proxy, market)
        if err:
            return {
                "engine": engine,
                "ok": False,
                "error": err,
                "results": [],
                "ads": 0,
            }
        results = parse_bing_rss(page)
        if _stub_page(results, 0, page):
            _cool(engine)
            return {
                "engine": engine,
                "ok": False,
                "error": STUB_ERROR,
                "results": [],
                "ads": 0,
            }
        return {
            "engine": engine,
            "ok": True,
            "error": "",
            "results": results[:count],
            "ads": 0,
        }
    if engine == "bing":
        params = {
            "q": query,
            "count": str(count + 6),
            "mkt": market,
            "setlang": "zh-hans" if market.startswith("zh") else "en",
        }
        flt = TIME_FILTERS.get(tr)
        if flt:
            params["filters"] = f'ex1:"{flt}"'
        url = BING_URL + urllib.parse.urlencode(params)
        page, err = await _get(session, engine, url, user_agent, timeout, proxy, market)
        if err:
            return {
                "engine": engine,
                "ok": False,
                "error": err,
                "results": [],
                "ads": 0,
            }
        results, ads = parse_bing(page, filter_ads)
        if _stub_page(results, ads, page):
            _cool(engine)
            return {
                "engine": engine,
                "ok": False,
                "error": STUB_ERROR,
                "results": [],
                "ads": 0,
            }
        return {
            "engine": engine,
            "ok": True,
            "error": "",
            "results": results[:count],
            "ads": ads,
        }
    return {"engine": engine, "ok": False, "error": "未知引擎", "results": [], "ads": 0}


KNOWN_ENGINES = ("bing_rss", "bing")


async def search_many(
    engines,
    query,
    count=8,
    user_agent="",
    timeout=15,
    proxy=None,
    market="zh-CN",
    time_range="",
    filter_ads=True,
):
    names = []
    for item in engines or []:
        name = resolve_engine(item)
        if name and name not in names:
            names.append(name)
    if not names:
        names = ["bing"]
    async with aiohttp.ClientSession() as session:
        tasks = [
            search_engine(
                session,
                name,
                query,
                count,
                user_agent,
                timeout,
                proxy,
                market,
                time_range,
                filter_ads,
            )
            for name in names
        ]
        done = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for name, res in zip(names, done):
        if isinstance(res, Exception):
            out.append(
                {
                    "engine": name,
                    "ok": False,
                    "error": str(res),
                    "results": [],
                    "ads": 0,
                }
            )
        else:
            out.append(res)
    return out
