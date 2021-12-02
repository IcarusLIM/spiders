import json
from aiohttp.helpers import NO_EXTENSIONS
from lxml import etree
from utils import download_page, get_query, push_detail, push_res, timestamp_to_date
from config import logging

logger = logging.getLogger(__name__)


async def parse_rank(req):
    url = req["url"]
    resp = await download_page(url)
    resp_data = json.loads(resp)
    for i, item in enumerate(resp_data.get("data", {}).get("formatData", {}).get("list", [])):
        detail_url = item.get("pageUrl", "")
        if detail_url:
            push_detail(
                {
                    "url": detail_url,
                    "meta": {
                        **req["meta"],
                        "index": i,
                        "title": item["name"],
                        "cover": item["imageUrl"],
                        "popularity": item["hotIndex"],
                        "score": item.get("score", 0),
                    },
                    "raw": {"rank": item},
                }
            )


# https://pcw-api.iqiyi.com/strategy/pcw/data/soBaseCardLeftSide?pageNum=1&key={query_key}&channel_name=&duration_level=0&need_qc=0&site_publish_date_level=&site=&mode=1&bitrate=&af=0
async def parse_search(req):
    url = req["url"]
    meta = req["meta"]
    raw = req.get("raw", {})
    meta["title"] = get_query(url).get("key", "")
    resp = await download_page(url)
    format_data = json.loads(resp).get("data", {}).get("formatData", {})

    new_url = None

    intent_list = format_data.get("intentList", [])
    if len(intent_list) > 0:
        intent = intent_list[0]
        meta["title"] = intent.get("g_title", "")
        meta["cover"] = intent.get("g_img", "")
        meta["score"] = intent.get("score", 0)
        meta["actors"] = [a.get("name", "") for a in intent.get("actor", [])]
        new_url = intent.get("g_main_link", "")

    video_list = format_data.get("list", [])
    if len(video_list) > 0 and not new_url:
        # videoDocType: 1 电影电视剧 2 第三方 3 演员 7 视频号（舞蹈生） 8 预告
        video = video_list[0]
        video_doc_type = video.get("videoDocType", -1)
        for v in video_list:
            if v.get("videoDocType", -1) == 3 or v.get("videoDocType", -1) == 7:
                continue
            video = v
            video_doc_type = v.get("videoDocType", -1)
            break
        raw["search"] = video

        if video_doc_type == 3:
            for work in video.get("starRecWork", []) + video.get("starWork", []):
                if meta["title"] != work.get("name", ""):
                    continue
                new_url = work.get("url", "")
                break
        elif video_doc_type == 7:
            new_url = video.get("ugcList", [{}])[0].get("url", "")
        else:
            if video_doc_type == 1 or video_doc_type == 8:
                meta["title"] = video.get("g_title", "")
                meta["actors"] = video.get("actor", None)
                meta["directors"] = video.get("director", None)
                meta["area"] = video.get("region", None)
                meta["year"] = video.get("year", None)
                meta["description"] = video.get("desc", None)
                meta["cover"] = video.get("g_img", None)
            if video_doc_type == 1:
                new_url = video.get("g_main_link", "") or video.get("moreLink", "")
                meta["score"] = video.get("score", "")
            elif video_doc_type == 8:
                new_url = video.get("prevueList", [{}])[0].get("url", "")

    if new_url.find("www.iqiyi.com/a_") >= 0:
        try:
            resp = await download_page(new_url)
            html_tree = etree.fromstring(resp, etree.HTMLParser())
            # 一般存在于电视剧分类，已确认包含所有分页，列表为正序
            album_avlist = json.loads(html_tree.xpath('input[@id="album-avlist-data"]/@value')[0])
            playlist = album_avlist["epsodelist"]
            raw["playlist"] = playlist
            meta["latest_issue"] = playlist[-1]["shortTitle"]
            meta["latest_issue_time"] = playlist[-1]["period"]
            meta["earliest_issue_time"] = playlist[0]["period"]
            new_url = album_avlist[0]["playUrl"]
        except:
            pass
    if new_url.startswith("//"):
        new_url = "https:" + new_url
    if new_url.find("www.iqiyi.com/v_") >= 0:
        await parse({"url": new_url, "meta": meta, "raw": raw})
    else:
        meta["raw"] = raw
        push_res(meta)


