import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from websearch.core import engines, fetcher, quality, query, textutil
from websearch.core.pipeline import web_search

BING_PAGE = """
<ol id="b_results">
<li class="b_algo"><h2><a href="https://www.python.org/">Welcome to Python.org</a></h2>
<p>Python is a programming language.</p></li>
<li class="b_algo"><h2><a href="https://go.microsoft.com/fwlink/?LinkID=999">Buy something</a></h2>
<p>Sponsored placement.</p></li>
<li class="b_algo"><h2><a href="https://docs.python.org/3/">Python 3 documentation</a></h2>
<p>Official documentation.</p></li>
</ol>
"""


RSS_PAGE = """<?xml version="1.0" encoding="utf-8" ?><rss version="2.0"><channel>
<item><title>小米 17 手机正式发布：首发第五代骁龙 8 至尊版</title>
<link>https://www.ithome.com/0/885/831.htm</link>
<description>IT之家 9 月 25 日消息，小米 17 手机今日正式发布</description>
<pubDate>周四, 25 9月 2025 20:21:00 GMT</pubDate></item>
<item><title>Xiaomi 17</title>
<link>https://www.mi.com/prod/xiaomi-17</link>
<description>Xiaomi 17，6.3 英寸小尺寸</description>
<pubDate>Sat, 12 Sep 2026 03:30:00 GMT</pubDate></item>
</channel></rss>"""


def item(engine, rank, title, url, snippet=""):
    return engines._item(engine, rank, title, url, snippet)


class QueryTest(unittest.TestCase):
    def test_strips_leading_filler_and_tail_particle(self):
        cleaned, changed = query.clean("帮我查一下 python 教程 谢谢喵")
        self.assertTrue(changed)
        self.assertEqual(cleaned, "python 教程")

    def test_strips_emoji_and_noise(self):
        cleaned, _ = query.clean("【求助】🎉 deepseek 价格？？？")
        self.assertNotIn("🎉", cleaned)
        self.assertIn("deepseek", cleaned)

    def test_keeps_query_without_filler(self):
        cleaned, changed = query.clean("小米 17 发布")
        self.assertEqual(cleaned, "小米 17 发布")
        self.assertFalse(changed)

    def test_pure_filler_query_cleans_to_empty(self):
        for text in (
            "喵",
            "谢谢",
            "帮我查一下",
            "搜索一下",
            "帮我查一下 谢谢喵",
            "你能帮我查一下吗",
        ):
            cleaned, _ = query.clean(text)
            self.assertEqual(cleaned, "", text)

    def test_filler_never_leaves_short_fragment(self):
        cleaned, _ = query.clean("帮我查一下 Python")
        self.assertEqual(cleaned, "Python")

    def test_short_but_real_query_is_kept(self):
        cleaned, _ = query.clean("京")
        self.assertEqual(cleaned, "京")
        cleaned, _ = query.clean("喵星人行为研究")
        self.assertEqual(cleaned, "喵星人行为研究")

    def test_variants_add_ascii_only(self):
        variants = query.variants("帮我查一下 AstrBot 插件开发 文档")
        self.assertIn("AstrBot 插件开发 文档", variants)
        self.assertIn("AstrBot", variants)

    def test_optimize_returns_original_when_clean_is_empty(self):
        info = query.optimize("   ")
        self.assertEqual(info["query"], "")


