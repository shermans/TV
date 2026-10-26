"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const axios_1 = require("axios");
const he = require("he");
const pageSize = 30;

// ============ 怡红院 · 沉音 ============
// 由 lx-music 音源脚本移植，解析接口来自原脚本
// API: https://musicserver.haitangw.cc/v1/ (主) / https://qt.haitangw.net/v1/ (备)
// 搜索/榜单/歌单数据来自酷我公开接口

const API1 = "https://musicserver.haitangw.cc/v1/";
const API2 = "https://qt.haitangw.net/v1/";
const CACHE_TTL = 20 * 60 * 1000; // 缓存20分钟

const QUALITY_MAP = {
  low: "128k",
  standard: "320k",
  high: "flac",
  super: "flac",
};

// 落雪源支持的音质级别映射（实测可用）
const API_QUALITY_MAP = {
  "128k": "standard",
  "320k": "exhigh",
  flac: "lossless",
};

const urlCache = new Map();

// 个人收藏曲库（yingyue）
const MY_MUSIC_JSON = "https://cdn.jsdelivr.net/gh/zxsla/yingyue@main/music.json";
let myMusicCache = null;
let myMusicCacheTime = 0;

async function getMyMusic() {
  if (myMusicCache && Date.now() - myMusicCacheTime < CACHE_TTL) return myMusicCache;
  const res = await (0, axios_1.default)({ method: "get", url: MY_MUSIC_JSON, timeout: 30000 });
  myMusicCache = res.data;
  myMusicCacheTime = Date.now();
  return myMusicCache;
}

// 个人收藏歌曲格式化（music.json 字段: name="歌手 - 歌名", url=直链, pic=封面）
// 个人收藏歌曲的 id -> {url, lyricText} 映射（防止 App 丢弃下划线字段）
const mySongMap = new Map();

function formatMySong(_) {
  const name = _.name || "";
  const sep = name.indexOf(" - ");
  const artist = sep !== -1 ? name.slice(0, sep).trim() : "";
  const title = sep !== -1 ? name.slice(sep + 3).trim() : name;
  const id = "my_" + (_.url || Math.random().toString(36).slice(2));
  mySongMap.set(id, { url: _.url, lyricText: _.lyric_text || "" });
  return {
    id: id,
    title: title,
    artist: artist,
    artwork: _.pic || undefined,
    _directUrl: _.url,
    _lyricText: _.lyric_text || "",
    _source: "my",
  };
}

function artworkShort2Long(albumpicShort) {
  var _a;
  const firstSlashOfAlbum =
    (_a =
      albumpicShort === null || albumpicShort === void 0
        ? void 0
        : albumpicShort.indexOf("/")) !== null && _a !== void 0
      ? _a
      : -1;
  return firstSlashOfAlbum !== -1
    ? `https://img4.kuwo.cn/star/albumcover/1080${albumpicShort.slice(
        firstSlashOfAlbum
      )}`
    : undefined;
}

function formatMusicItem(_) {
  return {
    id: _.MUSICRID.replace("MUSIC_", ""),
    artwork: artworkShort2Long(_.web_albumpic_short),
    title: he.decode(_.NAME || ""),
    artist: he.decode(_.ARTIST || ""),
    album: he.decode(_.ALBUM || ""),
    albumId: _.ALBUMID,
    artistId: _.ARTISTID,
    // 保存原始平台信息，供解析接口使用
    _source: "kw",
  };
}

// 榜单歌曲格式化（bang/musicList 接口字段）
function formatBangItem(_) {
  const rid = (_.musicrid || "").replace("MUSIC_", "") || String(_.rid || "");
  return {
    id: rid,
    artwork: _.pic || undefined,
    title: he.decode(_.name || ""),
    artist: he.decode(_.artist || ""),
    album: he.decode(_.album || ""),
    albumId: _.albumid,
    _source: "kw",
  };
}

// 歌单歌曲格式化（pl.svc 接口字段）
function formatSheetSong(_) {
  return {
    id: String(_.id || ""),
    title: he.decode(_.name || ""),
    artist: he.decode(_.artist || ""),
    album: he.decode(_.album || ""),
    albumId: _.albumid,
    artistId: _.artistid,
    _source: "kw",
  };
}

