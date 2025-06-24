#!/usr/bin/env python3
"""
Interactive PaissaDB Monitor - 互動式房屋監控介面
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import List, Optional
import logging

from paissa_client import PaissaClient, PlotState, HouseSize, LottoPhase


class InteractiveMonitor:
    def __init__(self):
        self.client = None
        self.selected_world_id = None
        self.selected_world_name = None
        self.filter_size = None
        self.filter_lottery_only = False
        self.sort_by = 'ward'  # ward, price, entries
        self.last_update = None
        self.update_interval = 60  # seconds
        self.running = True
        
    def clear_screen(self):
        """清除螢幕"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self):
        """印出標題"""
        width = 120
        print("╔" + "═" * (width - 2) + "╗")
        print("║" + "PaissaDB 互動式監控系統".center(width - 2) + "║")
        print("╚" + "═" * (width - 2) + "╝")
        
    def print_world_selection(self, worlds_by_dc):
        """顯示世界選擇選單"""
        print("\n請選擇要監控的世界:\n")
        
        world_list = []
        col_width = 25
        cols_per_row = 4
        
        for dc_name, worlds in sorted(worlds_by_dc.items()):
            print(f"\n【{dc_name}】")
            print("─" * 100)
            
            sorted_worlds = sorted(worlds, key=lambda w: w.name)
            for i in range(0, len(sorted_worlds), cols_per_row):
                row_worlds = sorted_worlds[i:i+cols_per_row]
                row_text = ""
                for world in row_worlds:
                    world_list.append(world)
                    row_text += f"[{len(world_list):3d}] {world.name:<20s}"
                print(row_text)
                
        return world_list
        
    def print_filter_menu(self):
        """顯示過濾選單"""
        width = 120
        print("\n" + "─" * width)
        print(f"目前監控: {self.selected_world_name}".center(width))
        print("─" * width)
        print("\n過濾設定:")
        print(f"  [1] 房屋大小: {self.get_size_display()}")
        print(f"  [2] 只顯示抽籤房屋: {'是' if self.filter_lottery_only else '否'}")
        print(f"  [3] 排序方式: {self.get_sort_display()}")
        print(f"  [4] 更新間隔: {self.update_interval} 秒")
        print("\n  [S] 開始監控")
        print("  [Q] 返回世界選擇")
        
    def get_size_display(self):
        """取得房屋大小顯示文字"""
        if self.filter_size is None:
            return "全部"
        return ['小型', '中型', '大型'][self.filter_size]
        
    def get_sort_display(self):
        """取得排序方式顯示文字"""
        sort_map = {
            'ward': '地區/房號',
            'price': '價格',
            'entries': '抽籤人數'
        }
        return sort_map.get(self.sort_by, '地區/房號')
        
    def format_plot(self, plot: PlotState) -> str:
        """格式化房屋資訊"""
        # 房屋大小圖示
        size_icons = {
            HouseSize.SMALL: "🏠",
            HouseSize.MEDIUM: "🏡", 
            HouseSize.LARGE: "🏰"
        }
        size_names = {
            HouseSize.SMALL: "小",
            HouseSize.MEDIUM: "中",
            HouseSize.LARGE: "大"
        }
        
        # 地區簡稱
        district_short = {
            "Mist": "海霧村",
            "The Lavender Beds": "薰衣草苗圃",
            "The Goblet": "高腳孤丘",
            "Shirogane": "白銀鄉",
            "Empyreum": "天穹街"
        }
        
        district = self.client.district_name(plot.district_id)
        district_display = district_short.get(district, district)
        
        # 格式化各欄位
        col1 = f"{district_display:<15s}"
        col2 = f"W{plot.ward_number:02d}-P{plot.plot_number:02d}"
        col3 = f"{size_names.get(plot.size, '?')}"
        col4 = f"{plot.price:>10,}"
        
        # 基本資訊行
        line = f"│ {col1} │ {col2} │ {col3} │ {col4} gil │"
        
        # 抽籤資訊
        if plot.lotto_entries is not None:
            phase_display = {
                LottoPhase.ENTRY: "📝 報名中",
                LottoPhase.RESULTS: "🎲 開獎中",
                LottoPhase.UNAVAILABLE: "🚫 不可用"
            }
            phase = phase_display.get(plot.lotto_phase, "❓ 未知")
            
            lottery_info = f"{plot.lotto_entries:>3d} 人 {phase}"
            line += f" {lottery_info:<18s} │"
            
            # 剩餘時間
            if plot.lotto_phase_until:
                phase_end = datetime.fromtimestamp(plot.lotto_phase_until)
                time_left = phase_end - datetime.now()
                if time_left.total_seconds() > 0:
                    days = int(time_left.total_seconds() // 86400)
                    hours = int((time_left.total_seconds() % 86400) // 3600)
                    minutes = int((time_left.total_seconds() % 3600) // 60)
                    
                    if days > 0:
                        time_str = f"{days}d {hours:02d}h {minutes:02d}m"
                    else:
                        time_str = f"{hours:2d}h {minutes:02d}m"
                    line += f" {time_str:>12s} │"
                else:
                    line += f" {'已結束':>12s} │"
            else:
                line += f" {'-':>12s} │"
        else:
            line += f" {'立即可購':^18s} │ {'-':>12s} │"
            
        return line
        
    def filter_and_sort_plots(self, plots: List[PlotState]) -> List[PlotState]:
        """過濾和排序房屋"""
        filtered = plots
        
        # 過濾大小
        if self.filter_size is not None:
            filtered = [p for p in filtered if p.size == self.filter_size]
            
        # 過濾抽籤
        if self.filter_lottery_only:
            filtered = [p for p in filtered if p.lotto_phase == LottoPhase.ENTRY]
            
        # 排序
        if self.sort_by == 'price':
            filtered.sort(key=lambda p: p.price)
        elif self.sort_by == 'entries':
            filtered.sort(key=lambda p: p.lotto_entries or 999999)
        else:  # ward
            filtered.sort(key=lambda p: (p.district_id, p.ward_number, p.plot_number))
            
        return filtered
        
    async def display_plots(self):
        """顯示房屋列表"""
        self.clear_screen()
        self.print_header()
        
        print(f"\n監控世界: {self.selected_world_name}")
        if self.last_update:
            print(f"最後更新: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"下次更新: {self.update_interval} 秒後")
        
        # 取得並過濾房屋
        plots = self.client.get_world_plots(self.selected_world_id)
        filtered_plots = self.filter_and_sort_plots(plots)
        
        print(f"\n找到 {len(filtered_plots)} 個房屋（總計 {len(plots)} 個）")
        
        # 表格標題
        print("\n┌" + "─" * 17 + "┬" + "─" * 10 + "┬" + "─" * 5 + "┬" + "─" * 16 + "┬" + "─" * 22 + "┬" + "─" * 15 + "┐")
        print("│ 地區            │ 房號     │ 大小 │ 價格           │ 抽籤狀態            │ 剩餘時間      │")
        print("├" + "─" * 17 + "┼" + "─" * 10 + "┼" + "─" * 5 + "┼" + "─" * 16 + "┼" + "─" * 22 + "┼" + "─" * 15 + "┤")
        
        # 顯示房屋
        display_limit = 40  # 顯示更多房屋
        for i, plot in enumerate(filtered_plots[:display_limit]):
            print(self.format_plot(plot))
            
        # 表格底部
        print("└" + "─" * 17 + "┴" + "─" * 10 + "┴" + "─" * 5 + "┴" + "─" * 16 + "┴" + "─" * 22 + "┴" + "─" * 15 + "┘")
        
        if len(filtered_plots) > display_limit:
            print(f"\n... 還有 {len(filtered_plots) - display_limit} 個房屋未顯示")
            
        # 統計資訊
        if filtered_plots:
            prices = [p.price for p in filtered_plots]
            print(f"\n統計資訊:")
            print(f"  最低價格: {min(prices):,} gil")
            print(f"  最高價格: {max(prices):,} gil")
            print(f"  平均價格: {sum(prices) // len(prices):,} gil")
            
            lottery_plots = [p for p in filtered_plots if p.lotto_phase == LottoPhase.ENTRY]
            if lottery_plots:
                entries = [p.lotto_entries for p in lottery_plots if p.lotto_entries is not None]
                if entries:
                    print(f"  抽籤房屋: {len(lottery_plots)} 個")
                    print(f"  平均報名人數: {sum(entries) // len(entries)} 人")
            
        print("\n按 Ctrl+C 停止監控")
        
    async def monitor_loop(self):
        """監控迴圈"""
        while self.running:
            try:
                # 更新資料
                await self.client.load_world(self.selected_world_id, force_reload=True)
                self.last_update = datetime.now()
                
                # 顯示
                await self.display_plots()
                
                # 等待下次更新
                await asyncio.sleep(self.update_interval)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"\n錯誤: {e}")
                await asyncio.sleep(5)
                
    async def run(self):
        """主程式"""
        async with PaissaClient() as client:
            self.client = client
            
            while True:
                try:
                    # 選擇世界
                    self.clear_screen()
                    self.print_header()
                    
                    # 取得世界列表
                    worlds = await client.get_worlds()
                    
                    # 按資料中心分組
                    worlds_by_dc = {}
                    for world in worlds:
                        if world.datacenter_name not in worlds_by_dc:
                            worlds_by_dc[world.datacenter_name] = []
                        worlds_by_dc[world.datacenter_name].append(world)
                    
                    # 顯示選單
                    world_list = self.print_world_selection(worlds_by_dc)
                    
                    print("\n" + "─" * 100)
                    print("請輸入世界編號 (或 Q 離開): ", end='')
                    choice = input().strip().upper()
                    
                    if choice == 'Q':
                        break
                        
                    try:
                        world_idx = int(choice) - 1
                        if 0 <= world_idx < len(world_list):
                            selected_world = world_list[world_idx]
                            self.selected_world_id = selected_world.id
                            self.selected_world_name = selected_world.name
                            
                            # 載入世界資料
                            print(f"\n正在載入 {self.selected_world_name} 的資料...")
                            await client.load_world(self.selected_world_id)
                            
                            # 設定過濾條件
                            await self.configure_filters()
                            
                        else:
                            print("\n無效的選擇，請重試")
                            await asyncio.sleep(2)
                            
                    except ValueError:
                        print("\n請輸入有效的數字")
                        await asyncio.sleep(2)
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"\n錯誤: {e}")
                    await asyncio.sleep(3)
                    
    async def configure_filters(self):
        """設定過濾條件"""
        while True:
            self.clear_screen()
            self.print_filter_menu()
            
            choice = input("\n請選擇: ").strip().upper()
            
            if choice == '1':
                # 房屋大小
                print("\n選擇房屋大小:")
                print("  [1] 全部")
                print("  [2] 小型")
                print("  [3] 中型") 
                print("  [4] 大型")
                size_choice = input("請選擇: ").strip()
                
                if size_choice == '1':
                    self.filter_size = None
                elif size_choice == '2':
                    self.filter_size = HouseSize.SMALL
                elif size_choice == '3':
                    self.filter_size = HouseSize.MEDIUM
                elif size_choice == '4':
                    self.filter_size = HouseSize.LARGE
                    
            elif choice == '2':
                # 抽籤過濾
                self.filter_lottery_only = not self.filter_lottery_only
                
            elif choice == '3':
                # 排序方式
                print("\n選擇排序方式:")
                print("  [1] 地區/房號")
                print("  [2] 價格（由低到高）")
                print("  [3] 抽籤人數（由少到多）")
                sort_choice = input("請選擇: ").strip()
                
                if sort_choice == '1':
                    self.sort_by = 'ward'
                elif sort_choice == '2':
                    self.sort_by = 'price'
                elif sort_choice == '3':
                    self.sort_by = 'entries'
                    
            elif choice == '4':
                # 更新間隔
                try:
                    interval = int(input("\n輸入更新間隔（秒，10-600）: ").strip())
                    if 10 <= interval <= 600:
                        self.update_interval = interval
                    else:
                        print("請輸入 10 到 600 之間的數字")
                        await asyncio.sleep(2)
                except ValueError:
                    print("請輸入有效的數字")
                    await asyncio.sleep(2)
                    
            elif choice == 'S':
                # 開始監控
                self.running = True
                await self.monitor_loop()
                
            elif choice == 'Q':
                # 返回
                break


async def main():
    """主程式進入點"""
    # 設定日誌等級為 WARNING，減少輸出
    logging.basicConfig(level=logging.WARNING)
    
    monitor = InteractiveMonitor()
    await monitor.run()
    print("\n感謝使用 PaissaDB 監控系統！")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程式已終止")
        sys.exit(0)