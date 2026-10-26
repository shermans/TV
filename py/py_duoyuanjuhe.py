# coding=utf-8
# =====================================================================
#  TVBox / 影视壳  ·  多源聚合增强版 py 站源
# ---------------------------------------------------------------------
#  【站点来源】从原源包 560+ 个源中实测筛选, 全部为在线验证可用的站点:
#     量子资源 / 飞快影视 / 奇点影视 / 非凡资源 / 电影天堂 / 麒麟影视 / 看客影视 / 次元动漫
#
#  【功能特性】
#   1. 多源聚合    —— 8 大采集站合一, 分类浏览 + 全站搜索
#   2. 搜索合并    —— 同名影片自动合并为单条结果, 详情页多线路(多站点)切换
#   3. 详细分类    —— 最新电影/最新剧集/最新动漫/最新综艺 +
#                     动作/恐怖/科幻/喜剧/爱情/战争/剧情/犯罪/惊悚/悬疑/奇幻/武侠/冒险 +
#                     国产/香港/台湾/韩国/日本/欧美/泰国剧 + 动漫/综艺/短剧/纪录片等 40+ 分类
#   4. 智能播放    —— 自动挑选 m3u8/mp4 直链线路; /share/ 分享页自动解析出直链;
#                     网页播放页自动转壳内解析; 返回格式(format)与请求头(header)
#   5. UA 轮换     —— 多 User-Agent 池自动轮换, 降低被拦截概率
#   6. 封面优化    —— 相对路径补全 / 多封面智能挑选 / http 自动升级 https / 剔除无效占位图
#   7. 去跑马灯    —— 剧情简介与备注自动清洗公告/滚动字幕/广告/外链
#   8. 容灾与加速  —— 站点多域名自动切换, 请求结果多级缓存
#
#  【使用】TVBox / 影视仓 / OK影视 等 → 设置 → 点播源 → 添加本地 py 源, 选择本文件
#  【更新】2026-10-13  · 全部接口经真实请求验证
# =====================================================================

import re
import sys
import json
import time
import random

try:
    from urllib.parse import quote, unquote, urlparse
except Exception:
    from urllib import quote, unquote  # noqa
    from urlparse import urlparse      # noqa

sys.path.append('..')
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass

try:
    import requests as _requests
except Exception:
    _requests = None

if _requests is not None:
    try:
        _requests.packages.urllib3.disable_warnings()
    except Exception:
        pass

try:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    _HAS_POOL = True
except Exception:
    ThreadPoolExecutor = None
    as_completed = None
    _HAS_POOL = False


# =====================================================================
#  一、站点注册表 (均经实测验证; alts 为备用域名, 失效自动切换)
# =====================================================================
SITES = {
    'lz':   {'name': '量子资源', 'api': 'https://cj.lziapi.com/api.php/provide/vod/',
             'alts': [], 'ref': 'https://cj.lziapi.com/'},
    'fk':   {'name': '飞快影视', 'api': 'https://feikuai.in/api.php/provide/vod/',
             'alts': [], 'ref': 'https://feikuai.in/'},
    'qd':   {'name': '奇点影视', 'api': 'https://qidianyingshi.net/api.php/provide/vod/',
             'alts': ['https://www.qdys2.cc/api.php/provide/vod/', 'https://www.yxxq41.cc/api.php/provide/vod/'],
             'ref': 'https://qidianyingshi.net/'},
    'ff':   {'name': '非凡资源', 'api': 'https://ffzy.tv/api.php/provide/vod/',
             'alts': ['https://ffzy5.tv/api.php/provide/vod/'], 'ref': 'https://ffzy.tv/'},
    'dy':   {'name': '电影天堂', 'api': 'http://caiji.dyttzyapi.com/api.php/provide/vod/',
             'alts': ['http://dyttzy2.tv/api.php/provide/vod/'], 'ref': 'http://caiji.dyttzyapi.com/'},
    'ql':   {'name': '麒麟影视', 'api': 'https://www.qlys.cc/api.php/provide/vod/',
             'alts': [], 'ref': 'https://www.qlys.cc/'},
    'seen': {'name': '看客影视', 'api': 'https://see95.seesee.sbs/api.php/provide/vod/',
             'alts': [], 'ref': 'https://see95.seesee.sbs/'},
    'jc':   {'name': '次元动漫', 'api': 'https://www.jciyuan.com/api.php/provide/vod/',
             'alts': [], 'ref': 'https://www.jciyuan.com/'},
}
NAME2CODE = dict((cfg['name'], code) for code, cfg in SITES.items())

