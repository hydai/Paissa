#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 hydai
# Licensed under the MIT License - see LICENSE file for details
#
"""
PaissaDB HTTP Server - RESTful API server with caching for PaissaDB data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from paissa_client import PaissaClient, PlotState, HouseSize, LottoPhase


# Pydantic models for API responses
class WorldInfo(BaseModel):
    id: int
    name: str
    datacenter_id: int
    datacenter_name: str


class PlotInfo(BaseModel):
    world_id: int
    district_id: int
    district_name: str
    ward_number: int
    plot_number: int
    size: int
    size_name: str
    price: int
    last_updated_time: int
    first_seen_time: int
    purchase_system: int
    lotto_entries: Optional[int] = None
    lotto_phase: Optional[int] = None
    lotto_phase_name: Optional[str] = None
    lotto_phase_until: Optional[int] = None
    time_left_seconds: Optional[int] = None


class WorldStats(BaseModel):
    world_id: int
    world_name: str
    total_plots: int
    plots_by_size: Dict[str, int]
    plots_by_phase: Dict[str, int]
    price_stats: Dict[str, int]
    last_updated: datetime


class CacheInfo(BaseModel):
    world_id: int
    cached_at: datetime
    expires_at: datetime
    plot_count: int


# Cache manager
class WorldCache:
    def __init__(self, ttl_minutes: int = 5):
        self.cache: Dict[int, Dict] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        
    def get(self, world_id: int) -> Optional[Dict]:
        """Get cached data if not expired"""
        if world_id in self.cache:
            cache_entry = self.cache[world_id]
            if datetime.now() < cache_entry['expires_at']:
                return cache_entry
        return None
        
    def set(self, world_id: int, plots: List[PlotState]):
        """Cache world data"""
        now = datetime.now()
        self.cache[world_id] = {
            'plots': plots,
            'cached_at': now,
            'expires_at': now + self.ttl
        }
        
    def invalidate(self, world_id: int):
        """Remove world from cache"""
        if world_id in self.cache:
            del self.cache[world_id]
            
    def get_info(self) -> List[CacheInfo]:
        """Get cache status information"""
        info = []
        for world_id, data in self.cache.items():
            info.append(CacheInfo(
                world_id=world_id,
                cached_at=data['cached_at'],
                expires_at=data['expires_at'],
                plot_count=len(data['plots'])
            ))
        return info


# Global instances
client: Optional[PaissaClient] = None
cache = WorldCache(ttl_minutes=5)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage PaissaClient lifecycle"""
    global client
    client = PaissaClient()
    await client.init()
    logger.info("PaissaDB client initialized")
    yield
    await client.close()
    logger.info("PaissaDB client closed")