async function searchMusic(query, page) {
  const res = (
    await (0, axios_1.default)({
      method: "get",
      url: `http://search.kuwo.cn/r.s`,
      params: {
        client: "kt",
        all: query,
        pn: page - 1,
        rn: pageSize,
        uid: 2574109560,
        ver: "kwplayer_ar_8.5.4.2",
        vipver: 1,
        ft: "music",
        cluster: 0,
        strategy: 2012,
        encoding: "utf8",
        rformat: "json",
        vermerge: 1,
        mobi: 1,
      },
    })
  ).data;
  const songs = res.abslist.map(formatMusicItem);
  return {
    isEnd: (+res.PN + 1) * +res.RN >= +res.TOTAL,
    data: songs,
  };
}

// ============ 我的收藏 ============
async function getTopLists() {
  const groups = [];
  // 只返回个人收藏，不含酷我榜单
  try {
    const my = await getMyMusic();
    const singers = my.singers || [];
    if (singers.length) {
      groups.push({
        title: "我的收藏",
        data: singers.map((g, idx) => ({
          id: "myfav_" + idx,
          title: g.name,
          coverImg: (g.songs[0] && g.songs[0].pic) || undefined,
          description: `${g.songs.length} 首`,
        })),
      });
    }
  } catch (e) {
    // 拉不到个人曲库就返回空
  }
  return groups;
}

async function getTopListDetail(topListItem, page) {
  // 我的收藏：从 music.json 取对应分组
  if (String(topListItem.id).startsWith("myfav_")) {
    const idx = parseInt(String(topListItem.id).replace("myfav_", ""), 10);
    const my = await getMyMusic();
    const group = (my.singers || [])[idx];
    if (!group) return { isEnd: true, data: [] };
    const songs = (group.songs || []).map(formatMySong);
    return { isEnd: true, data: songs };
  }
  return { isEnd: true, data: [] };
}

// ============ 精选歌单 ============
const SHEET_TAGS = [
  { id: "hot", title: "最热" },
  { id: "new", title: "最新" },
];

async function getRecommendSheetTags() {
  return { data: SHEET_TAGS };
}

async function getRecommendSheetsByTag(tag, page) {
  const order = tag.id === "new" ? "new" : "hot";
  const res = (
    await (0, axios_1.default)({
      method: "get",
      url: "http://wapi.kuwo.cn/api/pc/classify/playlist/getRcmPlayList",
      params: {
        loginUid: 0,
        loginSid: 0,
        appUid: 76039576,
        pn: page,
        rn: pageSize,
        order: order,
      },
      timeout: 30000,
    })
  ).data;
  if (res.code !== 200 || !res.data) return { isEnd: true, data: [] };
  const list = res.data.data || [];
  const total = +res.data.total || 0;
  return {
    isEnd: page * pageSize >= total || list.length < pageSize,
    data: list.map((_) => ({
      id: _.id,
      title: he.decode(_.name || ""),
      coverImg: _.img,
      artist: _.uname || "",
      playCount: +_.listencnt || 0,
      worksNum: +_.total || 0,
      description: _.info || _.digest || "",
    })),
  };
}

async function getMusicSheetInfo(sheet, page) {
  const rn = pageSize;
  const pn = (page - 1) * rn;
  const res = (
    await (0, axios_1.default)({
      method: "get",
      url: "http://nplserver.kuwo.cn/pl.svc",
      params: {
        op: "getlistinfo",
        pid: sheet.id,
        pn: pn,
        rn: rn,
        encode: "utf8",
        keyset: "pl2012",
        identity: "kuwo",
        pcmp4: 1,
        isnew: 1,
        vipver: 1,
      },
      timeout: 30000,
    })
  ).data;
  const list = res.musiclist || [];
  const total = +res.total || 0;
  return {
    isEnd: pn + rn >= total || list.length < rn,
    musicList: list.map(formatSheetSong),
  };
}

