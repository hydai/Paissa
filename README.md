# PaissaDB Client

完整的 Python 客戶端套件，用於存取 PaissaDB (Final Fantasy XIV 房屋資料庫) 的資料。提供多種使用方式，從程式化 API 到網頁服務。

## 功能特點

- 🔌 **完整的 API 支援** - REST API 和 WebSocket 即時更新
- 🔄 **即時監控** - 房屋狀態變更的即時通知
- 🔍 **強大的過濾** - 支援大小、價格、地區、抽籤狀態等多種條件
- 💾 **智慧快取** - HTTP 伺服器內建快取機制，減少 API 負載
- 🖥️ **多種介面** - CLI 工具、互動式監控、HTTP API 伺服器
- 📊 **資料分析** - 統計資訊和資料匯出功能

## 專案結構

```
paissa-client/
├── paissa_client.py       # 核心客戶端程式庫
├── paissa_cli.py          # 命令列介面
├── interactive_monitor.py # 互動式監控介面
├── paissa_server.py       # HTTP API 伺服器
├── examples/              # 使用範例
│   ├── example_usage.py
│   └── api_client_example.py
├── requirements.txt       # Python 依賴
└── README.md             # 本檔案
```

## 安裝

```bash
# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安裝依賴
pip install -r requirements.txt
```

## 使用方式

### 1. Python API 使用

```python
import asyncio
from paissa_client import PaissaClient

async def main():
    async with PaissaClient() as client:
        # 取得所有世界
        worlds = await client.get_worlds()
        
        # 載入特定世界的資料 (例如: Adamantoise, ID=35)
        await client.load_world(35)
        
        # 取得該世界的所有房屋
        plots = client.get_world_plots(35)
        print(f"找到 {len(plots)} 個房屋")

asyncio.run(main())
```

### 2. CLI 使用

#### 列出所有世界
```bash
python paissa_cli.py worlds
```

#### 顯示特定世界的房屋
```bash
# 顯示世界 ID 35 的所有房屋
python paissa_cli.py show 35

# 只顯示小型房屋
python paissa_cli.py show 35 --size small

# 只顯示價格低於 300 萬的房屋
python paissa_cli.py show 35 --max-price 3000000

# 只顯示抽籤中的房屋
python paissa_cli.py show 35 --lottery-only

# 組合過濾條件
python paissa_cli.py show 35 --size small --lottery-only --max-entries 5
```

#### 匯出資料
```bash
# 匯出世界 35 的資料到 JSON
python paissa_cli.py export 35 -o adamantoise_data.json

# 匯出時套用過濾條件
python paissa_cli.py export 35 --size small --lottery-only
```

#### 即時監控
```bash
# 監控世界 35 的變化（每 30 秒檢查一次）
python paissa_cli.py monitor 35

# 自訂檢查間隔（每 60 秒）
python paissa_cli.py monitor 35 --interval 60
```

### 3. 互動式監控介面

提供更友善的使用者介面，支援即時更新和統計資訊：

```bash
python interactive_monitor.py
```

功能特色：
- 圖形化表格顯示
- 即時更新（可自訂間隔）
- 過濾和排序功能
- 統計資訊顯示
- 中文化介面

### 4. HTTP API 伺服器

提供 RESTful API 服務，包含快取機制：

```bash
python paissa_server.py
```

伺服器功能：
- **智慧快取** - 自動快取查詢過的世界資料（預設 5 分鐘）
- **RESTful API** - 完整的 HTTP API 端點
- **過濾功能** - 支援多種查詢條件
- **跨世界搜尋** - 可同時搜尋多個世界
- **自動文件** - 訪問 http://localhost:8000/docs 查看 API 文件

#### API 端點：

- `GET /api/worlds` - 取得所有世界列表
- `GET /api/worlds/{world_id}/plots` - 取得特定世界的房屋
- `GET /api/worlds/{world_id}/stats` - 取得世界統計資料
- `GET /api/search` - 跨世界搜尋房屋
- `GET /api/cache` - 查看快取狀態
- `DELETE /api/cache/{world_id}` - 清除特定世界快取

#### 使用範例：

```python
# 查詢世界 35 的小型房屋（價格低於 350 萬）
GET http://localhost:8000/api/worlds/35/plots?size=small&max_price=3500000

# 跨世界搜尋便宜房屋
GET http://localhost:8000/api/search?max_price=3000000&size=small&worlds=34,35,36

# 強制重新載入資料（繞過快取）
GET http://localhost:8000/api/worlds/35/plots?force_refresh=true
```

## 範例程式

1. **`examples/example_usage.py`** - Python 客戶端使用範例：
   - 基本使用
   - 依房屋大小過濾
   - 監控抽籤狀態
   - 尋找便宜房屋
   - 即時更新監控
   - 資料匯出

2. **`examples/api_client_example.py`** - HTTP API 使用範例：
   - 使用 requests 呼叫 API
   - 查詢和過濾房屋
   - 跨世界搜尋
   - 統計資料查詢

## API 結構

### 主要類別

- `PaissaClient`: 主要客戶端類別
- `PlotState`: 房屋狀態資料
- `WorldSummary`: 世界摘要資訊
- `WorldDetail`: 世界詳細資訊

### 列舉值

- `HouseSize`: SMALL (0), MEDIUM (1), LARGE (2)
- `LottoPhase`: ENTRY (1), RESULTS (2), UNAVAILABLE (3)
- `PurchaseSystem`: LOTTERY (1), FREE_COMPANY (2), INDIVIDUAL (4)

## 架構說明

### 資料流程

```
PaissaDB API (paissadb.zhu.codes)
    ↓
PaissaClient (核心客戶端)
    ├─→ CLI 工具 (paissa_cli.py)
    ├─→ 互動監控 (interactive_monitor.py)
    └─→ HTTP 伺服器 (paissa_server.py) → 快取層 → REST API
```

### 快取策略

HTTP 伺服器使用智慧快取來優化效能：
- 每個世界的資料快取 5 分鐘（可調整）
- 首次查詢時從 PaissaDB 載入資料
- 後續查詢使用快取資料（除非指定 `force_refresh`）
- WebSocket 連線在背景持續更新資料

## 使用建議

1. **開發測試** - 使用 `paissa_client.py` 直接連接
2. **個人使用** - 使用互動式監控介面
3. **自動化腳本** - 使用 CLI 工具
4. **網頁應用** - 使用 HTTP API 伺服器

## 注意事項

- 請適度使用，避免對 PaissaDB 造成過度負載
- HTTP 伺服器的快取機制可有效減少 API 請求
- WebSocket 連線具有自動重連機制（最多 5 次）
- 建議在正式環境中使用 HTTP 伺服器以獲得最佳效能

## 資料來源

資料來自 [PaissaDB](https://paissadb.zhu.codes) - 感謝 PaissaHouse 專案提供的服務

## 授權

本專案僅為客戶端實作，使用時請遵守 PaissaDB 的使用條款。