import asyncio
import html
import ipaddress
import re
import urllib.parse

import aiohttp

from .textutil import DROP_RE, UA, clean_text

CHARSET_RE = re.compile(r'charset=["\']?([\w-]+)', re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

MAX_REDIRECTS = 5

BLOCKED_NETS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "64:ff9b::/96",
        "100::/64",
        "2001:db8::/32",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)


async def host_allowed(host, allow_private=False):
    if not host:
        return False
    if allow_private:
        return True
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
        for net in BLOCKED_NETS:
            if ip.version == net.version and ip in net:
                return False
    return True


def decode_body(raw, content_type):
    charset = ""
    if content_type:
        hit = CHARSET_RE.search(content_type)
        if hit:
            charset = hit.group(1)
    if not charset:
        head = raw[:2048].decode("ascii", "ignore")
        hit = CHARSET_RE.search(head)
        if hit:
            charset = hit.group(1)
    for enc in [charset, "utf-8", "gb18030"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


async def fetch_page_text(
    url, limit=6000, timeout=20, proxy=None, user_agent="", allow_private=False
):
    target = (url or "").strip()
    if not target.lower().startswith(("http://", "https://")):
        return {
            "ok": False,
            "error": "请提供完整的 http 或 https 链接",
            "text": "",
            "title": "",
        }
    headers = {
        "User-Agent": user_agent or UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    text = ""
    try:
        async with aiohttp.ClientSession() as session:
            for _ in range(MAX_REDIRECTS + 1):
                parts = urllib.parse.urlsplit(target)
                if parts.scheme not in ("http", "https") or not parts.hostname:
                    return {
                        "ok": False,
                        "error": "请提供完整的 http 或 https 链接",
                        "text": "",
                        "title": "",
                    }
                if not await host_allowed(parts.hostname, allow_private):
                    return {
                        "ok": False,
                        "error": "出于安全考虑，不允许读取内网或本机地址",
                        "text": "",
                        "title": "",
                    }
                async with session.get(
                    target,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    proxy=proxy,
                    allow_redirects=False,
                ) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        if not location:
                            return {
                                "ok": False,
                                "error": f"页面返回 {resp.status}",
                                "text": "",
                                "title": "",
                            }
                        target = urllib.parse.urljoin(target, location)
                        continue
                    if resp.status != 200:
                        return {
                            "ok": False,
                            "error": f"页面返回 {resp.status}",
                            "text": "",
                            "title": "",
                        }
                    raw = await resp.read()
                    text = decode_body(raw, resp.headers.get("Content-Type", ""))
                    break
            else:
                return {"ok": False, "error": "重定向次数过多", "text": "", "title": ""}
    except Exception as e:
        return {"ok": False, "error": f"抓取失败: {e}", "text": "", "title": ""}
    title = ""
    tm = TITLE_RE.search(text)
    if tm:
        title = clean_text(tm.group(1))
    body = DROP_RE.sub(" ", text)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", body, flags=re.I)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    lines = [line.strip() for line in body.splitlines()]
    lines = [line for line in lines if line]
    body = "\n".join(lines)
    body = re.sub(r"[ \t]{2,}", " ", body)
    cap = max(500, int(limit or 6000))
    if len(body) > cap:
        body = body[:cap] + "\n...(内容已截断)"
    return {"ok": True, "error": "", "text": body, "title": title}
