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
# No built-in linting/testing commands - add as needed
# Code uses type hints throughout - consider adding mypy
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
- Auto-reconnection with backoff: 1s → 2s → 4s → ... → 60s
- Subscribe to worlds: `{"type": "subscribe", "world": world_id}`
- Updates arrive as: `{"type": "plot_update", "plot": {...}}`

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