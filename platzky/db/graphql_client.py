"""Shared GraphQL client construction, exposed as a per-thread client getter.

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


def make_graphql_client_getter(endpoint: str, token: str) -> Callable[[], Client]:
    """Build a getter that lazily returns this thread's GraphQL client.

    This returns a getter, not a client: no client is built until the getter
    is first called.

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
