import hashlib
import json
from functools import lru_cache

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchVector
from redis import Redis, RedisError

from repository.models import CatalogRevision, Entry


PUBLIC_FIELDS = ("thesis_id", "course_id", "defense_id", "title", "author", "advisor", "keywords",
                 "defense_year", "result", "final_hash", "published_at")


def public_entries():
    return Entry.objects.filter(published_at__isnull=False)


def public_data(row):
    return {
        **row, "thesis_id": str(row["thesis_id"]), "course_id": str(row["course_id"]),
        "defense_id": str(row["defense_id"]), "published_at": row["published_at"].isoformat(),
        "keywords": row["keywords"].splitlines(),
    }


def search(params):
    query = public_entries()
    for field in ("title", "author", "keywords"):
        if field in params:
            query = query.alias(words=SearchVector(field, config="simple")).filter(
                words=SearchQuery(params[field], config="simple")
            )
    for field, column in (("course_id", "course_id"), ("advisor", "advisor"), ("year", "defense_year")):
        if field in params:
            query = query.filter(**{column: params[field]})
    size = params["page_size"]
    start = (params["page"] - 1) * size
    rows = list(query.order_by("-published_at", "thesis_id").values(*PUBLIC_FIELDS)[start:start + size + 1])
    return {"results": [public_data(row) for row in rows[:size]], "has_next": len(rows) > size}


@lru_cache(maxsize=4)
def redis_client(url):
    return Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)


def cached_search(params):
    revision = CatalogRevision.objects.values_list("revision", flat=True).filter(pk=1).first()
    if revision is None:
        return {"results": [], "has_next": False}
    key = hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    key = f"repository:public:v1:{revision}:{key}"
    cache = redis_client(settings.REDIS_URL)
    try:
        cached = cache.get(key)
        if cached:
            return json.loads(cached)
    except (RedisError, ValueError):
        return search(params)
    result = search(params)
    try:
        cache.setex(key, settings.CACHE_TTL, json.dumps(result))
    except RedisError:
        pass
    return result
