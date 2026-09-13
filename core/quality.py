import re

from .textutil import IP_HOST_RE, domain_of, freshness, host_in, relevance

SUSPICIOUS_TLDS = {
    "top",
    "xyz",
    "icu",
    "buzz",
    "click",
    "link",
    "online",
    "shop",
    "vip",
    "cc",
    "tk",
    "ml",
    "ga",
    "cf",
    "gq",
    "win",
    "bid",
    "loan",
    "work",
    "men",
    "live",
    "space",
    "website",
    "site",
    "store",
    "fun",
    "best",
    "bar",
    "rest",
    "cyou",
    "sbs",
    "monster",
    "quest",
    "lol",
    "club",
    "art",
    "pro",
    "wang",
    "ren",
    "xin",
    "asia",
    "moe",
    "kim",
    "ink",
    "wiki",
}

OFFICIAL = {
    "deepseek": ("deepseek.com",),
    "openai": ("openai.com", "chatgpt.com"),
    "chatgpt": ("openai.com", "chatgpt.com"),
    "gpt": ("openai.com", "chatgpt.com"),
    "claude": ("anthropic.com", "claude.ai", "claude.com"),
    "anthropic": ("anthropic.com", "claude.ai", "claude.com"),
    "gemini": ("google.com", "deepmind.google", "ai.google.dev"),
    "grok": ("x.ai",),
    "xai": ("x.ai",),
    "kimi": ("moonshot.cn", "kimi.com", "moonshot.ai"),
    "moonshot": ("moonshot.cn", "kimi.com", "moonshot.ai"),
    "qwen": ("qwen.ai", "tongyi.aliyun.com", "aliyun.com"),
    "tongyi": ("tongyi.aliyun.com", "aliyun.com"),
    "doubao": ("volcengine.com", "doubao.com"),
    "glm": ("zhipuai.cn", "bigmodel.cn"),
    "zhipu": ("zhipuai.cn", "bigmodel.cn"),
    "minimax": ("minimaxi.com", "minimax.io"),
    "llama": ("meta.com", "llama.com"),
    "mistral": ("mistral.ai",),
    "cursor": ("cursor.com", "cursor.sh", "cursor.so"),
    "midjourney": ("midjourney.com",),
    "perplexity": ("perplexity.ai",),
    "copilot": ("github.com", "microsoft.com"),
    "sora": ("openai.com",),
}

TRUST_DOMAINS = {
    "deepseek.com",
    "openai.com",
    "chatgpt.com",
    "anthropic.com",
    "claude.ai",
    "claude.com",
    "google.com",
    "deepmind.google",
    "ai.google.dev",
    "x.ai",
    "moonshot.cn",
    "kimi.com",
    "qwen.ai",
    "tongyi.aliyun.com",
    "aliyun.com",
    "volcengine.com",
    "zhipuai.cn",
    "bigmodel.cn",
    "minimaxi.com",
    "meta.com",
    "mistral.ai",
    "cursor.com",
    "midjourney.com",
    "perplexity.ai",
    "github.com",
    "gitee.com",
    "juejin.cn",
    "zhihu.com",
    "csdn.net",
    "cnblogs.com",
    "segmentfault.com",
    "oschina.net",
    "bilibili.com",
    "weibo.com",
    "smzdm.com",
    "tencent.com",
    "cloud.tencent.com",
    "huaweicloud.com",
    "microsoft.com",
    "apple.com",
    "nvidia.com",
    "amd.com",
    "intel.com",
    "wikipedia.org",
    "baike.baidu.com",
    "ithome.com",
    "36kr.com",
    "sspai.com",
    "stackoverflow.com",
    "python.org",
    "pypi.org",
    "npmjs.com",
    "arxiv.org",
    "nature.com",
    "sciencedirect.com",
    "medium.com",
    "reddit.com",
    "huggingface.co",
    "modelscope.cn",
    "openrouter.ai",
    "ollama.com",
    "lmstudio.ai",
    "docs.python.org",
    "readthedocs.io",
    "cloudflare.com",
    "docker.com",
    "ubuntu.com",
    "debian.org",
    "archlinux.org",
    "kernel.org",
    "52pojie.cn",
    "v2ex.com",
    "linux.do",
    "nodeseek.com",
    "hostloc.com",
    "developer.mozilla.org",
    "gov.cn",
    "xinhuanet.com",
    "people.com.cn",
    "thepaper.cn",
    "caixin.com",
    "sina.com.cn",
    "163.com",
    "sohu.com",
    "qq.com",
    "toutiao.com",
    "ifeng.com",
    "cnbeta.com",
    "solidot.org",
}

SPAM_STRONG = {
    "破解",
    "白嫖",
    "代充",
    "加群",
    "进群",
    "机场",
    "加速器",
    "翻墙",
    "vpn",
    "注册送",
    "免费领取",
    "点击进入",
    "立即注册",
    "返佣",
    "分销",
    "代理加盟",
    "私聊",
    "飞机号",
    "永久免费",
    "免费试用",
    "限时折扣",
    "一键下单",
    "包过",
    "内部渠道",
    "无门槛",
}

SPAM_WEAK = {
    "免费",
    "优惠",
    "折扣",
    "低价",
    "特价",
    "镜像",
    "中转",
    "直连",
    "国内可用",
    "官方入口",
    "限时",
    "福利",
    "充值",
    "包月",
    "节点",
    "加速",
    "不限量",
    "续费",
    "充值优惠",
    "新用户",
}

