from functools import partial
from typing import Any, Callable

from pydantic import BaseModel, Field

from abc import abstractmethod, ABC
from ..models import MenuItem, Post, Page, Color


class DB(ABC):
    db_name: str = "DB"
    module_name: str = "db"
    config_type: type

    def __init_subclass__(cls, *args, **kw):
        """Check that all methods defined in the subclass exist in the superclasses.
        This is to prevent subclasses from adding new methods to the DB object.
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

    def extend(self, function_name: str, function: Callable) -> None:
        """
        Add a function to the DB object. The function must take the DB object as first parameter.

        Parameters:
        function_name (str): The name of the function to add.
        function (Callable): The function to add to the DB object.
        """
        if not callable(function):
            raise ValueError(
                f"The provided func for '{function_name}' is not callable."
            )
        try:
            bound_function = partial(function, self)
            setattr(self, function_name, bound_function)
        except Exception as e:
            raise ValueError(f"Failed to extend DB with function {function_name}: {e}")

    @abstractmethod
    def get_all_posts(self, lang) -> list[Post]:
        pass

    @abstractmethod
    def get_menu_items(self) -> list[MenuItem]:
        pass

    @abstractmethod
    def get_post(self, slug) -> Post:
        pass

    @abstractmethod
    def get_page(self, slug) -> Page:
        pass

    @abstractmethod
    def get_posts_by_tag(self, tag, lang) -> Any:
        pass

    @abstractmethod
    def add_comment(self, author_name, comment, post_slug) -> None:
        pass

    @abstractmethod
    def get_logo_url(self) -> str:
        pass

    @abstractmethod
    def get_primary_color(self) -> Color:
        pass

    @abstractmethod
    def get_secondary_color(self) -> Color:
        pass

    @abstractmethod
    def get_plugins_data(self) -> list:
        pass

    @abstractmethod
    def get_font(self) -> str:
        pass

    @abstractmethod
    def get_site_content(self) -> str:
        pass


class DBConfig(BaseModel):
    type: str = Field(alias="TYPE")