class TextUtilTest(unittest.TestCase):
    def test_domain_of(self):
        self.assertEqual(textutil.domain_of("https://www.python.org/3/"), "python.org")
        self.assertEqual(textutil.domain_of("http://Example.COM:8080/x"), "example.com")
        self.assertEqual(textutil.domain_of("not a url"), "")

    def test_strip_tracking(self):
        url = "https://x.com/a?utm_source=wx&id=7&spm=abc"
        self.assertEqual(textutil.strip_tracking(url), "https://x.com/a?id=7")
        self.assertEqual(
            textutil.strip_tracking("https://x.com/a?id=7"), "https://x.com/a?id=7"
        )

    def test_url_key_merges_www_and_tracking(self):
        a = textutil.url_key("https://www.x.com/a/?utm_medium=1")
        b = textutil.url_key("http://x.com/a")
        self.assertEqual(a, b)

    def test_url_key_keeps_meaningful_query(self):
        self.assertNotEqual(
            textutil.url_key("https://x.com/view?v=AAA"),
            textutil.url_key("https://x.com/view?v=BBB"),
        )
        self.assertEqual(
            textutil.url_key("https://x.com/view?v=AAA&utm_source=wx"),
            textutil.url_key("https://x.com/view?v=AAA"),
        )

    def test_host_in(self):
        self.assertTrue(textutil.host_in("docs.python.org", ["python.org"]))
        self.assertTrue(textutil.host_in("python.org", ["python.org"]))
        self.assertFalse(textutil.host_in("notpython.org", ["python.org"]))
        self.assertFalse(textutil.host_in("python.org", []))

    def test_tokenize_mixes_cjk_bigram_and_ascii(self):
        tokens = textutil.tokenize("小米 python3")
        self.assertIn("小米", tokens)
        self.assertIn("python3", tokens)

    def test_freshness_relative_and_absolute(self):
        self.assertGreater(textutil.freshness("3 天前发布"), 0.9)
        self.assertEqual(textutil.freshness("3 年前发布"), 0.0)
        self.assertEqual(textutil.freshness("no date here"), 0.0)
        self.assertGreater(textutil.freshness("2026 年 9 月 10 日"), 0.9)

    def test_relevance(self):
        self.assertGreater(textutil.relevance("python 教程", "Python 教程", ""), 0.0)
        self.assertEqual(textutil.relevance("python", "完全无关的内容", ""), 0.0)
        self.assertEqual(textutil.relevance("", "anything", ""), 0.0)

    def test_similar(self):
        self.assertEqual(textutil.similar("小米17发布", "小米17发布"), 1.0)
        self.assertEqual(textutil.similar("alpha beta", "gamma delta"), 0.0)


class QualityTest(unittest.TestCase):
    def test_official_domain_is_trusted(self):
        score, flags = quality.judge("DeepSeek", "https://www.deepseek.com/", "")
        self.assertEqual(score, quality.QUALITY_MAX)
        self.assertEqual(flags, [])

    def test_fake_brand_site_is_flagged(self):
        score, flags = quality.judge(
            "DeepSeek 官网", "https://deepseek-fake.com.cn/", ""
        )
        self.assertLess(score, 0)
        self.assertIn("疑似山寨", flags)

    def test_spam_words_are_flagged(self):
        score, flags = quality.judge(
            "免费领取", "https://example.com/", "破解版 加群 注册送"
        )
        self.assertIn("推广话术", flags)
        self.assertLess(score, 0)

    def test_content_farm_title_is_flagged(self):
        score, flags = quality.judge(
            "2026 年最新 AI 工具盘点", "https://example.com/", ""
        )
        self.assertIn("内容农场", flags)

    def test_search_page_is_flagged(self):
        score, flags = quality.judge(
            "小米 17", "https://tv.example.com/s?q=%E5%B0%8F%E7%B1%B317", ""
        )
        self.assertIn("搜索结果页", flags)
        self.assertLess(score, 0)

    def test_ip_host_is_flagged(self):
        score, flags = quality.judge("站点", "http://1.2.3.4/admin", "")
        self.assertIn("直接 IP 站点", flags)

    def test_brand_inside_real_word_is_not_flagged(self):
        for host in (
            "https://www.llamaindex.ai/",
            "https://soracom.io/",
            "https://cursor.so/",
        ):
            score, flags = quality.judge("随便", host, "")
            self.assertNotIn("疑似山寨", flags, host)

    def test_brand_with_separator_or_short_suffix_is_flagged(self):
        for host in (
            "https://claudezh.com/",
            "https://deepseekvc.com/",
            "https://chatgpt-cnblog.com/",
            "https://deepseek-fake.com.cn/",
        ):
            score, flags = quality.judge("随便", host, "")
            self.assertIn("疑似山寨", flags, host)

    def test_trust_domains_override(self):
        score, flags = quality.quality_of(
            "随便什么",
            "https://my.internal.site/x",
            "",
            trust_domains=["internal.site"],
        )
        self.assertEqual(score, quality.QUALITY_MAX)
        self.assertEqual(flags, [])


