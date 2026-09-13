import re

EMOJI_RE = re.compile("[\U0001f000-\U0001faff←-⇿⌀-➿⬀-⯿️‍]+")
LEAD_FILLERS = (
    "帮我查一下",
    "帮我搜一下",
    "帮我找一下",
    "帮我看看",
    "帮我查",
    "帮我搜",
    "帮我找",
    "麻烦你帮我",
    "麻烦你",
    "麻烦",
    "请问一下",
    "请问",
    "请帮我",
    "你能不能帮我",
    "你能不能",
    "你能",
    "能不能",
    "我想知道",
    "我想问一下",
    "我想问",
    "我想了解",
    "给我查一下",
    "给我搜一下",
    "给我查",
    "给我搜",
    "帮我",
    "给我",
    "查一下",
    "搜一下",
    "搜索一下",
    "找一下",
    "看一下",
    "告诉我",
    "你搜一下",
    "你查一下",
    "搜索",
    "百度一下",
    "google一下",
)
TAIL_PARTICLES = (
    "可以吗",
    "好吗",
    "行吗",
    "谢谢喵",
    "谢谢",
    "拜托",
    "喵",
    "啊",
    "呀",
    "吧",
    "呢",
    "吗",
    "嘛",
    "哦",
    "咯",
    "啦",
    "哇",
    "哈",
)
NOISE_RE = re.compile(r"[\"'`“”‘’「」『』【】\[\]{}<>~^*|\\]+")
SPACE_RE = re.compile(r"\s+")
ASCII_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9._+-]{1,}")
CJK_RE = re.compile(r"[㐀-䶿一-鿿]")


EDGE_STRIP = " ，,、:：?？!！"


def _cut_head(q):
    for filler in LEAD_FILLERS:
        if q.startswith(filler):
            rest = q[len(filler) :].strip(EDGE_STRIP)
            return rest if len(rest) >= 2 else q
    return q


def _cut_tail(q):
    for particle in TAIL_PARTICLES:
        if q.endswith(particle):
            rest = q[: -len(particle)].strip(EDGE_STRIP)
            return rest if len(rest) >= 2 else q
    return q


def _pure_noise(q):
    return not q or q in LEAD_FILLERS or q in TAIL_PARTICLES


def clean(query, max_len=90):
    q = EMOJI_RE.sub(" ", query or "")
    q = NOISE_RE.sub(" ", q)
    q = SPACE_RE.sub(" ", q).strip()
    changed = False
    for _ in range(4):
        cut = _cut_tail(_cut_head(q))
        if cut == q:
            break
        q = cut
        changed = True
    q = SPACE_RE.sub(" ", q).strip(EDGE_STRIP)
    if len(q) > max_len:
        q = q[:max_len].strip(EDGE_STRIP)
        changed = True
    if _pure_noise(q):
        return "", bool((query or "").strip())
    return q, changed


def variants(query):
    cleaned, _ = clean(query)
    if not cleaned:
        return []
    out = [cleaned]
    tokens = ASCII_TOKEN_RE.findall(cleaned)
    if tokens and CJK_RE.search(cleaned):
        ascii_only = " ".join(tokens)
        if ascii_only.lower() != cleaned.lower() and len(ascii_only) >= 3:
            out.append(ascii_only)
    return out


def optimize(query):
    cleaned, changed = clean(query)
    return {"query": cleaned, "variants": variants(query), "changed": changed}
