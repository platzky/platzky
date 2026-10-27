# Platzky Database Modules

This directory contains the database abstraction layer for the Platzky application. The database modules provide a consistent interface for accessing content regardless of where it's stored.

## Architecture

The database layer is built on an abstract base class (DB) that defines a common interface. Multiple implementations are provided for different storage backends:

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

Behind the `DB` interface, data access is split into repositories, each a
`typing.Protocol`:

| Protocol | File | Covers |
|---|---|---|
| `SiteConfigRepository` | `site_config_repository.py` | branding, menu, home page, footer, blog meta |
| `PluginConfigRepository` | `plugin_config_repository.py` | plugin configuration |

Implementations live in `<backend>_<repo>.py` (for example
`json_site_config_repository.py`, `json_plugin_config_repository.py`). So far
only the `json` backend implements them; `mongo` and `graphql` still implement
those `DB` methods inline. A `DB` subclass builds its repositories and
forwards each of their methods to them, in `self._site_config` and
`self._plugin_config`. Posts, pages and comments are still read inline by each
`DB` subclass.

The JSON repositories share one `JsonDocument` (`json_document.py`): the loaded
dict, plus a private store and write lock. A JSON repository that writes does so
inside `with document.edit() as data:`, which holds the lock, yields the dict and
saves it on success (nothing is saved if the block raises).

To add a new repository:

1. Define its Protocol in a new `platzky/db/<name>.py`.
2. Add one implementation per backend, named `<backend>_<name>.py`.
3. Build each one in the matching `DB` subclass and forward the `DB` methods to it.
4. Add a contract test parametrized over all backends, plus one test file per implementation.
5. Add facade delegation tests to each backend's `DB` test file.


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

# Now you can use any of the standard DB methods
posts = db.get_all_posts("en")
menu_items = db.get_menu_items_in_lang("en")
```