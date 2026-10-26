"""Shared lazy, per-thread GraphQL client construction.

AIOHTTPTransport's connect/close cycle tracks a single session flag per
transport instance; sharing one Client across threads lets a second thread's
connect() race a first thread's still-open session, raising
TransportAlreadyConnected. A client per thread avoids that. Every GraphQL-backed
repository that needs a client gets one from here, rather than each
reimplementing the same thread-safety-sensitive construction independently.
"""

import threading
from typing import Callable

from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport


def make_lazy_graphql_client(endpoint: str, token: str) -> Callable[[], Client]:
    """Build a callable that lazily returns this thread's GraphQL client.

    Args:
        endpoint: GraphQL API endpoint URL.
        token: Authentication token for the API.

    Returns:
        A zero-argument callable returning the current thread's client,
        building it on first call and reusing it on later calls from the
        same thread.
    """
    headers = {"Authorization": "bearer " + token}
    local = threading.local()

    def get_client() -> Client:
        """Return this thread's client, building it on first call."""
        client = getattr(local, "client", None)
        if client is None:
            transport = AIOHTTPTransport(url=endpoint, headers=headers)
            client = Client(transport=transport)
            local.client = client
        return client

    return get_client