// 导入酷我歌单链接：https://www.kuwo.cn/playlist_detail/123456
async function importMusicSheet(url) {
  const m = url.match(/playlist_detail\/(\d+)/);
  if (!m) throw new Error("无法识别的歌单链接");
  const pid = m[1];
  // 拉取歌单基本信息（取第一页，顺带拿 title）
  const res = (
    await (0, axios_1.default)({
      method: "get",
      url: "http://nplserver.kuwo.cn/pl.svc",
      params: {
        op: "getlistinfo",
        pid: pid,
        pn: 0,
        rn: 1,
        encode: "utf8",
        keyset: "pl2012",
        identity: "kuwo",
        pcmp4: 1,
        isnew: 1,
        vipver: 1,
      },
      timeout: 30000,
    })
  ).data;
  return {
    id: pid,
    title: he.decode(res.title || "酷我歌单 " + pid),
    coverImg: res.pic || undefined,
    worksNum: +res.total || 0,
    description: res.info || "",
  };
}

async function resolveUrl(apiBase, source, rid, level) {
  const res = await (0, axios_1.default)({
    method: "post",
    url: `${apiBase}music/resolve-url`,
    headers: { "Content-Type": "application/json" },
    data: { source, rid: String(rid), level },
    timeout: 8000,
  });
  const body = res.data;
  if (body && body.data && body.data.url) return body.data.url;
  if (body && body.url) return body.url;
  throw new Error(body.message || "解析失败");
}

async function getMediaSource(musicItem, quality) {
  // 个人收藏：直链直接返回，不走解析接口（用 Map 查，防止 App 丢弃下划线字段）
  const myInfo = mySongMap.get(musicItem.id);
  if (myInfo && myInfo.url) {
    return { url: myInfo.url };
  }
  if (musicItem._directUrl) {
    return { url: musicItem._directUrl };
  }
  const userQuality = QUALITY_MAP[quality] || "320k";
  const apiLevel = API_QUALITY_MAP[userQuality] || "320k";
  const rid = musicItem.id;
  const source = musicItem._source || "kw";
  const cacheKey = `${source}-${rid}-${apiLevel}`;
  const cached = urlCache.get(cacheKey);

  // 缓存命中且未过期
  if (cached && Date.now() - cached.time < CACHE_TTL) {
    return { url: cached.url };
  }

  // 主线路 -> 备用线路
  let lastErr;
  for (const api of [API1, API2]) {
    try {
      const url = await resolveUrl(api, source, rid, apiLevel);
      urlCache.set(cacheKey, { url, time: Date.now() });
      return { url };
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("所有线路解析失败");
}

async function getLyric(musicItem) {
  // 个人收藏：用内嵌歌词（用 Map 查）
  const myInfo = mySongMap.get(musicItem.id);
  if (myInfo && myInfo.lyricText) {
    return { rawLrc: myInfo.lyricText };
  }
  if (musicItem._lyricText) {
    return { rawLrc: musicItem._lyricText };
  }
  const res = (
    await (0, axios_1.default)({
      method: "get",
      url: `http://m.kuwo.cn/newh5/singles/songinfoandlrc`,
      params: { musicId: musicItem.id },
    })
  ).data;
  if (res.status === 200 && res.data && res.data.lrclist) {
    return {
      rawLrc: res.data.lrclist.map((_) => `[${_.time}]${_.lineLyric}`).join("\n"),
    };
  }
  return { rawLrc: "" };
}

module.exports = {
  platform: "怡红院 · 沉音",
  version: "26.10.18-my4",
  appVersion: ">0.1.0-alpha.0",
  srcUrl: "",
  cacheControl: "no-cache",
  hints: {
    importMusicSheet: ["kuwo.cn/playlist_detail/"],
  },
  supportedSearchType: ["music"],
  async search(query, page, type) {
    if (type === "music") return await searchMusic(query, page);
  },
  // 最新热榜
  getTopLists,
  getTopListDetail,
  // 精选歌单
  getRecommendSheetTags,
  getRecommendSheetsByTag,
  getMusicSheetInfo,
  importMusicSheet,
  getMediaSource,
  getLyric,
};
