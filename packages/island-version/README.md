# island-version

Semantic version parsing and comparison for Island packages.

## Installation

```console
pip install island-version
```

## Features

- Parse semantic versions (MAJOR.MINOR.PATCH)
- Support pre-release suffixes (-alpha, -beta, -rc)
- Support build metadata suffixes (+build)
- PEP 440 compatible version ordering
- No external dependencies (stdlib only)

## API Reference

### Version Class

A dataclass representing a parsed semantic version.

```python
from island_version import Version

@dataclass(frozen=True)
class Version:
    major: int          # Major version number (breaking changes)
    minor: int          # Minor version number (new features)
    patch: int          # Patch version number (bug fixes)
    prerelease: str | None  # Pre-release identifier (e.g., "alpha.1")
    build: str | None   # Build metadata (e.g., "build.123")
```

#### Properties

- `is_prerelease` - Returns `True` if this is a pre-release version
- `base_version` - Returns the base version without pre-release or build metadata

#### Example

```python
from island_version import parse_version

version = parse_version("1.2.3-alpha.1+build.456")
print(version.major)        # 1
print(version.minor)        # 2
print(version.patch)        # 3
print(version.prerelease)   # "alpha.1"
print(version.build)        # "build.456"
print(version.is_prerelease)  # True
print(version.base_version)   # "1.2.3"
print(str(version))         # "1.2.3-alpha.1+build.456"
```

### parse_version(version_string)

Parse a semantic version string into a Version object.

```python
from island_version import parse_version, InvalidVersionError

# Basic version
version = parse_version("1.2.3")
# Version(major=1, minor=2, patch=3, prerelease=None, build=None)

# With pre-release
version = parse_version("1.0.0-alpha.1")
# Version(major=1, minor=0, patch=0, prerelease='alpha.1', build=None)

# With build metadata
version = parse_version("2.0.0-rc.1+build.456")
# Version(major=2, minor=0, patch=0, prerelease='rc.1', build='456')

# Invalid version raises exception
try:
    parse_version("invalid")
except InvalidVersionError as e:
    print(e.version)   # "invalid"
    print(e.message)   # "Invalid semantic version: invalid"
```

### is_valid_semver(version_string)

Check if a string is a valid semantic version.

```python
from island_version import is_valid_semver

is_valid_semver("1.0.0")        # True
is_valid_semver("1.0.0-alpha")  # True
is_valid_semver("1.0.0+build")  # True
is_valid_semver("1.0")          # False (missing patch)
is_valid_semver("v1.0.0")       # False (no 'v' prefix)
is_valid_semver("invalid")      # False
```

### compare_versions(version1, version2)

Compare two semantic versions following PEP 440 ordering.

```python
from island_version import compare_versions

# Returns -1 if version1 < version2
compare_versions("1.0.0", "2.0.0")  # -1

# Returns 0 if version1 == version2
compare_versions("1.0.0", "1.0.0")  # 0

# Returns 1 if version1 > version2
compare_versions("2.0.0", "1.0.0")  # 1

# Pre-release ordering: alpha < beta < rc < release
compare_versions("1.0.0-alpha", "1.0.0-beta")  # -1
compare_versions("1.0.0-beta", "1.0.0-rc")     # -1
compare_versions("1.0.0-rc.1", "1.0.0")        # -1 (pre-release < release)

# Numeric pre-release comparison
compare_versions("1.0.0-alpha.1", "1.0.0-alpha.2")  # -1

# Build metadata is ignored in comparisons
compare_versions("1.0.0+build1", "1.0.0+build2")  # 0
```

### version_key(version)

Return a sort key for a version, suitable for sorting.

```python
from island_version import version_key

versions = ["2.0.0", "1.0.0", "1.0.0-alpha", "1.0.0-beta", "1.0.0-rc.1"]
sorted_versions = sorted(versions, key=version_key)
# ['1.0.0-alpha', '1.0.0-beta', '1.0.0-rc.1', '1.0.0', '2.0.0']
```

### SEMVER_PATTERN

The compiled regex pattern for semantic version validation.

```python
from island_version import SEMVER_PATTERN

match = SEMVER_PATTERN.match("1.2.3-alpha.1+build")
if match:
    print(match.group("major"))       # "1"
    print(match.group("minor"))       # "2"
    print(match.group("patch"))       # "3"
    print(match.group("prerelease"))  # "alpha.1"
    print(match.group("buildmetadata"))  # "build"
```

## Version Format

This package follows [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

- **MAJOR**: Incremented for incompatible API changes
- **MINOR**: Incremented for backward-compatible new features
- **PATCH**: Incremented for backward-compatible bug fixes
- **PRERELEASE**: Optional, dot-separated identifiers (alpha, beta, rc)
- **BUILD**: Optional build metadata (ignored in comparisons)

### Valid Examples

```
0.0.1
1.0.0
1.2.3
1.0.0-alpha
1.0.0-alpha.1
1.0.0-beta.2
1.0.0-rc.1
1.0.0+build
1.0.0+build.123
1.0.0-alpha.1+build.456
```

### Invalid Examples

```
1.0           # Missing patch version
v1.0.0        # No 'v' prefix allowed
1.0.0.0       # Too many parts
1.0.0-        # Empty pre-release
1.0.0+        # Empty build metadata
```

## License

MIT License
