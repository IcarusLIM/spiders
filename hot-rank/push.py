from aiohttp.typedefs import DEFAULT_JSON_DECODER
from cryption import *
import binascii
import hmac
import hashlib
import random
import time
import json
import asyncio, aiohttp
import traceback
from urllib import parse
from uuid import uuid4
from config import (
    HOT_RESP_CACHE_KEY,
    PUSH_BATCH_SIZE,
    redis_client,
    mongo_client,
    logging,
)

logger = logging.getLogger(__name__)


async def push_loop():
    last_push = time.time()
    while True:
        if redis_client.llen(HOT_RESP_CACHE_KEY) > PUSH_BATCH_SIZE or time.time() - last_push > 30:
            res_mongo = []
            for _ in range(PUSH_BATCH_SIZE):
                r = redis_client.lpop(HOT_RESP_CACHE_KEY)
                if not r:
                    break
                data = json.loads(r.decode("utf-8"))
                res_mongo.append(data)
            if len(res_mongo) == 0:
                await asyncio.sleep(5)
                continue
            # save to mongo
            try:
                mongo_client["default"].insert_many(res_mongo)
            except Exception as e:
                logger.warning(e)
        else:
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(push_loop())