# 搜索顺序 (优先级从高到低)
SEARCH_ORDER = ['lz', 'fk', 'qd', 'ff', 'dy', 'ql', 'seen', 'jc']

# =====================================================================
#  二、分类表  (按国家地区 + 最新/恐怖/动作/最新电影 等编排)
#      格式: (分类名, [(站点代码, 站点分类ID), ...])   —— 表内为已验证的容灾链
# =====================================================================
CATS = [
    ('🔥 最新电影',   [('qd', 1), ('fk', 1), ('lz', 1)]),
    ('🔥 最新剧集',   [('qd', 2), ('fk', 2), ('dy', 2), ('lz', 2)]),
    ('🔥 最新动漫',   [('qd', 4), ('ff', 4), ('fk', 4), ('lz', 4)]),
    ('🔥 最新综艺',   [('qd', 3), ('ql', 5), ('fk', 3), ('lz', 3)]),
    ('🎬 电影大片',   [('dy', 6), ('ff', 6), ('ql', 10), ('lz', 6)]),
    ('🎭 动作片',     [('lz', 6), ('fk', 7), ('ff', 6), ('dy', 6), ('ql', 10), ('seen', 21)]),
    ('😱 恐怖片',     [('lz', 10), ('fk', 11), ('ff', 10), ('dy', 10), ('ql', 11), ('seen', 25)]),
    ('🚀 科幻片',     [('lz', 9), ('fk', 8), ('ff', 9), ('dy', 9), ('ql', 12), ('seen', 24)]),
    ('😂 喜剧片',     [('lz', 7), ('fk', 6), ('ff', 7), ('dy', 7), ('ql', 15), ('seen', 22)]),
    ('💕 爱情片',     [('lz', 8), ('fk', 9), ('ff', 8), ('dy', 8), ('ql', 14), ('seen', 23)]),
    ('⚔️ 战争片',     [('lz', 12), ('fk', 10), ('ff', 12), ('dy', 12), ('ql', 13), ('seen', 27)]),
    ('🎞️ 剧情片',     [('lz', 11), ('fk', 12), ('ff', 11), ('dy', 11), ('ql', 16), ('seen', 26)]),
    ('🕵️ 犯罪片',     [('seen', 29)]),
    ('🔪 惊悚片',     [('seen', 28)]),
    ('🧩 悬疑片',     [('seen', 32)]),
    ('🐉 奇幻片',     [('seen', 34)]),
    ('🥋 武侠片',     [('seen', 33)]),
    ('🗺️ 冒险片',     [('seen', 30)]),
    ('📼 精选短剧',   [('lz', 46), ('fk', 32), ('ql', 3), ('qd', 39), ('ff', 36)]),
    ('🇨🇳 国产剧',    [('lz', 13), ('fk', 13), ('ff', 13), ('dy', 13), ('ql', 6), ('seen', 38)]),
    ('🇭🇰 香港剧',    [('lz', 14), ('fk', 14), ('ff', 14), ('dy', 14), ('seen', 39)]),
    ('🏝️ 台湾剧',     [('lz', 21), ('fk', 14), ('ff', 21), ('dy', 21)]),
    ('🇰🇷 韩国剧',    [('lz', 15), ('fk', 15), ('ff', 15), ('dy', 15), ('seen', 41)]),
    ('🇯🇵 日本剧',    [('lz', 22), ('fk', 15), ('ff', 22), ('dy', 22), ('seen', 41)]),
    ('🌍 欧美剧',     [('lz', 16), ('fk', 16), ('ff', 16), ('dy', 16), ('ql', 9), ('seen', 40)]),
    ('🇹🇭 泰国剧',    [('lz', 24), ('ff', 24), ('dy', 24), ('ql', 22)]),
    ('🌏 海外剧',     [('lz', 23), ('ff', 23), ('dy', 23)]),
    ('🎨 国产动漫',   [('jc', 21), ('lz', 29), ('fk', 25), ('ff', 29), ('dy', 29)]),
    ('🗾 日本动漫',   [('jc', 20), ('lz', 30), ('fk', 27), ('ff', 30), ('dy', 30)]),
    ('🌐 欧美动漫',   [('lz', 31), ('fk', 28), ('ff', 31), ('dy', 31)]),
    ('🎎 港台动漫',   [('lz', 32), ('fk', 26), ('ff', 32), ('dy', 32)]),
    ('🎬 动漫剧场版', [('jc', 26), ('lz', 49)]),
    ('🎤 大陆综艺',   [('lz', 25), ('fk', 20)]),
    ('🎤 港台综艺',   [('lz', 26), ('fk', 21)]),
    ('🎤 日韩综艺',   [('lz', 27), ('fk', 23), ('ff', 27)]),
    ('🎤 欧美综艺',   [('lz', 28), ('fk', 22), ('ff', 28)]),
    ('🎥 纪录片',     [('lz', 20), ('fk', 34), ('ff', 20), ('dy', 20), ('ql', 17), ('seen', 35)]),
    ('🎬 电影解说',   [('lz', 35)]),
    ('🍿 Netflix',    [('seen', 53)]),
    ('🏀 体育',       [('qd', 53), ('lz', 36)]),
]

