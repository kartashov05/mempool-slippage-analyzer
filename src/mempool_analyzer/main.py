from functools import lru_cache

from dotenv import load_dotenv

import os
import time
import asyncio
import json

from web3 import Web3
import websockets

from prometheus_client import Counter, Histogram, start_http_server

load_dotenv()
from abi_loader import load_abi


WSS_RPC_URL = os.getenv("WSS_RPC_URL")
HTTP_RPC_URL = os.getenv("HTTP_RPC_URL")

METRICS_ADDR = os.getenv("METRICS_ADDR", "127.0.0.1")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

w3 = Web3(Web3.HTTPProvider(HTTP_RPC_URL))

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
    buckets=(
        0.5,
        1,
        2.5,
        5,
        10,
        25,
        50,
        100,
        250,
        500,
        1000,
        2500,
        5000,
    ),
)

SLIPPAGE_BUFFER_PCT_HISTOGRAM = Histogram(
    "slippage_buffer_pct_histogram",
    "Observed positive slippage buffer percentage for supported swaps.",
    buckets=(
        0,
        0.1,
        0.5,
        1,
        2.5,
        5,
        10,
        25,
        50,
        75,
        90,
        95,
        99,
        100,
        250,
        500,
    ),
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


SUPPORTED_SWAP_TYPES = (
    "swapExactTokensForTokens",
    "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "swapTokensForExactTokens",
    "swapExactETHForTokens",
    "swapExactETHForTokensSupportingFeeOnTransferTokens",
    "swapTokensForExactETH",
    "swapExactTokensForETH",
    "swapExactTokensForETHSupportingFeeOnTransferTokens",
    "swapETHForExactTokens",
)


def init_metric_labels() -> None:
    MEV_EXPOSURE.labels(exposed="true")
    MEV_EXPOSURE.labels(exposed="false")

    for swap_type in SUPPORTED_SWAP_TYPES:
        SWAP_TYPE.labels(type=swap_type)


def start_metrics_server() -> None:
    init_metric_labels()
    start_http_server(METRICS_PORT, addr=METRICS_ADDR)

    print(
        f"Prometheus metrics listening on "
        f"http://{METRICS_ADDR}:{METRICS_PORT}/metrics"
    )


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

UNISWAP_V2_ROUTER_ADDRESS = Web3.to_checksum_address(
    "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
)

UNISWAP_V2_ROUTER_ABI = load_abi("uniswap_v2_router")
uniswap_v2_router_contract = w3.eth.contract(
    address=UNISWAP_V2_ROUTER_ADDRESS,
    abi=UNISWAP_V2_ROUTER_ABI,
)

UNISWAP_V2_FACTORY_ADDRESS = Web3.to_checksum_address(
    "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
)

UNISWAP_V2_FACTORY_ABI = load_abi("uniswap_v2_factory")
uniswap_v2_factory_contract = w3.eth.contract(
    address=UNISWAP_V2_FACTORY_ADDRESS,
    abi=UNISWAP_V2_FACTORY_ABI,
)

UNISWAP_V2_POOL_ABI = load_abi("uniswap_v2_pool")


@lru_cache(maxsize=100_000)
def get_pair_address(token_a: str, token_b: str) -> str:
    pair_address = uniswap_v2_factory_contract.functions.getPair(
        token_a,
        token_b,
    ).call()

    if pair_address == ZERO_ADDRESS:
        raise ValueError(f"Pair not found: {token_a} -> {token_b}")

    return Web3.to_checksum_address(pair_address)


@lru_cache(maxsize=100_000)
def get_pool_contract(pair_address: str):
    return w3.eth.contract(
        address=Web3.to_checksum_address(pair_address),
        abi=UNISWAP_V2_POOL_ABI,
    )


@lru_cache(maxsize=100_000)
def get_pool_tokens(pair_address: str):
    pool_contract = get_pool_contract(pair_address)

    token0 = Web3.to_checksum_address(
        pool_contract.functions.token0().call()
    )

    token1 = Web3.to_checksum_address(
        pool_contract.functions.token1().call()
    )

    return token0, token1


def fetch_pool_reserves(pool_contract):
    started_at = time.perf_counter()

    try:
        return pool_contract.functions.getReserves().call()
    finally:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        POOL_RESERVE_FETCH_LATENCY_MS.observe(elapsed_ms)


def build_pairs(path: list[str]) -> list[tuple[str, str]]:
    path = [Web3.to_checksum_address(p) for p in path]

    return list(zip(path, path[1:]))


def get_amount_out(amount_in: int, reserve_in: int, reserve_out: int) -> int:
    if amount_in <= 0:
        raise ValueError("amount_in must be positive")

    if reserve_in <= 0 or reserve_out <= 0:
        raise ValueError("invalid reserves")

    amount_in_with_fee = amount_in * 997

    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * 1000 + amount_in_with_fee

    return numerator // denominator


def get_amount_in(amount_out: int, reserve_in: int, reserve_out: int) -> int:
    if amount_out <= 0:
        raise ValueError("amount_out must be positive")

    if reserve_in <= 0 or reserve_out <= 0:
        raise ValueError("invalid reserves")

    if amount_out >= reserve_out:
        raise ValueError("amount_out exceeds reserve_out")

    numerator = reserve_in * amount_out * 1000
    denominator = (reserve_out - amount_out) * 997

    return numerator // denominator + 1


def handle_exact_in(amount_in: int, path: list[str], fee: bool = False):
    pairs = build_pairs(path)

    current_amount_in = amount_in

    hops = []

    for token_in, token_out in pairs:
        pair_address = get_pair_address(token_in, token_out)
        pool_contract = get_pool_contract(pair_address)

        reserves = fetch_pool_reserves(pool_contract)
        token0, token1 = get_pool_tokens(pair_address)

        reserve0, reserve1, _ = reserves

        if token_in == token0 and token_out == token1:
            reserve_in = reserve0
            reserve_out = reserve1

            new_reserve0 = reserve0 + current_amount_in
        else:
            reserve_in = reserve1
            reserve_out = reserve0

            new_reserve1 = reserve1 + current_amount_in

        amount_out = get_amount_out(
            amount_in=current_amount_in,
            reserve_in=reserve_in,
            reserve_out=reserve_out,
        )

        if token_in == token0 and token_out == token1:
            new_reserve1 = reserve1 - amount_out
        else:
            new_reserve0 = reserve0 - amount_out

        hop = {
            "token_in": token_in,
            "token_out": token_out,
            "pair_address": pair_address,
            "reserve_in_before": reserve_in,
            "reserve_out_before": reserve_out,
            "amount_in": current_amount_in,
            "amount_out": amount_out,
            "reserve0_before": reserve0,
            "reserve1_before": reserve1,
            "reserve0_after": new_reserve0,
            "reserve1_after": new_reserve1,
            "token0": token0,
            "token1": token1,
        }

        hops.append(hop)

        current_amount_in = amount_out

    return {
        "type": "exact_in",
        "initial_amount_in": amount_in,
        "final_amount_out": current_amount_in,
        "path": path,
        "fee_on_transfer": fee,
        "hops": hops,
    }


def handle_exact_out(amount_out: int, path: list[str], fee: bool = False):
    pairs = build_pairs(path)

    current_amount_out = amount_out

    reversed_hops = []

    for token_in, token_out in reversed(pairs):
        pair_address = get_pair_address(token_in, token_out)
        pool_contract = get_pool_contract(pair_address)

        reserves = fetch_pool_reserves(pool_contract)
        token0, token1 = get_pool_tokens(pair_address)

        reserve0, reserve1, _ = reserves

        if token_in == token0 and token_out == token1:
            reserve_in = reserve0
            reserve_out = reserve1
        else:
            reserve_in = reserve1
            reserve_out = reserve0

        amount_in = get_amount_in(
            amount_out=current_amount_out,
            reserve_in=reserve_in,
            reserve_out=reserve_out,
        )

        if token_in == token0 and token_out == token1:
            new_reserve0 = reserve0 + amount_in
            new_reserve1 = reserve1 - current_amount_out
        else:
            new_reserve0 = reserve0 - current_amount_out
            new_reserve1 = reserve1 + amount_in

        hop = {
            "token_in": token_in,
            "token_out": token_out,
            "pair_address": pair_address,
            "reserve_in_before": reserve_in,
            "reserve_out_before": reserve_out,
            "amount_in": amount_in,
            "amount_out": current_amount_out,
            "reserve0_before": reserve0,
            "reserve1_before": reserve1,
            "reserve0_after": new_reserve0,
            "reserve1_after": new_reserve1,
            "token0": token0,
            "token1": token1,
        }

        reversed_hops.append(hop)

        current_amount_out = amount_in

    hops = list(reversed(reversed_hops))

    return {
        "type": "exact_out",
        "required_amount_in": current_amount_out,
        "final_amount_out": amount_out,
        "path": path,
        "fee_on_transfer": fee,
        "hops": hops,
    }


def analyze_slippage_exposure(result: dict, trigger_amount: int | None) -> dict:
    if trigger_amount is None:
        raise ValueError("trigger_amount is required")

    if result["type"] == "exact_in":
        expected_out = result["final_amount_out"]
        min_out = trigger_amount

        buffer_abs = expected_out - min_out
        buffer_pct = (
            buffer_abs / expected_out * 100
            if expected_out > 0
            else None
        )

        return {
            "mode": "exact_in",
            "expected_out": expected_out,
            "min_out": min_out,
            "slippage_buffer": buffer_abs,
            "slippage_buffer_pct": buffer_pct,
            "passes_slippage": expected_out >= min_out,
            "mev_exposure": buffer_abs > 0,
            "exposure_token": result["path"][-1],
        }

    elif result["type"] == "exact_out":
        required_in = result["required_amount_in"]
        max_in = trigger_amount

        buffer_abs = max_in - required_in
        buffer_pct = (
            buffer_abs / required_in * 100
            if required_in > 0
            else None
        )

        return {
            "mode": "exact_out",
            "required_in": required_in,
            "max_in": max_in,
            "input_buffer": buffer_abs,
            "input_buffer_pct": buffer_pct,
            "passes_slippage": required_in <= max_in,
            "mev_exposure": buffer_abs > 0,
            "exposure_token": result["path"][0],
        }

    else:
        raise ValueError(f"Unknown swap type: {result['type']}")


def observe_exposure_metrics(result: dict, exposure: dict) -> None:
    if result["type"] == "exact_in":
        buffer_pct = exposure.get("slippage_buffer_pct")
    else:
        buffer_pct = exposure.get("input_buffer_pct")

    if buffer_pct is not None:
        SLIPPAGE_BUFFER_PCT_HISTOGRAM.observe(max(float(buffer_pct), 0.0))

    exposed = str(bool(exposure["mev_exposure"])).lower()
    MEV_EXPOSURE.labels(exposed=exposed).inc()


def uniswap_v2_handler(tx):
    try:
        func, params = uniswap_v2_router_contract.decode_function_input(
            tx["input"]
        )
        SWAP_DECODE_SUCCESS.inc()
    except Exception:
        SWAP_DECODE_ERROR.inc()
        raise

    def _handler(
        swap_func,
        amount_in=None,
        amount_out=None,
        path=None,
        fee=False,
        trigger_amount=None,
    ):
        if path is None:
            raise ValueError("path is required")

        if amount_in is not None and amount_out is not None:
            raise ValueError("pass either amount_in or amount_out, not both")

        SWAP_TYPE.labels(type=swap_func).inc()

        if amount_in is not None:
            result = handle_exact_in(
                amount_in=amount_in,
                path=path,
                fee=fee,
            )
        elif amount_out is not None:
            result = handle_exact_out(
                amount_out=amount_out,
                path=path,
                fee=fee,
            )
        else:
            raise ValueError("amount_in or amount_out is required")

        print("swap_func", swap_func)
        print("swap type:", result["type"])
        print("path:", " -> ".join(result["path"]))

        if result["type"] == "exact_in":
            print("initial amount in:", result["initial_amount_in"])
            print("final amount out:", result["final_amount_out"])
        else:
            print("required amount in:", result["required_amount_in"])
            print("final amount out:", result["final_amount_out"])

        print("fee on transfer:", result["fee_on_transfer"])

        if trigger_amount is not None:
            exposure = analyze_slippage_exposure(
                result=result,
                trigger_amount=trigger_amount,
            )

            observe_exposure_metrics(
                result=result,
                exposure=exposure,
            )

            print("\nSlippage / MEV exposure")
            print("mode:", exposure["mode"])
            print("exposure_token:", exposure["exposure_token"])
            print("passes_slippage:", exposure["passes_slippage"])
            print("mev_exposure:", exposure["mev_exposure"])

            if result["type"] == "exact_in":
                print("expected_out:", exposure["expected_out"])
                print("min_out:", exposure["min_out"])
                print("slippage_buffer:", exposure["slippage_buffer"])
                print("slippage_buffer_pct:", exposure["slippage_buffer_pct"])
            else:
                print("required_in:", exposure["required_in"])
                print("max_in:", exposure["max_in"])
                print("input_buffer:", exposure["input_buffer"])
                print("input_buffer_pct:", exposure["input_buffer_pct"])

        for i, hop in enumerate(result["hops"], start=1):
            print(f"\nHop {i}")
            print("token_in:", hop["token_in"])
            print("token_out:", hop["token_out"])
            print("pair:", hop["pair_address"])
            print("amount_in:", hop["amount_in"])
            print("amount_out:", hop["amount_out"])
            print("reserve0 before:", hop["reserve0_before"])
            print("reserve1 before:", hop["reserve1_before"])
            print("reserve0 after:", hop["reserve0_after"])
            print("reserve1 after:", hop["reserve1_after"])

        tx_hash = tx.get("hash")
        tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash

        print(f"\ntx_hash: {tx_hash_hex}")
        print("-" * 80)

    if "swapExactTokensForTokens" in func.fn_name:
        fee = False

        if func.fn_name == "swapExactTokensForTokensSupportingFeeOnTransferTokens":
            fee = True

        _handler(
            swap_func=func.fn_name,
            amount_in=params["amountIn"],
            amount_out=None,
            path=params["path"],
            fee=fee,
            trigger_amount=params["amountOutMin"],
        )

    elif func.fn_name == "swapTokensForExactTokens":
        _handler(
            swap_func=func.fn_name,
            amount_in=None,
            amount_out=params["amountOut"],
            path=params["path"],
            fee=False,
            trigger_amount=params["amountInMax"],
        )

    elif "swapExactETHForTokens" in func.fn_name:
        fee = False

        if func.fn_name == "swapExactETHForTokensSupportingFeeOnTransferTokens":
            fee = True

        _handler(
            swap_func=func.fn_name,
            amount_in=tx["value"],
            amount_out=None,
            path=params["path"],
            fee=fee,
            trigger_amount=params["amountOutMin"],
        )

    elif func.fn_name == "swapTokensForExactETH":
        _handler(
            swap_func=func.fn_name,
            amount_in=None,
            amount_out=params["amountOut"],
            path=params["path"],
            fee=False,
            trigger_amount=params["amountInMax"],
        )

    elif "swapExactTokensForETH" in func.fn_name:
        fee = False

        if func.fn_name == "swapExactTokensForETHSupportingFeeOnTransferTokens":
            fee = True

        _handler(
            swap_func=func.fn_name,
            amount_in=params["amountIn"],
            amount_out=None,
            path=params["path"],
            fee=fee,
            trigger_amount=params["amountOutMin"],
        )

    elif func.fn_name == "swapETHForExactTokens":
        _handler(
            swap_func=func.fn_name,
            amount_in=None,
            amount_out=params["amountOut"],
            path=params["path"],
            fee=False,
            trigger_amount=tx["value"],
        )

    else:
        print(func.fn_name, "skip")

    return


async def tx_handler(tx):
    tx_to = tx.get("to")

    if not tx_to:
        return

    print(Web3.to_checksum_address(tx_to), Web3.to_checksum_address(tx_to) == UNISWAP_V2_ROUTER_ADDRESS)
    if Web3.to_checksum_address(tx_to) == UNISWAP_V2_ROUTER_ADDRESS:
        ROUTER_TX_MATCHED.inc()
        await asyncio.to_thread(uniswap_v2_handler, tx)
    else:
        return


def is_pending_tx(tx: dict) -> bool:
    return (
        tx.get("blockHash") is None
        and tx.get("blockNumber") is None
        and tx.get("transactionIndex") is None
    )


async def listen_pending_txs():
    async with websockets.connect(
        WSS_RPC_URL,
        ping_interval=20,
        ping_timeout=20,
        max_queue=10_000,
    ) as ws:
        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_subscribe",
            "params": ["newPendingTransactions"],
        }

        await ws.send(json.dumps(subscribe_msg))

        response = await ws.recv()
        print(f"Subscription response: {response}\n")

        while True:
            msg = json.loads(await ws.recv())

            try:
                tx_hash = msg["params"]["result"]
                PENDING_TX_SEEN.inc()
            except KeyError:
                continue

            try:
                tx = await asyncio.to_thread(
                    w3.eth.get_transaction,
                    tx_hash,
                )
            except Exception:
                continue

            if not is_pending_tx(tx):
                continue

            try:
                await tx_handler(tx)
            except Exception as e:
                print("tx_handler error: ", e)


async def listen_forever():
    while True:
        try:
            await listen_pending_txs()
        except websockets.exceptions.ConnectionClosedError as e:
            print("WebSocket closed:", e)
        except websockets.exceptions.ConnectionClosedOK:
            print("WebSocket closed normally")
        except OSError as e:
            print("Network error:", e)
        except Exception as e:
            print("Unexpected error:", e)

        RPC_RECONNECTS.inc()

        print("Reconnecting...")
        await asyncio.sleep(3)


if __name__ == "__main__":
    start_metrics_server()
    asyncio.run(listen_forever())