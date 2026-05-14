---

# Ethereum Mempool Slippage Exposure Analyzer

A real-time Ethereum mempool analytics tool that monitors pending Uniswap V2 swaps, simulates AMM reserve changes, estimates slippage-based MEV exposure before transactions are included in a block, and exposes production-style Prometheus metrics for observability.

---

## Overview

This project implements a real-time analytics pipeline for observing pending Ethereum transactions through a WebSocket RPC connection.

The system listens to the Ethereum mempool, filters transactions sent to the Uniswap V2 Router, decodes swap calldata using ABI definitions, reconstructs swap paths, fetches Uniswap V2 pool reserves, and simulates how each pending swap would affect AMM liquidity reserves.

The analyzer also exposes a Prometheus-compatible `/metrics` endpoint that reports mempool throughput, router match rate, ABI decode quality, swap type coverage, pool reserve read latency, slippage buffer distribution, MEV exposure classification, and WebSocket reconnect count.

The goal of this project is not to execute trades, send transactions, or build MEV bundles.

Instead, it is an analytical case study focused on understanding how pending swaps expose users to slippage and potential MEV impact before block inclusion.

---

## What This Project Demonstrates

This project demonstrates practical work with:

* Ethereum pending transaction monitoring
* WebSocket RPC subscriptions
* HTTP RPC transaction and pool-state reads
* Uniswap V2 Router calldata decoding
* ABI-based smart contract interaction
* AMM reserve simulation
* Multi-hop swap path reconstruction
* Slippage tolerance analysis
* MEV exposure estimation
* Prometheus metrics instrumentation
* Real-time blockchain data processing in Python
* Production-style observability for a live data pipeline

---

## Important Scope Clarification

This is an analytics tool only.

It does not:

* Send transactions
* Execute swaps
* Build MEV bundles
* Simulate private relay behavior
* Perform frontrunning or sandwich attacks
* Interact with Flashbots or block builders
* Attempt to profit from detected opportunities

The project is designed as a research and engineering case study for analyzing pending swaps and understanding how slippage parameters can create MEV exposure.

---

## Features

* Real-time monitoring of Ethereum pending transactions
* Filtering for Uniswap V2 Router transactions
* Decoding of swap calldata using router ABI
* Support for exact-input and exact-output swaps
* Support for fee-on-transfer swap function variants
* Reconstruction of token swap paths
* Fetching pair addresses through the Uniswap V2 Factory
* Reading live pool reserves from Uniswap V2 pairs
* Simulation of reserve changes after pending swaps
* Calculation of expected output or required input
* Slippage buffer analysis
* Basic MEV exposure classification
* Automatic WebSocket reconnect logic
* Caching of pair, pool, and token metadata
* Prometheus `/metrics` endpoint
* Counters for mempool flow, router matches, decode success, decode errors, swap types, MEV exposure, and RPC reconnects
* Histograms for pool reserve fetch latency and slippage buffer distribution

---

## Supported Uniswap V2 Swap Types

The analyzer supports the main Uniswap V2 Router swap functions, including:

* `swapExactTokensForTokens`
* `swapTokensForExactTokens`
* `swapExactETHForTokens`
* `swapTokensForExactETH`
* `swapExactTokensForETH`
* `swapETHForExactTokens`
* `swapExactTokensForTokensSupportingFeeOnTransferTokens`
* `swapExactETHForTokensSupportingFeeOnTransferTokens`
* `swapExactTokensForETHSupportingFeeOnTransferTokens`

---

## Architecture

```text
Ethereum Mempool
        ↓
WebSocket RPC subscription
        ↓
Pending transaction hash stream
        ↓
Fetch full transaction via HTTP RPC
        ↓
Filter Uniswap V2 Router calls
        ↓
Decode calldata using ABI
        ↓
Reconstruct swap path
        ↓
Fetch pair reserves from Uniswap V2 pools
        ↓
Simulate AMM reserve changes
        ↓
Calculate slippage buffer
        ↓
Estimate MEV exposure
        ↓
Expose pipeline metrics through /metrics
```

---

## Core Logic