class RankTest(unittest.TestCase):
    def test_multi_engine_consensus_outranks_single(self):
        alone = item("bing", 1, "Python 官网", "https://www.python.org/", "python")
        both_a = item("bing", 1, "Python 官网", "https://www.python.org/", "python")
        both_b = item("other", 1, "Python 官网", "https://www.python.org/", "python")
        solo, _ = quality.rank([alone], "python")
        fused, _ = quality.rank([both_a, both_b], "python")
        self.assertEqual(fused[0]["engines"], ["bing", "other"])
        self.assertGreater(fused[0]["score"], solo[0]["score"])

    def test_rss_surface_outranks_html_at_same_rank(self):
        rss = item("bing_rss", 1, "Python 教程", "https://a.example.com/x", "python")
        html = item("bing", 1, "Python 教程", "https://b.example.com/x", "python")
        kept, _ = quality.rank([html, rss], "python")
        self.assertEqual(kept[0]["engines"], ["bing_rss"])

    def test_block_domains_removes_and_counts(self):
        items = [item("bing", 1, "垃圾站", "https://spam.example.com/a", "")]
        kept, stats = quality.rank(items, "x", block_domains=["spam.example.com"])
        self.assertEqual(kept, [])
        self.assertEqual(stats["blocked"], 1)

    def test_strict_level_drops_negative_quality(self):
        items = [item("bing", 1, "DeepSeek 官网", "https://deepseek-fake.xyz/", "")]
        normal, _ = quality.rank(items, "deepseek", level="normal")
        strict, _ = quality.rank(items, "deepseek", level="strict")
        self.assertEqual(len(normal), 1)
        self.assertEqual(strict, [])

    def test_off_level_skips_judging(self):
        items = [item("bing", 1, "DeepSeek 官网", "https://deepseek-fake.xyz/", "")]
        kept, stats = quality.rank(items, "deepseek", level="off")
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["flags"], [])
        self.assertEqual(kept[0]["quality"], 0)
        self.assertEqual(stats["tagged"], 0)

    def test_off_level_still_honours_trust_domains(self):
        items = [item("bing", 1, "内网站", "https://my.internal.site/x", "")]
        kept, _ = quality.rank(items, "x", level="off", trust_domains=["internal.site"])
        self.assertEqual(kept[0]["quality"], quality.QUALITY_MAX)

    def test_max_per_domain(self):
        items = [
            item("bing", 1, "Alpha one", "https://d.example.com/a", ""),
            item("bing", 2, "Bravo two", "https://d.example.com/b", ""),
            item("bing", 3, "Charlie three", "https://d.example.com/c", ""),
        ]
        kept, _ = quality.rank(items, "x", max_per_domain=2)
        self.assertEqual(len(kept), 2)

    def test_similar_titles_same_host_are_deduped(self):
        items = [
            item("bing", 1, "小米17发布", "https://n.example.com/a", ""),
            item("bing", 2, "小米17发布了", "https://n.example.com/b", ""),
        ]
        kept, stats = quality.rank(items, "小米17")
        self.assertEqual(len(kept), 1)
        self.assertEqual(stats["blocked"], 1)

    def test_dedupe_can_be_disabled(self):
        items = [
            item("bing", 1, "小米17发布", "https://n.example.com/a", ""),
            item("bing", 2, "小米17发布了", "https://n.example.com/b", ""),
        ]
        kept, _ = quality.rank(items, "小米17", dedupe_similar=False)
        self.assertEqual(len(kept), 2)

    def test_trust_domain_sorts_first(self):
        items = [
            item("bing", 1, "乱七八糟聚合页", "https://junk.example.com/a", ""),
            item("other", 5, "Python 官网", "https://www.python.org/", ""),
        ]
        kept, _ = quality.rank(items, "python")
        self.assertEqual(kept[0]["host"], "python.org")


