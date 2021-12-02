import json
import re
import math
from lxml import etree
from utils import (
    download_page,
    extract_prop_dict,
    first,
    get_query,
    push_detail,
    push_res,
    push_search,
)
from config import logging
from urllib import parse as urlparse

logger = logging.getLogger(__name__)

COVER_INFO_REG = re.compile("var COVER_INFO = (.+)")
COLUMN_INFO_REG = re.compile("var COLUMN_INFO = (.+)")
VIDEO_INFO_REG = re.compile("var VIDEO_INFO = (.+)")

REMAINS_N_REG = re.compile("余(\d+)集")


async def parse_rank(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    html = etree.fromstring(resp, etree.HTMLParser())
    ul = html.xpath('//ul[contains(@class, "table_list")]/li[contains(@class, "item_odd")]')
    for i, li in enumerate(ul):
        try:
            search_url = li.xpath(".//a/@href")[0]
            meta = {**meta, "index": i, "title": li.xpath(".//a/text()")[0]}
            popularity_match = re.search(
                "width:\s*(\d+)%",
                li.xpath('.//div[contains(@class, "bar")]/span/@style')[0],
            )[1]
            if popularity_match:
                meta["popularity"] = popularity_match
            push_search({"url": search_url, "meta": meta, "raw": {}})
        except Exception as e:
            logger.warning(e)


# https://v.qq.com/x/search/?q={query_key}&stag=12
async def parse_search(req):
    url = req["url"]
    meta = req["meta"]
    raw = req.get("raw", {})
    meta["title"] = get_query(url).get("q", "") or meta.get("title", "")
    resp = await download_page(url)
    html = etree.fromstring(resp, etree.HTMLParser())
    result_item = first(
        html.xpath('//div[contains(@class, "wrapper_main")]/div[@data-index="0" and contains(@class, "mix_warp")]')
    )
    if result_item is None:
        parse_search2(url, meta, raw, html)
        return
    video_url = first(result_item.xpath('.//div[contains(@class, "_infos")]/div/a/@href'), "")
    cover_url = first(result_item.xpath('.//img[contains(@class, "figure_pic")]/@src'), "")
    if cover_url:
        if cover_url.startswith("//"):
            cover_url = "https:" + cover_url
        meta["cover"] = cover_url

    inline_series_data = first(result_item.xpath('.//div[@r-component="inline-series"]/@r-props'))
    result_episode_list_props = first(result_item.xpath('.//div[contains(@class, "result_episode_list ")]/@r-props'))
    if inline_series_data:
        props = extract_prop_dict(inline_series_data)
        props["initList"] = json.loads(urlparse.unquote(props.get("initList", "[]")))
        raw["search"] = props
        # 后续在expand_tab_playlist中处理
    # 出现在动漫中
    elif result_episode_list_props:
        search_data = extract_prop_dict(result_episode_list_props)
        result_episode_list_data = first(result_item.xpath('.//div[contains(@class, "result_episode_list")]/@r-data'))
        if result_episode_list_data:
            search_data = {
                **search_data,
                **extract_prop_dict(result_episode_list_data),
            }
        if "initPlaySrc" in search_data:
            # 正序
            initPlaySrc = json.loads(urlparse.unquote(search_data["initPlaySrc"]))
            search_data["initPlaySrc"] = initPlaySrc
            if len(initPlaySrc) > 0:
                meta["earliest_issue_time"] = initPlaySrc[0].get("checkUpTime", "").split(" ")[0]
                meta["latest_issue_time"] = initPlaySrc[-1].get("checkUpTime", "").split(" ")[0]
                meta["latest_issue"] = initPlaySrc[-1].get("title", None)
        raw["search"] = search_data
    if video_url.find("v.qq.com/search_redirect") >= 0:
        meta["raw"] = raw
        push_res(meta)
    else:
        push_detail({"url": video_url, "meta": meta, "raw": raw})


# 处理有聚合intent_list的情况
def parse_search2(url, meta, raw, html):
    li = first(html.xpath('//div[contains(@class, "wrapper_main")]/div[contains(@class, "result_intention")]//ul/li'))
    if li is not None:
        new_url = first(li.xpath("./a/@href"))
        meta["title"] = first(li.xpath('./*[contains(@class, "figure_title")]//text()'))
        push_detail({"url": new_url, "meta": meta, "raw": raw})


def _get_episodeInfo_title_time(episodeInfo):
    title = episodeInfo.get("title", "")
    publish_time = episodeInfo.get("checkUpTime", "")
    time_in_title_match = re.search("\d+-\d+-\d+", title)
    if time_in_title_match:
        publish_time = time_in_title_match[0] or publish_time
    return title, publish_time


def _get_episodeInfo_remain(episodeInfo):
    title = episodeInfo.get("title", "")
    remains_n_match = REMAINS_N_REG.search(title)
    last_page_number = -1
    if remains_n_match:
        remains_n = int(remains_n_match[1])
        last_page_number = math.ceil(remains_n / 10) - 1  # 10 per page
    return last_page_number


def _get_firstBlockSite(data):
    return (
        data.get("data", {})
        .get("normalList", {})
        .get("itemList", [{}])[0]
        .get("videoInfo", {})
        .get("firstBlockSites", [{}])[0]
    )


async def expand_playlist(id, meta, raw):
    def get_playlist_url(page_number, is_initlist, async_param=None):
        url = f"https://pbaccess.video.qq.com/trpc.videosearch.search_cgi.http/load_playsource_list_info?dataType=3&scene={1 if is_initlist else 3}&platform=2&appId=10718&site=qq&g_tk=&g_vstk=&g_actk=&id={id}&pageNum={page_number}"
        if async_param is not None:
            url += f"&pageContext={async_param}"
        return url

    playlists = []
    firstBlockSite = raw.get("search", {}).get("initList", None)
    if firstBlockSite is None:
        resp = await download_page(get_playlist_url(0, True))
        firstBlockSite = _get_firstBlockSite(json.loads(resp))
    playlists.append(firstBlockSite)
    title, publish_time = _get_episodeInfo_title_time(firstBlockSite["episodeInfoList"][0])
    meta["latest_issue_time"] = publish_time
    meta["latest_issue"] = title

    tabs = firstBlockSite.get("tabs", [])
    async_param = None
    try:
        if len(tabs) > 0:
            async_param = tabs[-1].get("asnycParams", None)
            resp = await download_page(get_playlist_url(0, True, async_param))
            firstBlockSite = _get_firstBlockSite(json.loads(resp))
            playlists.append(firstBlockSite)

        last_page_number = _get_episodeInfo_remain(firstBlockSite["episodeInfoList"][-1])
        if last_page_number < 0:
            _, publish_time = _get_episodeInfo_title_time(firstBlockSite["episodeInfoList"][-1])
            meta["earliest_issue_time"] = publish_time
        else:
            resp = await download_page(get_playlist_url(last_page_number, False, async_param))
            firstBlockSite = _get_firstBlockSite(json.loads(resp))
            playlists.append(firstBlockSite)
            _, publish_time = _get_episodeInfo_title_time(firstBlockSite["episodeInfoList"][-1])
            meta["earliest_issue_time"] = publish_time
    except:
        pass

    raw["playlists"] = playlists


# https://v.qq.com/x/cover/mzc00200a4ikd1f.html
async def parse(req):
    url = req["url"]
    meta = req["meta"]
    raw = req["raw"]
    resp = await download_page(url)

    detail_data = {}
    for item, item_reg in [
        ("cover_info", COVER_INFO_REG),
        ("column_info", COLUMN_INFO_REG),
        ("video_info", VIDEO_INFO_REG),
    ]:
        try:
            detail_data[item] = json.loads(item_reg.search(resp)[1])
        except:
            pass
    raw["detail"] = detail_data

    cover_info = detail_data.get("cover_info", {})
    meta["area"] = cover_info.get("area_name", "")
    meta["title"] = cover_info.get("title", "")
    labels = []
    if cover_info.get("main_genre", None):
        labels.append(cover_info["main_genre"])
    sub_genre = cover_info.get("sub_genre", None)
    if sub_genre:
        labels.extend(sub_genre)
    meta["labels"] = labels
    scores = cover_info.get("score", None) or {}
    meta["score"] = scores.get("score", "")
    # meta["popularity"] = scores.get("hot", "")
    meta["directors"] = cover_info.get("director", None) or []
    if len(meta["directors"]) > 0 and meta["directors"][0] == "":
        meta["directors"] = cover_info.get("director_id", [])
    meta["actors"] = cover_info.get("leading_actor", None) or []
    meta["year"] = cover_info.get("year", "")
    if meta.get("type", "") == "":
        type_map = {"综艺": "show", "动漫": "comic", "电视剧": "tv", "电影": "movie"}
        if "type_name" in cover_info and cover_info["type_name"] in type_map:
            meta["type"] = type_map[cover_info["type_name"]]

    column_info = detail_data.get("column_info", {})
    prompt_text = column_info.get("prompt_text", None) or cover_info.get("update_desc", None) or ""
    meta["prompt_text"] = prompt_text
    meta["is_ending"] = not (len(prompt_text) > 0 and prompt_text.find("集全") < 0 and prompt_text.find("全集") < 0)

    if "earliest_issue_time" not in meta:
        await expand_playlist(cover_info.get("id", ""), meta, raw)

    if meta.get("type", "")=="movie":
        if meta.get("earliest_issue_time", "") == "":
            meta["earliest_issue_time"] = cover_info.get("publish_date", None)
    else:
        if meta.get("latest_issue_time", "") == "":
            meta["latest_issue_time"] = cover_info.get("publish_date", None)
        if meta.get("latest_issue") == "":
            meta["latest_issue"] = cover_info.get("episode_updated", None)

    meta["raw"] = raw
    push_res(meta)
