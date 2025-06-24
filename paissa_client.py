#!/usr/bin/env python3
"""
PaissaDB Client - A Python client for fetching FFXIV housing data from PaissaDB API
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import IntEnum

import aiohttp
import websockets


# Constants
PAISSADB_BASE = "https://paissadb.zhu.codes"
PAISSADB_WS_URL = "wss://paissadb.zhu.codes/ws"


# Enums
class PurchaseSystem(IntEnum):
    LOTTERY = 1
    FREE_COMPANY = 2
    INDIVIDUAL = 4


class LottoPhase(IntEnum):
    ENTRY = 1
    RESULTS = 2
    UNAVAILABLE = 3


class HouseSize(IntEnum):
    SMALL = 0
    MEDIUM = 1
    LARGE = 2


# Data Classes
@dataclass
class WorldSummary:
    id: int
    name: str
    datacenter_id: int
    datacenter_name: str


@dataclass
class OpenPlotDetail:
    world_id: int
    district_id: int
    ward_number: int
    plot_number: int
    size: int
    price: int
    last_updated_time: int
    first_seen_time: int
    est_time_open_min: int
    est_time_open_max: int
    purchase_system: int
    lotto_entries: Optional[int] = None
    lotto_phase: Optional[int] = None
    lotto_phase_until: Optional[int] = None


@dataclass
class PlotUpdate:
    world_id: int
    district_id: int
    ward_number: int
    plot_number: int
    size: int
    price: int
    last_updated_time: int
    first_seen_time: int
    purchase_system: int
    lotto_entries: int
    lotto_phase: int
    previous_lotto_phase: Optional[int]
    lotto_phase_until: int


@dataclass
class SoldPlotDetail:
    world_id: int
    district_id: int
    ward_number: int
    plot_number: int
    size: int
    last_updated_time: int
    est_time_sold_min: int
    est_time_sold_max: int


@dataclass
class DistrictDetail:
    id: int
    name: str
    num_open_plots: int
    oldest_plot_time: int
    open_plots: List[OpenPlotDetail] = field(default_factory=list)


@dataclass
class WorldDetail:
    id: int
    name: str
    districts: List[DistrictDetail]
    num_open_plots: int
    oldest_plot_time: int


@dataclass
class PlotState:
    world_id: int
    district_id: int
    ward_number: int
    plot_number: int
    size: int
    price: int
    last_updated_time: int
    first_seen_time: int
    purchase_system: int
    lotto_entries: Optional[int] = None
    lotto_phase: Optional[int] = None
    lotto_phase_until: Optional[int] = None

    @classmethod
    def from_open_plot(cls, plot: OpenPlotDetail) -> 'PlotState':
        return cls(
            world_id=plot.world_id,
            district_id=plot.district_id,
            ward_number=plot.ward_number,
            plot_number=plot.plot_number,
            size=plot.size,
            price=plot.price,
            last_updated_time=plot.last_updated_time,
            first_seen_time=plot.first_seen_time,
            purchase_system=plot.purchase_system,
            lotto_entries=plot.lotto_entries,
            lotto_phase=plot.lotto_phase,
            lotto_phase_until=plot.lotto_phase_until
        )

    @classmethod
    def from_plot_update(cls, update: PlotUpdate) -> 'PlotState':
        return cls(
            world_id=update.world_id,
            district_id=update.district_id,
            ward_number=update.ward_number,
            plot_number=update.plot_number,
            size=update.size,
            price=update.price,
            last_updated_time=update.last_updated_time,
            first_seen_time=update.first_seen_time,
            purchase_system=update.purchase_system,
            lotto_entries=update.lotto_entries,
            lotto_phase=update.lotto_phase,
            lotto_phase_until=update.lotto_phase_until
        )


class PaissaClient:
    """Client for interacting with PaissaDB API and WebSocket"""
    
    def __init__(self):
        self.plot_states: Dict[str, PlotState] = {}
        self.worlds: List[WorldSummary] = []
        self.world_map: Dict[int, WorldSummary] = {}
        self.district_names: Dict[int, str] = {}
        self.worlds_loaded: Set[int] = set()
        self._ws = None
        self._ws_task = None
        self._session = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        await self.init()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def init(self):
        """Initialize the client and establish connections"""
        self._session = aiohttp.ClientSession()
        await self.get_worlds()
        # Start WebSocket connection in background
        self._ws_task = asyncio.create_task(self._ws_handler())
        
    async def close(self):
        """Close all connections"""
        if self._ws:
            await self._ws.close()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
            
    async def get_worlds(self) -> List[WorldSummary]:
        """Fetch all available worlds"""
        async with self._session.get(f"{PAISSADB_BASE}/worlds") as resp:
            data = await resp.json()
            self.worlds = [WorldSummary(**world) for world in data]
            self.world_map = {world.id: world for world in self.worlds}
            self.logger.info(f"Loaded {len(self.worlds)} worlds")
            return self.worlds
            
    async def load_world(self, world_id: int, force_reload: bool = False) -> WorldDetail:
        """Load detailed data for a specific world"""
        if world_id in self.worlds_loaded and not force_reload:
            self.logger.debug(f"World {world_id} already loaded, skipping")
            return
            
        self.worlds_loaded.add(world_id)
        
        async with self._session.get(f"{PAISSADB_BASE}/worlds/{world_id}") as resp:
            data = await resp.json()
            
        # Parse districts
        districts = []
        for district_data in data['districts']:
            open_plots = [OpenPlotDetail(**plot) for plot in district_data['open_plots']]
            district = DistrictDetail(
                id=district_data['id'],
                name=district_data['name'],
                num_open_plots=district_data['num_open_plots'],
                oldest_plot_time=district_data['oldest_plot_time'],
                open_plots=open_plots
            )
            districts.append(district)
            self.district_names[district.id] = district.name
            
            # Update plot states
            for plot in open_plots:
                plot_key = self._get_plot_key(plot)
                self.plot_states[plot_key] = PlotState.from_open_plot(plot)
        
        world = WorldDetail(
            id=data['id'],
            name=data['name'],
            districts=districts,
            num_open_plots=data['num_open_plots'],
            oldest_plot_time=data['oldest_plot_time']
        )
        
        self.logger.info(f"Loaded world {world.name} with {world.num_open_plots} open plots")
        return world
        
    async def _ws_handler(self):
        """Handle WebSocket connection and messages"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(PAISSADB_WS_URL) as websocket:
                    self._ws = websocket
                    self.logger.info("WebSocket connected")
                    retry_count = 0  # Reset retry count on successful connection
                    
                    async for message in websocket:
                        await self._handle_ws_message(message)
                        
            except websockets.exceptions.WebSocketException as e:
                self.logger.error(f"WebSocket error: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_count * 2  # Exponential backoff
                    self.logger.info(f"Reconnecting in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error("Max reconnection attempts reached")
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in WebSocket handler: {e}")
                break
                
    async def _handle_ws_message(self, message: str):
        """Process incoming WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data')
            
            if msg_type == 'plot_open':
                plot = OpenPlotDetail(**msg_data)
                plot_key = self._get_plot_key(plot)
                self.plot_states[plot_key] = PlotState.from_open_plot(plot)
                self.logger.debug(f"Plot opened: {plot_key}")
                
            elif msg_type == 'plot_update':
                update = PlotUpdate(**msg_data)
                plot_key = self._get_plot_key(update)
                self.plot_states[plot_key] = PlotState.from_plot_update(update)
                self.logger.debug(f"Plot updated: {plot_key}")
                
            elif msg_type == 'plot_sold':
                sold = SoldPlotDetail(**msg_data)
                plot_key = self._get_plot_key(sold)
                if plot_key in self.plot_states:
                    del self.plot_states[plot_key]
                    self.logger.debug(f"Plot sold: {plot_key}")
                    
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            
    def _get_plot_key(self, plot) -> str:
        """Generate unique key for a plot"""
        return f"{plot.world_id}-{plot.district_id}-{plot.ward_number}-{plot.plot_number}"
        
    def get_world_plots(self, world_id: int) -> List[PlotState]:
        """Get all plots for a specific world"""
        return [plot for plot in self.plot_states.values() if plot.world_id == world_id]
        
    def get_district_plots(self, world_id: int, district_id: int) -> List[PlotState]:
        """Get all plots for a specific district"""
        return [
            plot for plot in self.plot_states.values() 
            if plot.world_id == world_id and plot.district_id == district_id
        ]
        
    def world_name(self, world_id: int) -> str:
        """Get world name by ID"""
        world = self.world_map.get(world_id)
        return world.name if world else str(world_id)
        
    def district_name(self, district_id: int) -> str:
        """Get district name by ID"""
        return self.district_names.get(district_id, str(district_id))


async def main():
    """Example usage of PaissaClient"""
    logging.basicConfig(level=logging.INFO)
    
    async with PaissaClient() as client:
        # Get all worlds
        worlds = await client.get_worlds()
        print(f"\nAvailable worlds: {len(worlds)}")
        
        # Group by datacenter
        datacenters = {}
        for world in worlds:
            if world.datacenter_name not in datacenters:
                datacenters[world.datacenter_name] = []
            datacenters[world.datacenter_name].append(world)
            
        # Display worlds by datacenter
        for dc_name, dc_worlds in sorted(datacenters.items()):
            print(f"\n{dc_name}:")
            for world in sorted(dc_worlds, key=lambda w: w.name):
                print(f"  - {world.name} (ID: {world.id})")
                
        # Example: Load specific world data
        # Change this to the world ID you want to check
        world_id = 34  # Example: Brynhildr
        
        print(f"\nLoading data for world {client.world_name(world_id)}...")
        world_detail = await client.load_world(world_id)
        
        if world_detail:
            print(f"\nWorld: {world_detail.name}")
            print(f"Total open plots: {world_detail.num_open_plots}")
            
            # Show plots by district
            for district in world_detail.districts:
                if district.num_open_plots > 0:
                    print(f"\n{district.name}: {district.num_open_plots} plots")
                    for plot in district.open_plots[:5]:  # Show first 5 plots
                        size_name = ['Small', 'Medium', 'Large'][plot.size]
                        print(f"  - Ward {plot.ward_number} Plot {plot.plot_number} "
                              f"({size_name}, {plot.price:,} gil)")
                        if plot.lotto_entries is not None:
                            print(f"    Lottery entries: {plot.lotto_entries}")
                            
            # Keep running to receive real-time updates
            print("\nListening for real-time updates... (Press Ctrl+C to stop)")
            await asyncio.sleep(3600)  # Run for 1 hour
            
        
if __name__ == "__main__":
    asyncio.run(main())