The analyzer follows this pipeline:

1. Subscribe to pending Ethereum transactions using `eth_subscribe`.
2. Receive pending transaction hashes from the WebSocket RPC stream.
3. Count all observed pending transaction hashes with `pending_tx_seen_total`.
4. Fetch full transaction data through HTTP RPC.
5. Filter transactions addressed to the Uniswap V2 Router.
6. Count matched router transactions with `router_tx_matched_total`.
7. Decode the transaction input using the router ABI.
8. Count successful and failed ABI decoding with `swap_decode_success_total` and `swap_decode_error_total`.
9. Identify the swap function and its parameters.
10. Count supported swap function usage with `swap_type_total{type="..."}`.
11. Build the token path and corresponding Uniswap V2 pairs.
12. Fetch current reserves from each liquidity pool.
13. Measure pool reserve read latency with `pool_reserve_fetch_latency_ms`.
14. Simulate the swap using the Uniswap V2 constant product formula.
15. Compare the simulated result with the user-provided slippage limits.
16. Observe slippage buffer distribution with `slippage_buffer_pct_histogram`.
17. Classify the transaction as MEV-exposed or not exposed with `mev_exposure_total{exposed="true|false"}`.
18. Print a structured analysis of the transaction.

---

## Slippage and MEV Exposure Analysis

For exact-input swaps, the analyzer compares:

```text
expected output vs amountOutMin
```

If the simulated output is greater than the minimum accepted output, the difference is treated as the user’s slippage buffer.

For exact-output swaps, the analyzer compares:

```text
required input vs amountInMax
```

If the required input is lower than the maximum input the user is willing to spend, the difference is treated as the input buffer.

This buffer does not mean that an MEV attack will happen.

It means that the transaction exposes a measurable tolerance range that could potentially be exploited by adverse price movement, priority ordering, or sandwich-style strategies.

---

## Prometheus Metrics

The analyzer exposes Prometheus-compatible metrics on:

```text
http://127.0.0.1:9100/metrics
```

The metrics endpoint is useful for validating the real-time pipeline, measuring RPC bottlenecks, and demonstrating that the analyzer reaches the final MEV exposure signal instead of only decoding transactions.

### Metrics Reference

| Metric | Type | Purpose |
| ------ | ---- | ------- |
| `pending_tx_seen_total` | Counter | Total pending transaction hashes received from the WebSocket mempool stream |
| `router_tx_matched_total` | Counter | Number of pending transactions addressed to the Uniswap V2 Router |
| `swap_decode_success_total` | Counter | Number of Router transactions successfully decoded with the Uniswap V2 Router ABI |
| `swap_decode_error_total` | Counter | Number of ABI decoding failures for Router transactions |
| `swap_type_total{type}` | Counter | Number of supported swap calls by function name |
| `pool_reserve_fetch_latency_ms` | Histogram | Latency of Uniswap V2 `getReserves()` calls through HTTP RPC |
| `slippage_buffer_pct_histogram` | Histogram | Distribution of observed slippage/input buffer percentage |
| `mev_exposure_total{exposed}` | Counter | Final MEV exposure classification for analyzed swaps |
| `rpc_reconnects_total` | Counter | Number of WebSocket reconnect attempts |

### Metrics Design

The metrics are placed at key stages of the pipeline:

```text
pending_tx_seen_total
        ↓
router_tx_matched_total
        ↓
swap_decode_success_total / swap_decode_error_total
        ↓
swap_type_total{type}
        ↓
pool_reserve_fetch_latency_ms
        ↓
slippage_buffer_pct_histogram
        ↓
mev_exposure_total{exposed="true|false"}
```

This makes it possible to see where transactions drop out of the analysis pipeline.

For example:

* A high `pending_tx_seen_total` with low `router_tx_matched_total` means most mempool transactions are unrelated to the Uniswap V2 Router.
* A rising `swap_decode_error_total` would indicate ABI decoding issues.
* A high `pool_reserve_fetch_latency_ms` would indicate an HTTP RPC or pool read bottleneck.
* `mev_exposure_total{exposed="true"}` is the main final signal produced by the analyzer.

