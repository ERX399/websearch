<div align="center">

![:name](https://count.getloli.com/@websearch?name=websearch&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# websearch

_✨ 免 Key 联网搜索 · 必应 RSS + 网页双出口 ✨_

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/作者-ERX399-blue)](https://github.com/ERX399)

</div>

给 AstrBot 用的联网搜索插件，不需要任何 API Key

多引擎并发检索 → 去重融合 → 按可信度与相关度重排 → 广告与山寨站过滤，再把干净的结果交给大模型

## 特性

- **无需 API Key**，不需要代理，装上就能用
- **两个出口同时抓**，必应 RSS 与必应网页并发检索：RSS 结构化、无广告、自带发布时间，排序权重更高
- **RRF 融合排序**，多个出口或引擎都命中的结果自动加权
- **反广告**，识别必应的广告位、跳转广告与推广落地页
- **反山寨**，品牌名撞域名但不是官方域名的站点直接打标，例如「Claude 中文版官网」这类
- **搜索词清洗**，自动剥掉「帮我查一下」「谢谢喵」这类前后缀和表情
- **相似度去重**，同域名下的转载与刷屏只留一条
- **引擎限流冷却**，被搜索引擎限流后自动冷却，不会把出口 IP 打到黑名单
- **网页正文读取**，附带一个 `web_fetch` 工具，能直接把链接内容喂给模型
- **内网防护**，读取网页只放行公网地址，回环、内网与云元数据地址直接拒绝，跳转逐跳校验
- **LLM Tool + 指令双入口**，模型自己会调，用户也能手动 `/搜` `/读`

## 效果

模型拿到的不是一堆原始链接，而是清洗、去重、重排过的结果，并且带上了过滤统计与可疑标记

```text
关键词：claude 官网
引擎：bing_rss=10 bing=10
过滤：剔除重复或低质 3，标记可疑 4
共 8 条结果，已按可信度与相关度重排
1. [bing_rss+bing] Download Claude | Claude by Anthropic
   https://claude.com/download
   2026 年 9 月 12 日 · Download Claude apps for Mac, Windows, iOS, and Android.
2. [bing_rss] App unavailable in region | Claude
   https://claude.ai/
   2026 年 9 月 12 日 · Claude is not available in your region.
3. [bing] Claude官网网址
   http://www.yjpoo.com/site/841.html
   ⚠️ 疑似山寨，别当权威，先怀疑
```

## 安装

### 方式一：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/ERX399/websearch.git
```

或者把整个 `websearch` 目录上传到 `AstrBot/data/plugins/` 下

### 方式二：插件市场

在 AstrBot 面板的「插件市场」里搜索 `websearch` 安装

装完重启 AstrBot，若提示缺少依赖，在面板里点一次「安装依赖」即可（只依赖 `aiohttp`）

### 环境要求

- AstrBot `>= 4.9.2`

## 配置

在 AstrBot 面板的插件配置页里改，全部有默认值，开箱可用

### 搜索设置

| 配置项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `engines` | list | `["bing_rss", "bing"]` | 启用的搜索引擎，可选 `bing_rss`（必应 RSS）/ `bing`（必应网页），框架支持继续加 |
| `max_results` | int | `8` | 默认返回条数，3 到 15 |
| `timeout_seconds` | int | `15` | 单次请求超时 |
| `cache_ttl` | int | `600` | 相同查询的缓存时长，0 表示不缓存 |
| `min_interval` | int | `3` | 同一用户两次调用的最小间隔 |
| `max_output_chars` | int | `4000` | 喂给模型的文本上限 |
| `page_chars` | int | `6000` | 网页正文抓取上限 |
| `market` | string | `zh-CN` | 搜索地区 |
| `query_optimize` | bool | `true` | 自动清洗搜索词 |
| `dedupe_similar` | bool | `true` | 按标题相似度去重 |
| `llm_rewrite` | bool | `false` | 先用模型把整句话压成关键词再搜，效果好一些但每次多花一次模型调用 |
| `proxy` | string | 空 | HTTP 代理，留空直连 |
| `user_agent` | string | 空 | 自定义 UA |
| `allow_private_hosts` | bool | `false` | 允许 `web_fetch` 读取内网地址，默认只放行公网 |

### 过滤设置

| 配置项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `filter_ads` | bool | `true` | 过滤广告位与跳转广告 |
| `anti_fake_level` | string | `normal` | `off` 不判断 / `normal` 打标沉底 / `strict` 直接剔除 |
| `max_per_domain` | int | `2` | 同一域名最多保留条数，0 表示不限 |
| `block_domains` | list | `[]` | 强制屏蔽的域名后缀，命中直接丢弃 |
| `trust_domains` | list | `[]` | 额外信任的域名，命中后免检并置顶 |

### 工具与范围

| 配置项 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `enable_search` | bool | `true` | 启用联网搜索工具 |
| `enable_fetch` | bool | `true` | 启用网页读取工具 |
| `send_sources` | bool | `false` | 把来源链接单独追加到回复末尾 |
| `enable_in_group` | bool | `true` | 群聊可用 |
| `enable_in_private` | bool | `true` | 私聊可用 |
| `group_whitelist` | list | `[]` | 群白名单，留空表示所有群可用 |

## 使用

### 让模型自己调

不用做任何事，模型会根据工具描述自行判断该不该联网

`web_search` 的参数

- `query` 搜索关键词
- `count` 返回条数
- `site` 限定单个站点，例如 `github.com`
- `time_range` 时效过滤，可选 `day` / `week` / `month` / `year`

`web_fetch` 的参数

- `url` 要读取的完整链接

### 手动调用

```text
/搜 小米 17 发布
/读 https://www.ithome.com/0/885/833.htm
```

## 工作原理

```text
用户提问
   ↓
搜索词清洗（去礼貌词、去表情、生成英文回退变体）
   ↓
多引擎并发抓取 ──┬── 必应 RSS（优先）
                ├── 必应网页
                └── （可继续接入其它引擎）
   ↓
按 URL 归一化合并（去掉 utm 等跟踪参数，保留有意义的查询参数）
   ↓
RRF 融合 + 域名可信度 + 相关度 + 时效
   ↓
相似度去重 → 同域名条数限制
   ↓
广告与山寨站打标 / 剔除
   ↓
交给大模型
```

排序公式

```text
score = RRF × 1500 + 可信度 × 0.5 + 相关度 × 25 + 时效 × 15
RRF   = Σ 出口权重 / (60 + 该出口中的排名)
```

必应 RSS 出口权重 1.0，必应网页 0.85，两个出口都命中的结果会叠加，所以「RSS 和网页都搜到」的条目排得更前

相关度用中文二元组 + 英文分词算词面重合，时效优先用 RSS 给出的真实发布时间，没有才从摘要里的「3 天前」「2026 年 9 月 2 日」这类表达推算

### 可信度打分

| 命中 | 分值 | 标记 |
| --- | --- | --- |
| 可信域名白名单 | +100 | |
| 品牌名撞域名但非官方 | −50 | 疑似山寨 |
| 强推广词，例如「破解」「加群」「注册送」 | −30 | 推广话术 |
| 弱推广词出现两次以上，例如「免费」「镜像」「中转」 | −20 | 推广话术 |
| 标题同时含年份与「攻略」「盘点」这类词 | −25 | 内容农场 |
| 搜索结果中间页，例如 `/s?q=` | −40 | 搜索结果页 |
| 可疑顶级域，例如 `.top` `.xyz` `.icu` | −15 | 可疑域名 |
| 直接使用 IP 的站点 | −60 | 直接 IP 站点 |

`off` 完全不判断只按相关度排，`normal` 模式下可疑结果只打标并沉底，`strict` 模式下直接剔除
品牌撞域名按域名的段落匹配，`llamaindex.ai` `soracom.io` 这类把品牌词嵌在真实单词里的站点不会被误判

## 支持的搜索引擎

| 引擎 | 标识 | 状态 |
| --- | --- | --- |
| 必应 RSS | `bing_rss` | 稳定，结构化、无广告、自带发布时间，每次最多 10 条，权重更高 |
| 必应网页 | `bing` | 稳定，一次能拿更多结果，但夹广告位与跳转链接 |

搜索引擎多不一定好用，这里只保留实测能稳住的
360 搜索在机房出口 IP 下请求一多就回一个 200 的空壳页，DuckDuckGo 一律 202 限流，百度、搜狗、Startpage、Brave、Ecosia 分别是验证码、反爬、403 与 429，装了也只是白等超时，都没做适配

## 已知限制

- **通用检索是必应单点**，两个出口都是必应，被它限流后只能等冷却（5 分钟），没有第二家能顶上来
- **必应 RSS 出口每次最多 10 条**，条数配置对它无效
- **必应 RSS 出口不接受时间过滤**，`time_range` 传了也不生效，只有网页出口能按时间筛
- **必应 RSS 出口对查不到的词也会硬返回 10 条近似结果**，所以「到底有没有结果」只能看网页出口，别拿 RSS 的条数当准
- **必应网页出口是 HTML 解析**，广告位靠特征匹配，偶尔漏网，必应改版后正则可能要跟着改
- **时效打分不总是准**：RSS 用的是真实发布时间，网页出口只能从摘要里的「3 天前」这类表达猜，猜不到按 0 分算
- **反山寨靠域名匹配**，只对内置的品牌对照表生效，表里没收录的品牌不判断，也可能把真实站点误标成可疑
- **结果是公开页面解析**，不保证任何时刻都能搜到，也不保证与搜索引擎网页完全一致
- **阅读网页有长度上限**（默认 6000 字符），超出部分会截断

## 常见问题

**搜不到东西怎么办**

先看返回里的「引擎」一行，如果显示「失败」说明被限流或者被拦了（搜索引擎有时不返回错误码，而是悄悄给一个空壳页），插件会把它冷却几分钟再试

**结果里还是有垃圾站**

把 `anti_fake_level` 调到 `strict`，再把垃圾站的域名填进 `block_domains`

**模型不调用搜索工具**

确认 `enable_search` 是打开的，并且你用的模型支持 Function Calling，本插件依赖工具调用能力

**为什么读取网页提示「不允许读取内网」**

`web_fetch` 默认只放行公网地址，会拒绝回环、内网、链路本地与云元数据地址（例如 `169.254.169.254`），每次跳转都会重新校验，防止被搜索结果里的链接诱导去读你自己的内网服务
如果你确实要让它读内网站点，把 `allow_private_hosts` 打开

**会不会把模型带偏**

插件会在可疑结果后面附上「疑似山寨」这类警告，建议在你的系统提示词里说明看到警告就别信那一条

## 项目结构

```text
websearch/
├── main.py                 插件入口，工具与指令注册、配置读取、缓存限流
├── metadata.yaml           插件元信息
├── _conf_schema.json       配置面板定义
├── requirements.txt
├── core/
│   ├── textutil.py         文本清洗、域名处理、分词、相关度、时效
│   ├── query.py            搜索词清洗与变体生成
│   ├── engines.py          各引擎的抓取与解析、限流冷却
│   ├── quality.py          可信度打分与融合排序
│   ├── pipeline.py         检索管线编排
│   └── fetcher.py          网页正文提取
└── tests/
    └── test_core.py        离线单元测试
```

## 开发

```bash
pip install aiohttp
python -m unittest discover -s tests -v
```

单元测试全部离线，不联网，覆盖搜索词清洗、可信度判定、融合排序、页面解析与文本工具

## 免责声明

- 本插件通过抓取搜索引擎的公开结果页面工作，属于个人学习与自用性质
- 请遵守目标站点的服务条款与 `robots.txt`，不要高频请求
- 插件内置了限流冷却与调用间隔限制，请不要调低这些值来刷接口
- 使用本插件产生的一切后果由使用者自行承担，作者不对搜索结果的准确性负责
- 搜索结果中的内容与立场与本项目无关

## 许可证

[MIT](LICENSE)
