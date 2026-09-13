from .engines import search_many
from .quality import rank
from .query import optimize

MIN_RESULTS = 3


def _merge_stats(stats, engine_out):
    for item in engine_out:
        name = item["engine"]
        if item["ok"]:
            prev = stats["engines"].get(name, 0)
            n = len(item["results"])
            stats["engines"][name] = prev + n if isinstance(prev, int) else n
        else:
            stats["engines"].setdefault(name, item["error"])
        stats["ads"] += item.get("ads", 0)
    return stats


async def web_search(
    query,
    count=8,
    site="",
    time_range="",
    market="zh-CN",
    timeout=15,
    proxy=None,
    user_agent="",
    engines=("bing_rss", "bing"),
    optimize_query=True,
    level="normal",
    block_domains=(),
    trust_domains=(),
    max_per_domain=2,
    dedupe_similar=True,
    filter_ads=True,
):
    raw = (query or "").strip()
    if not raw:
        return {
            "ok": False,
            "error": "查询内容为空",
            "results": [],
            "stats": {},
            "query": "",
        }
    primary = raw
    variants = [raw]
    if optimize_query:
        info = optimize(raw)
        if not info["query"]:
            return {
                "ok": False,
                "error": "去掉礼貌用语后没有剩下有效关键词，换几个词再试",
                "results": [],
                "stats": {},
                "query": "",
            }
        primary = info["query"]
        variants = info["variants"] or [primary]
    want = max(3, min(15, int(count or 8)))
    ask = max(want, 8) + 4

    def build(q):
        return f"site:{site.strip()} {q}" if site else q

    stats = {"engines": {}, "ads": 0, "blocked": 0, "tagged": 0, "variants": 0}
    engine_out = await search_many(
        engines,
        build(primary),
        count=ask,
        user_agent=user_agent,
        timeout=timeout,
        proxy=proxy,
        market=market,
        time_range=time_range,
        filter_ads=filter_ads,
    )
    _merge_stats(stats, engine_out)
    items = [r for e in engine_out for r in e["results"]]
    stats["variants"] = 1

    kept, rs = rank(
        items,
        primary,
        trust_domains=trust_domains,
        block_domains=block_domains,
        level=level,
        max_per_domain=max_per_domain,
        dedupe_similar=dedupe_similar,
    )
    stats["blocked"] += rs["blocked"]
    stats["tagged"] = rs["tagged"]

    if len(kept) < min(MIN_RESULTS, want) and len(variants) > 1:
        alt = variants[1]
        alt_out = await search_many(
            engines,
            build(alt),
            count=ask,
            user_agent=user_agent,
            timeout=timeout,
            proxy=proxy,
            market=market,
            time_range=time_range,
            filter_ads=filter_ads,
        )
        _merge_stats(stats, alt_out)
        items += [r for e in alt_out for r in e["results"]]
        stats["variants"] = 2
        kept, rs = rank(
            items,
            primary,
            trust_domains=trust_domains,
            block_domains=block_domains,
            level=level,
            max_per_domain=max_per_domain,
            dedupe_similar=dedupe_similar,
        )
        stats["blocked"] = rs["blocked"]
        stats["tagged"] = rs["tagged"]

    if not kept:
        errors = [f"{k}:{v}" for k, v in stats["engines"].items() if isinstance(v, str)]
        return {
            "ok": False,
            "error": "没有可用的搜索结果"
            + (f"（{'; '.join(errors)}）" if errors else ""),
            "results": [],
            "stats": stats,
            "query": primary,
        }
    return {
        "ok": True,
        "error": "",
        "results": kept[:want],
        "stats": stats,
        "query": primary,
    }
