# Platzky Database Modules

This directory contains the database abstraction layer for the Platzky application. The database modules provide a consistent interface for accessing content regardless of where it's stored.

## Architecture

The database layer is built on an abstract base class (`DB`): a container of three repositories (`blog`, `site_config`, `plugin_config`), declared as abstract read-only properties, plus a `health_check()`. `DB` has no data-access methods of its own, and a backend that does not provide all three cannot be instantiated. Multiple implementations are provided for different storage backends:

- **Json**: Base implementation for JSON data sources
- **JsonFile**: Local JSON file storage
- **GithubJsonDb**: JSON files stored in GitHub repository
- **GoogleJsonDb**: JSON files stored in Google Cloud Storage
- **GraphQL**: Content stored in a GraphQL API

### Storage transports

`Json`, `JsonFile`, `GoogleJsonDb`, and `GithubJsonDb` are one data model (a
JSON document) with different persistence transports, not four independent
implementations. `Json` holds all the document logic (posts, pages, menu
items, comments, ...) and delegates *where the bytes live* to a
`JsonStore` (see `platzky/db/json_stores.py`):

- `MemoryStore` — in-memory only, used by the plain `Json` backend.
- `FileStore` — a local file, written atomically (temp file + rename) so a
  crash mid-write cannot corrupt the database. Used by `JsonFile`.
- `ReadOnlyStore` — wraps a document already fetched by the caller (a GCS
  blob, a GitHub file) and rejects writes with `ReadOnlyStorageError` instead
  of silently discarding them. Used by `GoogleJsonDb` and `GithubJsonDb`.

Subclassing `Json` with a new transport is a matter of implementing
`JsonStore` and passing it via `Json(store=...)`; no document logic needs
to be duplicated.


### Repositories

A `DB` exposes its data access as three repositories, each a `typing.Protocol`,
in the attributes `db.blog`, `db.site_config` and `db.plugin_config`:

| Attribute | Protocol | File | Covers |
|---|---|---|---|
| `db.blog` | `BlogRepository` (`.posts`: `PostRepository`, `.pages`: `PageRepository`) | `blog_repository.py` | posts, pages, comments, and `get_meta(lang)`, the blog index's title and description |
| `db.site_config` | `SiteConfigRepository` | `site_config_repository.py` | two methods: `get_site_config()` returns the site-wide `SiteConfig` (texts and logo defaults, favicon, font, colors) and `get_localized_content(lang)` returns the `LocalizedContent` of a language (texts and logo overrides, menu, footer, home page path; empty if the language has none). Both models are in the same file; `SiteSettings.from_layers` combines them |
| `db.plugin_config` | `PluginConfigRepository` | `plugin_config_repository.py` | plugin configuration |

Implementations live in `<backend>_<repo>.py` (for example
`json_blog_repository.py`, `mongo_plugin_config_repository.py`). Every backend
(`json`, `graphql`, `mongo`) implements all three. A `DB` subclass builds its
three repositories in its constructor, keeps them in private attributes and returns
them from the `blog`, `site_config` and `plugin_config` properties; that, plus
`health_check()`, is all a custom backend has to implement. A custom
`SiteConfigRepository` maps its storage to the two models: `get_site_config()`
and `get_localized_content(lang)`; the contract suite in
`tests/unit_tests/db/site_config_repository_contract.py` checks exactly that. The blog blueprint
(`create_blog_blueprint`) receives `db.blog` only, not the `DB`.

Each repository owns its storage and reads nothing else. In the JSON document,
`site_config` (the site-wide keys and `localized_content`) belongs to
`JsonSiteConfigRepository`, `blog` (`posts`, `pages`, `meta`) to `JsonBlogRepository` and
`plugins` to `JsonPluginConfigRepository`; each validates only its own section
(`SiteConfigSection` and `BlogSection`, unknown keys and nulls are errors), and
`Json.health_check()` and `platzky check` validate both through `validate_json_document`. In
Mongo, the `site_config` collection (document `_id: "config"`) and `localized_content` belong to
the site config repository, and `posts`, `pages` and `blog_meta` to the blog repository. Invalid
stored data raises `InvalidDataError` in both.

