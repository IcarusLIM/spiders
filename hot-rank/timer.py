# interval (10min) spider trigger
import json
from time import time
import aiohttp, asyncio
from config import HOT_RANK_KEY, logging, redis_client
from datetime import datetime

logger = logging.getLogger(__name__)

reqs = [
    {
        "url": "https://pcw-api.iqiyi.com/strategy/pcw/data/topReboBlock?cid=6&dim=hour&type=realTime&len=50&pageNumber=1",
        "meta": {"brand": "iqiyi", "type": "show"},
    },
    {
        "url": "https://pcw-api.iqiyi.com/strategy/pcw/data/topReboBlock?cid=1&dim=hour&type=realTime&len=50&pageNumber=1",
        "meta": {"brand": "iqiyi", "type": "movie"},
    },
    {
        "url": "https://pcw-api.iqiyi.com/strategy/pcw/data/topReboBlock?cid=2&dim=hour&type=realTime&len=50&pageNumber=1",
        "meta": {"brand": "iqiyi", "type": "tv"},
    },
    {
        "url": "https://pcw-api.iqiyi.com/strategy/pcw/data/topReboBlock?cid=4&dim=hour&type=realTime&len=50&pageNumber=1",
        "meta": {"brand": "iqiyi", "type": "comic"},
    },
    {
        "url": "https://v.qq.com/biu/ranks/?t=hotsearch&channel=movie",
        "meta": {"brand": "qq", "type": "movie"},
    },
    {
        "url": "https://v.qq.com/biu/ranks/?t=hotsearch&channel=tv",
        "meta": {"brand": "qq", "type": "tv"},
    },
    {
        "url": "https://v.qq.com/biu/ranks/?t=hotsearch&channel=variety",
        "meta": {"brand": "qq", "type": "show"},
    },
    {
        "url": "https://v.qq.com/biu/ranks/?t=hotsearch&channel=cartoon",
        "meta": {"brand": "qq", "type": "comic"},
    },
    {
        "url": "https://m.douban.com/rexxar/api/v2/subject_collection/movie_hot_gaia/items?start=0&count=50&items_only=1&for_mobile=1",
        "meta": {"brand": "douban", "type": "movie"},
    },
    {
        "url": "https://m.douban.com/rexxar/api/v2/subject_collection/tv_hot/items?start=0&count=50&items_only=1&for_mobile=1",
        "meta": {"brand": "douban", "type": "tv"},
    },
    {
        "url": "https://m.douban.com/rexxar/api/v2/subject_collection/show_hot/items?start=0&count=50&updated_at=&items_only=1&for_mobile=1",
        "meta": {"brand": "douban", "type": "show"},
    },
    {
        "url": "https://m.douban.com/rexxar/api/v2/subject_collection/movie_showing/items?start=0&count=50&updated_at=&items_only=1&for_mobile=1",
        "meta": {"brand": "douban", "type": "theater"},
    },
    {
        "url": "https://rc.mgtv.com/pc/ranklist?&c=3&t=day&limit=30&rt=c&callback=callback_rc_ranklist_3&_support=10000000",
        "meta": {"brand": "mgtv", "type": "movie"},
    },
    {
        "url": "https://rc.mgtv.com/pc/ranklist?&c=2&t=day&limit=30&rt=c&callback=callback_rc_ranklist_2&_support=10000000",
        "meta": {"brand": "mgtv", "type": "tv"},
    },
    {
        "url": "https://www.maoyan.com/films?showType=1",
        "meta": {"brand": "maoyan", "type": "theater"},
    },
    {
        "url": "https://dianying.taobao.com/showList.htm",
        "meta": {"brand": "taopiaopiao", "type": "theater"},
    },
]


async def send(curr):
    for req in reqs:
        req["meta"]["_datetime"] = curr
        redis_client.lpush(HOT_RANK_KEY, json.dumps(req, ensure_ascii=False))
        logger.info(f"Spider loop: {req['url']}")


async def send_loop():
    # await send(datetime.now().strftime("%Y%m%d%H%M"))
    # return
    minute = datetime.now().minute
    while True:
        now = datetime.now()
        if now.minute != minute and now.minute % 10 == 0:
            curr = now.strftime("%Y%m%d%H%M")
            logger.info(f"Spider loop start: {curr}")
            await send(curr)
            minute = now.minute

        await asyncio.sleep(1)