---

## Live Metrics Snapshot

Example snapshot from a live run:

```text
pending_tx_seen_total        60814
router_tx_matched_total      265
swap_decode_success_total    265
swap_decode_error_total      0
supported swap calls         254
fully analyzed swaps         238
mev_exposure true / false    135 / 103
rpc_reconnects_total         0
```

### Interpretation

During this run, the analyzer observed `60,814` pending mempool transactions and matched `265` transactions sent to the Uniswap V2 Router.

The Router match rate was approximately:

```text
265 / 60814 ≈ 0.44%
```

All matched Router transactions were decoded successfully:

```text
265 successful decodes
0 decode errors
100% decode success rate
```

The analyzer identified `254` supported swap calls out of `265` decoded Router calls:

```text
254 / 265 ≈ 95.85% supported swap coverage
```

The remaining decoded Router calls were likely non-swap Router methods or methods intentionally outside the analyzer scope.

The analyzer produced final slippage and MEV exposure classification for `238` swaps:

```text
135 exposed
103 not exposed
135 / 238 ≈ 56.7% exposed
```

This means that, in this sample, around `56.7%` of fully analyzed swaps had a positive slippage/input buffer and were classified as MEV-exposed by the analyzer.

### Swap Type Distribution

```text
swapExactETHForTokens                               115
swapExactTokensForTokens                            67
swapExactETHForTokensSupportingFeeOnTransferTokens   26
swapExactTokensForETH                                21
swapExactTokensForETHSupportingFeeOnTransferTokens    9
swapETHForExactTokens                                 9
swapExactTokensForTokensSupportingFeeOnTransferTokens 4
swapTokensForExactTokens                              3
swapTokensForExactETH                                 0
```

The most common observed swap type in this run was `swapExactETHForTokens`, followed by `swapExactTokensForTokens`.

### Pool Reserve Fetch Latency

The live run recorded `247` Uniswap V2 pool reserve reads:

```text
pool_reserve_fetch_latency_ms_count 247
pool_reserve_fetch_latency_ms_sum   452.059 ms
```

Average reserve read latency:

```text
452.059 / 247 ≈ 1.83 ms
```

Histogram buckets showed:

```text
240 / 247 reserve reads completed within 2.5 ms
247 / 247 reserve reads completed within 5.0 ms
```

This indicates that pool reserve reads were not the bottleneck during this sample run.

### Slippage Buffer Distribution

The analyzer recorded `238` slippage buffer observations:

```text
slippage_buffer_pct_histogram_count 238
slippage_buffer_pct_histogram_sum   4214.0564
```

Average observed buffer across all analyzed swaps:

```text
4214.0564 / 238 ≈ 17.71%
```

Because non-exposed or negative-buffer swaps are recorded as `0` in the current histogram implementation, the average among exposed swaps is more informative:

```text
4214.0564 / 135 ≈ 31.22%
```

The histogram also showed that:

```text
103 swaps were recorded at 0%
172 swaps were at or below 1%
203 swaps were at or below 25%
230 swaps were at or below 100%
238 swaps were at or below 250%
```

Large values near `100%` can occur when swaps have very loose slippage limits, for example when `amountOutMin` is set very low or close to zero.

---

## Example Metrics Output

