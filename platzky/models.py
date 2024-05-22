from pydantic import BaseModel
import datetime
import humanize


class Image(BaseModel):
    url: str
    alternateText: str


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
    # excerpt: str
    tags: list[str]
    language: str
    coverImage: Image
    date: str

    def __lt__(self, other):
        if isinstance(other, Post):
            return self.date < other.date
        return NotImplemented

    # def format_post(post):
    #     now = datetime.datetime.now()
    #     def comment_sort_key(comment_: Dict[str, Any]) -> Any:
    #         return comment_["date"]
    #
    #     for comment in post["comments"]:
    #         comment.update({"time_delta": get_delta(now, comment["date"])})
    #
    #     post["comments"].sort(key=comment_sort_key, reverse=True)
    #     return post


Page = Post


class Color(BaseModel):
    r: int
    g: int
    b: int
    a: int
