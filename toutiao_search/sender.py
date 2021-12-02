from config import redis_client, SEARCH_KEY

with open("keys.txt", "r") as f:
    for line in f.readlines():
        redis_client.lpush(SEARCH_KEY, (line.split("\t", 1)[0]).strip())