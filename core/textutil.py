import html
import re
import time
import urllib.parse

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

TAG_RE = re.compile(r"<[^>]+>")
DROP_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
UTM_RE = re.compile(r"^utm_", re.I)
TRACK_KEYS = {"spm", "scm", "share_token", "share_source", "from_source"}
IP_HOST_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._+-]*")
CJK_RUN_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ가-힯]+")

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "you",
    "your",
    "www",
    "com",
    "http",
    "https",
    "html",
    "php",
    "index",
}

REL_CN_RE = re.compile(r"(\d+)\s*(分钟|小时|天|周|个月|年)\s*前")
REL_EN_RE = re.compile(r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", re.I)
ABS_CN_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
ABS_ISO_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")
ABS_EN_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})",
    re.I,
)

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

REL_UNITS = {
    "分钟": 60,
    "小时": 3600,
    "天": 86400,
    "周": 604800,
    "个月": 2592000,
    "年": 31536000,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
}


def clean_text(raw):
    if not raw:
        return ""
    text = TAG_RE.sub("", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def domain_of(url):
    if not url:
        return ""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    host = host.split(":")[0].strip(".")
    return host[4:] if host.startswith("www.") else host


def strip_tracking(url):
    try:
        parts = urllib.parse.urlsplit(url)
    except Exception:
        return url
    if not parts.query:
        return url
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    kept = [
        (k, v) for k, v in pairs if not UTM_RE.match(k) and k.lower() not in TRACK_KEYS
    ]
    if len(kept) == len(pairs):
        return url
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urllib.parse.urlencode(kept),
            parts.fragment,
        )
    )


def url_key(url):
    cleaned = strip_tracking(url)
    try:
        parts = urllib.parse.urlsplit(cleaned)
    except Exception:
        return url
    host = parts.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = parts.path.rstrip("/") or "/"
    if parts.query:
        return f"{host}{path}?{parts.query}"
    return f"{host}{path}"


def host_in(host, domains):
    if not host or not domains:
        return False
    for item in domains:
        item = str(item).strip().lower().lstrip(".")
        if not item:
            continue
        if host == item or host.endswith("." + item):
            return True
    return False


def tokenize(text):
    text = (text or "").lower()
    tokens = [w for w in WORD_RE.findall(text) if len(w) >= 2 and w not in STOPWORDS]
    for run in CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _mk(year, month, day):
    try:
        return time.mktime((int(year), int(month), int(day), 12, 0, 0, 0, 0, -1))
    except Exception:
        return None


def extract_date(text):
    if not text:
        return None
    now = time.time()
    hit = REL_CN_RE.search(text) or REL_EN_RE.search(text)
    if hit:
        unit = hit.group(2).lower()
        step = REL_UNITS.get(unit)
        if step:
            return now - int(hit.group(1)) * step
    hit = ABS_CN_RE.search(text) or ABS_ISO_RE.search(text)
    if hit:
        return _mk(hit.group(1), hit.group(2), hit.group(3))
    hit = ABS_EN_RE.search(text)
    if hit:
        return _mk(hit.group(3), MONTHS.get(hit.group(1)[:3].lower(), 1), hit.group(2))
    return None


def freshness(text):
    ts = extract_date(text)
    if not ts:
        return 0.0
    age_days = max(0.0, (time.time() - ts) / 86400.0)
    if age_days <= 1:
        return 1.0
    if age_days >= 730:
        return 0.0
    return max(0.0, 1.0 - (age_days / 730.0))


def relevance(query, title, snippet):
    qset = set(tokenize(query))
    if not qset:
        return 0.0
    tset = set(tokenize(title))
    sset = set(tokenize(snippet))
    hits = len(qset & tset) * 2 + len(qset & sset)
    return min(1.0, hits / (2.0 * len(qset)))


def similar(a, b):
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))
