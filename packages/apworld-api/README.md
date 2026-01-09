# apworld-api

Repository server for APWorld package hosting and discovery.

## Installation

```console
pip install apworld-api
```

## Quick Start

```python
from apworld_api import create_app, APIConfig

# Create app with default configuration
app = create_app()

# Or with custom configuration
config = APIConfig(
    title="My APWorld Repository",
    debug=True,
)
app = create_app(config)
```

Run with uvicorn:

```console
uvicorn apworld_api:app --host 0.0.0.0 --port 8000
```

## Configuration

### APIConfig

Main configuration class with nested sub-configurations.

```python
from apworld_api import APIConfig, DatabaseConfig, StorageConfig, RateLimitConfig, AuthConfig

config = APIConfig(
    # Server settings
    title="APWorld Package Index",
    description="Repository server for APWorld packages",
    version="0.1.0",
    debug=False,
    
    # API settings
    api_prefix="/v1",
    docs_url="/docs",
    openapi_url="/openapi.json",
    
    # Sub-configurations
    database=DatabaseConfig(...),
    storage=StorageConfig(...),
    rate_limit=RateLimitConfig(...),
    auth=AuthConfig(...),
)
```

### DatabaseConfig

```python
from apworld_api import DatabaseConfig

database = DatabaseConfig(
    url="sqlite:///./apworld_repository.db",  # Database URL
    echo=False,                                # Log SQL queries
    pool_size=5,                               # Connection pool size
    max_overflow=10,                           # Max overflow connections
)
```

### StorageConfig

```python
from apworld_api import StorageConfig

# Local storage
storage = StorageConfig(
    backend="local",
    local_path="./packages",
)

# S3 storage
storage = StorageConfig(
    backend="s3",
    s3_bucket="my-apworld-bucket",
    s3_prefix="packages/",
)
```

### RateLimitConfig

```python
from apworld_api import RateLimitConfig

rate_limit = RateLimitConfig(
    enabled=True,
    requests_per_minute=100,
    burst_size=20,
)
```

### AuthConfig

```python
from apworld_api import AuthConfig

auth = AuthConfig(
    require_auth_for_upload=True,
    api_token_header="Authorization",
    oidc_enabled=False,
    oidc_issuer=None,
    oidc_audience=None,
)
```

### Environment Variables

Configuration can be loaded from environment variables:

```bash
# Database
APWORLD_DATABASE_URL=postgresql://localhost/apworld
APWORLD_DATABASE_ECHO=false

# Storage
APWORLD_STORAGE_BACKEND=s3
APWORLD_STORAGE_LOCAL_PATH=./packages
APWORLD_STORAGE_S3_BUCKET=my-bucket

# Rate limiting
APWORLD_RATE_LIMIT_ENABLED=true
APWORLD_RATE_LIMIT_RPM=100

# Authentication
APWORLD_OIDC_ENABLED=true
APWORLD_OIDC_ISSUER=https://github.com

# Debug
APWORLD_DEBUG=false
```

```python
# Load from environment
config = APIConfig.from_env()
app = create_app(config)
```

## API Endpoints

### Package Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/packages` | List all packages (paginated) |
| GET | `/v1/packages/{name}` | Get package metadata |
| GET | `/v1/packages/{name}/versions` | List package versions |
| GET | `/v1/packages/{name}/{version}` | Get specific version metadata |
| GET | `/v1/search` | Search packages by query |
| GET | `/v1/index.json` | Full package index for offline tooling |

### Download

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/packages/{name}/{version}/download/{filename}` | Download distribution file |

Response includes checksum headers:
- `X-Checksum-SHA256`: SHA256 hash of the file

### Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/packages/{name}/upload` | Upload new version |
| DELETE | `/v1/packages/{name}/{version}/yank` | Yank a version |

Upload requires authentication via API token or Trusted Publisher OIDC.

### Health & Documentation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check endpoint |
| GET | `/docs` | Swagger UI documentation |
| GET | `/openapi.json` | OpenAPI specification |

## Checksum Utilities

```python
from apworld_api import (
    compute_sha256,
    compute_sha256_file,
    compute_sha256_stream,
    verify_checksum,
    verify_checksum_file,
    ChecksumMismatchError,
)

# Compute SHA256 from bytes
hash_value = compute_sha256(b"file content")

# Compute SHA256 from file
hash_value = compute_sha256_file("path/to/file.apworld")

# Compute SHA256 from stream
with open("file.apworld", "rb") as f:
    hash_value = compute_sha256_stream(f)

# Verify checksum
try:
    verify_checksum(b"content", expected_hash)
except ChecksumMismatchError as e:
    print(f"Checksum mismatch: expected {e.expected}, got {e.actual}")

# Verify file checksum
verify_checksum_file("file.apworld", expected_hash)
```

## Error Handling

The API returns consistent error responses:

```json
{
    "error": {
        "code": "PACKAGE_NOT_FOUND",
        "message": "Package 'my-game' not found",
        "details": {}
    }
}
```

### Error Classes

```python
from apworld_api import (
    APIError,              # Base error class
    ErrorCode,             # Error code enum
    PackageNotFoundError,  # Package doesn't exist
    VersionNotFoundError,  # Version doesn't exist
    VersionExistsError,    # Version already uploaded
    InvalidManifestError,  # Manifest validation failed
    InvalidVersionError,   # Invalid version format
    UnauthorizedError,     # Authentication required
    ForbiddenError,        # Permission denied
    RateLimitedError,      # Rate limit exceeded
)

# Raise custom API errors
raise PackageNotFoundError("my-game")
raise VersionExistsError("my-game", "1.0.0")
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PACKAGE_NOT_FOUND` | 404 | Package doesn't exist |
| `VERSION_NOT_FOUND` | 404 | Version doesn't exist |
| `VERSION_EXISTS` | 409 | Version already uploaded |
| `INVALID_MANIFEST` | 400 | Manifest validation failed |
| `INVALID_VERSION` | 400 | Invalid version format |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Permission denied |
| `RATE_LIMITED` | 429 | Rate limit exceeded |

## Rate Limiting

When rate limiting is enabled, responses include headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

## Authentication

### API Token

```bash
curl -X POST https://api.example.com/v1/packages/my-game/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@my_game-1.0.0-py3-none-any.apworld"
```

### Trusted Publisher (OIDC)

For GitHub Actions workflows:

```yaml
- name: Publish to APWorld Repository
  uses: actions/upload-artifact@v4
  env:
    APWORLD_OIDC_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "apworld_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t apworld-api .
docker run -p 8000:8000 \
  -e APWORLD_DATABASE_URL=postgresql://db/apworld \
  -e APWORLD_STORAGE_BACKEND=s3 \
  -e APWORLD_STORAGE_S3_BUCKET=my-bucket \
  apworld-api
```

## OpenAPI Specification

The API automatically generates OpenAPI documentation:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Export the OpenAPI spec:

```bash
# Using curl
curl http://localhost:8000/openapi.json > openapi.json

# Using Python
from apworld_api import create_app
import json

app = create_app()
with open("openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)
```

## License

MIT License
