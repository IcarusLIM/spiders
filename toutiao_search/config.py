import redis

redis_client = redis.Redis(
    host="10.143.15.226", port="6379", password="waibiwaibiwaibibabo"
)
SEARCH_KEY = "toutiao_search:keys"
RES_KEY = "toutiao_search:res"