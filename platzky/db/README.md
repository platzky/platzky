# Platzky Database Modules

This directory contains the database abstraction layer for the Platzky application. The database modules provide a consistent interface for accessing content regardless of where it's stored.

## Architecture

The database layer is built on an abstract base class (DB) that defines a common interface. Multiple implementations are provided for different storage backends:

- **Json**: Base implementation for JSON data sources
- **JsonFile**: Local JSON file storage
- **GithubJsonDb**: JSON files stored in GitHub repository
- **GoogleJsonDb**: JSON files stored in Google Cloud Storage
- **GraphQL**: Content stored in a GraphQL API


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

## Cache Management (Optional)

By default, DB classes cache data for the lifetime of the instance. For long-running applications, you can enable optional cache TTL (time-to-live) and manual invalidation features.

### TTL-Based Cache Expiration

Add a `CACHE_TTL` parameter (in seconds) to enable automatic cache expiration:

```yaml
DB:
  TYPE: json_file
  PATH: "/path/to/data.json"
  CACHE_TTL: 300  # Cache expires after 5 minutes
```

```yaml
DB:
  TYPE: google_json
  BUCKET_NAME: "your-bucket-name"
  SOURCE_BLOB_NAME: "data.json"
  CACHE_TTL: 600  # Cache expires after 10 minutes
```

```yaml
DB:
  TYPE: github_json
  REPO_NAME: "username/repository"
  GITHUB_TOKEN: "your_github_token"
  BRANCH_NAME: "main"
  PATH_TO_FILE: "data.json"
  CACHE_TTL: 1800  # Cache expires after 30 minutes
```

When cache TTL expires, the database will automatically reload data from the source on the next access.

### Manual Cache Invalidation

You can manually refresh the cache at any time using the `refresh_cache()` method:

```python
from platzky.db.db_loader import get_db

db = get_db(db_config)

# Force reload data from source
db.refresh_cache()

# Now get fresh data
posts = db.get_all_posts("en")
```

### Backward Compatibility

Cache TTL is **opt-in**. If you don't specify `CACHE_TTL`, the database behaves exactly as before:
- Cache never expires during instance lifetime
- No automatic reloading
- Minimal overhead

This makes it perfect for:
- Short-lived processes (e.g., CLI tools, serverless functions)
- Static content that rarely changes
- Applications where restart is acceptable for updates