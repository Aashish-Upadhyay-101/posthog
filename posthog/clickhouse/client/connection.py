from enum import Enum
from functools import lru_cache

from clickhouse_driver import Client as SyncClient
from clickhouse_pool import ChPool
from django.conf import settings


class Workload(Enum):
    # Analytics queries, other 'lively' queries
    ONLINE = "ONLINE"
    # Historical exports, other long-running processes where latency is less critical
    OFFLINE = "OFFLINE"


def get_pool(workload: Workload):
    """
    Returns the right connection pool given a workload.

    Note that the same pool should be returned every call.
    """
    if workload == Workload.OFFLINE and settings.CLICKHOUSE_OFFLINE_CLUSTER_HOST is not None:
        return make_ch_pool(host=settings.CLICKHOUSE_OFFLINE_CLUSTER_HOST)

    return make_ch_pool()


def default_client():
    """
    Return a bare bones client for use in places where we are only interested in general ClickHouse state
    DO NOT USE THIS FOR QUERYING DATA
    """
    return SyncClient(
        host=settings.CLICKHOUSE_HOST,
        # We set "system" here as we don't necessarily have a "default" database,
        # which is what the clickhouse_driver would use by default. We are
        # assuming that this exists and we have permissions to access it. This
        # feels like a reasonably safe assumption as e.g. we already reference
        # `system.numbers` in multiple places within queries. We also assume
        # access to various other tables e.g. to handle async migrations.
        database="system",
        secure=settings.CLICKHOUSE_SECURE,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
        ca_certs=settings.CLICKHOUSE_CA,
        verify=settings.CLICKHOUSE_VERIFY,
    )


@lru_cache(maxsize=None)
def make_ch_pool(**overrides) -> ChPool:
    kwargs = {
        "host": settings.CLICKHOUSE_HOST,
        "database": settings.CLICKHOUSE_DATABASE,
        "secure": settings.CLICKHOUSE_SECURE,
        "user": settings.CLICKHOUSE_USER,
        "password": settings.CLICKHOUSE_PASSWORD,
        "ca_certs": settings.CLICKHOUSE_CA,
        "verify": settings.CLICKHOUSE_VERIFY,
        "connections_min": settings.CLICKHOUSE_CONN_POOL_MIN,
        "connections_max": settings.CLICKHOUSE_CONN_POOL_MAX,
        "settings": {"mutations_sync": "1"} if settings.TEST else {},
        # Without this, OPTIMIZE table and other queries will regularly run into timeouts
        "send_receive_timeout": 30 if settings.TEST else 999_999_999,
        **overrides,
    }

    return ChPool(**kwargs)


ch_pool = get_pool(workload=Workload.ONLINE)
