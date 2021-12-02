import asyncio
from io import BytesIO
import json
import re
import traceback
from uuid import uuid4
from PIL.Image import TRANSPOSE, new
from lxml import etree
from urllib import parse as urlparse
from fonts.font_decrypter import FontDecrypter

from utils import download_page, first, get_query, purge_meta, logging, push_detail, push_res, strip_arr, strip_join

logger = logging.getLogger(__name__)


font_url_reg = re.compile("url\('(.+?\.woff)'\)")

fd = None
with open("fonts/maoyan.woff", "rb") as f, open("fonts/maoyan.json", "r") as f_ucmap:
    fd = FontDecrypter(f, json.load(f_ucmap))


async def parse_rank(req):
    url = req["url"]
    offset = int(get_query(url).get("offset", None) or 0)
    meta = req["meta"]
    resp = await download_page(url)
    html_tree = etree.fromstring(resp, etree.HTMLParser())

    retry_on_empty = 0
    while retry_on_empty < 5 and len(html_tree.cssselect("dl.movie-list .movie-item")) == 0:
        retry_on_empty += 1
        resp = await download_page(url)
        html_tree = etree.fromstring(resp, etree.HTMLParser())

    for i, item in enumerate(html_tree.cssselect("dl.movie-list .movie-item")):
        try:
            new_url = first(item.xpath("a/@href"))
            if new_url:
                meta["index"] = offset + i
                push_detail({"url": urlparse.urljoin(url, new_url), "meta": meta})
        except:
            traceback.print_exc()
    next_pages = html_tree.xpath('//div[contains(@class, "movies-pager")]/ul/li/a')
    if len(next_pages) > 0 and first(next_pages[-1].xpath("text()"), "").strip() == "下一页":
        next_page_url = first(next_pages[-1].xpath("@href"))
        await parse_rank({"url": urlparse.urljoin(url, next_page_url), "meta": meta})


async def parse(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url)
    html_tree = etree.fromstring(resp, etree.HTMLParser())

    movie_ver = first(html_tree.cssselect(".celeInfo-left .movie-ver i"))
    if movie_ver is not None:
        meta["movie_version"] = first(movie_ver.xpath("@class"))

    banner_celeInfo_right = first(html_tree.xpath('//div[contains(@class, "celeInfo-right")]'))

    movie_brief = first(banner_celeInfo_right.xpath('div[contains(@class, "movie-brief-container")]'))
    meta["title"] = first(movie_brief.xpath('*[contains(@class, "name")]/text()'), "").strip()
    ellipsis = movie_brief.xpath("ul/li")
    if len(ellipsis) != 3:
        raise Exception(f"Unsupport ellipsis list {url}")
    meta["labels"] = [i.strip() for i in ellipsis[0].xpath("a/text()")]
    area_duration = first(ellipsis[1].xpath("text()"))
    if area_duration:
        area_duration = area_duration.split("/")
        if len(area_duration) == 2:
            meta["area"] = area_duration[0].strip()
            meta["duration"] = area_duration[1].strip()
    publish_time_match = re.search("\d+-\d+(-\d+)?", first(ellipsis[2].xpath("text()"), ""))
    if publish_time_match:
        meta["earliest_issue_time"] = publish_time_match[0]

    for movie_index in banner_celeInfo_right.xpath(
        'div[contains(@class, "movie-stats-container")]/div[contains(@class, "movie-index")]'
    ):
        title = first(movie_index.xpath('p[contains(@class, "movie-index-title")]/text()'), "").strip()
        if title == "猫眼口碑":
            score = first(
                movie_index.xpath('.//*[contains(@class, "index-left")]/span[contains(@class, "stonefont")]/text()')
            )
            if score:
                meta["score"] = score
            rating_count = first(
                movie_index.xpath('.//*[contains(@class, "index-right")]//span[contains(@class, "stonefont")]//text()')
            )
            if rating_count:
                meta["rating_count"] = rating_count
        elif title == "累计票房":
            box_office = "".join(
                strip_arr(movie_index.xpath('div[contains(@class, "movie-index-content")]/span/text()'))
            )
            if len(box_office) > 0 and box_office != "暂无":
                meta["box_office"] = box_office

    tab_contents = html_tree.cssselect(".main-content .tab-content-container .tab-content")
    for tab_content in tab_contents:
        data_val = first(tab_content.xpath("@data-val"), "")
        if data_val.find("desc") >= 0:
            meta["description"] = strip_join(
                tab_content.xpath('div[contains(@class, "module")][1]/div[contains(@class, "mod-content")]//text()')
            )
        elif data_val.find("celebrity") >= 0:
            for group in tab_content.xpath('.//div[contains(@class, "celebrity-group")]'):
                ct = first(group.xpath('div[contains(@class, "celebrity-type")]/text()'), "").strip()
                if ct != "导演" and ct != "演员":
                    continue
                people = strip_arr(
                    group.xpath('ul[contains(@class, "celebrity-list")]/li/div[contains(@class, "info")]/a/text()')
                )
                if ct == "导演":
                    meta["directors"] = people
                elif ct == "演员":
                    meta["actors"] = people

    try:
        # decrypter words
        font_url_match = font_url_reg.search(resp)
        if font_url_match:
            font_url = font_url_match[1]
            if font_url.startswith("//"):
                font_url = "https:" + font_url
            font_bytes = await download_page(font_url, raw_bytes=True)
            for k in ["score", "rating_count", "box_office"]:
                if k in meta:
                    meta[k] = fd.sub_all(BytesIO(font_bytes), meta[k], raw=True)
    except:
        traceback.print_exc()

    push_res(meta)


if __name__ == "__main__":
    asyncio.run(parse({"url": "https://www.maoyan.com/films/1291076", "meta": {}}))
