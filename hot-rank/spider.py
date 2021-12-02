import json
import asyncio
import traceback
from config import HOT_RANK_KEY, HOT_SEARCH_KEY, HOT_DETAIL_KEY, redis_client, logging

from parsers.qq import (
    parse as qq_parse,
    parse_rank as qq_parse_rank,
    parse_search as qq_parse_search,
)
from parsers.iqiyi import (
    parse as iqiyi_parse,
    parse_rank as iqiyi_parse_rank,
    parse_search as iqiyi_parse_search,
)
from parsers.douban import (
    parse as douban_parse,
    parse_rank as douban_parse_rank,
    parse_search as douban_parse_search,
)
from parsers.mgtv import (
    parse as mgtv_parse,
    parse_rank as mgtv_parse_rank,
)
from parsers.maoyan import (
    parse as maoyan_parse,
    parse_rank as maoyan_parse_rank,
)
from parsers.taopiaopiao import (
    parse as tpp_parse,
    parse_rank as tpp_parse_rank,
)


logger = logging.getLogger(__name__)

WAIT_ON_IDLE = 5
CONCURRENT = 20


async def consum_and_crawl(key, f):
    while True:
        item = redis_client.lpop(key)
        if not item:
            await asyncio.sleep(WAIT_ON_IDLE)
            continue
        req = json.loads(item.decode("utf-8"))
        try:
            await f(req)
        except:
            traceback.print_exc()


async def consum_rank():
    async def dispatch(req):
        meta = req["meta"]
        if meta["brand"] == "douban":
            await douban_parse_rank(req)
        elif meta["brand"] == "iqiyi":
            await iqiyi_parse_rank(req)
        elif meta["brand"] == "qq":
            await qq_parse_rank(req)
        elif meta["brand"] == "mgtv":
            await mgtv_parse_rank(req)
        elif meta["brand"] == "maoyan":
            await maoyan_parse_rank(req)
        elif meta["brand"]=="taopiaopiao":
            await tpp_parse_rank(req)
        else:
            logger.warning(f"consume_rank unsupport {meta['brand']}")

    await consum_and_crawl(HOT_RANK_KEY, dispatch)


async def consum_search():
    async def dispatch(req):
        meta = req["meta"]
        if meta["brand"] == "douban":
            await douban_parse_search(req)
        elif meta["brand"] == "iqiyi":
            await iqiyi_parse_search(req)
        elif meta["brand"] == "qq":
            await qq_parse_search(req)
        else:
            logger.warning(f"consume_search unsupport {meta['brand']}")

    await consum_and_crawl(HOT_SEARCH_KEY, dispatch)


async def consum_detail():
    async def dispatch(req):
        meta = req["meta"]
        if meta["brand"] == "douban":
            await douban_parse(req)
        elif meta["brand"] == "iqiyi":
            await iqiyi_parse(req)
        elif meta["brand"] == "qq":
            await qq_parse(req)
        elif meta["brand"] == "mgtv":
            await mgtv_parse(req)
        elif meta["brand"] == "maoyan":
            await maoyan_parse(req)
        elif meta["brand"]=="taopiaopiao":
            await tpp_parse(req)
        else:
            logger.warning(f"consume_rank unsupport {meta['brand']}")

    await consum_and_crawl(HOT_DETAIL_KEY, dispatch)


async def run():
    await asyncio.gather(
        *[consum_rank() for _ in range(CONCURRENT)],
        *[consum_search() for _ in range(CONCURRENT)],
        *[consum_detail() for _ in range(CONCURRENT * 3)],
    )
