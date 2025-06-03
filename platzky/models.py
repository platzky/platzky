import datetime

import humanize
from pydantic import BaseModel


class CmsModule(BaseModel):
    name: str = ""
    description: str = ""
    template: str = ""
    slug: str = ""


# CmsModuleGroup is also a CmsModule, but it contains other CmsModules
class CmsModuleGroup(CmsModule):
    modules: list[CmsModule] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.modules: list[CmsModule] = data.get("modules", [])


class Image(BaseModel):
    url: str = ""
    alternateText: str = ""


class MenuItem(BaseModel):
    name: str
    url: str


class Comment(BaseModel):
    author: str
    comment: str
    date: str  # TODO change its type to datetime

    @property
    def time_delta(self) -> str:
        now = datetime.datetime.now()
        date = datetime.datetime.strptime(self.date.split(".")[0], "%Y-%m-%dT%H:%M:%S")
        return humanize.naturaltime(now - date)


class Post(BaseModel):
    author: str
    slug: str
    title: str
    contentInMarkdown: str
    comments: list[Comment]
    excerpt: str
    tags: list[str]
    language: str
    coverImage: Image
    date: str

    def __lt__(self, other):
        if isinstance(other, Post):
            return self.date < other.date
        raise NotImplementedError("Posts can only be compared with other posts")


Page = Post


class Color(BaseModel):
    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: int = 255):
        if not (0 <= r <= 255):
            raise ValueError("r must be between 0 and 255")
        if not (0 <= g <= 255):
            raise ValueError("g must be between 0 and 255")
        if not (0 <= b <= 255):
            raise ValueError("b must be between 0 and 255")
        if not (0 <= a <= 255):
            raise ValueError("a must be between 0 and 255")
        super().__init__(r=r, g=g, b=b, a=a)

    r: int
    g: int
    b: int
    a: int
