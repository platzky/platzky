"""Closed set of page sections for page-decorator plugin filtering."""

from typing import Literal, get_args

PageSection = Literal["head", "body"]
ALL_PAGE_SECTIONS: frozenset[PageSection] = frozenset(get_args(PageSection))
