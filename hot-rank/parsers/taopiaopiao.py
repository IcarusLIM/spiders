import json
import re
import asyncio
import traceback
from lxml import etree
from urllib import parse as urlparse
from utils import download_page, first, purge_meta, logging, push_detail, push_res, strip_arr, update_url_query

logger = logging.getLogger(__name__)


json_str_reg = re.compile("callback_rc_ranklist_\d+\((.*)\)")


async def parse_rank(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    html_tree = etree.fromstring(resp, etree.HTMLParser())

    def keep_showId(d):
        return {"showId": d.get("showId", "")}

    for i, a in enumerate(html_tree.cssselect(".tab-movie-list:nth-child(1) .movie-card-wrap a.movie-card")):
        try:
            meta["index"] = i
            new_url, _ = update_url_query(first(a.xpath("@href")), keep_showId)
            card_tag_class = first(a.xpath('div[@class="movie-card-tag"]/i/@class'))
            card_tag = {"t-203": "IMAX", "t-201": "3D IMAX"}.get(card_tag_class, None)
            if card_tag:
                meta["movie_version"] = card_tag
            cover = first(a.xpath('div[@class="movie-card-poster"]/img/@src'))
            if cover:
                meta["cover"] = cover
            meta["title"] = first(a.xpath('div[@class="movie-card-name"]/span[@class="bt-l"]/text()'))
            meta["score"] = first(a.xpath('div[@class="movie-card-name"]/span[@class="bt-r"]/text()'))

            for info in a.xpath('div[@class="movie-card-info"]/div[@class="movie-card-list"]/span/text()'):
                info_tuple = strip_arr(info.split("：", 1))
                if len(info_tuple) != 2:
                    continue
                info_key, info_value = info_tuple
                if info_key == "导演":
                    meta["directors"] = strip_arr(info_value.split(","))
                elif info_key == "主演":
                    meta["actors"] = strip_arr(info_value.split(","))
                elif info_key == "类型":
                    meta["labels"] = strip_arr(info_value.split(","))
                elif info_key == "地区":
                    meta["area"] = info_value.strip()
                elif info_key == "片长":
                    meta["duration"] = info_value.strip()
            push_detail({"url": new_url, "meta": meta})
        except:
            traceback.print_exc()


async def parse(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    html_tree = etree.fromstring(resp, etree.HTMLParser())
    publish_time_match = re.search(
        "\d+-\d+(-\d+)?", first(html_tree.xpath('//div[contains(@class, "cont-time")]/text()'), "")
    )
    if publish_time_match:
        meta["earliest_issue_time"] = publish_time_match[0]
    for li_text in html_tree.xpath('//ul[contains(@class, "cont-info")]/li/text()'):
        li_text = li_text.strip()
        if li_text.startswith("剧情介绍"):
            meta["description"] = re.sub("剧情介绍[:： ]*", "", li_text)
    push_res(meta)


if __name__ == "__main__":
    asyncio.run(parse_rank({"url": "https://dianying.taobao.com/showList.htm", "meta": {}}))
