#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 hydai
# Licensed under the MIT License - see LICENSE file for details
#
"""
PaissaDB CLI - Command line interface for fetching FFXIV housing data
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, List

from paissa_client import HouseSize, LottoPhase, PaissaClient, PlotState


def format_plot(plot: PlotState, client: PaissaClient) -> str:
    """Format a plot for display"""
    size_names = ["Small", "Medium", "Large"]
    size = size_names[plot.size]
    district = client.district_name(plot.district_id)

    info = f"Ward {plot.ward_number} Plot {plot.plot_number} - {district} ({size}, {plot.price:,} gil)"

    if plot.lotto_entries is not None:
        info += f" - {plot.lotto_entries} entries"

    return info


def filter_plots(plots: List[PlotState], args) -> List[PlotState]:
    """Apply filters to plot list based on CLI arguments"""
    filtered = plots

    # Filter by size
    if args.size:
        size_map = {"small": HouseSize.SMALL, "medium": HouseSize.MEDIUM, "large": HouseSize.LARGE}
        size_value = size_map[args.size.lower()]
        filtered = [p for p in filtered if p.size == size_value]

    # Filter by max price
    if args.max_price:
        filtered = [p for p in filtered if p.price <= args.max_price]

    # Filter by district
    if args.district:
        # Note: PlotState doesn't have district_name, need to use client to get it
        # This is handled at display time, not filtering
        pass

    # Filter by lottery status
    if args.lottery_only:
        filtered = [p for p in filtered if p.lotto_phase == LottoPhase.ENTRY]

    # Filter by max lottery entries
    if args.max_entries is not None:
        filtered = [p for p in filtered if p.lotto_entries is not None and p.lotto_entries <= args.max_entries]

    return filtered


async def list_worlds(client: PaissaClient):
    """List all available worlds"""
    worlds = await client.get_worlds()

    # Group by datacenter
    datacenters: Dict[str, List] = {}
    for world in worlds:
        if world.datacenter_name not in datacenters:
            datacenters[world.datacenter_name] = []
        datacenters[world.datacenter_name].append(world)

    print("\nAvailable Worlds:")
    print("-" * 50)
    for dc_name, dc_worlds in sorted(datacenters.items()):
        print(f"\n{dc_name}:")
        for world in sorted(dc_worlds, key=lambda w: w.name):
            print(f"  {world.id:3d} - {world.name}")


async def show_plots(client: PaissaClient, args):
    """Show plots for a specific world"""
    world_id = args.world_id

    print(f"\nLoading data for world {world_id}...")
    await client.load_world(world_id)

    world_name = client.world_name(world_id)
    plots = client.get_world_plots(world_id)

    # Apply filters
    filtered_plots = filter_plots(plots, args)

    print(f"\n{world_name} - {len(filtered_plots)} plots found")
    print("-" * 80)

    # Sort plots
    if args.sort == "price":
        filtered_plots.sort(key=lambda p: p.price)
    elif args.sort == "entries":
        filtered_plots.sort(key=lambda p: p.lotto_entries or 999999)
    elif args.sort == "ward":
        filtered_plots.sort(key=lambda p: (p.district_id, p.ward_number, p.plot_number))

    # Display plots
    for i, plot in enumerate(filtered_plots):
        if args.limit and i >= args.limit:
            break
        print(format_plot(plot, client))


async def export_data(client: PaissaClient, args):
    """Export plot data to JSON file"""
    world_id = args.world_id

    print(f"\nLoading data for world {world_id}...")
    await client.load_world(world_id)

    world_name = client.world_name(world_id)
    plots = client.get_world_plots(world_id)

    # Apply filters
    filtered_plots = filter_plots(plots, args)

    # Prepare export data
    export_data = {
        "world": world_name,
        "world_id": world_id,
        "timestamp": datetime.now().isoformat(),
        "total_plots": len(filtered_plots),
        "filters_applied": {
            "size": args.size,
            "max_price": args.max_price,
            "district": args.district,
            "lottery_only": args.lottery_only,
            "max_entries": args.max_entries,
        },
        "plots": [
            {
                "district": client.district_name(plot.district_id),
                "ward": plot.ward_number,
                "plot": plot.plot_number,
                "size": ["Small", "Medium", "Large"][plot.size],
                "price": plot.price,
                "lottery_entries": plot.lotto_entries,
                "lottery_phase": plot.lotto_phase,
                "last_updated": datetime.fromtimestamp(plot.last_updated_time).isoformat(),
                "first_seen": datetime.fromtimestamp(plot.first_seen_time).isoformat(),
            }
            for plot in filtered_plots
        ],
    }

    # Write to file
    filename = args.output or f"paissa_{world_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(export_data, f, indent=2)

    print(f"\nExported {len(filtered_plots)} plots to {filename}")


async def monitor_world(client: PaissaClient, args):
    """Monitor a world for changes"""
    world_id = args.world_id
    interval = args.interval or 30

    print(f"\nLoading data for world {world_id}...")
    await client.load_world(world_id)

    world_name = client.world_name(world_id)
    initial_plots = client.get_world_plots(world_id)
    initial_count = len(initial_plots)

    print(f"\nMonitoring {world_name}")
    print(f"Initial plot count: {initial_count}")
    print(f"Checking every {interval} seconds... (Press Ctrl+C to stop)\n")

    plot_states = {f"{p.district_id}-{p.ward_number}-{p.plot_number}": p for p in initial_plots}

    try:
        while True:
            await asyncio.sleep(interval)

            current_plots = client.get_world_plots(world_id)
            current_states = {f"{p.district_id}-{p.ward_number}-{p.plot_number}": p for p in current_plots}

            # Check for new plots
            for key, plot in current_states.items():
                if key not in plot_states:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] NEW: {format_plot(plot, client)}")

            # Check for sold plots
            for key, plot in plot_states.items():
                if key not in current_states:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SOLD: {format_plot(plot, client)}")

            # Check for updated plots (lottery entries changed)
            for key, plot in current_states.items():
                if key in plot_states:
                    old_plot = plot_states[key]
                    if old_plot.lotto_entries != plot.lotto_entries:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] UPDATED: {format_plot(plot, client)}")

            plot_states = current_states

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


async def main():
    parser = argparse.ArgumentParser(description="PaissaDB CLI - FFXIV Housing Data")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List worlds command
    subparsers.add_parser("worlds", help="List all available worlds")

    # Show plots command
    parser_show = subparsers.add_parser("show", help="Show plots for a world")
    parser_show.add_argument("world_id", type=int, help="World ID to query")
    parser_show.add_argument("--size", choices=["small", "medium", "large"], help="Filter by house size")
    parser_show.add_argument("--max-price", type=int, help="Maximum price filter")
    parser_show.add_argument("--district", help="Filter by district name (partial match)")
    parser_show.add_argument("--lottery-only", action="store_true", help="Show only lottery plots")
    parser_show.add_argument("--max-entries", type=int, help="Maximum lottery entries")
    parser_show.add_argument("--sort", choices=["price", "entries", "ward"], default="ward", help="Sort order")
    parser_show.add_argument("--limit", type=int, help="Limit number of results")

    # Export command
    parser_export = subparsers.add_parser("export", help="Export plot data to JSON")
    parser_export.add_argument("world_id", type=int, help="World ID to export")
    parser_export.add_argument("-o", "--output", help="Output filename")
    parser_export.add_argument("--size", choices=["small", "medium", "large"], help="Filter by house size")
    parser_export.add_argument("--max-price", type=int, help="Maximum price filter")
    parser_export.add_argument("--district", help="Filter by district name (partial match)")
    parser_export.add_argument("--lottery-only", action="store_true", help="Export only lottery plots")
    parser_export.add_argument("--max-entries", type=int, help="Maximum lottery entries")

    # Monitor command
    parser_monitor = subparsers.add_parser("monitor", help="Monitor a world for changes")
    parser_monitor.add_argument("world_id", type=int, help="World ID to monitor")
    parser_monitor.add_argument("--interval", type=int, help="Check interval in seconds (default: 30)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    async with PaissaClient() as client:
        if args.command == "worlds":
            await list_worlds(client)
        elif args.command == "show":
            await show_plots(client, args)
        elif args.command == "export":
            await export_data(client, args)
        elif args.command == "monitor":
            await monitor_world(client, args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
