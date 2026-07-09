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
`DocumentStore` (see `platzky/db/stores.py`):

- `MemoryStore` — in-memory only, used by the plain `Json` backend.
- `FileStore` — a local file, written atomically (temp file + rename) so a
  crash mid-write cannot corrupt the database. Used by `JsonFile`.
- `ReadOnlyStore` — wraps a document already fetched by the caller (a GCS
  blob, a GitHub file) and rejects writes with `ReadOnlyStorageError` instead
  of silently discarding them. Used by `GoogleJsonDb` and `GithubJsonDb`.

Subclassing `Json` with a new transport is a matter of implementing
`DocumentStore` and passing it via `Json(store=...)`; no document logic needs
to be duplicated.


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