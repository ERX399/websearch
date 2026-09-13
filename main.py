import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .core.fetcher import fetch_page_text
from .core.pipeline import web_search

PLUGIN_NAME = "websearch"
DEFAULT_ENGINES = ["bing_rss", "bing"]

CONFIG_PATHS = {
    "max_results": ("search_settings", "max_results"),
    "timeout_seconds": ("search_settings", "timeout_seconds"),
    "cache_ttl": ("search_settings", "cache_ttl"),
    "min_interval": ("search_settings", "min_interval"),
    "max_output_chars": ("search_settings", "max_output_chars"),
    "page_chars": ("search_settings", "page_chars"),
    "market": ("search_settings", "market"),
    "proxy": ("search_settings", "proxy"),
    "user_agent": ("search_settings", "user_agent"),
    "engines": ("search_settings", "engines"),
    "query_optimize": ("search_settings", "query_optimize"),
    "llm_rewrite": ("search_settings", "llm_rewrite"),
    "dedupe_similar": ("search_settings", "dedupe_similar"),
    "enable_search": ("tool_settings", "enable_search"),
    "enable_fetch": ("tool_settings", "enable_fetch"),
    "send_sources": ("tool_settings", "send_sources"),
    "filter_ads": ("filter_settings", "filter_ads"),
    "anti_fake_level": ("filter_settings", "anti_fake_level"),
    "max_per_domain": ("filter_settings", "max_per_domain"),
    "block_domains": ("filter_settings", "block_domains"),
    "trust_domains": ("filter_settings", "trust_domains"),
    "enable_in_group": ("scope_settings", "enable_in_group"),
    "enable_in_private": ("scope_settings", "enable_in_private"),
    "group_whitelist": ("scope_settings", "group_whitelist"),
    "allow_private_hosts": ("search_settings", "allow_private_hosts"),
}

CONFIG_DEFAULTS = {
    "max_results": 8,
    "timeout_seconds": 15,
    "cache_ttl": 600,
    "min_interval": 3,
    "max_output_chars": 4000,
    "page_chars": 6000,
    "market": "zh-CN",
    "proxy": "",
    "user_agent": "",
    "allow_private_hosts": False,
    "engines": list(DEFAULT_ENGINES),
    "query_optimize": True,
    "llm_rewrite": False,
    "dedupe_similar": True,
    "enable_search": True,
    "enable_fetch": True,
    "send_sources": False,
    "enable_in_group": True,
    "enable_in_private": True,
    "group_whitelist": [],
    "filter_ads": True,
    "anti_fake_level": "normal",
    "max_per_domain": 2,
    "block_domains": [],
    "trust_domains": [],
}

try:
    from astrbot.core.provider.register import llm_tools as _llm_tools_registry
except ImportError:
    _llm_tools_registry = None