class EngineParseTest(unittest.TestCase):
    def setUp(self):
        engines.BLOCKED_UNTIL.clear()

    def test_parse_bing_skips_ads(self):
        results, ads = engines.parse_bing(BING_PAGE)
        self.assertEqual(ads, 1)
        urls = [r["url"] for r in results]
        self.assertIn("https://www.python.org/", urls)
        self.assertNotIn("https://go.microsoft.com/fwlink/?LinkID=999", urls)
        self.assertEqual([r["ranks"]["bing"] for r in results], [1, 2])

    def test_parse_bing_keeps_ads_when_filter_disabled(self):
        results, ads = engines.parse_bing(BING_PAGE, False)
        self.assertEqual(ads, 0)
        urls = [r["url"] for r in results]
        self.assertIn("https://go.microsoft.com/fwlink/?LinkID=999", urls)
        self.assertEqual([r["ranks"]["bing"] for r in results], [1, 2, 3])

    def test_time_filter_supports_year(self):
        self.assertEqual(engines.TIME_FILTERS["year"], "ez4")

    def test_parse_bing_rss_keeps_direct_links(self):
        results = engines.parse_bing_rss(RSS_PAGE)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "https://www.ithome.com/0/885/831.htm")
        self.assertEqual(results[0]["engines"], ["bing_rss"])
        self.assertEqual([r["ranks"]["bing_rss"] for r in results], [1, 2])

    def test_parse_bing_rss_normalises_dates(self):
        results = engines.parse_bing_rss(RSS_PAGE)
        self.assertEqual(results[0]["date"], "2025 年 9 月 25 日")
        self.assertEqual(results[1]["date"], "2026 年 9 月 12 日")

    def test_resolve_engine_aliases(self):
        self.assertEqual(engines.resolve_engine(" 必应 "), "bing")
        self.assertEqual(engines.resolve_engine("cn.bing"), "bing")
        self.assertEqual(engines.resolve_engine("rss"), "bing_rss")
        self.assertEqual(engines.resolve_engine("unknown"), "")
        self.assertEqual(engines.resolve_engine("duckduckgo"), "")
        self.assertEqual(engines.resolve_engine("360"), "")

    def test_stub_page_is_detected(self):
        self.assertTrue(engines._stub_page([], 0, "<html><title>搜索</title></html>"))
        self.assertFalse(engines._stub_page([], 0, "x" * 20000))
        self.assertFalse(engines._stub_page([object()], 0, "x" * 100))
        self.assertFalse(engines._stub_page([], 3, "x" * 100))

    def test_cooldown_blocks_engine(self):
        engines._cool("bing")
        self.assertTrue(engines.cooling("bing"))
        self.assertFalse(engines.cooling("other"))


class FetchGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_public_ip_is_allowed(self):
        self.assertTrue(await fetcher.host_allowed("8.8.8.8"))
        self.assertTrue(await fetcher.host_allowed("2606:4700::1111"))

    async def test_private_and_metadata_addresses_are_blocked(self):
        for host in (
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fd00::1",
        ):
            self.assertFalse(await fetcher.host_allowed(host), host)

    async def test_allow_private_override(self):
        self.assertTrue(await fetcher.host_allowed("127.0.0.1", True))

    async def test_empty_host_is_blocked(self):
        self.assertFalse(await fetcher.host_allowed(""))

    async def test_non_http_scheme_is_rejected(self):
        result = await fetcher.fetch_page_text("file:///etc/passwd")
        self.assertFalse(result["ok"])

    async def test_private_target_is_refused_before_connecting(self):
        result = await fetcher.fetch_page_text("http://127.0.0.1:1/admin")
        self.assertFalse(result["ok"])
        self.assertIn("内网", result["error"])


class PipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_empty_query_fails_without_network(self):
        result = await web_search("")
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"], [])

    async def test_blank_query_fails_without_network(self):
        result = await web_search("   ")
        self.assertFalse(result["ok"])

    async def test_filler_only_query_fails_without_network(self):
        result = await web_search("帮我查一下")
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"], [])


if __name__ == "__main__":
    unittest.main()
