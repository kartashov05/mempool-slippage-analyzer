---

# Ethereum Mempool Slippage Exposure Analyzer

A real-time Ethereum mempool analytics tool that monitors pending Uniswap V2 swaps, simulates AMM reserve changes, and estimates slippage-based MEV exposure before transactions are included in a block.

---

## Overview

This project implements a real-time analytics pipeline for observing pending Ethereum transactions through a WebSocket RPC connection.

The system listens to the Ethereum mempool, filters transactions sent to the Uniswap V2 Router, decodes swap calldata using ABI definitions, reconstructs swap paths, fetches Uniswap V2 pool reserves, and simulates how each pending swap would affect AMM liquidity reserves.

The goal of this project is not to execute trades, send transactions, or build MEV bundles.

Instead, it is an analytical case study focused on understanding how pending swaps expose users to slippage and potential MEV impact before block inclusion.

---

## What This Project Demonstrates

This project demonstrates practical work with:

* Ethereum pending transaction monitoring
* WebSocket RPC subscriptions
* Uniswap V2 Router calldata decoding
* ABI-based smart contract interaction
* AMM reserve simulation
* Multi-hop swap path reconstruction
* Slippage tolerance analysis
* MEV exposure estimation
* Real-time blockchain data processing in Python

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
````

---

## Core Logic

The analyzer follows this pipeline:

1. Subscribe to pending Ethereum transactions using `eth_subscribe`.
2. Receive pending transaction hashes from the WebSocket RPC stream.
3. Fetch full transaction data through HTTP RPC.
4. Filter transactions addressed to the Uniswap V2 Router.
5. Decode the transaction input using the router ABI.
6. Identify the swap function and its parameters.
7. Build the token path and corresponding Uniswap V2 pairs.
8. Fetch current reserves from each liquidity pool.
9. Simulate the swap using the Uniswap V2 constant product formula.
10. Compare the simulated result with the user-provided slippage limits.
11. Print a structured analysis of the transaction.

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
```

---

### Environment Variables

| Variable       | Description                                                                   |
| -------------- | ----------------------------------------------------------------------------- |
| `WSS_RPC_URL`  | WebSocket Ethereum RPC endpoint used for pending transaction subscription     |
| `HTTP_RPC_URL` | HTTP Ethereum RPC endpoint used to fetch full transaction data and pool state |
| `ABI_DIR`      | Directory containing Uniswap V2 ABI files                                      |

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

---

## Run

Start the analyzer with:

```bash
python src/mempool_analyzer/main.py
```

After startup, the script subscribes to pending Ethereum transactions and begins printing decoded Uniswap V2 swap analysis when matching transactions are detected.

---

## Design Decisions

### WebSocket for mempool monitoring

The project uses a WebSocket RPC connection to receive pending transaction hashes in real time.

This makes the implementation accessible and easy to run without requiring a direct Ethereum P2P node implementation.

### HTTP RPC for transaction and pool reads

The analyzer uses HTTP RPC calls to fetch full transaction data, pair addresses, token metadata, and pool reserves.

This keeps the architecture simple while still allowing real-time analysis of pending swaps.

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

Because pending transaction state can change quickly, the output should be interpreted as an analytical estimate rather than a guaranteed execution result.

---

## Why This Project Matters

Most users submit swaps with some level of slippage tolerance.

That tolerance is necessary for successful execution, but it also creates a measurable range between the expected execution price and the worst acceptable execution price.

This project shows how that exposure can be detected and quantified from pending transaction data before a transaction is included in a block.

It demonstrates a practical understanding of Ethereum mempool mechanics, Uniswap V2 internals, ABI decoding, AMM math, and real-time blockchain analytics.

The project is not a trading bot.

It is a technical case study in observing pending DeFi activity and extracting useful risk signals from public mempool data.

---

## Disclaimer

This project is for educational and analytical purposes only.

It does not provide financial advice, does not execute trades, and does not implement MEV extraction strategies.

---