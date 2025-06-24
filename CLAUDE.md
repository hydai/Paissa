# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PaissaDB client - A Python library for accessing the PaissaDB API (Final Fantasy XIV housing database). Provides multiple interfaces: core client library, CLI, interactive TUI, and HTTP API server.

## Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Applications
```bash
# CLI Tool
python paissa_cli.py worlds                    # List all worlds
python paissa_cli.py show 35 --size small      # Show plots for world
python paissa_cli.py export 35 -o data.json    # Export to JSON
python paissa_cli.py monitor 35 --interval 60  # Monitor changes

# Interactive TUI
python interactive_monitor.py

# HTTP API Server
python paissa_server.py  # Access http://localhost:8000/docs for API docs

# Run Examples
python examples/example_usage.py      # Client library demo
python examples/api_client_example.py # HTTP API client demo
```

### Development
```bash
# Linting and type checking
black .                      # Format code
isort .                      # Sort imports
flake8 .                     # Lint code
mypy --install-types --non-interactive --ignore-missing-imports .  # Type check

# Docker operations
docker build -t paissa-server .
docker run -e PORT=8080 -p 8080:8080 paissa-server
docker-compose up -d         # Using docker-compose
```

## Architecture

### Core Components

1. **paissa_client.py** - Core client library
   - `PaissaClient` class handles WebSocket and REST connections
   - Automatic reconnection with exponential backoff
   - Methods: `get_worlds()`, `get_plots()`, `monitor_plots()`
   - Pure asyncio implementation

2. **paissa_cli.py** - Command-line interface
   - Built on argparse with subcommands
   - Filtering: `--size`, `--max-price`, `--district`, `--lottery-available`
   - Sorting: `--sort` by ward/price/entries
   - Output formats: console tables or JSON

3. **interactive_monitor.py** - Terminal UI
   - Real-time monitoring with configurable refresh
   - Unicode table rendering with statistics
   - Chinese district name translations
   - Interactive keyboard controls

4. **paissa_server.py** - FastAPI HTTP server
   - REST endpoints: `/worlds`, `/plots/{world_id}`, `/stats/{world_id}`, `/search`
   - Built-in caching with 5-minute TTL (configurable)
   - Swagger UI at `/docs`
   - CORS enabled for web frontends

### Data Flow

```
PaissaDB API (paissadb.zhu.codes)
    ↓ WebSocket/REST
PaissaClient (async client)
    ├─→ CLI (synchronous wrapper)
    ├─→ TUI (async monitor)
    └─→ HTTP Server (FastAPI + cache)
            ↓
        REST API consumers
```

### Key Data Models

- `World`: id, name, datacenter
- `Plot`: id, world_id, district, ward, plot, size, price, entries, lottery_available
- `PlotResponse`: Pydantic model for API responses
- `WorldCache`: TTL-based cache implementation

## Implementation Notes

### Adding New Features

**New CLI Filter:**
1. Add argument in `paissa_cli.py` argparse setup
2. Update `filter_plots()` function logic
3. Add to help text documentation

**New API Endpoint:**
1. Add route in `paissa_server.py`
2. Create Pydantic response model if needed
3. Implement business logic (consider caching)
4. Document in endpoint docstring

**Modifying Cache:**
- TTL in `WorldCache.__init__` (default 300 seconds)
- Cache key is world_id
- Force refresh with `force_refresh=True` parameter

### WebSocket Handling

- Connection URL: `wss://paissadb.zhu.codes/ws`
- Auto-reconnection with exponential backoff (max 5 retries)
- Message types handled:
  - `plot_open`: New plot available
  - `plot_update`: Plot information changed
  - `plot_sold`: Plot no longer available
- WebSocket runs in background task (`_ws_handler`)

### Error Handling Patterns

- WebSocket: Catch `websockets.exceptions`, reconnect automatically
- HTTP client: Raise on non-200 status codes
- CLI: User-friendly error messages to stderr
- Server: Return appropriate HTTP status codes with detail

### Performance Considerations

- Single WebSocket connection for all world subscriptions
- HTTP server reuses client instance
- Cache prevents redundant API calls
- Use `asyncio.gather()` for concurrent operations

## Common Patterns

### Async Context Manager
```python
async with PaissaClient() as client:
    plots = await client.get_plots(world_id)
```

### CLI with Filters
```python
filtered = [p for p in plots if matches_filters(p)]
sorted_plots = sorted(filtered, key=sort_key)
```

### Cache Usage
```python
if not force_refresh and world_id in cache:
    return cache[world_id]
```

## Development Reminders

- Always activate virtual environment
  - Every time installing or executing Python, first enter venv
    - 每次要安裝或者執行 python 以前都需要先進入 venv 中

## CI/CD Workflows

### GitHub Actions

1. **Lint Workflow** (`.github/workflows/lint.yml`)
   - Runs on push/PR to master branch
   - Tests Python 3.9-3.12 compatibility
   - Executes: Black, isort, flake8, mypy
   - Caches pip dependencies

2. **Docker Workflow** (`.github/workflows/docker.yml`)
   - Builds multi-platform images (amd64, arm64)
   - Publishes to ghcr.io (GitHub Container Registry)
   - Tags: latest, version tags, branch-sha
   - Generates SBOM for security scanning

### Git Commit Conventions

When creating commits with Claude:
- Include attribution in commit messages:
  ```
  Your commit message here
  
  🤖 Generated with [Claude Code](https://claude.ai/code)
  
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```