# Create FastAPI app
app = FastAPI(
    title="PaissaDB API Server",
    description="RESTful API for FFXIV housing data with caching",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
def format_plot_info(plot: PlotState, client: PaissaClient) -> PlotInfo:
    """Convert PlotState to PlotInfo with additional formatted fields"""
    size_names = {
        HouseSize.SMALL: "Small",
        HouseSize.MEDIUM: "Medium",
        HouseSize.LARGE: "Large"
    }
    
    phase_names = {
        LottoPhase.ENTRY: "Entry",
        LottoPhase.RESULTS: "Results",
        LottoPhase.UNAVAILABLE: "Unavailable"
    }
    
    # Calculate time left
    time_left = None
    if plot.lotto_phase_until:
        time_left = max(0, plot.lotto_phase_until - int(datetime.now().timestamp()))
    
    return PlotInfo(
        world_id=plot.world_id,
        district_id=plot.district_id,
        district_name=client.district_name(plot.district_id),
        ward_number=plot.ward_number,
        plot_number=plot.plot_number,
        size=plot.size,
        size_name=size_names.get(plot.size, "Unknown"),
        price=plot.price,
        last_updated_time=plot.last_updated_time,
        first_seen_time=plot.first_seen_time,
        purchase_system=plot.purchase_system,
        lotto_entries=plot.lotto_entries,
        lotto_phase=plot.lotto_phase,
        lotto_phase_name=phase_names.get(plot.lotto_phase) if plot.lotto_phase else None,
        lotto_phase_until=plot.lotto_phase_until,
        time_left_seconds=time_left
    )


async def get_world_plots(world_id: int, force_refresh: bool = False) -> List[PlotState]:
    """Get plots for a world with caching"""
    # Check cache first
    if not force_refresh:
        cached_data = cache.get(world_id)
        if cached_data:
            logger.info(f"Returning cached data for world {world_id}")
            return cached_data['plots']
    
    # Load from API
    logger.info(f"Loading data from API for world {world_id}")
    await client.load_world(world_id, force_reload=True)
    plots = client.get_world_plots(world_id)
    
    # Update cache
    cache.set(world_id, plots)
    
    return plots


# API Endpoints
@app.get("/", tags=["General"])
async def root():
    """API root endpoint"""
    return {
        "message": "PaissaDB API Server",
        "version": "1.0.0",
        "endpoints": {
            "worlds": "/api/worlds",
            "world_plots": "/api/worlds/{world_id}/plots",
            "world_stats": "/api/worlds/{world_id}/stats",
            "search": "/api/search",
            "cache": "/api/cache"
        }
    }


@app.get("/api/worlds", response_model=List[WorldInfo], tags=["Worlds"])
async def get_worlds():
    """Get all available worlds"""
    if not client.worlds:
        await client.get_worlds()
    
    return [
        WorldInfo(
            id=world.id,
            name=world.name,
            datacenter_id=world.datacenter_id,
            datacenter_name=world.datacenter_name
        )
        for world in client.worlds
    ]


@app.get("/api/worlds/{world_id}/plots", response_model=List[PlotInfo], tags=["Plots"])
async def get_plots(
    world_id: int,
    size: Optional[str] = Query(None, description="Filter by size: small, medium, large"),
    min_price: Optional[int] = Query(None, description="Minimum price"),
    max_price: Optional[int] = Query(None, description="Maximum price"),
    lottery_only: bool = Query(False, description="Only show lottery plots"),
    available_only: bool = Query(False, description="Only show immediately available plots"),
    sort_by: str = Query("ward", description="Sort by: ward, price, entries"),
    limit: int = Query(100, description="Maximum number of results"),
    force_refresh: bool = Query(False, description="Force refresh from API")
):
    """Get plots for a specific world with optional filters"""
    plots = await get_world_plots(world_id, force_refresh)
    
    # Apply filters
    filtered_plots = plots
    
    # Size filter
    if size:
        size_map = {
            "small": HouseSize.SMALL,
            "medium": HouseSize.MEDIUM,
            "large": HouseSize.LARGE
        }
        if size.lower() in size_map:
            size_value = size_map[size.lower()]
            filtered_plots = [p for p in filtered_plots if p.size == size_value]
    
    # Price filters
    if min_price:
        filtered_plots = [p for p in filtered_plots if p.price >= min_price]
    if max_price:
        filtered_plots = [p for p in filtered_plots if p.price <= max_price]
    
    # Lottery filter
    if lottery_only:
        filtered_plots = [p for p in filtered_plots if p.lotto_phase == LottoPhase.ENTRY]
    
    # Available only filter
    if available_only:
        filtered_plots = [p for p in filtered_plots if p.lotto_entries is None]
    
    # Sorting
    if sort_by == "price":
        filtered_plots.sort(key=lambda p: p.price)
    elif sort_by == "entries":
        filtered_plots.sort(key=lambda p: p.lotto_entries or 999999)
    else:  # ward
        filtered_plots.sort(key=lambda p: (p.district_id, p.ward_number, p.plot_number))
    
    # Apply limit
    filtered_plots = filtered_plots[:limit]
    
    # Convert to response model
    return [format_plot_info(plot, client) for plot in filtered_plots]


@app.get("/api/worlds/{world_id}/stats", response_model=WorldStats, tags=["Statistics"])
async def get_world_stats(
    world_id: int,
    force_refresh: bool = Query(False, description="Force refresh from API")
):
    """Get statistics for a specific world"""
    plots = await get_world_plots(world_id, force_refresh)
    
    if not plots:
        raise HTTPException(status_code=404, detail=f"No data found for world {world_id}")
    
    # Calculate statistics
    size_counts = {"small": 0, "medium": 0, "large": 0}
    phase_counts = {"available": 0, "entry": 0, "results": 0, "unavailable": 0}
    prices = []
    
    for plot in plots:
        # Size statistics
        if plot.size == HouseSize.SMALL:
            size_counts["small"] += 1
        elif plot.size == HouseSize.MEDIUM:
            size_counts["medium"] += 1
        elif plot.size == HouseSize.LARGE:
            size_counts["large"] += 1
        
        # Phase statistics
        if plot.lotto_entries is None:
            phase_counts["available"] += 1
        elif plot.lotto_phase == LottoPhase.ENTRY:
            phase_counts["entry"] += 1
        elif plot.lotto_phase == LottoPhase.RESULTS:
            phase_counts["results"] += 1
        elif plot.lotto_phase == LottoPhase.UNAVAILABLE:
            phase_counts["unavailable"] += 1
        
        prices.append(plot.price)
    
    # Price statistics
    price_stats = {
        "min": min(prices) if prices else 0,
        "max": max(prices) if prices else 0,
        "average": sum(prices) // len(prices) if prices else 0
    }
    
    return WorldStats(
        world_id=world_id,
        world_name=client.world_name(world_id),
        total_plots=len(plots),
        plots_by_size=size_counts,
        plots_by_phase=phase_counts,
        price_stats=price_stats,
        last_updated=datetime.now()
    )


@app.get("/api/search", response_model=List[PlotInfo], tags=["Search"])
async def search_plots(
    max_price: int = Query(..., description="Maximum price"),
    size: Optional[str] = Query(None, description="Filter by size: small, medium, large"),
    worlds: Optional[str] = Query(None, description="Comma-separated world IDs"),
    lottery_only: bool = Query(False, description="Only show lottery plots"),
    limit: int = Query(50, description="Maximum number of results")
):
    """Search for plots across multiple worlds"""
    # Parse world IDs
    world_ids = []
    if worlds:
        try:
            world_ids = [int(w.strip()) for w in worlds.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid world IDs format")
    else:
        # If no worlds specified, search all worlds
        if not client.worlds:
            await client.get_worlds()
        world_ids = [w.id for w in client.worlds[:10]]  # Limit to first 10 worlds
    
    # Collect plots from all worlds
    all_plots = []
    for world_id in world_ids:
        try:
            plots = await get_world_plots(world_id)
            all_plots.extend(plots)
        except Exception as e:
            logger.error(f"Error loading world {world_id}: {e}")
    
    # Apply filters
    filtered_plots = all_plots
    
    # Price filter
    filtered_plots = [p for p in filtered_plots if p.price <= max_price]
    
    # Size filter
    if size:
        size_map = {
            "small": HouseSize.SMALL,
            "medium": HouseSize.MEDIUM,
            "large": HouseSize.LARGE
        }
        if size.lower() in size_map:
            size_value = size_map[size.lower()]
            filtered_plots = [p for p in filtered_plots if p.size == size_value]
    
    # Lottery filter
    if lottery_only:
        filtered_plots = [p for p in filtered_plots if p.lotto_phase == LottoPhase.ENTRY]
    
    # Sort by price and limit
    filtered_plots.sort(key=lambda p: p.price)
    filtered_plots = filtered_plots[:limit]
    
    # Convert to response model
    return [format_plot_info(plot, client) for plot in filtered_plots]


@app.get("/api/cache", response_model=List[CacheInfo], tags=["Cache"])
async def get_cache_info():
    """Get cache status information"""
    return cache.get_info()


@app.delete("/api/cache/{world_id}", tags=["Cache"])
async def clear_world_cache(world_id: int):
    """Clear cache for a specific world"""
    cache.invalidate(world_id)
    return {"message": f"Cache cleared for world {world_id}"}


@app.delete("/api/cache", tags=["Cache"])
async def clear_all_cache():
    """Clear all cached data"""
    cache.cache.clear()
    return {"message": "All cache cleared"}


# Health check
@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "client_connected": client is not None and client._ws is not None,
        "cached_worlds": len(cache.cache),
        "timestamp": datetime.now().isoformat()
    }


def main():
    """Run the server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PaissaDB HTTP API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    uvicorn.run(
        "paissa_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()