```text
# HELP pending_tx_seen_total Total pending transaction hashes seen from Ethereum mempool WebSocket stream.
# TYPE pending_tx_seen_total counter
pending_tx_seen_total 60814.0

# HELP router_tx_matched_total Total pending transactions addressed to Uniswap V2 Router.
# TYPE router_tx_matched_total counter
router_tx_matched_total 265.0

# HELP swap_decode_success_total Total successfully decoded Uniswap V2 Router transactions.
# TYPE swap_decode_success_total counter
swap_decode_success_total 265.0

# HELP swap_decode_error_total Total Uniswap V2 Router calldata decode errors.
# TYPE swap_decode_error_total counter
swap_decode_error_total 0.0

# HELP swap_type_total Total decoded supported swap functions by Uniswap V2 Router function name.
# TYPE swap_type_total counter
swap_type_total{type="swapExactETHForTokens"} 115.0
swap_type_total{type="swapExactTokensForTokens"} 67.0
swap_type_total{type="swapExactETHForTokensSupportingFeeOnTransferTokens"} 26.0

# HELP pool_reserve_fetch_latency_ms Uniswap V2 pool getReserves RPC latency in milliseconds.
# TYPE pool_reserve_fetch_latency_ms histogram
pool_reserve_fetch_latency_ms_bucket{le="2.5"} 240.0
pool_reserve_fetch_latency_ms_bucket{le="5.0"} 247.0
pool_reserve_fetch_latency_ms_count 247.0
pool_reserve_fetch_latency_ms_sum 452.05902867019176

# HELP mev_exposure_total Total analyzed swaps grouped by MEV exposure classification.
# TYPE mev_exposure_total counter
mev_exposure_total{exposed="true"} 135.0
mev_exposure_total{exposed="false"} 103.0

# HELP rpc_reconnects_total Total WebSocket RPC reconnect attempts.
# TYPE rpc_reconnects_total counter
rpc_reconnects_total 0.0
```

---

## Example Output

```text
swap_func swapExactTokensForETHSupportingFeeOnTransferTokens
swap type: exact_in
path: 0xf374a6D1293BFA40dae3EE6FEfb3dD77A9Db6CE4 -> 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
initial amount in: 1263151846044667
final amount out: 157647197592439444
fee on transfer: True

Slippage / MEV exposure
mode: exact_in
exposure_token: 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
passes_slippage: True
mev_exposure: True
expected_out: 157647197592439444
min_out: 31529439518480000
slippage_buffer: 126117758073959444
slippage_buffer_pct: 80.000000000005

Hop 1
token_in: 0xf374a6D1293BFA40dae3EE6FEfb3dD77A9Db6CE4
token_out: 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
pair: 0x185B1AAa6f492A6877a5DEec9b28ED1C647EAbd8
amount_in: 1263151846044667
amount_out: 157647197592439444
reserve0 before: 7976236688931746054
reserve1 before: 62458690687658310
reserve0 after: 7818589491339306610
reserve1 after: 63721842533702977

tx_hash: 0x69ebbcab124b9099e6118f7d232945761e9659d583b809a84ffeb95f326c1b08
```

---

## Configuration

Create a `.env` file in the project root:

```env
WSS_RPC_URL=
HTTP_RPC_URL=
ABI_DIR=./abi
METRICS_ADDR=127.0.0.1
METRICS_PORT=9100
```

A safe `.env.example` file can be committed to the repository:

```env
WSS_RPC_URL=wss://your-websocket-rpc-url
HTTP_RPC_URL=https://your-http-rpc-url
ABI_DIR=./abi
METRICS_ADDR=127.0.0.1
METRICS_PORT=9100
```

Do not commit real RPC credentials or private endpoints in `.env`.

---

### Environment Variables

| Variable | Description |
| -------- | ----------- |
| `WSS_RPC_URL` | WebSocket Ethereum RPC endpoint used for pending transaction subscription |
| `HTTP_RPC_URL` | HTTP Ethereum RPC endpoint used to fetch full transaction data and pool state |
| `ABI_DIR` | Directory containing Uniswap V2 ABI files |
| `METRICS_ADDR` | Address used by the Prometheus metrics HTTP server. Defaults to `127.0.0.1` |
| `METRICS_PORT` | Port used by the Prometheus metrics HTTP server. Defaults to `9100` |

---

## Requirements

Python dependencies are listed in:

```text
requirements.txt
```

Install them with:

```bash
pip install -r requirements.txt
```

The project uses:

```text
python-dotenv
web3
websockets
prometheus-client
```

---

## Run

Start the analyzer with default metrics settings:

```bash
python src/mempool_analyzer/main.py
```

Or explicitly set the metrics port:

```bash
METRICS_PORT=9100 python src/mempool_analyzer/main.py
```

If your local import path requires it, run:

```bash
PYTHONPATH=src/mempool_analyzer METRICS_PORT=9100 python src/mempool_analyzer/main.py
```

