import asyncio
import json
import aiohttp
import random
import re
from urllib import parse
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

logger = logging.getLogger(__name__)

from config import (
    HOT_DETAIL_KEY,
    HOT_SEARCH_KEY,
    MAX_RETRY,
    PROXIES,
    HOT_RESP_CACHE_KEY,
    redis_client,
)


def get_query(url):
    parsed = list(parse.urlparse(url))
    return dict(parse.parse_qsl(parsed[4], keep_blank_values=True))


def update_url_query(url, f):
    parsed = list(parse.urlparse(url))
    query = dict(parse.parse_qsl(parsed[4], keep_blank_values=True))
    new_query = f(query)
    parsed[4] = parse.urlencode(new_query)
    return parse.urlunparse(parsed), new_query


def purge_meta(meta):
    return {k: v for k, v in meta.items() if k.startswith("_rs_")}


default_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.80 Safari/537.36",
    "Connection": "close",
}

timeout10 = aiohttp.ClientTimeout(total=10)


async def download_page(url, max_retry=MAX_RETRY, headers=default_headers, raw_bytes=False):
    retry_count = 0
    while True:
        status_code = -1
        msg = ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=random.choice(PROXIES), timeout=timeout10) as r:
                    status_code = r.status
                    if status_code == 200:
                        content = await r.read()
                        logger.debug(f"download {url} {status_code}")
                        return content.decode("utf-8") if not raw_bytes else content
                    if status_code == 429:
                        await asyncio.sleep(5)
                        continue
        except Exception as e:
            status_code = e.status if hasattr(e, "status") else status_code
            if status_code == 429:
                await asyncio.sleep(5)
                continue
            msg = type(e).__name__
            logger.warning(f"download error {url} {status_code} {msg}")
        retry_count += 1
        if retry_count >= max_retry:
            raise Exception(f"download {url} fail {status_code} {msg}")
        await asyncio.sleep(5)


def push_search(req):
    redis_client.lpush(HOT_SEARCH_KEY, json.dumps(req, ensure_ascii=False))


def push_detail(req):
    redis_client.lpush(HOT_DETAIL_KEY, json.dumps(req, ensure_ascii=False))


def push_res(data):
    redis_client.lpush(HOT_RESP_CACHE_KEY, json.dumps(data, ensure_ascii=False))
    # mongo_client.


def first(l, d=None):
    if l and len(l) > 0:
        return l[0]
    return d


def extract_prop_dict(prop):
    kv_pair = re.compile("(.+?)\s*:\s*'(.*?)';")
    d = {}
    for l in prop.split("\n"):
        l = l.strip()
        match = kv_pair.search(l)
        if match:
            d[match[1]] = match[2]
    return d


def timestamp_to_date(ts):
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")


def strip_arr(a):
    return [i.strip() for i in a if i.strip() != ""]


def strip_join(a, delimiter=" "):
    return delimiter.join(strip_arr(a))
