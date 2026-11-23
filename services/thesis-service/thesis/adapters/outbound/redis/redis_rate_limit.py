from uuid import UUID

from redis import Redis

from thesis.application.ports.rate_limit import RateLimitExceeded


CONSUME = """
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local count = tonumber(redis.call('GET', KEYS[1]) or '0')

if count >= limit then
    local ttl = redis.call('TTL', KEYS[1])

    if ttl < 0 then
        redis.call('EXPIRE', KEYS[1], window)
        ttl = window
    end

    return math.max(1, ttl)
end

redis.call('INCR', KEYS[1])

if redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], window)
end

return 0
"""


class RedisRateLimit:

    def __init__(self, client: Redis, operation: str, limit: int, window_seconds: int):
        if limit < 1 or window_seconds < 1:
            raise ValueError("A cota e a duração da janela devem ser positivas.")

        self.client = client
        self.operation = operation
        self.limit = limit
        self.window_seconds = window_seconds

    def key(self, account_id: UUID) -> str:
        return f"thesis:rate:{self.operation}:{account_id}"

    def consume(self, account_id: UUID) -> None:
        retry_after = int(self.client.eval(CONSUME, 1, self.key(account_id), self.limit, self.window_seconds))

        if retry_after:
            raise RateLimitExceeded(retry_after)
