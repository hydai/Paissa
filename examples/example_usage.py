#!/usr/bin/env python3
"""
Example usage of PaissaClient with various filtering and monitoring scenarios
"""

import asyncio
import logging
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paissa_client import PaissaClient, HouseSize, LottoPhase


async def example_basic_usage():
    """Basic example: Get all plots for a world"""
    async with PaissaClient() as client:
        # Load Adamantoise (ID: 35)
        world_id = 35
        await client.load_world(world_id)
        
        plots = client.get_world_plots(world_id)
        print(f"\nTotal plots on {client.world_name(world_id)}: {len(plots)}")
        
        # Show first 5 plots
        for plot in plots[:5]:
            size_name = ['Small', 'Medium', 'Large'][plot.size]
            print(f"Ward {plot.ward_number} Plot {plot.plot_number} - "
                  f"{client.district_name(plot.district_id)} "
                  f"({size_name}, {plot.price:,} gil)")


async def example_filter_by_size():
    """Example: Filter plots by size"""
    async with PaissaClient() as client:
        world_id = 35  # Adamantoise
        await client.load_world(world_id)
        
        plots = client.get_world_plots(world_id)
        
        # Filter by house size
        small_plots = [p for p in plots if p.size == HouseSize.SMALL]
        medium_plots = [p for p in plots if p.size == HouseSize.MEDIUM]
        large_plots = [p for p in plots if p.size == HouseSize.LARGE]
        
        print(f"\nPlots by size on {client.world_name(world_id)}:")
        print(f"Small: {len(small_plots)}")
        print(f"Medium: {len(medium_plots)}")
        print(f"Large: {len(large_plots)}")


async def example_lottery_monitoring():
    """Example: Monitor lottery entries"""
    async with PaissaClient() as client:
        world_id = 35  # Adamantoise
        await client.load_world(world_id)
        
        plots = client.get_world_plots(world_id)
        
        # Find plots in lottery entry phase
        lottery_plots = [
            p for p in plots 
            if p.lotto_phase == LottoPhase.ENTRY
        ]
        
        print(f"\nLottery plots on {client.world_name(world_id)}:")
        
        # Sort by number of entries (ascending)
        lottery_plots.sort(key=lambda p: p.lotto_entries or 0)
        
        for plot in lottery_plots[:10]:  # Show top 10
            phase_end = datetime.fromtimestamp(plot.lotto_phase_until) if plot.lotto_phase_until else None
            print(f"Ward {plot.ward_number} Plot {plot.plot_number} - "
                  f"{client.district_name(plot.district_id)}: "
                  f"{plot.lotto_entries} entries")
            if phase_end:
                print(f"  Phase ends: {phase_end}")


async def example_real_time_monitoring():
    """Example: Monitor real-time updates for a specific world"""
    logging.basicConfig(level=logging.INFO)
    
    async with PaissaClient() as client:
        world_id = 35  # Adamantoise
        await client.load_world(world_id)
        
        initial_count = len(client.get_world_plots(world_id))
        print(f"\nMonitoring {client.world_name(world_id)}")
        print(f"Initial plot count: {initial_count}")
        print("Waiting for updates... (Press Ctrl+C to stop)\n")
        
        # Monitor for 5 minutes
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < 300:  # 5 minutes
            await asyncio.sleep(10)  # Check every 10 seconds
            
            current_count = len(client.get_world_plots(world_id))
            if current_count != initial_count:
                print(f"Plot count changed: {initial_count} -> {current_count}")
                initial_count = current_count


async def example_find_cheap_plots():
    """Example: Find cheapest plots across all worlds"""
    async with PaissaClient() as client:
        # Get all worlds
        worlds = await client.get_worlds()
        
        # Load data for multiple worlds (be considerate of API rate limits)
        cheap_plots = []
        
        # Example: Check first 5 worlds
        for world in worlds[:5]:
            print(f"Loading {world.name}...")
            await client.load_world(world.id)
            await asyncio.sleep(0.5)  # Small delay to be polite to the API
            
            plots = client.get_world_plots(world.id)
            for plot in plots:
                if plot.size == HouseSize.SMALL and plot.price < 3_000_000:
                    cheap_plots.append((world, plot))
                    
        print(f"\nFound {len(cheap_plots)} cheap small plots under 3M gil:")
        cheap_plots.sort(key=lambda x: x[1].price)
        
        for world, plot in cheap_plots[:10]:  # Show cheapest 10
            print(f"{world.name} - Ward {plot.ward_number} Plot {plot.plot_number}: "
                  f"{plot.price:,} gil")


async def example_export_data():
    """Example: Export plot data to JSON"""
    import json
    
    async with PaissaClient() as client:
        world_id = 35  # Adamantoise
        await client.load_world(world_id)
        
        plots = client.get_world_plots(world_id)
        
        # Convert to exportable format
        export_data = {
            'world': client.world_name(world_id),
            'world_id': world_id,
            'timestamp': datetime.now().isoformat(),
            'total_plots': len(plots),
            'plots': [
                {
                    'district': client.district_name(plot.district_id),
                    'ward': plot.ward_number,
                    'plot': plot.plot_number,
                    'size': ['Small', 'Medium', 'Large'][plot.size],
                    'price': plot.price,
                    'lottery_entries': plot.lotto_entries,
                    'last_updated': datetime.fromtimestamp(plot.last_updated_time).isoformat()
                }
                for plot in plots
            ]
        }
        
        filename = f"paissa_export_{world_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        print(f"\nExported {len(plots)} plots to {filename}")


async def main():
    """Run various examples"""
    print("PaissaDB Client Examples")
    print("=" * 50)
    
    # Uncomment the example you want to run:
    
    await example_basic_usage()
    # await example_filter_by_size()
    # await example_lottery_monitoring()
    # await example_find_cheap_plots()
    # await example_export_data()
    # await example_real_time_monitoring()


if __name__ == "__main__":
    asyncio.run(main())