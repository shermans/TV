# -*- coding: utf-8 -*-
# ============================================================
# 🌐｜EcoHub｜影视 · TVBox Python 爬虫
# 数据源：eco.fe-spark.cn（前后端分离，纯 JSON API）
# 功能：分类浏览 / 全站搜索 / 多源播放 / 多UA轮换
# ============================================================
import re, json
from urllib.parse import quote
try:
    import requests as _requests
except Exception:
    _requests = None

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; M2007J3SC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
]

API = "https://eco.fe-spark.cn/api"

# 精选分类（置顶）+ 站内导航分类
CATES = [
    ("new", "🆕｜最新｜更新"),
    ("horror", "😱｜恐怖｜电影"),
    ("action", "💥｜动作｜电影"),
    ("fantasy", "🔮｜奇幻｜电影"),
    ("1", "📺｜电视｜剧集"),
    ("9", "🎬｜电影｜综合"),
    ("20", "🎨｜动漫｜综合"),
    ("24", "🎤｜综艺｜综合"),
    ("29", "⚽｜体育｜赛事"),
    ("34", "⚡｜短剧｜热门"),
    ("44", "🎞️｜预告｜片花"),
]


class Spider:
    def __init__(self):
        self.site = "https://eco.fe-spark.cn"
        self.name = "🌐｜EcoHub｜影视"
        self._ua_idx = 0
        self.s = _requests.Session() if _requests else None

    def getName(self):
        return self.name

    def _next_ua(self):
        ua = USER_AGENTS[self._ua_idx % len(USER_AGENTS)]
        self._ua_idx += 1
        return ua

    def _headers(self, referer=None):
        return {
            "User-Agent": self._next_ua(),
            "Referer": referer or self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "application/json, text/plain, */*",
        }

    def _api(self, path, referer=None):
        url = API + path
        h = self._headers(referer)
        try:
            if self.s is not None:
                r = self.s.get(url, headers=h, timeout=15)
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _item(self, it):
        pic = it.get("picture") or ""
        if pic.startswith("http://"):
            pic = "https://" + pic[7:]
        area = it.get("area") or ""
        year = it.get("year") or ""
        remarks = ""
        if area:
            remarks += f"🌍{area}"
        if year and year != "0":
            remarks += f" 📅{year}"
        return {
            "vod_id": str(it.get("id", "")),
            "vod_name": it.get("name", ""),
            "vod_pic": pic,
            "vod_remarks": remarks.strip(),
        }

    def init(self, extend=""):
        pass

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=None):
        cats = [{"type_id": cid, "type_name": name} for cid, name in CATES]
        # 首页推荐
        d = self._api("/index")
        vod_list = []
        try:
            for it in d.get("data", {}).get("filmList", [])[:12]:
                vod_list.append(self._item(it))
        except Exception:
            pass
        return {"class": cats, "list": vod_list}

    def homeVideoContent(self):
        d = self._api("/dailyUpdates")
        vod_list = []
        try:
            for it in d.get("data", {}).get("list", [])[:12]:
                vod_list.append(self._item(it))
        except Exception:
            pass
        return {"list": vod_list}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        tid = str(tid).strip()
        items, pagecount = [], pg

        if tid == "new":
            d = self._api("/dailyUpdates")
            lst = d.get("data", {}).get("list", [])
            items = [self._item(it) for it in lst]
        elif tid in ("horror", "action", "fantasy"):
            cls = {"horror": "恐怖", "action": "动作", "fantasy": "奇幻"}[tid]
            d = self._api(f"/filmClassifySearch?Pid=9&class={quote(cls)}&page={pg}")
            lst = d.get("data", {}).get("list", [])
            items = [self._item(it) for it in lst]
            page = d.get("data", {}).get("page", {})
            total = page.get("total", 0)
            pagecount = max(pg, (total + 47) // 48) if total else pg
        else:
            d = self._api(f"/filmClassifySearch?Pid={tid}&page={pg}")
            lst = d.get("data", {}).get("list", [])
            items = [self._item(it) for it in lst]
            page = d.get("data", {}).get("page", {})
            total = page.get("total", 0)
            pagecount = max(pg, (total + 47) // 48) if total else pg

        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 48, "total": pagecount * 48}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids)
        d = self._api(f"/filmPlayInfo?id={vid}")
        data = d.get("data", {})
        det = data.get("detail", {})
        if not det:
            return {"list": []}
        play_from, play_url = [], []
        for src in det.get("list", []):
            sname = src.get("name", "默认")
            sid = src.get("id", "")
            eps = []
            for i, ep in enumerate(src.get("linkList", [])):
                ename = ep.get("episode") or f"第{i+1}集"
                eps.append(f"{ename}${vid}@@{sid}@@{i}")
            if eps:
                play_from.append(sname)
                play_url.append("#".join(eps))
        pic = det.get("picture") or ""
        if pic.startswith("http://"):
            pic = "https://" + pic[7:]
        vod = {
            "vod_id": str(vid),
            "vod_name": det.get("name", ""),
            "vod_pic": pic,
            "vod_year": str(det.get("year", "")),
            "vod_area": det.get("area", ""),
            "vod_actor": det.get("actor", ""),
            "vod_director": det.get("director", ""),
            "vod_content": det.get("blurb", ""),
            "vod_remarks": det.get("remarks", ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        d = self._api(f"/searchFilm?keyword={quote(str(key))}&current={pg}&pageSize=24")
        items = []
        try:
            for it in d.get("data", {}).get("list", []):
                items.append(self._item(it))
        except Exception:
            pass
        return {"list": items}

    def playerContent(self, flag, ids, vipFlags=None):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        parts = raw.split("@@")
        if len(parts) != 3:
            return {"parse": 0, "url": "", "header": self._headers()}
        vid, source, ep = parts
        d = self._api(f"/filmPlayInfo?id={vid}&playFrom={quote(source)}&episode={ep}")
        link = ""
        try:
            link = d.get("data", {}).get("current", {}).get("link", "")
        except Exception:
            pass
        if link.startswith("//"):
            link = "https:" + link
        elif link.startswith("http://"):
            link = "https://" + link[7:]
        # m3u8/mp4 直链直接播
        if link and re.search(r"\.(m3u8|mp4)(\?|$)", link):
            return {"parse": 0, "url": link, "header": self._headers(self.site)}
        return {"parse": 0, "url": link, "header": self._headers(self.site)}

    def localProxy(self, param):
        return None