After startup, the script subscribes to pending Ethereum transactions and begins printing decoded Uniswap V2 swap analysis when matching transactions are detected.

The metrics endpoint is available at:

```bash
curl http://127.0.0.1:9100/metrics
```

---

## Example PromQL Queries

Router match rate:

```promql
rate(router_tx_matched_total[5m]) / rate(pending_tx_seen_total[5m])
```

ABI decode error rate:

```promql
rate(swap_decode_error_total[5m]) / (rate(swap_decode_success_total[5m]) + rate(swap_decode_error_total[5m]))
```

p95 pool reserve fetch latency:

```promql
histogram_quantile(0.95, rate(pool_reserve_fetch_latency_ms_bucket[5m]))
```

MEV exposure rate:

```promql
rate(mev_exposure_total{exposed="true"}[5m]) / sum(rate(mev_exposure_total[5m]))
```

Swap type distribution:

```promql
sum by (type) (rate(swap_type_total[5m]))
```

WebSocket reconnects:

```promql
increase(rpc_reconnects_total[1h])
```

---

## Design Decisions

### WebSocket for mempool monitoring

The project uses a WebSocket RPC connection to receive pending transaction hashes in real time.

This makes the implementation accessible and easy to run without requiring a direct Ethereum P2P node implementation.

### HTTP RPC for transaction and pool reads

The analyzer uses HTTP RPC calls to fetch full transaction data, pair addresses, token metadata, and pool reserves.

This keeps the architecture simple while still allowing real-time analysis of pending swaps.

### Prometheus metrics for observability

The analyzer exposes a lightweight HTTP metrics endpoint on `127.0.0.1:9100` by default.

This makes the pipeline easier to evaluate as an engineering system, not only as a script that prints decoded swaps.

The metrics show throughput, decoding quality, latency, supported swap coverage, final exposure classification, and WebSocket stability.

### No transaction execution

The system is intentionally read-only.

It observes, decodes, simulates, and reports.

This makes the project suitable as a portfolio case study for blockchain analytics, DeFi infrastructure, and MEV research without crossing into automated execution logic.

### AMM simulation instead of trade execution

The analyzer applies the Uniswap V2 pricing formulas locally to estimate swap output or required input.

This allows the tool to reason about pending swaps without interacting with contracts in a state-changing way.

---

## Use Cases

* Ethereum mempool analysis
* DeFi transaction monitoring
* Slippage tolerance research
* MEV exposure analysis
* Uniswap V2 swap behavior study
* Real-time blockchain data engineering
* Portfolio demonstration for Web3 infrastructure roles
* Educational tool for understanding AMM mechanics
* Observability example for a real-time Web3 data pipeline

---

## Limitations

This project is intentionally limited in scope.

It does not account for:

* Final block ordering
* Competing pending transactions
* Private mempools
* Builder-specific transaction ordering
* Flashbots bundles
* State changes between observation and inclusion
* Full sandwich profitability simulation
* Gas costs or execution profitability
* Universal Router, Uniswap V3, 1inch, 0x, CoW Swap, or other aggregator flows

Because pending transaction state can change quickly, the output should be interpreted as an analytical estimate rather than a guaranteed execution result.

Metrics should also be interpreted as local runtime observations. They depend on RPC provider behavior, network conditions, mempool visibility, and how long the analyzer has been running.

---

## Why This Project Matters

Most users submit swaps with some level of slippage tolerance.

That tolerance is necessary for successful execution, but it also creates a measurable range between the expected execution price and the worst acceptable execution price.

This project shows how that exposure can be detected and quantified from pending transaction data before a transaction is included in a block.

It demonstrates a practical understanding of Ethereum mempool mechanics, Uniswap V2 internals, ABI decoding, AMM math, real-time blockchain analytics, and production-style observability.

The project is not a trading bot.

It is a technical case study in observing pending DeFi activity and extracting useful risk signals from public mempool data.

---

## Disclaimer

This project is for educational and analytical purposes only.

It does not provide financial advice, does not execute trades, and does not implement MEV extraction strategies.

---
