"""Abstract base classes for database implementations."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any

from pydantic import BaseModel, Field

from platzky.models import MenuItem, Page, Post


class DB(ABC):
    """Abstract base class for all database implementations."""
    db_name: str = "DB"
    module_name: str = "db"
    config_type: type

    def __init_subclass__(cls, *args, **kw):
        """Check that all methods defined in the subclass exist in the superclasses.
        This is to prevent subclasses from splitting up DB interface.
        """
        super().__init_subclass__(*args, **kw)
        for name in cls.__dict__:
            if name.startswith("_"):
                continue
            for superclass in cls.__mro__[1:]:
                if name in dir(superclass):
                    break
            else:
                raise TypeError(
                    f"Method {name} defined in {cls.__name__} does not exist in superclasses"
                )

    def extend(self, function_name: str, function: Callable[..., Any]) -> None:
        """
        Add a function to the DB object. The function must take the DB object as first parameter.

        Parameters:
        function_name (str): The name of the function to add.
        function (Callable): The function to add to the DB object.
        """
        if not callable(function):
            raise ValueError(f"The provided func for '{function_name}' is not callable.")
        try:
            bound_function = partial(function, self)
            setattr(self, function_name, bound_function)
        except Exception as e:
            raise ValueError(f"Failed to extend DB with function {function_name}: {e}")

    @abstractmethod
    def get_app_description(self, lang) -> str:
        """Retrieve the application description for a specific language."""
        pass

    @abstractmethod
    def get_all_posts(self, lang) -> list[Post]:
        """Retrieve all posts for a specific language."""
        pass

    @abstractmethod
    def get_menu_items_in_lang(self, lang) -> list[MenuItem]:
        """Retrieve menu items for a specific language."""
        pass

    @abstractmethod
    def get_post(self, slug) -> Post:
        """Retrieve a single post by its slug."""
        pass

    @abstractmethod
    def get_page(self, slug) -> Page:
        """Retrieve a page by its slug."""
        pass

    @abstractmethod
    def get_posts_by_tag(self, tag, lang) -> Any:
        """Retrieve posts filtered by tag and language."""
        pass

    @abstractmethod
    def add_comment(self, author_name, comment, post_slug) -> None:
        """Add a new comment to a post."""
        pass

    @abstractmethod
    def get_logo_url(self) -> str:
        """Retrieve the URL of the application logo.

        TODO: Provide alternative text along with the URL of logo.
        """
        pass

    @abstractmethod
    def get_favicon_url(self) -> str:
        """Retrieve the URL of the application favicon."""
        pass

    @abstractmethod
    def get_primary_color(self) -> str:
        """Retrieve the primary color for the application theme."""
        pass

    @abstractmethod
    def get_secondary_color(self) -> str:
        """Retrieve the secondary color for the application theme."""
        pass

    @abstractmethod
    def get_plugins_data(self) -> list[Any]:
        """Retrieve configuration data for all plugins."""
        pass

    @abstractmethod
    def get_font(self) -> str:
        """Get the font configuration for the application."""
        pass

    @abstractmethod
    def health_check(self) -> None:
        """Perform a health check on the database.

        Should raise an exception if the database is not healthy.
        This should be a lightweight operation suitable for health checks.
        """
        pass


class DBConfig(BaseModel):
    """Base configuration class for database connections."""
    type: str = Field(alias="TYPE")