The JSON repositories share one `JsonDocument` (`json_document.py`): the loaded
dict, plus a private store and write lock. A JSON repository that writes does so
inside `with document.edit() as data:`, which holds the lock, yields the dict and
saves it on success (nothing is saved if the block raises).

To add a new repository:

1. Define its Protocol in a new `platzky/db/<name>.py`.
2. Add one implementation per backend, named `<backend>_<name>.py`.
3. Declare it as an abstract property on `DB` and build it in each `DB` subclass.
4. Add one test file per implementation, and a contract base class (like
   `blog_repository_contract.py`) that each backend's test module subclasses. For a remote backend (GraphQL) the contract's mock returns
   exactly what the server would answer in that test and never re-implements server logic
   such as filtering; what the server decides is tested in the backend's own file through
   the query variables it is sent. A backend that fails the contract has a bug: mark the
   test `xfail` with a link to the issue instead of special-casing the backend.
5. Test in each backend's `DB` test file that the constructor wires the repository.


## Configuration

Database configuration is specified in your application config file. Each database type has its own configuration schema.

### JSON File Database

```yaml
DB:
  TYPE: json_file
  PATH: "/path/to/data.json"

```
### GitHub JSON Database

```yaml
DB:
  TYPE: github_json
  REPO_NAME: "username/repository"
  GITHUB_TOKEN: "your_github_token"
  BRANCH_NAME: "main"
  PATH_TO_FILE: "data.json"
```

### Google JSON Database

```yaml
DB:
  TYPE: google_json
  BUCKET_NAME: "your-bucket-name"
  SOURCE_BLOB_NAME: "data.json"
```

### GraphQL Database

```yaml
DB:
  TYPE: graph_ql
  CMS_ENDPOINT: "https://your-graphql-endpoint.com/api"
  CMS_TOKEN: "your_graphql_token"
```

## Usage

The database is automatically initialized based on your configuration. The application will use the appropriate database implementation

```python
from platzky.db.db_loader import get_db

# db_config is loaded from your application config
db = get_db(db_config)

# Use the repositories
posts = db.blog.posts.get_all("en")
menu_items = db.site_config.get_localized_content("en").menu_items
```

## Extending: host-app repositories

A host app (for example Goodmap) that needs its own data access builds its own
repositories on the storage behind the database, rather than adding methods to
the `DB` object. Two read-only properties are the supported way in:

- `db.document` on every JSON backend (`Json`, `JsonFile`, `GoogleJsonDb`,
  `GithubJsonDb`) returns the `JsonDocument`. Read the dict through
  `document.data`; every write must go through `document.edit()`, which holds
  the write lock and persists atomically (and restores the document if the
  block raises). Hold on to nested values only briefly: a rolled-back edit
  replaces them with copies, so look them up from `data` on each call. On
  `GoogleJsonDb` and `GithubJsonDb` the store is read-only, so `edit()` raises
  `ReadOnlyStorageError` when the block exits.
- `db.database` on `MongoDB` returns the pymongo `Database`, for the host app's
  own collections and queries.

```python
class LocationRepository:
    def __init__(self, document: JsonDocument) -> None:
        self._document = document

    def all(self) -> list[dict]:
        return self._document.data.get("map", {}).get("data", [])

    def add(self, location: dict) -> None:
        with self._document.edit() as data:
            data.setdefault("map", {}).setdefault("data", []).append(location)


repository = LocationRepository(db.document)  # JSON backends
locations = db.database.locations  # MongoDB
```

Backends are chosen by configuration, so a host app picks its repository
implementation by checking which kind of database it was given (`isinstance`
against `Json` or `MongoDB`), not by a name attribute.
