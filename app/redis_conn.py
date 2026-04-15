import redis

redis_client = redis.Redis(
    host="localhost",   # if using docker: "redis"
    port=6379,
    decode_responses=True
)