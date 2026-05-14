import os

from prometheus_client import Counter, Histogram, start_http_server


PENDING_TX_SEEN = Counter(
    "pending_tx_seen",
    "Total pending transaction hashes seen from Ethereum mempool WebSocket stream.",
)

ROUTER_TX_MATCHED = Counter(
    "router_tx_matched",
    "Total pending transactions addressed to Uniswap V2 Router.",
)

SWAP_DECODE_SUCCESS = Counter(
    "swap_decode_success",
    "Total successfully decoded Uniswap V2 Router transactions.",
)

SWAP_DECODE_ERROR = Counter(
    "swap_decode_error",
    "Total Uniswap V2 Router calldata decode errors.",
)

SWAP_TYPE = Counter(
    "swap_type",
    "Total decoded supported swap functions by Uniswap V2 Router function name.",
    ["type"],
)

POOL_RESERVE_FETCH_LATENCY_MS = Histogram(
    "pool_reserve_fetch_latency_ms",
    "Uniswap V2 pool getReserves RPC latency in milliseconds.",
    buckets=(0.5, 1, 2.5, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

SLIPPAGE_BUFFER_PCT = Histogram(
    "slippage_buffer_pct_histogram",
    "Observed positive slippage buffer percentage for supported swaps.",
    buckets=(0, 0.1, 0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 99, 100, 250, 500),
)

MEV_EXPOSURE = Counter(
    "mev_exposure",
    "Total analyzed swaps grouped by MEV exposure classification.",
    ["exposed"],
)

RPC_RECONNECTS = Counter(
    "rpc_reconnects",
    "Total WebSocket RPC reconnect attempts.",
)


def init_metric_labels() -> None:
    MEV_EXPOSURE.labels(exposed="true")
    MEV_EXPOSURE.labels(exposed="false")


def start_metrics_server() -> None:
    port = int(os.getenv("METRICS_PORT", "9100"))
    addr = os.getenv("METRICS_ADDR", "127.0.0.1")

    init_metric_labels()
    start_http_server(port, addr=addr)

    print(f"[metrics] Prometheus endpoint started: http://{addr}:{port}/metrics")