# =====================================================================
#  三、多 User-Agent 轮换池
# =====================================================================
UA_POOL = [
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; U; Android 12; zh-cn; Mi 10 Build/SKQ1.211006.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/89.0.4389.116 Mobile Safari/537.36 XiaoMi/MiuiBrowser/16.2.20',
    'Mozilla/5.0 (Linux; Android 9; SHIELD Android TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'okhttp/4.12.0',
]

# 播放后缀识别
_DIRECT_RE = re.compile(r'\.(m3u8|mp4|flv|mkv|avi|mov|m4u8|ts)(?:[?#/]|$)', re.I)
# 跑马灯/广告清洗词
_JUNK_RE = re.compile(
    r'(跑马灯|滚动字幕|滚动公告|【公告】|公告[:：]|加群|加微信|微信号[:：]?[^\s，。]*|QQ群|TG群|'
    r'Telegram群|点击下载|下载APP|APP下载|访问官网|复制到浏览器|请复制到浏览器|永久域名|发布页|'
    r'最新地址|备用网址|回家不迷路|收藏不迷路|收藏本页|收藏网址)',
    re.I)
_URL_RE = re.compile(r'(?:https?://|www\.)[^\s，。、）】]+', re.I)
_DOMAIN_RE = re.compile(
    r'(?<![a-z0-9\-\.])[a-z0-9][a-z0-9\-]{0,60}\.'
    r'(?:com|net|org|tv|cc|xyz|top|vip|cn|me|app|site|club|live|fun|online|ink|icu|la|us|io|info|biz)'
    r'(?:/[^\s，。、）】]*)?',
    re.I)
_HTML_RE = re.compile(r'<[^>]+>')
_ENT_RE = re.compile(r'&[a-zA-Z]+;|&#\d+;')


