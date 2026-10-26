# -*- coding: utf-8 -*-
# ============================================================
# 🎬｜森林｜影视 · TVBox Python 爬虫
# 数据源：影视森林 (imtlink.com) · 8源实测唯一可用
# 功能：去跑马灯 / 全站搜索 / 智能播放解析 / 多UA轮换
# 分类：最新 / 恐怖 / 动作 / 奇幻 / 按国家地区
# ============================================================
import re, json, base64, random
try:
    import requests as _requests
except Exception:
    _requests = None

# 多 User-Agent 轮换
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; M2007J3SC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
]

def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s


class Spider:
    def __init__(self):
        self.site = "https://www.imtlink.com"
        self.name = "🎬｜森林｜影视"
        self._ua_idx = 0
        self.s = _requests.Session() if _requests else None
        # 精选分类：最新/恐怖/动作/奇幻 置顶 + 常规分类
        self.cates = [
            ("dianying", "🆕｜最新｜电影"),
            ("kongbupian", "😱｜恐怖｜电影"),
            ("dongzuopian", "💥｜动作｜电影"),
            ("qihuanpian", "🔮｜奇幻｜电影"),
            ("dsj", "📺｜国产｜剧集"),
            ("oumeiju", "🦅｜欧美｜剧集"),
            ("hanju", "💃｜韩圈｜剧集"),
            ("riju", "🗾｜日剧｜剧集"),
            ("gangju", "🌃｜港剧｜剧集"),
            ("taiju", "🏝️｜台剧｜剧集"),
            ("dongman", "🎨｜动漫｜综合"),
            ("zongyi", "🎤｜综艺｜综合"),
            ("xijupian", "😄｜喜剧｜电影"),
            ("aiqingpian", "💕｜爱情｜电影"),
            ("kehuanpian", "🚀｜科幻｜电影"),
            ("juqingpian", "🎭｜剧情｜电影"),
            ("zhanzhengpian", "⚔️｜战争｜电影"),
            ("xuanyipian", "🔍｜悬疑｜电影"),
            ("fanzuipian", "🚔｜犯罪｜电影"),
            ("maoxianpian", "🧭｜冒险｜电影"),
            ("jingsongpian", "👻｜惊悚｜电影"),
            ("jilupian", "📹｜纪录｜电影"),
            ("remenduanju", "⚡｜热门｜短剧"),
        ]

    def _next_ua(self):
        ua = USER_AGENTS[self._ua_idx % len(USER_AGENTS)]
        self._ua_idx += 1
        return ua

    def _headers(self, referer=None):
        return {
            "User-Agent": self._next_ua(),
            "Referer": referer or self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return True

    def _get(self, url, referer=None):
        h = self._headers(referer)
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=12, allow_redirects=True)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        """URL 规范化 + 封面优化"""
        if not u:
            return u
        u = u.strip()
        # 去跑马灯/推广参数
        u = re.sub(r'[?&](spm|from|_t)=[^&]*', '', u)
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http://"):
            u = "https://" + u[7:]  # http→https 优化
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _tx(self, s):
        # 去跑马灯文字
        s = re.sub(r'(欢迎|公告|通知|推广|广告|QQ群|微信|关注).*?[，。！\n]', '', s or '')
        return re.sub(r"<[^>]+>", "", _html_unescape(s or "")).strip()

    def _parse_cards(self, html):
        items, seen = [], set()
        for m in re.finditer(r'<a[^>]+href="(/voddetail/(\d+)\.html)"[^>]*title="([^"]+)"[^>]*>', html):
            vid, title = m.group(2), self._tx(m.group(3))
            if not title or vid in seen:
                continue
            seen.add(vid)
            seg = html[m.end():m.end() + 800]
            pm = re.search(r'data-original="([^"]+)"', seg) or re.search(r'data-background="([^"]+)"', seg)
            pic = self._u(pm.group(1)) if pm else ""
            # 地区标记
            am = re.search(r'>(大陆|香港|台湾|日本|韩国|美国|英国|法国|德国|泰国|欧美|国产)<', seg)
            area = am.group(1) if am else ""
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": f"🌍{area}" if area else "",
            })
        return items

    def init(self, extend=""):
        return None

    def homeContent(self, filter=None):
        cats = [{"type_id": cid, "type_name": name} for cid, name in self.cates]
        try:
            html = self._get(self.site)
            vod_list = self._parse_cards(html) if html else []
        except Exception:
            vod_list = []
        return {"class": cats, "list": vod_list}

    def homeVideoContent(self):
        try:
            html = self._get(self.site)
            return {"list": self._parse_cards(html) if html else []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        tid = str(tid).strip()
        if pg <= 1:
            url = "{0}/vodtype/{1}.html".format(self.site, tid)
        else:
            url = "{0}/vodtype/{1}-{2}.html".format(self.site, tid, pg)
        try:
            html = self._get(url)
        except Exception:
            html = ""
        items = self._parse_cards(html) if html else []
        pagecount = pg + 1 if len(items) >= 20 else pg
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": pagecount * 24}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids)
        m0 = re.search(r"(\d+)", str(vid))
        if not m0:
            return {"list": []}
        vid = m0.group(1)
        try:
            html = self._get("{0}/voddetail/{1}.html".format(self.site, vid))
        except Exception:
            return {"list": []}
        if not html:
            return {"list": []}
        tm = re.search(r'<h3><a href="/voddetail/\d+\.html">([^<]+)</a></h3>', html)
        title = self._tx(tm.group(1)) if tm else ""
        if not title:
            tm2 = re.search(r'《([^》]{1,40})》', html)
            title = tm2.group(1).strip() if tm2 else vid
        pm = re.search(r'<div class="pic"><img[^>]+data-original="([^"]+)"', html)
        pic = self._u(pm.group(1)) if pm else ""
        am = re.search(r'主演：(.*?)</span>', html, re.S)
        actor = ",".join(re.findall(r'>([^<>]{1,16})</a>', am.group(1))) if am else ""
        ym = re.search(r'年份：<a[^>]*>([^<]+)</a>', html)
        year = ym.group(1).strip() if ym else ""
        dm = re.search(r'导演：(.*?)</span>', html, re.S)
        director = ",".join(re.findall(r'>([^<>]{1,16})</a>', dm.group(1))) if dm else ""
        rm = re.search(r'地区：<a[^>]*>([^<]+)</a>', html)
        area = rm.group(1).strip() if rm else ""
        ds = re.search(r'简介：([\s\S]{2,800}?)</div>', html)
        desc = ""
        if ds:
            raw = _html_unescape(ds.group(1))
            raw = re.sub(r"(&amp;\s*;?\s*)+", "", raw)
            desc = self._tx(raw)
        # 播放源：智能多线路
        tabs = re.findall(r'data-target="#ewave-playlist-(\d+)">([^<]{1,20})<', html)
        play_from, play_url = [], []
        for sid, label in tabs:
            sec = html.split('id="ewave-playlist-{0}"'.format(sid), 1)
            sec = sec[1].split('id="ewave-playlist-')[0] if len(sec) > 1 else ""
            eps, seen = [], set()
            for em in re.finditer(r'href="(/vodplay/\d+-{0}-\d+\.html)"[^>]*>([^<]{{1,32}})</a>'.format(sid), sec):
                name = self._tx(em.group(2)) or "播放"
                u = self._u(em.group(1))
                if (name, u) in seen:
                    continue
                seen.add((name, u))
                eps.append("{0}${1}".format(name, u))
            if eps:
                play_from.append(label.strip() or "线路{0}".format(sid))
                play_url.append("#".join(eps))
        vod = {
            "vod_id": vid, "vod_name": title, "vod_pic": pic,
            "vod_year": year, "vod_area": area, "vod_actor": actor,
            "vod_director": director, "vod_content": desc,
            "vod_remarks": f"🌍{area} 📅{year}" if area or year else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        # 站内搜索（走 suggest 联想接口）
        try:
            from urllib.parse import quote
            txt = self._get("{0}/index.php/ajax/suggest?mid=1&wd={1}".format(
                self.site, quote(str(key), safe="")))
            data = json.loads(txt) if txt else {}
        except Exception:
            return {"list": []}
        items = []
        if isinstance(data, dict) and data.get("code") == 1:
            for it in data.get("list") or []:
                try:
                    vid = str(it.get("id", ""))
                    name = str(it.get("name", "")).strip()
                    if not vid or not name:
                        continue
                    items.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": self._u(it.get("pic", "")),
                        "vod_remarks": "",
                    })
                except Exception:
                    continue
        return {"list": items}

    def playerContent(self, flag, ids, vipFlags=None):
        """智能解析播放：解密 player_aaaa 中的真实地址"""
        url = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        url = url.strip()
        if not url:
            return {"parse": 0, "url": "", "header": self._headers()}
        if not url.startswith("http"):
            url = self._u(url)
        try:
            html = self._get(url, referer=self.site)
        except Exception:
            html = ""
        if not html:
            return {"parse": 0, "url": "", "header": self._headers()}
        found, encrypt = "", "0"
        # 直接提取 url/encrypt 字段（兼容嵌套 JSON，避免非贪婪截断）
        m_url = re.search(r'var\s+player_aaaa\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html, re.S)
        m_enc = re.search(r'var\s+player_aaaa\s*=\s*\{.*?"encrypt"\s*:\s*(\d+)', html, re.S)
        if m_url:
            found = m_url.group(1).replace("\\/", "/").strip()
        if m_enc:
            encrypt = m_enc.group(1)
        if not found:
            m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
            if m:
                try:
                    data = json.loads(m.group(1))
                    found = str(data.get("url", "") or "").strip()
                    encrypt = str(data.get("encrypt", "0"))
                except Exception:
                    found = ""
        if encrypt == "1" and found:
            try:
                from urllib.parse import unquote
                found = unquote(found)
            except Exception:
                pass
        elif encrypt == "2" and found:
            try:
                found = base64.b64decode(found).decode("utf-8", "replace").strip()
            except Exception:
                pass
        if found.startswith("//"):
            found = "https:" + found
        elif found and not found.startswith("http"):
            found = self._u(found)
        # m3u8/mp4 直链直接播，网页走解析
        if found and re.search(r'\.(m3u8|mp4)(\?|$)', found):
            return {"parse": 0, "url": found, "header": self._headers(url)}
        return {"parse": 0, "url": found, "header": self._headers(url)}

    def localProxy(self, param):
        return None
