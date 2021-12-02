from datetime import datetime
import json
import mysql.connector
import aiohttp, asyncio

from config import logging, redis_client, HOT_SEARCH_KEY
import os
import traceback


logger = logging.getLogger(__name__)


class DBConnection:
    db_param = {
        "host": "host",
        "port": "3306",
        "user": "user",
        "password": "password",
        "database": "database",
    }
    connection = None

    def __enter__(self):
        self.connection = mysql.connector.connect(**self.db_param)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()


progress_file = "progress.txt"


def load_progress():
    progress = 0
    dup = set()
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            progress = int(f.readline().strip())
            for l in f:
                dup.add(l.strip())
    return progress, dup


def store_progress(progress, query_ids=set()):
    with open(progress_file, "w") as f:
        f.write(str(progress) + "\n")
        for query_id in query_ids:
            f.write(query_id + "\n")


def new_req(brand, query_key, _src, _datetime):
    url = None
    if brand == "douban":
        url = f"https://m.douban.com/search/?query={query_key}&type=movie"
    elif brand == "iqiyi":
        url = f"https://pcw-api.iqiyi.com/strategy/pcw/data/soBaseCardLeftSide?pageNum=1&key={query_key}&channel_name=&duration_level=0&need_qc=0&site_publish_date_level=&site=&mode=1&bitrate=&af=0"
    elif brand == "qq":
        url = f"https://v.qq.com/x/search/?q={query_key}&stag=12"
    meta = {"brand": brand, "type": "", "_src": _src, "_datetime": _datetime}
    return {"url": url, "meta": meta}


async def send():
    progress, dup = load_progress()
    count = 0
    with DBConnection() as db:
        cursor = db.cursor()
        try:
            cursor.execute(
                f"SELECT item_id, item, update_time FROM `app_board_crawler` WHERE update_time >= {progress} order by update_time"
            )
            async with aiohttp.ClientSession() as session:
                for query_id, data, update_time in cursor:
                    if update_time != progress:
                        progress = update_time
                        store_progress(progress)
                        dup.clear()
                    if query_id in dup:
                        continue
                    dup.add(query_id)
                    count += 1
                    try:
                        data = json.loads(data)
                        _src = {key: data[key] for key in ["id", "name", "board", "output_type"] if key in data}
                        brand = _src.get("board", "ALL")
                        query_key = _src["name"]
                        _datetime = datetime.fromtimestamp(update_time).strftime("%Y%m%d%H%M")
                        if brand == "ALL":
                            reqs = [new_req(b, query_key, _src, _datetime) for b in ["douban", "iqiyi", "qq"]]
                            for req in reqs:
                                redis_client.lpush(HOT_SEARCH_KEY, json.dumps(req, ensure_ascii=False))
                                logger.debug(f"push query: {req['url']}")
                        else:
                            req = new_req(brand, query_key, _src,_datetime)
                            redis_client.lpush(HOT_SEARCH_KEY, json.dumps(req, ensure_ascii=False))
                            logger.debug(f"push query: {req['url']}")
                    except Exception as e:
                        logger.warning(f"key error: {e}")

            store_progress(progress, dup)
            return count
        finally:
            cursor.close()
            db.commit()


async def scanner_loop():
    while True:
        logger.info("Scanner loop start")
        try:
            count = await send()
            logger.info(f"Scanner loop finish - {count}")
            if count == 0:
                await asyncio.sleep(10)
        except:
            traceback.print_exc()
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(scanner_loop())
