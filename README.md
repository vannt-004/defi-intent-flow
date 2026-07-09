# DeFi Intent Flow

AI-assisted DeFi Portfolio Analytics and Simulation.

Hệ thống tập trung vào quản lý danh mục DeFi theo hướng phân tích và mô phỏng:

- Theo dõi token hold, lending/borrow positions và Uniswap V3 LP positions.
- Tính net worth, cashflow, PnL flow và transaction history từ `cashflow`.
- Đánh giá rủi ro từng vị thế lending/LP.
- Mô phỏng các action như swap, lend, borrow, provide liquidity.
- Không đưa ra khuyến nghị đầu tư; chỉ cung cấp phân tích, cảnh báo và giả định mô phỏng.

## Quick Start

Backend CLI hiện dùng `run.py` làm entrypoint chính:

```bash
cd backend
python3 run.py portfolio_stream_worker
python3 run.py portfolio_sync_wallet <wallet> --mode SYNC
python3 run.py portfolio_sync_wallet <wallet> --mode CRAWL_NEW_USER
python3 run.py portfolio_sync_wallet <wallet> --full-history
python3 run.py gas_fee_worker
```

Để dựng dataset backtest cho một ví, dùng full-history crawl:

```bash
cd backend
python3 run.py portfolio_sync_wallet <wallet> --full-history --reset-first --backfill-days 180
```

Luồng này crawl protocol cashflow và supported on-chain transfers từ block `FULL_HISTORY_START_BLOCK` (mặc định `0`), rebuild snapshot/read model và dựng synthetic snapshots theo `FULL_HISTORY_SYNTHETIC_BACKFILL_DAYS`. `--reset-first` chỉ xóa dữ liệu derived của ví đó (`cashflow`, snapshots, risk, dashboard view), không xóa token/price/yield reference data.

Frontend:

```bash
cd frontend
npm run dev
```

## Docker

Chạy full stack cơ bản gồm MongoDB, Redis, API, frontend, portfolio stream worker và gas fee worker:

```bash
docker compose up --build
```

Mở giao diện tại:

```text
http://localhost:3000
```

API chạy tại:

```text
http://localhost:8000
```

Worker crawl market/price/yield được để trong profile riêng vì có thể gọi API ngoài nặng:

```bash
docker compose --profile workers up --build
```

Các biến như `RPC_URL`, `ETHERSCAN_API_KEY`, `THE_GRAPH_URL`, `UNISWAP_GRAPH`, `AAVE_GRAPH` vẫn đọc từ `backend/.env`. Compose chỉ override `CONNECTION_URL` và `REDIS_URL` để backend dùng service Mongo/Redis trong Docker network.

## Data Flow Hiện Tại

```text
wallet connect / Update Plus
-> Redis portfolio stream
-> PortfolioSyncService
-> wallet token balances
-> Aave/Compound positions
-> Uniswap V3 LP positions
-> protocol cashflows + supported on-chain token cashflows
-> asset_snapshot / position_snapshot / portfolio_snapshot
-> position_risk_snapshot
-> portfolio_dashboard_view
-> UI dashboard / risk / simulator
```

Lưu ý: hệ thống đã bỏ collection trung gian `onchain_transactions`. Transaction UI và PnL Flow đọc từ `cashflow`, nơi gom cả protocol events và on-chain events đã lọc theo token support.

## Công Thức Chính

```text
netWorthUsd = tokenHoldUsd + totalSupplyUsd + totalAmmUsd - totalBorrowUsd
```

Dạng phân rã:

```text
supplyPrincipalUsd = depositUsd - withdrawUsd
borrowPrincipalUsd = borrowUsd - repayUsd
supplyInterestUsd = totalSupplyUsd - supplyPrincipalUsd
borrowInterestUsd = totalBorrowUsd - borrowPrincipalUsd

netWorthUsd =
  tokenHoldUsd
  + supplyPrincipalUsd
  + supplyInterestUsd
  + totalAmmUsd
  - totalBorrowUsd
```

Một số số liệu là ước lượng và cần được UI/API gắn nhãn đúng:

- `synthetic_7d_backfill`: lịch sử 7 ngày giả lập từ current balance + cashflow + price/yield snapshot.
- `priceAtTx`: giá xấp xỉ theo snapshot gần thời điểm transaction.
- LP IL/range risk: heuristic, chưa phải định giá chính xác đầy đủ cho Uniswap V3.
- AHP/risk score/simulator fee: heuristic/fallback, không phải lời khuyên đầu tư.

## Tài Liệu Chi Tiết

Xem đầy đủ tại:

- [docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md)