class Spider(_BaseSpider):
    """多源聚合增强版 —— TVBox / 影视壳 py 站源"""

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def init(self, extend=''):
        self._ready = False
        self._boot(extend)
        return

    def _boot(self, extend=''):
        if getattr(self, '_ready', False):
            return
        self.name = '多源聚合增强版'
        self.timeout = 8          # 默认请求超时(秒)
        self.ua_rotate = True     # UA 轮换开关
        self._ua_idx = random.randint(0, len(UA_POOL) - 1)
        self._cache = {}          # 接口缓存 {(site,params): (过期时间, 数据)}
        self._wbase = {}          # 每站当前可用域名 (容灾记忆)
        # 可选: extend 传 JSON 可微调 (例: {"timeout":10,"ua_rotate":false})
        try:
            if extend and isinstance(extend, str) and extend.strip().startswith('{'):
                cfg = json.loads(extend)
                self.timeout = int(cfg.get('timeout', self.timeout))
                self.ua_rotate = bool(cfg.get('ua_rotate', True))
        except Exception:
            pass
        self._ready = True

    # ------------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------------
    def _ua(self):
        """多 UA 轮换"""
        if not self.ua_rotate:
            return UA_POOL[0]
        self._ua_idx = (self._ua_idx + 1) % len(UA_POOL)
        return UA_POOL[self._ua_idx]

    def _rtext(self, r):
        if r is None:
            return None
        if isinstance(r, str):
            return r
        if isinstance(r, bytes):
            return r.decode('utf-8', 'ignore')
        t = getattr(r, 'text', None)
        if callable(t):
            try:
                t = t()
            except Exception:
                t = None
        if t is not None:
            try:
                return t if isinstance(t, str) else str(t)
            except Exception:
                pass
        c = getattr(r, 'content', None)
        if c is not None:
            try:
                return c.decode('utf-8', 'ignore') if isinstance(c, bytes) else str(c)
            except Exception:
                pass
        return None

    def _req(self, url, ref=None, timeout=None, ua=None):
        """统一请求: 优先壳内 fetch(安卓 OkHttp), 失败回退 requests"""
        hdr = {
            'User-Agent': ua or self._ua(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        if ref:
            hdr['Referer'] = ref
        t = timeout or self.timeout
        fetch = getattr(self, 'fetch', None)
        if callable(fetch):
            try:
                try:
                    r = fetch(url, headers=hdr, timeout=t)
                except TypeError:
                    r = fetch(url, headers=hdr)
                txt = self._rtext(r)
                if txt is not None:
                    return txt
            except Exception:
                pass
        if _requests is not None:
            try:
                r = _requests.get(url, headers=hdr, timeout=t, verify=False)
                try:
                    r.encoding = 'utf-8'
                except Exception:
                    pass
                return r.text
            except Exception:
                pass
        return ''

    def _json(self, txt):
        """容错 JSON 解析"""
        if not txt:
            return None
        s = txt.strip().lstrip('\ufeff')
        try:
            return json.loads(s)
        except Exception:
            pass
        m = re.search(r'\{.*\}', s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None

    def _cget(self, key):
        try:
            v = self._cache.get(key)
            if v and v[0] > time.time():
                return v[1]
        except Exception:
            pass
        return None

    def _cset(self, key, val, ttl):
        try:
            if len(self._cache) > 400:
                self._cache = dict(sorted(self._cache.items(), key=lambda x: x[1][0])[-200:])
            self._cache[key] = (time.time() + ttl, val)
        except Exception:
            pass

    def _jget(self, site, params, timeout=None, ttl=0):
        """站点 API 请求 (含域名容灾 + 缓存); params 例: 'ac=detail&t=1&pg=1'"""
        ck = site + '|' + params
        if ttl:
            hit = self._cget(ck)
            if hit is not None:
                return hit
        cfg = SITES[site]
        bases = []
        for b in [self._wbase.get(site), cfg['api']] + list(cfg.get('alts') or []):
            if b and b not in bases:
                bases.append(b)
        for base in bases:
            txt = self._req(base + '?' + params, ref=cfg['ref'], timeout=timeout)
            d = self._json(txt)
            if isinstance(d, dict) and ('list' in d or 'class' in d):
                self._wbase[site] = base
                if ttl:
                    self._cset(ck, d, ttl)
                return d
        return None

    def _int(self, v, d=0):
        try:
            return int(v)
        except Exception:
            return d

    def _is_direct(self, u):
        """判断是否视频直链 (m3u8/mp4/flv 等)"""
        if not u:
            return False
        u = str(u).lower()
        if not u.startswith('http'):
            return False
        if 'index.m3u8' in u:
            return True
        return bool(_DIRECT_RE.search(u))

    # ------------------------------------------------------------------
    # 内容清洗 (去跑马灯 / 广告 / 外链)
    # ------------------------------------------------------------------
    def _clean(self, s, n=0):
        try:
            s = str(s or '')
            s = _HTML_RE.sub(' ', s)
            s = _ENT_RE.sub(' ', s)
            s = _JUNK_RE.sub(' ', s)
            s = _URL_RE.sub(' ', s)
            s = _DOMAIN_RE.sub(' ', s)
            s = re.sub(r'\s+', ' ', s).strip()
            if n and len(s) > n:
                s = s[:n]
            return s
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # 封面优化 (相对路径补全 / 多封面挑选 / http升级 / 剔除占位图)
    # ------------------------------------------------------------------
    def _fix_pic(self, site, pic):
        try:
            pic = (pic or '').strip()
            if not pic:
                return ''
            chosen = ''
            for p in [x.strip() for x in pic.split('#') if x.strip()]:
                if '.test.com' in p:      # 采集站占位图, 剔除
                    continue
                chosen = p
                break
            if not chosen:
                return ''
            if chosen.startswith('//'):
                chosen = 'https:' + chosen
            elif chosen.startswith('/'):  # 相对路径 -> 补全站点域名
                api = self._wbase.get(site) or SITES[site]['api']
                m = re.match(r'https?://[^/]+', api)
                chosen = (m.group(0) if m else '') + chosen
            if chosen.startswith('http://'):
                chosen = 'https://' + chosen[7:]
            return chosen
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # 列表项构造
    # ------------------------------------------------------------------
    def _mk(self, site, it):
        if not isinstance(it, dict):
            it = {}
        vid = str(it.get('vod_id') or '').strip()
        rm = self._clean(it.get('vod_remarks'), 60)
        return {
            'vod_id': site + ':' + vid,
            'vod_name': self._clean(it.get('vod_name'), 90),
            'vod_pic': self._fix_pic(site, it.get('vod_pic')),
            'vod_remarks': rm,
            'vod_year': str(it.get('vod_year') or ''),
            'type_name': str(it.get('type_name') or ''),
        }

    # ------------------------------------------------------------------
    # 播放组智能挑选 (优先 m3u8 直链组)
    # ------------------------------------------------------------------
    def _best_group(self, pf, pu):
        """从 vod_play_from / vod_play_url 中挑选最佳播放组 -> (组名, [(集名,链接)], 是否直链)"""
        if not pf or not pu:
            return ('', [], False)
        names = str(pf).split('$$$')
        groups = str(pu).split('$$$')
        best = ('', [], False)
        best_score = -1
        best_len = -1
        for i, g in enumerate(groups):
            nm = (names[i] if i < len(names) else '').strip()
            eps = []
            for part in g.split('#'):
                part = part.strip()
                if not part:
                    continue
                if '$' in part:
                    ep, u = part.split('$', 1)
                else:
                    ep, u = '', part
                u = u.strip()
                if u.startswith('http') or u.startswith('/'):
                    eps.append((ep.strip(), u))
            if not eps:
                continue
            direct = any(self._is_direct(u) for _, u in eps[:4])
            score = 0
            if direct:
                score += 3
            if 'm3u8' in nm.lower():
                score += 2
            if not direct and '/share/' in ' '.join(u for _, u in eps[:3]):
                score += 1
            if score > best_score or (score == best_score and len(eps) > best_len):
                best_score = score
                best_len = len(eps)
                best = (nm, eps, direct)
        return best

    def _epstr(self, eps):
        out = []
        for ep, u in eps:
            out.append((ep + '$' + u) if ep else u)
        return '#'.join(out)

    # ------------------------------------------------------------------
    # 首页 (分类导航 + 最新推荐)
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        self._boot()
        classes = []
        for i, item in enumerate(CATS):
            classes.append({'type_id': 'c%d' % i, 'type_name': item[0]})
        lst = []
        try:
            d = self._jget('qd', 'ac=detail&t=1&pg=1', timeout=6, ttl=300)
            for it in (d.get('list') or [])[:12] if d else []:
                lst.append(self._mk('qd', it))
        except Exception:
            pass
        return {'class': classes, 'filters': {}, 'list': lst}

    # 兼容个别壳: 首页视频内容
    def homeVideoContent(self):
        self._boot()
        try:
            d = self._jget('qd', 'ac=detail&t=2&pg=1', timeout=6, ttl=300)
            return {'list': [self._mk('qd', it) for it in (d.get('list') or [])[:12]] if d else []}
        except Exception:
            return {'list': []}

    # ------------------------------------------------------------------
    # 分类浏览
    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        self._boot()
        pg = self._int(pg, 1) or 1
        empty = {'page': pg, 'pagecount': 0, 'limit': 20, 'total': 0, 'list': []}
        try:
            idx = self._int(str(tid).lstrip('cC'))
        except Exception:
            return empty
        if idx < 0 or idx >= len(CATS):
            return empty
        chains = CATS[idx][1]
        for site, cid in chains:
            d = self._jget(site, 'ac=detail&t=%d&pg=%d' % (cid, pg), ttl=240)
            if not d:
                continue
            lst = [self._mk(site, it) for it in (d.get('list') or [])]
            if not lst:
                if pg > 1 or d.get('list') is not None:
                    # 有效站点但该页为空: 不再降级, 直接返回空页
                    if pg == 1 and not (d.get('list') or []):
                        continue
                    return {'page': pg, 'pagecount': pg, 'limit': 20, 'total': 0, 'list': []}
                continue
            return {
                'page': self._int(d.get('page'), pg) or pg,
                'pagecount': self._int(d.get('pagecount'), 9999) or 9999,
                'limit': self._int(d.get('limit'), 20) or 20,
                'total': self._int(d.get('total'), len(lst)),
                'list': lst,
            }
        return empty

    # ------------------------------------------------------------------
    # 全站搜索 (8 站并发 + 同名合并)
    # ------------------------------------------------------------------
    def searchContent(self, key, quick=False, pg='1'):
        self._boot()
        pg = self._int(pg, 1) or 1
        key = (key or '').strip()
        empty = {'page': pg, 'pagecount': 0, 'limit': 20, 'total': 0, 'list': []}
        if not key:
            return empty
        q = quote(key)

        def worker(site):
            try:
                d = self._jget(site, 'ac=detail&wd=' + q + '&pg=%d' % pg, timeout=7, ttl=120)
                return site, (d.get('list') or []) if d else []
            except Exception:
                return site, []

        out = []
        if _HAS_POOL:
            with ThreadPoolExecutor(max_workers=min(8, len(SEARCH_ORDER))) as ex:
                futs = [ex.submit(worker, s) for s in SEARCH_ORDER]
                for f in as_completed(futs):
                    try:
                        out.append(f.result())
                    except Exception:
                        pass
        else:
            for s in SEARCH_ORDER:
                out.append(worker(s))
        out.sort(key=lambda t: SEARCH_ORDER.index(t[0]) if t[0] in SEARCH_ORDER else 99)

        merged = {}
        ordered = []
        for site, items in out:
            for it in items:
                vid = str(it.get('vod_id') or '').strip()
                name = self._clean(it.get('vod_name'), 90)
                if not vid or not name:
                    continue
                nk = self._norm(name)
                if nk in merged:
                    g = merged[nk]
                    if len(g) < 5 and not any(m[0] == site for m in g):
                        g.append((site, vid, it))
                    continue
                grp = [(site, vid, it)]
                merged[nk] = grp
                ordered.append(grp)

        lst = []
        for grp in ordered[:80]:
            site0, vid0, it0 = grp[0]
            item = self._mk(site0, it0)
            if len(grp) > 1:
                item['vod_id'] = 'AGG~' + '~'.join('%s:%s' % (s, v) for s, v, _ in grp)
            if not item.get('vod_pic'):
                for s2, _v2, it2 in grp[1:]:
                    p = self._fix_pic(s2, it2.get('vod_pic'))
                    if p:
                        item['vod_pic'] = p
                        break
            if not item.get('vod_remarks'):
                for s2, _v2, it2 in grp[1:]:
                    r2 = self._clean(it2.get('vod_remarks'), 60)
                    if r2:
                        item['vod_remarks'] = r2
                        break
            lst.append(item)
        return {'page': pg, 'pagecount': pg + (1 if lst else 0), 'limit': 20, 'total': len(lst), 'list': lst}

    def _norm(self, s):
        s = (s or '').lower()
        s = re.sub(r'[\s\u3000【】\[\]()（）《》<>:：·\-_—,，.。!！?？\'"“”‘’/\\|]+', '', s)
        s = re.sub(r'(高清|hd|bd|4k|蓝光|完整版|未删减|抢先版|tc|ts版)$', '', s)
        return s

    # ------------------------------------------------------------------
    # 详情 (支持单站与多站合并 vod_id)
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        self._boot()
        try:
            raw = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        except Exception:
            raw = str(ids)
        raw = unquote(str(raw or '').strip())
        matches = []
        if raw.startswith('AGG~'):
            for seg in raw.split('~')[1:]:
                if ':' in seg:
                    s, v = seg.split(':', 1)
                    if s in SITES and v:
                        matches.append((s, v))
        elif ':' in raw:
            s, v = raw.split(':', 1)
            if s in SITES and v:
                matches.append((s, v))
        elif raw.isdigit():
            matches.append(('lz', raw))
        if not matches:
            return {'list': []}
        matches = matches[:6]

        def worker(m):
            s, v = m
            try:
                d = self._jget(s, 'ac=detail&ids=' + str(v), timeout=8, ttl=600)
                if d and (d.get('list') or []):
                    return s, d['list'][0]
            except Exception:
                pass
            return s, None

        infos = []
        if _HAS_POOL:
            with ThreadPoolExecutor(max_workers=len(matches)) as ex:
                for s, it in ex.map(worker, matches):
                    if it:
                        infos.append((s, it))
        else:
            for m in matches:
                s, it = worker(m)
                if it:
                    infos.append((s, it))
        if not infos:
            return {'list': []}

        base = infos[0][1]
        # 合并播放线路: 每站取最佳播放组, 一个站点一条线路
        tabs = []
        for s, it in infos:
            nm, eps, direct = self._best_group(it.get('vod_play_from') or '', it.get('vod_play_url') or '')
            if not eps:
                continue
            tab = SITES[s]['name'] + ('' if direct else '[解析]')
            k = tab
            n = 2
            while tab in [t[0] for t in tabs]:
                tab = '%s·%d' % (k, n)
                n += 1
            tabs.append((tab, eps))

        # 封面/简介: 优先取有效值
        pic = ''
        for s, it in infos:
            pic = self._fix_pic(s, it.get('vod_pic'))
            if pic:
                break
        content = ''
        for s, it in infos:
            content = self._clean(it.get('vod_content') or it.get('vod_blurb'), 800)
            if content:
                break
        remarks = ''
        for s, it in infos:
            remarks = self._clean(it.get('vod_remarks'), 60)
            if remarks:
                break

        item = {
            'vod_id': raw,
            'vod_name': self._clean(base.get('vod_name'), 90),
            'vod_pic': pic,
            'type_name': str(base.get('type_name') or ''),
            'vod_year': str(base.get('vod_year') or ''),
            'vod_area': str(base.get('vod_area') or ''),
            'vod_lang': str(base.get('vod_lang') or ''),
            'vod_remarks': remarks,
            'vod_actor': self._clean(base.get('vod_actor'), 150),
            'vod_director': self._clean(base.get('vod_director'), 60),
            'vod_content': content,
            'vod_play_from': '$$$'.join(t[0] for t in tabs),
            'vod_play_url': '$$$'.join(self._epstr(t[1]) for t in tabs),
        }
        return {'list': [item]}

    # ------------------------------------------------------------------
    # 播放 (智能解析)
    # ------------------------------------------------------------------
    def _play_hdr(self, u, ua):
        h = {'User-Agent': ua}
        try:
            p = urlparse(u)
            if p.scheme and p.netloc:
                h['Referer'] = '%s://%s/' % (p.scheme, p.netloc)
        except Exception:
            pass
        return h

    def _resolve_share(self, u, ref, ua):
        """尝试从 /share/ 分享页解析出真实 m3u8 直链"""
        try:
            txt = self._req(u, ref=ref, timeout=8, ua=ua)
            if not txt or len(txt) < 150:
                return ''
            for pat in (r'"url"\s*:\s*"([^"]+)"', r"url\s*:\s*'([^']+)'", r"url\s*=\s*'([^']+)'"):
                m = re.search(pat, txt)
                if m:
                    c = m.group(1).replace('\\/', '/').replace('\\u002F', '/')
                    if self._is_direct(c):
                        return c
            m = re.search(r'https?://[^\s\'"<>\\]+?\.m3u8[^\s\'"<>\\]*', txt)
            if m:
                return m.group(0).replace('\\/', '/')
        except Exception:
            pass
        return ''

    def playerContent(self, flag, id, vipFlags=None):
        self._boot()
        url = id
        if isinstance(url, (list, tuple)):
            url = url[0] if url else ''
        url = str(url or '').strip()
        try:
            url = unquote(url)
        except Exception:
            pass
        if url.startswith('//'):
            url = 'https:' + url

        # 线路 -> 站点
        site = 'lz'
        fbase = str(flag or '').split('[')[0].split('·')[0].strip()
        if fbase in NAME2CODE:
            site = NAME2CODE[fbase]
        ref = SITES[site]['ref']
        ua = self._ua()

        # 1) 标准直链: 直接播放
        if self._is_direct(url):
            fmt = 'application/vnd.apple.mpegurl' if 'm3u8' in url.lower() else 'video/mp4'
            return {'parse': 0, 'url': url, 'playUrl': url,
                    'header': self._play_hdr(url, ua), 'format': fmt}

        # 2) /share/ 分享页: 尝试解析直链, 失败转壳内解析
        if '/share/' in url:
            u2 = self._resolve_share(url, ref, ua)
            if u2:
                return {'parse': 0, 'url': u2, 'playUrl': u2,
                        'header': self._play_hdr(u2, ua), 'format': 'application/vnd.apple.mpegurl'}
            return {'parse': 1, 'url': url, 'playUrl': url, 'header': self._play_hdr(url, ua)}

        # 3) 网页播放页/其他: 交给壳内嗅探解析
        if url.startswith('http'):
            return {'parse': 1, 'url': url, 'playUrl': url, 'header': self._play_hdr(url, ua)}

        # 4) 容错
        return {'parse': 0, 'url': url, 'playUrl': url, 'header': {}}

    # 供部分壳判断格式
    def isVideoFormat(self, url):
        return self._is_direct(url)

    # 供部分壳嗅探判断
    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------------
    def getName(self):
        return '多源聚合增强版'

    def destroy(self):
        try:
            self._cache = {}
        except Exception:
            pass