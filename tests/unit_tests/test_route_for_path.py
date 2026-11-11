import pytest
from werkzeug.routing import Map, RequestRedirect, Rule

from platzky.language_routing import RouteMatch, route_for_path

_URL_MAP = Map(
    [
        Rule("/about", endpoint="about", methods=["GET"]),
        Rule("/items/<int:item_id>", endpoint="item", methods=["GET"]),
        Rule("/submit", endpoint="submit", methods=["POST"]),
        Rule("/dir/", endpoint="dir", methods=["GET"]),
    ]
)


def test_route_for_path_returns_endpoint_and_view_args():
    assert route_for_path(_URL_MAP, "localhost", "/items/7") == RouteMatch("item", {"item_id": 7})


def test_route_for_path_is_none_for_unknown_path():
    assert route_for_path(_URL_MAP, "localhost", "/nowhere") is None


def test_route_for_path_is_none_when_only_other_methods_are_served():
    assert route_for_path(_URL_MAP, "localhost", "/submit") is None


def test_route_for_path_propagates_strict_slash_redirect():
    with pytest.raises(RequestRedirect):
        route_for_path(_URL_MAP, "localhost", "/dir")
