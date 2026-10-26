# -*- coding: utf-8 -*-
"""
云朵影视 — 兼容 FongMi/TV (T3) 与 WebHomeTV/PeekPro (T4) 双壳子
站点: https://ds3xy2yunsa.xyz
API: 自定义接口，需 web-sign 签名头
版本: 1.0.0
"""
import sys
import json
import re
import time
import base64
from urllib.parse import quote, unquote, urljoin

sys.path.append('..')

# ===== 兼容导入 =====
try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, data=None, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.post(url, data=data, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    """云朵影视 Spider — API驱动"""

    def getName(self):
        return "云朵影视"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''

        self.host = "https://ds3xy2yunsa.xyz"
        self.api_base = self.host + "/api.php/web"

        # 签名头（从前端JS提取，所有 api.php 请求必需）
        self.sign = "yda81x6d9ad3c4s"
        self.client_id = "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a"

        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'X-Client': self.client_id,
            'web-sign': self.sign,
            'Referer': self.host + '/',
            'Connection': 'keep-alive',
        }

        self._home_cache = []
        self._home_cache_time = 0
        self._class_list = []
        self._type_map = {}  # type_id -> type_name 映射

    # ========== 网络请求封装 ==========
    def _fetch_json(self, url, timeout=15):
        """GET请求返回JSON"""
        try:
            rsp = self.fetch(url, headers=self.header, timeout=timeout)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            text = rsp.text
            return json.loads(text)
        except Exception:
            return None

    def _fetch_html(self, url, referer=None, timeout=15):
        """GET请求返回HTML文本"""
        headers = dict(self.header)
        headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        if referer:
            headers['Referer'] = referer
        try:
            rsp = self.fetch(url, headers=headers, timeout=timeout)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            return rsp.text
        except Exception:
            return ''

    def _match(self, pattern, text, default='', flags=re.S):
        m = re.search(pattern, text, flags)
        return m.group(1) if m else default

    def _url(self, path):
        if not path:
            return ''
        if path.startswith('http'):
            return path
        if path.startswith('//'):
            return 'https:' + path
        return urljoin(self.host + '/', path)

    def _fix_pic(self, pic):
        if not pic:
            return ''
        if pic.startswith('//'):
            return 'https:' + pic
        if pic.startswith('/'):
            return self.host + pic
        return pic

    def _is_direct_media(self, url):
        url = (url or '').lower()
        return '.m3u8' in url or '.mp4' in url or '.flv' in url or '.mkv' in url

    def _is_official_source(self, url):
        url = (url or '').lower()
        keys = (
            'mgtv.com', 'youku.com', 'iqiyi.com', 'qiyi.com',
            'v.qq.com', 'qq.com', 'bilibili.com', 'le.com',
            'sohu.com', 'pptv.com', '1905.com',
        )
        return any(k in url for k in keys) and not self._is_direct_media(url)

    def _is_encoded_url(self, url):
        """检测是否为站内编码URL（需WASM解码）"""
        if not url:
            return False
        # co_xxx, NSYS-xxx, JD2K-xxx 等编码格式
        encoded_prefixes = ('co_', 'NSYS-', 'JD2K-', 'JD4K-', 'NBY-', 'vwnet_', 'YYNB-', 'CO4K-', 'BBA-')
        return any(url.startswith(p) for p in encoded_prefixes)

    def _resolve_m3u8_child(self, m3u8_url, referer=''):
        """解析master m3u8到子m3u8，提升Exo兼容性"""
        if not m3u8_url or '.m3u8' not in m3u8_url.lower():
            return m3u8_url
        try:
            text = self._fetch_html(m3u8_url, referer=referer or self.host + '/', timeout=15)
            if not text or '#EXTM3U' not in text:
                return m3u8_url
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    for nxt in lines[i + 1:]:
                        if nxt and not nxt.startswith('#'):
                            return urljoin(m3u8_url, nxt)
        except Exception:
            pass
        return m3u8_url

    def _proxy_url(self, media_url, referer=''):
        if not hasattr(self, 'getProxyUrl'):
            return media_url
        try:
            base = self.getProxyUrl()
            return base + '&url=' + quote(media_url, safe='') + '&referer=' + quote(referer or self.host + '/', safe='')
        except Exception:
            return media_url

    # ========== 首页 ==========
    def homeContent(self, filter):
        result = {}

        # 默认分类（兜底）
        default_classes = [
            {'type_id': '1', 'type_name': '电影'},
            {'type_id': '2', 'type_name': '剧集'},
            {'type_id': '3', 'type_name': '动漫'},
            {'type_id': '4', 'type_name': '综艺'},
        ]

        # 从首页API获取分类
        classes = []
        data = self._fetch_json(self.api_base + '/index/home', timeout=15)
        if data and data.get('code') == 200 and data.get('data'):
            d = data['data']
            if d.get('categories'):
                for c in d['categories']:
                    tid = str(c.get('type_id', ''))
                    tname = c.get('type_name', '')
                    classes.append({
                        'type_id': tid,
                        'type_name': tname,
                    })
                    # 建立 type_id -> type_name 映射，categoryContent 用得上
                    if tid and tname:
                        self._type_map[tid] = tname

        if not classes:
            classes = default_classes
            for c in classes:
                self._type_map[c['type_id']] = c['type_name']

        self._class_list = classes
        result['class'] = classes

        if filter:
            result['filters'] = self._build_filters(classes)

        return result

    def _build_filters(self, classes):
        filters = {}
        year_values = [
            {'n': '全部', 'v': ''},
            {'n': '2026', 'v': '2026'}, {'n': '2025', 'v': '2025'},
            {'n': '2024', 'v': '2024'}, {'n': '2023', 'v': '2023'},
            {'n': '2022', 'v': '2022'}, {'n': '2021', 'v': '2021'},
            {'n': '2020', 'v': '2020'}, {'n': '2019', 'v': '2019'},
        ]
        sort_values = [
            {'n': '人气', 'v': 'hits'}, {'n': '时间', 'v': 'time'}, {'n': '评分', 'v': 'score'},
        ]
        area_values = [
            {'n': '全部', 'v': ''},
            {'n': '大陆', 'v': '大陆'}, {'n': '中国大陆', 'v': '中国大陆'},
            {'n': '香港', 'v': '香港'}, {'n': '台湾', 'v': '台湾'},
            {'n': '美国', 'v': '美国'}, {'n': '日本', 'v': '日本'},
            {'n': '韩国', 'v': '韩国'}, {'n': '英国', 'v': '英国'},
            {'n': '法国', 'v': '法国'}, {'n': '印度', 'v': '印度'},
        ]

        # 各分类的子类型
        class_map = {
            '电影': [
                {'n': '全部', 'v': ''}, {'n': '动作', 'v': '动作'}, {'n': '喜剧', 'v': '喜剧'},
                {'n': '爱情', 'v': '爱情'}, {'n': '科幻', 'v': '科幻'}, {'n': '恐怖', 'v': '恐怖'},
                {'n': '悬疑', 'v': '悬疑'}, {'n': '惊悚', 'v': '惊悚'}, {'n': '剧情', 'v': '剧情'},
                {'n': '动画', 'v': '动画'}, {'n': '武侠', 'v': '武侠'}, {'n': '战争', 'v': '战争'},
                {'n': '犯罪', 'v': '犯罪'}, {'n': '奇幻', 'v': '奇幻'}, {'n': '冒险', 'v': '冒险'},
            ],
            '剧集': [
                {'n': '全部', 'v': ''}, {'n': '国产剧', 'v': '国产剧'}, {'n': '港台剧', 'v': '港台剧'},
                {'n': '日韩剧', 'v': '日韩剧'}, {'n': '欧美剧', 'v': '欧美剧'},
                {'n': '悬疑', 'v': '悬疑'}, {'n': '喜剧', 'v': '喜剧'}, {'n': '爱情', 'v': '爱情'},
                {'n': '古装', 'v': '古装'}, {'n': '武侠', 'v': '武侠'}, {'n': '家庭', 'v': '家庭'},
                {'n': '奇幻', 'v': '奇幻'}, {'n': '犯罪', 'v': '犯罪'}, {'n': '战争', 'v': '战争'},
            ],
            '动漫': [
                {'n': '全部', 'v': ''}, {'n': '日漫番', 'v': '日漫番'}, {'n': '国产动漫', 'v': '国产动漫'},
                {'n': '日本动漫', 'v': '日本动漫'}, {'n': '中国动漫', 'v': '中国动漫'},
                {'n': '热血', 'v': '热血'}, {'n': '搞笑', 'v': '搞笑'}, {'n': '恋爱', 'v': '恋爱'},
                {'n': '校园', 'v': '校园'}, {'n': '奇幻', 'v': '奇幻'}, {'n': '科幻', 'v': '科幻'},
                {'n': '冒险', 'v': '冒险'}, {'n': '玄幻', 'v': '玄幻'}, {'n': '战斗', 'v': '战斗'},
            ],
            '综艺': [
                {'n': '全部', 'v': ''}, {'n': '大陆综艺', 'v': '大陆综艺'}, {'n': '港台综艺', 'v': '港台综艺'},
                {'n': '欧美综艺', 'v': '欧美综艺'}, {'n': '真人秀', 'v': '真人秀'},
                {'n': '脱口秀', 'v': '脱口秀'}, {'n': '搞笑', 'v': '搞笑'}, {'n': '游戏', 'v': '游戏'},
                {'n': '音乐', 'v': '音乐'}, {'n': '美食', 'v': '美食'}, {'n': '竞技', 'v': '竞技'},
                {'n': '旅行', 'v': '旅行'}, {'n': '明星', 'v': '明星'}, {'n': '推理', 'v': '推理'},
            ],
        }

        for c in classes:
            tid = c.get('type_id', '')
            tname = c.get('type_name', '')
            if tid:
                cls_values = class_map.get(tname, [{'n': '全部', 'v': ''}])
                filters[tid] = [
                    {'key': 'class', 'name': '类型', 'value': cls_values},
                    {'key': 'area', 'name': '地区', 'value': area_values},
                    {'key': 'year', 'name': '年份', 'value': year_values},
                    {'key': 'sort', 'name': '排序', 'value': sort_values},
                ]
        return filters

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {'list': self._home_cache[:72]}

        videos = []
        seen = set()

        # 从首页API获取推荐视频
        data = self._fetch_json(self.api_base + '/index/home', timeout=15)
        if data and data.get('code') == 200 and data.get('data'):
            d = data['data']
            # 分类下的视频
            if d.get('categories'):
                for cat in d['categories']:
                    for v in cat.get('videos', []):
                        vid = str(v.get('vod_id', ''))
                        if vid and vid not in seen:
                            seen.add(vid)
                            videos.append({
                                'vod_id': vid,
                                'vod_name': v.get('vod_name', ''),
                                'vod_pic': self._fix_pic(v.get('vod_pic', '')),
                                'vod_remarks': v.get('vod_remarks', ''),
                            })
                        if len(videos) >= 72:
                            break
                    if len(videos) >= 72:
                        break
            # 推荐列表
            if len(videos) < 20 and d.get('recommend'):
                for v in d['recommend']:
                    vid = str(v.get('vod_id', ''))
                    if vid and vid not in seen:
                        seen.add(vid)
                        videos.append({
                            'vod_id': vid,
                            'vod_name': v.get('vod_name', ''),
                            'vod_pic': self._fix_pic(v.get('vod_pic', '')),
                            'vod_remarks': v.get('vod_remarks', ''),
                        })
                    if len(videos) >= 72:
                        break

        # 兜底：从各分类第一页获取
        if len(videos) < 20:
            classes = self._class_list or [
                {'type_id': '1', 'type_name': '电影'},
                {'type_id': '2', 'type_name': '剧集'},
                {'type_id': '3', 'type_name': '动漫'},
                {'type_id': '4', 'type_name': '综艺'},
            ]
            for c in classes[:4]:
                tid = c.get('type_id', '')
                if not tid:
                    continue
                cat_data = self._fetch_json(
                    self.api_base + '/filter/vod?type_id=' + tid + '&page=1&sort=hits',
                    timeout=12
                )
                if cat_data and cat_data.get('code') == 200 and cat_data.get('data'):
                    for item in cat_data['data']:
                        vid = str(item.get('vod_id', ''))
                        if vid and vid not in seen:
                            seen.add(vid)
                            videos.append({
                                'vod_id': vid,
                                'vod_name': item.get('vod_name', ''),
                                'vod_pic': self._fix_pic(item.get('vod_pic', '')),
                                'vod_remarks': item.get('vod_remarks', ''),
                            })
                        if len(videos) >= 72:
                            break
                if len(videos) >= 72:
                    break

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {'list': self._home_cache}

    # ========== 分类列表 ==========
    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or '1')
        tid = str(tid or '1')

        # 关键：此站 filter/vod 接口靠 type_name 筛选，type_id 无效
        type_name = self._type_map.get(tid, '')
        if not type_name:
            # 兜底：根据常见ID猜
            fallback = {'1': '电影', '2': '剧集', '3': '动漫', '4': '综艺'}
            type_name = fallback.get(tid, '')

        # 构建参数（type_name 为主筛选条件）
        params = 'type_name=' + quote(type_name) + '&page=' + pg
        if extend:
            sort = extend.get('sort', '') or 'hits'
            area = extend.get('area', '') or ''
            year = extend.get('year', '') or ''
            cls = extend.get('class', '') or ''
            params += '&sort=' + quote(sort)
            if cls:
                params += '&class=' + quote(cls)
            if area:
                params += '&area=' + quote(area)
            if year:
                params += '&year=' + quote(year)
        else:
            params += '&sort=hits'

        url = self.api_base + '/filter/vod?' + params
        data = self._fetch_json(url, timeout=20)

        videos = []
        pagecount = 1

        if data and data.get('code') == 200 and data.get('data'):
            items = data['data']
            if isinstance(items, list):
                for item in items:
                    videos.append(self._format_list_vod(item))

            # 分页：此站 total/pageCount 元数据不可靠（恒返回24/1）
            # 但实际翻页有效，用条数启发式判断
            if len(videos) >= 20:
                pagecount = int(pg) + 1
            else:
                pagecount = int(pg)
        else:
            # 兜底：不带class/area/year再试一次
            url2 = self.api_base + '/filter/vod?type_name=' + quote(type_name) + '&page=' + pg + '&sort=hits'
            data2 = self._fetch_json(url2, timeout=20)
            if data2 and data2.get('code') == 200 and data2.get('data'):
                items = data2['data']
                if isinstance(items, list):
                    for item in items:
                        videos.append(self._format_list_vod(item))
                pagecount = int(pg) + 1 if len(videos) >= 20 else int(pg)

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': len(videos) or 20,
            'total': pagecount * 20,
        }

    def _format_list_vod(self, item):
        """格式化列表页视频信息"""
        return {
            'vod_id': str(item.get('vod_id', '')),
            'vod_name': item.get('vod_name', ''),
            'vod_pic': self._fix_pic(item.get('vod_pic', '')),
            'vod_remarks': item.get('vod_remarks', ''),
        }

    # ========== 详情页 ==========
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0])

        # 1. 获取详情基本信息
        detail_data = self._fetch_json(
            self.api_base + '/vod/get_detail?vod_id=' + vod_id,
            timeout=20
        )

        vod = {
            'vod_id': vod_id,
            'vod_name': '',
            'vod_pic': '',
            'type_name': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': '',
            'vod_play_from': '',
            'vod_play_url': '',
        }

        if detail_data and detail_data.get('code') == 200 and detail_data.get('data'):
            item = detail_data['data'][0] if detail_data['data'] else {}
            vod['vod_name'] = item.get('vod_name', '')
            vod['vod_pic'] = self._fix_pic(item.get('vod_pic', ''))
            vod['type_name'] = item.get('type_name', '')
            vod['vod_year'] = str(item.get('vod_year', ''))
            vod['vod_area'] = item.get('vod_area', '') if isinstance(item.get('vod_area'), str) else ','.join(item.get('vod_area', []))
            vod['vod_remarks'] = item.get('vod_remarks', '')
            vod['vod_actor'] = item.get('vod_actor', '')
            vod['vod_director'] = item.get('vod_director', '')
            # 清理简介HTML标签
            content = item.get('vod_content', '')
            if content:
                content = re.sub(r'<[^>]+>', '', content).strip()
            vod['vod_content'] = content

        # 2. 获取聚合搜索结果（含直链m3u8源）
        agg_data = self._fetch_json(
            self.api_base + '/internal/search_aggregate?vod_id=' + vod_id,
            timeout=20
        )

        play_from_list = []
        play_url_list = []

        if agg_data and agg_data.get('code') == 200 and agg_data.get('data'):
            for src in agg_data['data']:
                decode_status = src.get('decode_status', 0)
                src_name = src.get('site_name', '') or src.get('vod_play_from', '')
                play_url = src.get('vod_play_url', '')
                if not play_url:
                    continue

                if decode_status == 0:
                    # 直链源（m3u8/mp4），直接使用
                    play_from_list.append(src_name)
                    play_url_list.append(play_url)
                elif decode_status == 1:
                    # 官源（qq/youku等），需要解析
                    play_from_list.append(src_name + '(解析)')
                    play_url_list.append(play_url)

        # 3. 如果聚合搜索没有结果，使用详情接口的播放源
        if not play_from_list and detail_data and detail_data.get('code') == 200 and detail_data.get('data'):
            item = detail_data['data'][0] if detail_data['data'] else {}
            pf = item.get('vod_play_from', '')
            pu = item.get('vod_play_url', '')
            if pf and pu:
                from_names = pf.split('$$$')
                url_parts = pu.split('$$$')
                for i, name in enumerate(from_names):
                    if i < len(url_parts):
                        url_part = url_parts[i]
                        if not url_part:
                            continue
                        # 检查是否为直链或官源
                        first_url = url_part.split('#')[0].split('$')[-1] if '$' in url_part else ''
                        if self._is_direct_media(first_url):
                            play_from_list.append(name)
                            play_url_list.append(url_part)
                        elif self._is_official_source(first_url):
                            play_from_list.append(name + '(解析)')
                            play_url_list.append(url_part)
                        # 编码URL(co_xxx等)无法解码，跳过

        # 4. 兜底
        if not play_from_list:
            play_from_list.append('默认线路')
            play_url_list.append('正片$' + vod_id)

        vod['vod_play_from'] = '$$$'.join(play_from_list)
        vod['vod_play_url'] = '$$$'.join(play_url_list)

        return {'list': [vod]}

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or '1')
        url = self.api_base + '/search/index?wd=' + quote(key) + '&page=' + pg + '&limit=20'
        data = self._fetch_json(url, timeout=15)

        videos = []
        if data and data.get('code') == 200 and data.get('data'):
            for item in data['data']:
                videos.append({
                    'vod_id': str(item.get('vod_id', '')),
                    'vod_name': item.get('vod_name', ''),
                    'vod_pic': self._fix_pic(item.get('vod_pic', '')),
                    'vod_remarks': item.get('vod_remarks', ''),
                })

        return {'list': videos}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ========== 播放解析 ==========
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        url = id
        # 如果是纯数字（vod_id兜底），返回parse=1
        if url.isdigit():
            return {
                'parse': 1,
                'playUrl': '',
                'url': self.host + '/',
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
            }

        # 确保是完整URL
        if not url.startswith('http'):
            url = self._url(url)

        # 1. 直链媒体（m3u8/mp4）— 直接返回
        if self._is_direct_media(url):
            # 解析子m3u8提升兼容性
            if '.m3u8' in url.lower():
                url = self._resolve_m3u8_child(url, referer=self.host + '/')
            return {
                'parse': 0,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
                'format': 'application/x-mpegURL' if '.m3u8' in url.lower() else '',
                'contentType': 'application/x-mpegURL' if '.m3u8' in url.lower() else '',
            }

        # 2. 官方源（qq/youku等）— 交给壳子解析
        if self._is_official_source(url):
            return {
                'parse': 1,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
            }

        # 3. 编码URL（co_xxx等）— 无法解码，交给壳子嗅探
        if self._is_encoded_url(url):
            return {
                'parse': 1,
                'playUrl': '',
                'url': self.host + '/',
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
            }

        # 4. 其他URL — 尝试嗅探
        return {
            'parse': 1,
            'playUrl': '',
            'url': url,
            'header': {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
            },
        }

    # ========== 本地代理 ==========
    def localProxy(self, param):
        try:
            import urllib.parse as up
            raw_url = ''
            referer = self.host + '/'
            if isinstance(param, dict):
                raw_url = param.get('url', '') or param.get('u', '')
                referer = param.get('referer', '') or param.get('ref', '') or referer
            elif isinstance(param, str):
                qs = up.parse_qs(param)
                raw_url = qs.get('url', [''])[0] or qs.get('u', [''])[0]
                referer = qs.get('referer', [''])[0] or qs.get('ref', [''])[0] or referer

            media_url = unquote(raw_url) if raw_url else ''
            referer = unquote(referer) if referer else self.host + '/'

            if not media_url:
                return [404, 'text/plain', b'']

            headers = {
                'User-Agent': self.header['User-Agent'],
                'Referer': referer,
            }

            rsp = self.fetch(media_url, headers=headers, timeout=30)
            content = rsp.content if hasattr(rsp, 'content') else rsp.text.encode('utf-8')
            ctype = ''
            if hasattr(rsp, 'headers'):
                ctype = rsp.headers.get('Content-Type', '') or ''

            # m3u8内容处理：改写相对路径为代理URL
            text = ''
            try:
                text = content.decode('utf-8')
            except Exception:
                text = ''
            if '#EXTM3U' in text:
                out = []
                for line in text.splitlines():
                    s = line.strip()
                    if not s or s.startswith('#'):
                        out.append(line)
                    else:
                        abs_url = urljoin(media_url, s)
                        out.append(self._proxy_url(abs_url, referer))
                data = '\n'.join(out).encode('utf-8')
                return [200, 'application/x-mpegURL', data]

            return [200, ctype or 'application/octet-stream', content]
        except Exception:
            return [500, 'text/plain', b'proxy error']

    # ========== 可选接口 ==========
    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv|avi)(\?|$)', url or '', re.I))

    def manualVideoCheck(self):
        return True

    # ========== 清理 ==========
    def destroy(self):
        pass

    def close(self):
        self.destroy()


if __name__ == '__main__':
    spider = Spider()
    spider.init()
    # 测试首页
    # print(json.dumps(spider.homeContent(None), ensure_ascii=False, indent=2)[:2000])
    # 测试分类
    # print(json.dumps(spider.categoryContent('1', '1', None, None), ensure_ascii=False, indent=2)[:2000])
    # 测试搜索
    # print(json.dumps(spider.searchContent('百花杀', False), ensure_ascii=False, indent=2)[:2000])
    # 测试详情
    # print(json.dumps(spider.detailContent('57786'), ensure_ascii=False, indent=2)[:3000])
    # 测试播放
    # print(json.dumps(spider.playerContent('', 'https://cdn.ryplay11.com/20260709/203099_8393bb05/index.m3u8', ''), ensure_ascii=False, indent=2))
