# coding=utf-8
"""
目标站: 4KMP
首页: https://4kmp.com
"""
import re
import urllib.parse
from bs4 import BeautifulSoup
import sys
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://4kmp.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Referer": self.host
        }

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        try:
            classes = [
                {"type_name": "电影", "type_id": "movie"},
                {"type_name": "电视剧", "type_id": "tv"}
            ]
            result["class"] = classes
            print(f"[homeContent] 返回分类数量: {len(classes)}")
        except Exception as e:
            print(f"[homeContent] 异常: {e}")
        return result

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            cat_map = {"movie": "movie", "tv": "tv"}
            cat = cat_map.get(tid, "movie")
            if pg == 1:
                url = f"{self.host}/{cat}/"
            else:
                url = f"{self.host}/{cat}/page-{pg}.html"
            res = self.fetch(url, headers=self.headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            videos = []
            items = soup.select('.NTMitem')
            if not items:
                items = soup.select('.RTMitem')
            for item in items:
                try:
                    a_tag = item.select_one('.title a')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')
                    if not href:
                        continue
                    title = a_tag.select_one('h2')
                    vod_name = title.text.strip() if title else a_tag.get('title', '').strip()
                    if not vod_name:
                        continue
                    img = item.select_one('img')
                    pic = img.get('src', '') if img else ''
                    videos.append({
                        "vod_id": href,
                        "vod_name": vod_name,
                        "vod_pic": urllib.parse.urljoin(self.host, pic) if pic else ""
                    })
                except:
                    continue
            pagecount = 1
            pn_span = soup.select_one('.page-number')
            if pn_span:
                m = re.search(r'(\d+)/(\d+)', pn_span.text)
                if m:
                    pagecount = int(m.group(2))
            print(f"[categoryContent] 分类 {tid} 第{pg}页 匹配 {len(videos)} 条")
            return {"list": videos, "page": pg, "pagecount": pagecount, "limit": len(videos), "total": len(videos) * pagecount if pagecount else len(videos)}
        except Exception as e:
            print(f"[categoryContent] 异常: {e}")
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids.split(",")[0]
            url = urllib.parse.urljoin(self.host, vod_id) if vod_id.startswith("/") else vod_id
            res = self.fetch(url, headers=self.headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            title_div = soup.select_one('#MainContent_titleh12 div')
            vod_name = title_div.text.strip() if title_div else ""
            if not vod_name:
                h1 = soup.select_one('h1')
                vod_name = h1.text.strip() if h1 else ""
            poster_img = soup.select_one('.poster img')
            vod_pic = poster_img.get('src', '') if poster_img else ""
            source_tag = soup.select_one('video source')
            play_from = ""
            play_url = ""
            if source_tag:
                src = source_tag.get('src', '')
                if src:
                    play_from = "4KMP"
                    play_url = f"原画${urllib.parse.urljoin(self.host, src) if src.startswith('/') else src}"
            rtlist = soup.select('#rtlist a[href]')
            ep_list = []
            for a in rtlist:
                href = a.get('href', '')
                if not href or ('/tv/' not in href and '/movie/' not in href):
                    continue
                span = a.select_one('span')
                ep_name = span.text.strip() if span else a.get('title', '').strip()
                if not ep_name:
                    continue
                ep_list.append(f"{ep_name}${urllib.parse.urljoin(self.host, href)}")
            if ep_list:
                if play_from:
                    play_from = "4KMP$$$剧集列表"
                    play_url = f"{play_url}$$${'#'.join(ep_list)}"
                else:
                    play_from = "4KMP"
                    play_url = "#".join(ep_list)
            vod = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": urllib.parse.urljoin(self.host, vod_pic) if vod_pic else "",
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }
            print(f"[detailContent] {vod_name} 源:{1 if play_from else 0}")
            return {"list": [vod]}
        except Exception as e:
            print(f"[detailContent] 异常: {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
            url = f"{self.host}/s?k={urllib.parse.quote(key)}"
            res = self.fetch(url, headers=self.headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            videos = []
            items = soup.select('.NTMitem')
            if not items:
                items = soup.select('.RTMitem')
            for item in items:
                try:
                    a_tag = item.select_one('.title a')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')
                    title = a_tag.select_one('h2')
                    vod_name = title.text.strip() if title else a_tag.get('title', '').strip()
                    if not vod_name:
                        continue
                    img = item.select_one('img')
                    pic = img.get('src', '') if img else ''
                    videos.append({
                        "vod_id": href,
                        "vod_name": vod_name,
                        "vod_pic": urllib.parse.urljoin(self.host, pic) if pic else ""
                    })
                except:
                    continue
            print(f"[searchContent] 搜索 {key} 结果 {len(videos)} 条")
            return {"list": videos, "page": pg, "pagecount": 1, "limit": len(videos), "total": len(videos)}
        except Exception as e:
            print(f"[searchContent] 异常: {e}")
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        try:
            if ".m3u8" in id or ".mp4" in id:
                return {"parse": 0, "playUrl": "", "url": id, "header": self.headers}
            if id.startswith("/"):
                url = urllib.parse.urljoin(self.host, id)
                res = self.fetch(url, headers=self.headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                source_tag = soup.select_one('video source')
                if source_tag:
                    src = source_tag.get('src', '')
                    if src:
                        play_url = urllib.parse.urljoin(self.host, src) if src.startswith("/") else src
                        print(f"[playerContent] 播放: {flag} -> {play_url[:50]}...")
                        return {"parse": 0, "playUrl": "", "url": play_url, "header": self.headers}
            print(f"[playerContent] 播放: {flag} 未解析到链接")
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}
        except Exception as e:
            print(f"[playerContent] 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}