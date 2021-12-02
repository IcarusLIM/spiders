import logging
import pymongo
import redis

logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
logging.getLogger("chardet").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("fontTools").setLevel(logging.WARNING)

PROXIES = [
    "http://test:test@host:port",
]
MAX_RETRY = 5

PUSH_BATCH_SIZE = 100
redis_client = redis.Redis(host="10.143.15.226", port="6379", password="waibiwaibiwaibibabo")
HOT_RANK_KEY = "hot_rank:reqs:rank"
HOT_SEARCH_KEY = "hot_rank:reqs:search"
HOT_DETAIL_KEY = "hot_rank:reqs:detail"
HOT_RESP_CACHE_KEY = "hot_rank:resp:cache"


mongo_client = pymongo.MongoClient("mongodb://root:waibiwaibiwaibibabo@host:27017")["hot"]
