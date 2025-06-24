#!/usr/bin/env python3
"""
Example client for PaissaDB HTTP API Server
"""

import requests
import json
from typing import List, Dict, Optional


class PaissaAPIClient:
    """Simple client for PaissaDB API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        
    def get_worlds(self) -> List[Dict]:
        """Get all available worlds"""
        response = self.session.get(f"{self.base_url}/api/worlds")
        response.raise_for_status()
        return response.json()
        
    def get_world_plots(
        self,
        world_id: int,
        size: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        lottery_only: bool = False,
        available_only: bool = False,
        sort_by: str = "ward",
        limit: int = 100,
        force_refresh: bool = False
    ) -> List[Dict]:
        """Get plots for a specific world with filters"""
        params = {
            "sort_by": sort_by,
            "limit": limit,
            "force_refresh": force_refresh,
            "lottery_only": lottery_only,
            "available_only": available_only
        }
        
        if size:
            params["size"] = size
        if min_price:
            params["min_price"] = min_price
        if max_price:
            params["max_price"] = max_price
            
        response = self.session.get(
            f"{self.base_url}/api/worlds/{world_id}/plots",
            params=params
        )
        response.raise_for_status()
        return response.json()
        
    def get_world_stats(self, world_id: int, force_refresh: bool = False) -> Dict:
        """Get statistics for a world"""
        params = {"force_refresh": force_refresh}
        response = self.session.get(
            f"{self.base_url}/api/worlds/{world_id}/stats",
            params=params
        )
        response.raise_for_status()
        return response.json()
        
    def search_plots(
        self,
        max_price: int,
        size: Optional[str] = None,
        worlds: Optional[List[int]] = None,
        lottery_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Search plots across multiple worlds"""
        params = {
            "max_price": max_price,
            "lottery_only": lottery_only,
            "limit": limit
        }
        
        if size:
            params["size"] = size
        if worlds:
            params["worlds"] = ",".join(map(str, worlds))
            
        response = self.session.get(
            f"{self.base_url}/api/search",
            params=params
        )
        response.raise_for_status()
        return response.json()
        
    def get_cache_info(self) -> List[Dict]:
        """Get cache status"""
        response = self.session.get(f"{self.base_url}/api/cache")
        response.raise_for_status()
        return response.json()


def main():
    """Example usage of the API client"""
    # Create client
    client = PaissaAPIClient()
    
    try:
        # 1. Get all worlds
        print("=== Getting all worlds ===")
        worlds = client.get_worlds()
        print(f"Found {len(worlds)} worlds")
        
        # Show first 5 worlds
        for world in worlds[:5]:
            print(f"  - {world['name']} (ID: {world['id']}, DC: {world['datacenter_name']})")
            
        # 2. Get plots for a specific world
        world_id = 35  # Adamantoise
        print(f"\n=== Getting plots for world {world_id} ===")
        plots = client.get_world_plots(
            world_id,
            size="small",
            max_price=3500000,
            available_only=True,
            limit=10
        )
        
        print(f"Found {len(plots)} small plots under 3.5M gil:")
        for plot in plots:
            print(f"  - {plot['district_name']} W{plot['ward_number']:02d} "
                  f"P{plot['plot_number']:02d}: {plot['price']:,} gil")
            
        # 3. Get world statistics
        print(f"\n=== Statistics for world {world_id} ===")
        stats = client.get_world_stats(world_id)
        print(f"Total plots: {stats['total_plots']}")
        print(f"By size: {stats['plots_by_size']}")
        print(f"By phase: {stats['plots_by_phase']}")
        print(f"Price range: {stats['price_stats']['min']:,} - {stats['price_stats']['max']:,} gil")
        
        # 4. Search across multiple worlds
        print("\n=== Searching for cheap small plots ===")
        cheap_plots = client.search_plots(
            max_price=3000000,
            size="small",
            worlds=[34, 35, 36],  # Multiple worlds
            limit=10
        )
        
        print(f"Found {len(cheap_plots)} cheap small plots:")
        for plot in cheap_plots:
            world_name = next(w['name'] for w in worlds if w['id'] == plot['world_id'])
            print(f"  - {world_name}: {plot['district_name']} "
                  f"W{plot['ward_number']:02d} P{plot['plot_number']:02d}: "
                  f"{plot['price']:,} gil")
                  
        # 5. Check cache status
        print("\n=== Cache Status ===")
        cache_info = client.get_cache_info()
        for info in cache_info:
            print(f"  World {info['world_id']}: "
                  f"{info['plot_count']} plots cached at {info['cached_at']}")
                  
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        print("Make sure the API server is running (python paissa_server.py)")


if __name__ == "__main__":
    main()