async def parse(req):
    url = req["url"]
    meta = req["meta"]
    raw = req["raw"]
    resp = await download_page(url)

    html_tree = etree.fromstring(resp, etree.HTMLParser())
    raw["detail"] = {}
    update_tip = html_tree.xpath('//p[contains(@class, "update-tip")]/text()')
    prompt_text = " ".join([t.strip() for t in update_tip])
    meta["prompt_text"] = prompt_text
    meta["is_ending"] = not (prompt_text.find("集全") < 0 and len(prompt_text) > 0)
    video_info = html_tree.xpath('//div[@id="iqiyi-main"]//@*[name()=":video-info"]')
    if len(video_info) >= 1:
        video_info = json.loads(video_info[0])
        raw["detail"]["video_info"] = video_info

        cast = video_info.get("cast", None)
        if cast:
            meta["directors"] = [d["name"] for d in cast.get("directors", [])]
            meta["actors"] = [d["name"] for d in cast.get("mainActors", [])]
            if len(meta["actors"]) == 0:
                meta["actors"] = [d["name"] for d in cast.get("guests", [])]
        period = video_info.get("period", None)
        if period:
            meta["year"] = period.strip()[:4]
        # if not meta.get("score", None):
        #     meta["score"] = video_info.get("score", 0)
        description = video_info.get("description", None)
        if description and not meta.get("description", None):
            meta["description"] = description

        area = video_info.get("areas", None)
        if area:
            meta["area"] = " ".join(area)
        categories = video_info.get("categories", None)
        if categories:
            meta["labels"] = [c["name"] for c in categories if c["subName"] == "类型" or c["subName"] == "题材"]

        tag = video_info.get("tag", None)
        if tag:
            if len(meta.get("labels", [])) <= 0:
                meta["labels"] = [
                    item.replace("Tag_Pps_type_", "").split("_")[0] for item in tag if item.startswith("Tag_Pps_type_")
                ]
            if meta.get("area", None) is None:
                meta["area"] = " ".join(
                    [
                        item.replace("Tag_Pps_region_", "").split("_")[0]
                        for item in tag
                        if item.startswith("Tag_Pps_region_")
                    ]
                )
        publish_time = video_info.get("firstPublishTime", None) or 0
        if publish_time > 0 and meta.get("latest_issue_time", None) is None:
            publish_datetime = timestamp_to_date(publish_time)
            # 电视剧电影详情页默认第一集，综艺默认最后一期
            if meta.get("type", "") == "show":
                meta["latest_issue_time"] = publish_datetime
            else:
                meta["earliest_issue_time"] = publish_datetime

    page_info = html_tree.xpath('//div[@id="iqiyi-main"]//@*[name()=":page-info"]')
    if len(page_info) >= 1:
        page_info = json.loads(page_info[0])
        raw["detail"]["page_info"] = page_info
        if meta.get("type", "") == "":
            type_map = {"综艺": "show", "动漫": "comic", "电视剧": "tv", "电影": "movie"}
            category_name = page_info.get("categoryName", "")
            if category_name in type_map:
                meta["type"] = type_map[category_name]

    albumId = page_info.get("albumId", 0)
    tvId = page_info.get("tvId", 0)

    if meta.get("popularity", None) is None and raw.get("search", {}).get("videoDocType", -1) == 1:
        hot_id = str(albumId) if albumId != 0 else f"{albumId},{tvId}"
        hot_url = f"https://pcw-api.iqiyi.com/video/video/hotplaytimes/{hot_id}"
        try:
            resp = await download_page(hot_url)
            meta["popularity"] = json.loads(resp).get("data", [])[0].get("hot", 0)
        except Exception as e:
            logger.warning(f"Crawl popularity {hot_url} {e}")

    if meta["type"] != "movie" and albumId != 0:
        playlist_error = False
        try:
            # 倒序
            resp = await download_page(
                f"https://pcw-api.iqiyi.com/strategy/pcw/data/soMoreSourceListBlock?album_id={albumId}",
                max_retry=3,
            )
            playlist = json.loads(resp).get("data", {}).get("formatData", {}).get("videoinfos", [])
            if len(playlist) > 0:
                raw["playlist"] = playlist
                meta["latest_issue"] = playlist[0].get("name", "")
                meta["latest_issue_time"] = timestamp_to_date(playlist[0]["first_online_time"])
                meta["earliest_issue_time"] = timestamp_to_date(playlist[-1]["first_online_time"])
        except Exception as e:
            playlist_error = True
            logger.warning(f"Crawl playlist {url} {e}")
        if playlist_error:
            try:
                playlist2 = []
                raw["playlist2"] = playlist2
                # 正序
                resp = await download_page(
                    f"https://pcw-api.iqiyi.com/albums/album/avlistinfo?aid={albumId}&page=1&size=30",
                    max_retry=3,
                )
                data = json.loads(resp).get("data", {})
                epsodelist = data.get("epsodelist", [])
                meta["earliest_issue_time"] = timestamp_to_date(epsodelist[0]["publishTime"])
                max_page_num = data.get("page", 1)
                if max_page_num > 1:
                    playlist2.append(data)
                    resp = await download_page(
                        f"https://pcw-api.iqiyi.com/albums/album/avlistinfo?aid={albumId}&page={max_page_num}&size=30",
                        max_retry=3,
                    )
                    data = json.loads(resp).get("data", {})
                    epsodelist = data.get("epsodelist", [])
                playlist2.append(data)
                meta["latest_issue_time"] = timestamp_to_date(epsodelist[-1]["publishTime"])
                meta["latest_issue"] = f'{epsodelist[-1].get("name", "")} {epsodelist[-1].get("subtitle", "")}'.strip()
            except Exception as e:
                logger.warning(f"Crawl playlist2 {url} {e}")

    meta["raw"] = raw
    push_res(meta)
