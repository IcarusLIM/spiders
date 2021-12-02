from datetime import datetime
import json
import math
import random
import sys, signal
import asyncio
import aiohttp
import logging
import time
from config import redis_client, SEARCH_KEY
from urllib import parse

logging.basicConfig(level=logging.WARNING, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

STOP_FLAG = False

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.80 Safari/537.36",
    "Connection": "close",
}
PROXIES = ["http://test:test@host:port"]


async def download_page(url):
    retry_count = 0
    while True:
        status_code = -1
        msg = ""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=random.choice(PROXIES)) as r:
                    status_code = r.status
                    if status_code == 200:
                        return await r.json()
                    if status_code == 429:
                        await asyncio.sleep(5)
                        continue
        except Exception as e:
            status_code = e.status if hasattr(e, "status") else status_code
            if status_code == 429:
                await asyncio.sleep(5)
                continue
            msg = type(e).__name__
        retry_count += 1
        if retry_count >= 3:
            raise Exception(f"download {url} fail {status_code} {msg}")
        await asyncio.sleep(5)


def get_next_url():
    try:
        line = redis_client.lpop(SEARCH_KEY)
        if line is not None:
            return line.decode("utf-8")
    except Exception as e:
        logger.error("fetch from redis fail: " + str(e))


async def task(thread_num):
    out_file = open(f"out/out{thread_num}.txt", "a")

    while not STOP_FLAG:
        key = redis_client.lpop(SEARCH_KEY)
        if not key:
            logger.debug(f"{thread_num} idle")
            await asyncio.sleep(5)
            continue
        key = key.decode("utf-8")
        logger.info(f"[Thread {thread_num:02d}] process: {key}")

        for i in range(5):
            count = 20
            offset = i * count
            timestamp = math.floor(datetime.now().timestamp() * 1000)
            url = (
                "https://www.toutiao.com/api/search/content/"
                + f"?aid=24&app_name=web_search&offset={offset}&format=json&keyword={parse.quote(key)}"
                + f"&autoload=true&count=20&en_qc=1&cur_tab=1&from=search_tab&pd=synthesis&timestamp={timestamp}"
            )
            try:
                res = await download_page(url)
                if res:
                    out_file.write(json.dumps(res, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error(f"[Thread {thread_num:02d}] {url} fail, caused by: " + str(e))
                await asyncio.sleep(5)

        # break  # test

    out_file.close()
    logger.info(f"[Thread {thread_num:02d}] exit ...")


def signal_recv(signal, frame):
    global STOP_FLAG
    if not STOP_FLAG:
        STOP_FLAG = True
        logger.info("Cancel received, press ctrl+c again for force exit!")
    else:
        sys.exit(1)


signal.signal(signal.SIGINT, signal_recv)


async def main():
    await asyncio.gather(*([task(i) for i in range(100)]))


asyncio.run(main())
logger.debug("Graceful exit ^_^ ::")