SEO_WORDS = (
    "指南",
    "攻略",
    "最新",
    "整理",
    "合集",
    "汇总",
    "一文",
    "详解",
    "盘点",
    "推荐",
    "排行榜",
    "保姆级",
    "看这篇",
    "就够了",
)

YEAR_RE = re.compile(r"20[2-9]\d")
SEARCH_PAGE_RE = re.compile(
    r"[/.](?:s|so|search|results?|web|w)\?[^#]*\b(?:q|wd|query|keyword|kw|word|text)=",
    re.I,
)

QUALITY_MIN = -100
QUALITY_MAX = 100

ENGINE_WEIGHT = {"bing_rss": 1.0, "bing": 0.85}

BRAND_SEPS = "-_."


def brand_hit(host, brand):
    for label in host.split("."):
        if label == brand:
            return True
        if label.startswith(brand):
            rest = label[len(brand) :]
            if rest and (rest[0] in BRAND_SEPS or (len(rest) <= 2 and rest.isalnum())):
                return True
        if label.endswith(brand):
            head = label[: -len(brand)]
            if head and head[-1] in BRAND_SEPS:
                return True
    return False


def judge(title, url, snippet):
    host = domain_of(url)
    if not host:
        return -80, ["无有效域名"]
    if IP_HOST_RE.match(host):
        return -60, ["直接 IP 站点"]
    if host_in(host, TRUST_DOMAINS):
        return 100, []
    score = 0
    flags = []
    for brand, officials in OFFICIAL.items():
        if host_in(host, officials):
            continue
        if brand_hit(host, brand):
            score -= 50
            flags.append("疑似山寨")
            break
    text = f"{title or ''} {snippet or ''}".lower()
    if any(word.lower() in text for word in SPAM_STRONG):
        score -= 30
        flags.append("推广话术")
    elif sum(1 for word in SPAM_WEAK if word.lower() in text) >= 2:
        score -= 20
        flags.append("推广话术")
    title_text = title or ""
    if YEAR_RE.search(title_text) and any(word in title_text for word in SEO_WORDS):
        score -= 25
        flags.append("内容农场")
    if SEARCH_PAGE_RE.search(url or ""):
        score -= 40
        flags.append("搜索结果页")
    if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS:
        score -= 15
        flags.append("可疑域名")
    return score, flags


def quality_of(title, url, snippet, trust_domains=()):
    host = domain_of(url)
    if host_in(host, trust_domains):
        return QUALITY_MAX, []
    return judge(title, url, snippet)


def rank(
    items,
    query,
    *,
    trust_domains=(),
    block_domains=(),
    level="normal",
    max_per_domain=2,
    rrf_k=60,
    dedupe_similar=True,
):
    from .textutil import similar

    merged = {}
    for item in items:
        url = item.get("url") or ""
        host = domain_of(url)
        key = item.get("key")
        bucket = merged.get(key)
        if bucket is None:
            merged[key] = {
                "title": item.get("title", ""),
                "url": strip_url(url),
                "snippet": item.get("snippet", ""),
                "date": item.get("date", ""),
                "host": host,
                "engines": list(item.get("engines", [])),
                "ranks": dict(item.get("ranks", {})),
            }
        else:
            for eng in item.get("engines", []):
                if eng not in bucket["engines"]:
                    bucket["engines"].append(eng)
            bucket["ranks"].update(item.get("ranks", {}))
            if not bucket["date"]:
                bucket["date"] = item.get("date", "")
            if len(item.get("snippet", "")) > len(bucket["snippet"]):
                bucket["snippet"] = item.get("snippet", "")
            if len(item.get("title", "")) > len(bucket["title"]):
                bucket["title"] = item.get("title", "")

    out = []
    dropped_block = 0
    for item in merged.values():
        if host_in(item["host"], block_domains):
            dropped_block += 1
            continue
        if level == "off":
            q = QUALITY_MAX if host_in(item["host"], trust_domains) else 0
            flags = []
        else:
            q, flags = quality_of(
                item["title"], item["url"], item["snippet"], trust_domains
            )
        if level == "strict" and q < 0:
            dropped_block += 1
            continue
        rrf = sum(
            ENGINE_WEIGHT.get(eng, 1.0) / (rrf_k + float(r))
            for eng, r in item["ranks"].items()
        )
        rel = relevance(query, item["title"], item["snippet"])
        fresh = freshness(item.get("date") or f"{item['snippet']} {item['title']}")
        final = rrf * 1500.0 + q * 0.5 + rel * 25.0 + fresh * 15.0
        item["score"] = round(final, 2)
        item["quality"] = q
        item["flags"] = flags
        item["relevance"] = round(rel, 3)
        item["freshness"] = round(fresh, 3)
        out.append(item)

    out.sort(key=lambda x: -x["score"])

    if dedupe_similar:
        kept = []
        for item in out:
            if any(
                other["host"] == item["host"]
                and similar(other["title"], item["title"]) > 0.7
                for other in kept
            ):
                dropped_block += 1
                continue
            kept.append(item)
        out = kept

    if max_per_domain and int(max_per_domain) > 0:
        limit = int(max_per_domain)
        seen = {}
        kept = []
        for item in out:
            if seen.get(item["host"], 0) >= limit:
                dropped_block += 1
                continue
            seen[item["host"]] = seen.get(item["host"], 0) + 1
            kept.append(item)
        out = kept

    return out, {"blocked": dropped_block, "tagged": sum(1 for x in out if x["flags"])}


def strip_url(url):
    from .textutil import strip_tracking

    return strip_tracking(url)
