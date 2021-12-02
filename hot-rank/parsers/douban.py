import asyncio
import json
import re
import traceback
from urllib import parse as urlparse
from lxml import etree

from config import MAX_RETRY
from utils import (
    download_page,
    default_headers,
    first,
    logging,
    push_detail,
    push_res,
    update_url_query,
)

logger = logging.getLogger(__name__)

LD_RE = re.compile('<script type="application/ld\+json">(.+?)</script>', re.DOTALL)

headers = {**default_headers, "Referer": "https://m.douban.com"}
headers_android = {
    **headers,
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36",
}
max_retry = MAX_RETRY * 4


async def parse_rank(req):
    url = req["url"]
    meta = req["meta"]
    resp = await download_page(url, headers=headers, max_retry=max_retry)
    resp_data = json.loads(resp)
    start = resp_data.get("start", -1)
    for i, item in enumerate(resp_data["subject_collection_items"]):
        try:
            info = [i.strip() for i in item["info"].split("/")]
            new_meta = {
                "index": start + i,
                "title": item["title"],
                "actors": item["actors"],
                "directors": item["directors"],
                "area": info[0],
                "labels": [s.strip() for s in info[1].split(" ") if s.strip() != ""],
                "year": item.get("year", ""),
            }
            release_date = (item.get("release_date", None) or "").replace(".", "-")
            if len(release_date) > 0:
                release_date = "-" + release_date
            new_meta["earliest_issue_time"] = str(item["year"]) + release_date
            if "rating" in item and item["rating"] is not None:
                new_meta["score"] = item["rating"].get("value", "")
                new_meta["rating_count"] = item["rating"].get("count", "")
            new_url = item["url"]
            if new_url.find("m.douban.com/movie") >= 0:
                new_url = new_url.replace("m.douban.com/movie", "movie.douban.com")
            # push_detail({"url": new_url, "meta": {**meta, **new_meta}, "raw": {"rank": item}})
            new_meta["raw"] = item
            push_res({**meta, **new_meta})
        except:
            traceback.print_exc()

    count = resp_data.get("count", 50)
    total = resp_data.get("total", -1)
    if start >= 0 and total >= 0 and start + count < total:

        def page_plus(d):
            d["start"] = start + count
            return d

        next_url, _ = update_url_query(url, page_plus)
        await parse_rank({**req, "url": next_url})


# https://m.douban.com/search/?query={query_key}&type=movie, mobile ua
async def parse_search(req):
    url = req["url"]
    meta = req["meta"]
    raw = req.get("raw", {})
    resp = await download_page(url, headers=headers_android, max_retry=max_retry)
    html_tree = etree.fromstring(resp, etree.HTMLParser())
    movie = first(html_tree.xpath('//ul[contains(@class, "search_results_subjects")]/li/a'))
    if movie is not None:
        new_url = first(movie.xpath("./@href"))
        meta["title"] = first(movie.xpath('.//span[contains(@class, "subject-title")]/text'))
        if new_url is not None:
            new_url = urlparse.urljoin(url, new_url)
            if new_url.find("m.douban.com/movie") >= 0:
                new_url = new_url.replace("m.douban.com/movie", "movie.douban.com")
            push_detail({"url": new_url, "meta": meta, "raw": raw})


async def parse(req):
    url = req["url"]
    meta = req["meta"]
    raw = req.get("raw", {})
    try:
        resp = await download_page(url, headers=headers)
        html_tree = etree.fromstring(resp, etree.HTMLParser())
        resource_sites = html_tree.xpath('//div[contains(@class, "aside")]//a[contains(@class, "playBtn")]/text()')
        raw["resource_site"] = [r.strip() for r in resource_sites if r.strip() != ""]

        ld_match = LD_RE.search(resp)
        if ld_match:
            try:
                ld_data = json.loads(ld_match[1])
                raw["detail"] = ld_data
                meta["title"] = ld_data["name"]
                meta["cover"] = ld_data["image"]
                meta["actors"] = [i["name"] for i in ld_data["actor"]]
                meta["directors"] = [i["name"] for i in ld_data["director"]]
                for key in ["actors", "directors"]:
                    if len(meta[key]) > 0:
                        v0 = meta[key][0]
                        v0_ = re.sub("[a-zA-z ]*", "", v0)
                        if len(v0_) > 0 and len(v0_) != len(v0):
                            meta[key] = [re.sub("[a-zA-z -]*$", "", i) for i in meta[key]]
                meta["labels"] = ld_data["genre"]
                meta["description"] = ld_data["description"]
                meta["score"] = ld_data["aggregateRating"]["ratingValue"]
                meta["rating_count"] = ld_data["aggregateRating"]["ratingCount"]
                if "earliest_issue_time" not in meta and ld_data.get("datePublished", "") != "":
                    meta["earliest_issue_time"] = ld_data["datePublished"]
            except Exception as e:
                logger.warning(e)
        if "earliest_issue_time" not in meta:
            release_date_match = re.search(
                "\d+-\d+(-\d+)?",
                first(html_tree.xpath('//*[@property="v:initialReleaseDate"]/text()')) or "",
            )
            if release_date_match:
                meta["earliest_issue_time"] = release_date_match[0]
    except:
        traceback.print_exc()
    meta["raw"] = raw
    push_res(meta)


if __name__ == "__main__":
    asyncio.run(parse({"url": "https://movie.douban.com/subject/2156663/", "meta": {}}))