class WebSearchPlugin(Star):
    """联网搜索与网页读取

    大模型会自动调用 web_search 与 web_fetch 两个工具，也可以手动触发：

    /搜 关键词    搜索并列出带可信度标记的结果
    /读 链接      读取网页正文
    """

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self._cache: dict = {}
        self._last_call: dict = {}
        self._sources: dict = {}

    def _cfg(self, key, default=None):
        path = CONFIG_PATHS.get(key)
        if path:
            section = self.config.get(path[0], {})
            if isinstance(section, dict) and path[1] in section:
                return section[path[1]]
        return self.config.get(key, CONFIG_DEFAULTS.get(key, default))

    def _engines(self):
        raw = self._cfg("engines", DEFAULT_ENGINES) or DEFAULT_ENGINES
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.replace("，", ",").split(",")]
        names = [str(x).strip() for x in raw if str(x).strip()]
        return names or list(DEFAULT_ENGINES)

    def _drop_tool(self, name):
        remover = getattr(_llm_tools_registry, "remove_func", None)
        if remover is None:
            logger.warning(
                f"[{PLUGIN_NAME}] 当前 AstrBot 版本不支持卸载工具，{name} 仍会注册"
            )
            return
        try:
            remover(name)
            logger.info(f"[{PLUGIN_NAME}] 已按配置卸载工具 {name}")
        except Exception as e:
            logger.warning(f"[{PLUGIN_NAME}] 卸载工具 {name} 失败: {e}")

    async def initialize(self):
        if _llm_tools_registry is None:
            logger.warning(f"[{PLUGIN_NAME}] 未找到 LLM 工具注册表，跳过工具开关")
            return
        if not self._cfg("enable_search", True):
            self._drop_tool("web_search")
        if not self._cfg("enable_fetch", True):
            self._drop_tool("web_fetch")

    def _scope_ok(self, event: AstrMessageEvent) -> bool:
        group_id = event.get_group_id()
        if group_id:
            if not self._cfg("enable_in_group", True):
                return False
            whitelist = self._cfg("group_whitelist", []) or []
            if whitelist and str(group_id) not in [str(x) for x in whitelist]:
                return False
            return True
        return bool(self._cfg("enable_in_private", True))

    def _rate_limited(self, event: AstrMessageEvent, bucket: str = "") -> bool:
        span = max(0, int(self._cfg("min_interval", 3) or 0))
        if span <= 0:
            return False
        key = f"{bucket}:{event.unified_msg_origin}:{event.get_sender_id()}"
        now = time.time()
        last = self._last_call.get(key, 0)
        if now - last < span:
            return True
        self._last_call[key] = now
        if len(self._last_call) > 2000:
            self._last_call.clear()
            self._last_call[key] = now
        return False

    def _cache_get(self, key):
        ttl = int(self._cfg("cache_ttl", 600) or 0)
        if ttl <= 0:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        if time.time() - item[0] > ttl:
            self._cache.pop(key, None)
            return None
        return item[1]

    def _cache_set(self, key, value):
        if int(self._cfg("cache_ttl", 600) or 0) <= 0:
            return
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[key] = (time.time(), value)

    async def _read_page(self, url):
        return await fetch_page_text(
            url,
            limit=int(self._cfg("page_chars", 6000) or 6000),
            timeout=int(self._cfg("timeout_seconds", 15) or 15) + 10,
            proxy=self._cfg("proxy", "") or None,
            user_agent=self._cfg("user_agent", "") or "",
            allow_private=bool(self._cfg("allow_private_hosts", False)),
        )

    async def _rewrite(self, query, event):
        if not self._cfg("llm_rewrite", False):
            return ""
        try:
            provider = self.context.get_using_provider(event.unified_msg_origin)
            if not provider:
                return ""
            resp = await provider.text_chat(
                prompt=(
                    "把下面这句话改写成一条网页搜索关键词，只输出关键词本身，"
                    "不超过 20 个字，不要解释，不要引号：\n" + query
                ),
                system_prompt="你是搜索关键词改写器，只输出关键词。",
            )
            text = (getattr(resp, "completion_text", "") or "").strip()
            text = text.splitlines()[0].strip().strip('"“”「」') if text else ""
            return text if 1 < len(text) <= 60 else ""
        except Exception as e:
            logger.warning(f"[{PLUGIN_NAME}] 关键词改写失败，回退规则优化: {e}")
            return ""

    def _format_results(self, query, results, stats=None):
        cap = max(500, int(self._cfg("max_output_chars", 4000) or 4000))
        stats = stats or {}
        head = f"关键词：{query}"
        if stats.get("variants", 1) > 1:
            head += "（已放宽二次检索）"
        lines = [head]
        eng = stats.get("engines") or {}
        if eng:
            detail = " ".join(
                f"{k}={v}" if not isinstance(v, str) else f"{k}=失败"
                for k, v in eng.items()
            )
            lines.append(f"引擎：{detail}")
        extra = []
        if stats.get("ads"):
            extra.append(f"过滤广告 {stats['ads']}")
        if stats.get("blocked"):
            extra.append(f"剔除重复或低质 {stats['blocked']}")
        if stats.get("tagged"):
            extra.append(f"标记可疑 {stats['tagged']}")
        if extra:
            lines.append("过滤：" + "，".join(extra))
        lines.append(f"共 {len(results)} 条结果，已按可信度与相关度重排")
        for idx, item in enumerate(results, 1):
            tag = "+".join(item.get("engines") or [])
            lines.append(f"{idx}. [{tag}] {item['title']}")
            lines.append(f"   {item['url']}")
            body = item.get("snippet") or ""
            if item.get("date"):
                body = f"{item['date']} · {body}" if body else item["date"]
            if body:
                lines.append(f"   {body}")
            if item.get("flags"):
                lines.append(f"   ⚠️ {'/'.join(item['flags'])}，别当权威，先怀疑")
        text = "\n".join(lines)
        if len(text) > cap:
            text = text[:cap] + "\n...(结果已截断)"
        return text

    async def _do_search(self, query, count=None, site="", time_range="", event=None):
        count = int(count or self._cfg("max_results", 8) or 8)
        rewritten = ""
        if event is not None:
            rewritten = await self._rewrite(query, event)
        key_query = rewritten or query
        cache_key = ("search", key_query, count, site, time_range)
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._remember_sources(event, cached)
            return cached
        result = await web_search(
            key_query,
            count=count,
            site=site,
            time_range=time_range,
            market=self._cfg("market", "zh-CN"),
            timeout=int(self._cfg("timeout_seconds", 15) or 15),
            proxy=self._cfg("proxy", "") or None,
            user_agent=self._cfg("user_agent", "") or "",
            engines=self._engines(),
            optimize_query=bool(self._cfg("query_optimize", True)),
            level=str(self._cfg("anti_fake_level", "normal") or "normal"),
            block_domains=self._cfg("block_domains", []) or [],
            trust_domains=self._cfg("trust_domains", []) or [],
            max_per_domain=int(self._cfg("max_per_domain", 2) or 0),
            dedupe_similar=bool(self._cfg("dedupe_similar", True)),
            filter_ads=bool(self._cfg("filter_ads", True)),
        )
        if result.get("ok"):
            self._cache_set(cache_key, result)
            self._remember_sources(event, result)
        return result

    def _remember_sources(self, event, result):
        if event is None or not result.get("ok"):
            return
        self._sources[event.unified_msg_origin] = [
            x["url"] for x in result["results"][:5]
        ]

    @filter.llm_tool(name="web_search")
    async def search_tool(
        self,
        event: AstrMessageEvent,
        query: str,
        count: int = 8,
        site: str = "",
        time_range: str = "",
    ) -> str:
        """Search the live web across several search engines and return ranked results.

        The results are merged from multiple engines, de-duplicated, and re-ranked by
        credibility and relevance. Ads and low-quality sites are filtered out.

        When to use:
        - The user asks about anything time-sensitive: news, prices, releases, weather, sports, events
        - The question is about information after your training cutoff, or you are unsure of the fact
        - The user explicitly asks you to search, or shares a term that you do not recognize
        - You need the current status of a product, model, person or website

        When NOT to use:
        - Casual chat, opinions, emotional support, or things you already know for sure
        - Do not search twice for the same question in one turn

        Args:
            query(string): Clear, self-contained search keywords in the user's language
            count(int): How many results to return, 3 to 15. Default 8
            site(string): Restrict to one site, for example "github.com". Empty means no restriction
            time_range(string): "day", "week", "month" or "year" for freshness filter. Empty means no filter
        """
        if not self._cfg("enable_search", True):
            return "联网搜索功能没启用"
        if not self._scope_ok(event):
            return "当前场景不允许联网搜索"
        if self._rate_limited(event, "search"):
            return "搜索太频繁了，稍等一下再试"
        if not query or not query.strip():
            return "请提供要搜索的关键词"
        result = await self._do_search(
            query.strip(), count=count, site=site, time_range=time_range, event=event
        )
        if not result.get("ok"):
            return f"搜索失败：{result.get('error')}"
        return self._format_results(
            result.get("query") or query.strip(), result["results"], result.get("stats")
        )

    @filter.llm_tool(name="web_fetch")
    async def fetch_tool(self, event: AstrMessageEvent, url: str):
        """Fetch a web page and return its readable text content.

        When to use:
        - The user gives a URL and asks what it says or what it is about
        - You need details from a page found by web_search before answering
        - You need to check whether a link is reachable or what it contains

        Args:
            url(string): Full http or https URL of the page
        """
        if not self._cfg("enable_fetch", True):
            return "网页读取功能没启用"
        if not self._scope_ok(event):
            return "当前场景不允许读取网页"
        if self._rate_limited(event, "fetch"):
            return "读取太频繁了，稍等一下再试"
        result = await self._read_page(url)
        if not result.get("ok"):
            return f"读取失败：{result.get('error')}"
        title = result.get("title") or url
        return f"标题：{title}\n链接：{url}\n\n{result.get('text', '')}"

    @filter.command("搜")
    async def search_cmd(self, event: AstrMessageEvent, keyword: str = ""):
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("用法：搜 关键词")
            return
        if not self._cfg("enable_search", True):
            yield event.plain_result("联网搜索功能没启用")
            return
        if not self._scope_ok(event):
            yield event.plain_result("当前场景不允许联网搜索")
            return
        if self._rate_limited(event, "search"):
            yield event.plain_result("搜太勤了，歇一下喵")
            return
        result = await self._do_search(keyword, event=event)
        if not result.get("ok"):
            yield event.plain_result(f"搜不到：{result.get('error')}")
            return
        eng = result.get("stats", {}).get("engines") or {}
        detail = " ".join(k for k, v in eng.items() if not isinstance(v, str))
        lines = [f"搜到 {len(result['results'])} 条（{detail}）："]
        for idx, item in enumerate(result["results"], 1):
            mark = "⚠️" if item.get("flags") else ""
            tag = "+".join(item.get("engines") or [])
            lines.append(f"{idx}. {mark}[{tag}] {item['title']}")
            lines.append(item["url"])
        yield event.plain_result("\n".join(lines))

    @filter.command("读")
    async def fetch_cmd(self, event: AstrMessageEvent, url: str = ""):
        url = (url or "").strip()
        if not url:
            yield event.plain_result("用法：读 网页链接")
            return
        if not self._cfg("enable_fetch", True):
            yield event.plain_result("网页读取功能没启用")
            return
        if not self._scope_ok(event):
            yield event.plain_result("当前场景不允许读取网页")
            return
        if self._rate_limited(event, "fetch"):
            yield event.plain_result("读太勤了，歇一下喵")
            return
        result = await self._read_page(url)
        if not result.get("ok"):
            yield event.plain_result(f"读不到：{result.get('error')}")
            return
        text = result.get("text", "")
        if len(text) > 1500:
            text = text[:1500] + "\n...(截断)"
        yield event.plain_result(f"{result.get('title') or url}\n\n{text}")

    @filter.on_decorating_result()
    async def _attach_sources(self, event: AstrMessageEvent):
        if not self._cfg("send_sources", False):
            return
        links = self._sources.pop(event.unified_msg_origin, None)
        if not links:
            return
        try:
            from astrbot.core.message.components import Plain

            result = event.get_result()
            if result is None:
                return
            result.chain.append(Plain("\n来源：\n" + "\n".join(links)))
        except Exception as e:
            logger.warning(f"[{PLUGIN_NAME}] 附加来源失败: {e}")

    async def terminate(self):
        self._cache.clear()
        self._last_call.clear()
        self._sources.clear()
