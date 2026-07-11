# backtest.py — Backtesting Standalone com múltiplas fontes de dados
# Krypton TradeBot | Estratégia: Supertrend + RSI + MACD Filter
#
# Baixa dados históricos primeiro pela Binance Global, depois Binance US e,
# se necessário, usa Yahoo Finance como fallback. A estratégia do bot não foi alterada.
#
# ✅ FIX v2: Pré-aquecimento de 300 candles antes do período solicitado
#    Isso garante que RSI(14), MACD(12,26,9) e Supertrend(7) estejam
#    totalmente estabilizados quando o backtest começar a contabilizar trades.
#    Sem isso, períodos curtos (ex: 1 ano) retornam 0 trades por falta de
#    histórico nos indicadores.
#
# Uso:
#   python backtest.py --symbol SOLUSDT --start 2022-01-01 --end 2026-06-01
#   python backtest.py --symbol BTCUSDT --start 2024-01-01
#   python backtest.py  # SOLUSDT desde 2022-01-01

import argparse
import time
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from config import (
    FEE_RATE,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MAX_DRAWDOWN_PCT,
    RISK_PER_TRADE,
    RSI_HIGH,
    RSI_LOW,
    RSI_PERIOD,
    STOP_LOSS_ATR_MULT,
    SUPERTREND_MULTIPLIER,
    SUPERTREND_PERIOD,
    TAKE_PROFIT_ATR_MULT,
)
from indicators import compute_atr, compute_signals

# Capital inicial simulado (mesma base dos relatórios do projeto)
INITIAL_CAPITAL = 10_000.0


BINANCE_GLOBAL_URL = "https://api.binance.com/api/v3/klines"
BINANCE_US_URL     = "https://api.binance.us/api/v3/klines"

# Binance US usa pares USD em alguns ativos. Binance Global usa USDT.
BINANCE_US_SYMBOL_MAP = {
    "SOLUSDT": "SOLUSD",
    "BTCUSDT": "BTCUSD",
    "ETHUSDT": "ETHUSD",
    "BNBUSDT": "BNBUSD",
}

YAHOO_SYMBOL_MAP = {
    "SOLUSDT": "SOL-USD",
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
}

# Número de candles extras buscados ANTES do período para aquecer os indicadores.
# RSI precisa de ~14, MACD de ~35, Supertrend de ~30 → 300 dias é margem segura.
WARMUP_DAYS = 300


def _date_to_ms(value: str) -> int:
    return int(datetime.strptime(value, "%Y-%m-%d").timestamp() * 1000)


def _klines_to_df(klines: list) -> pd.DataFrame:
    if not klines:
        return pd.DataFrame()

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df[["open", "high", "low", "close", "volume"]]


def get_ohlcv_binance(symbol: str, start_str: str, end_str: str | None,
                       base_url: str, symbol_map: dict | None = None) -> pd.DataFrame:
    """
    Baixa OHLCV pela API pública da Binance/Binance US em lotes de 1000 candles.
    """
    symbol_api = (symbol_map.get(symbol.upper(), symbol.upper())
                  if symbol_map else symbol.upper())
    start_ts = _date_to_ms(start_str)
    end_ts   = _date_to_ms(end_str) if end_str else None

    all_klines = []
    current_ts = start_ts

    while True:
        params = {
            "symbol":    symbol_api,
            "interval":  "1d",
            "startTime": current_ts,
            "limit":     1000,
        }
        if end_ts:
            params["endTime"] = end_ts

        try:
            response = requests.get(base_url, params=params, timeout=15)
            if response.status_code != 200:
                break
            klines = response.json()
        except Exception:
            time.sleep(2)
            break

        if not klines or isinstance(klines, dict):
            break

        all_klines.extend(klines)

        if len(klines) < 1000:
            break

        current_ts = klines[-1][0] + 86_400_000
        if end_ts and current_ts >= end_ts:
            break

        time.sleep(0.2)

    return _klines_to_df(all_klines)


def get_ohlcv_yahoo(symbol: str, start_str: str,
                     end_str: str | None = None) -> pd.DataFrame:
    """
    Fallback via Yahoo Finance para períodos em que Binance não estiver disponível.
    """
    yf_symbol = YAHOO_SYMBOL_MAP.get(symbol.upper())
    if not yf_symbol:
        return pd.DataFrame()

    try:
        df = yf.download(
            yf_symbol,
            start=start_str,
            end=end_str,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })

    required_cols = ["open", "high", "low", "close", "volume"]
    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()

    df.index = pd.to_datetime(df.index)
    return df[required_cols].dropna()


def get_ohlcv(symbol: str, start_str: str,
               end_str: str | None = None) -> tuple[pd.DataFrame, str]:
    """
    Busca dados em múltiplas fontes. Retorna a fonte com mais candles.
    """
    sources = [
        ("Binance Global", lambda: get_ohlcv_binance(
            symbol, start_str, end_str, BINANCE_GLOBAL_URL)),
        ("Binance US",     lambda: get_ohlcv_binance(
            symbol, start_str, end_str, BINANCE_US_URL, BINANCE_US_SYMBOL_MAP)),
        ("Yahoo Finance",  lambda: get_ohlcv_yahoo(symbol, start_str, end_str)),
    ]

    best_df     = pd.DataFrame()
    best_source = "nenhuma fonte"

    for source_name, loader in sources:
        print(f"\n  Tentando {source_name}...", end=" ", flush=True)
        df = loader()
        if len(df) > len(best_df):
            best_df     = df
            best_source = source_name

        if len(df) >= 50:
            print(f"✓ {len(df)} candles")
            return df, source_name

        print(f"{len(df)} candles")

    return best_df, best_source


def default_strategy_params() -> dict:
    """Parâmetros de estratégia atuais em config.py (baseline)."""
    return {
        "st_period":  SUPERTREND_PERIOD,
        "st_mult":    SUPERTREND_MULTIPLIER,
        "rsi_period": RSI_PERIOD,
        "rsi_low":    RSI_LOW,
        "rsi_high":   RSI_HIGH,
        "macd_fast":  MACD_FAST,
        "macd_slow":  MACD_SLOW,
        "macd_sig":   MACD_SIGNAL,
    }


def simulate_strategy(df: pd.DataFrame, signals: pd.Series) -> dict:
    """
    Simula a estratégia sobre uma janela já fatiada (sem warm-up).

    Parâmetros de risco vêm de config.py (ATR mult, fees, capital, max DD).
    """
    if len(df) < 10:
        return {}

    atr = compute_atr(df["high"], df["low"], df["close"])
    capital  = INITIAL_CAPITAL
    peak     = capital
    equity   = [capital]
    trades   = []
    pos      = 0
    entry    = 0.0
    pos_size = 0.0

    for i in range(1, len(df)):
        price = float(df["close"].iloc[i])
        sig   = int(signals.iloc[i]) if pd.notna(signals.iloc[i]) else 0
        atr_v = atr.iloc[i]

        if pos != 0:
            sl = (
                entry - STOP_LOSS_ATR_MULT * atr_v if pos == 1
                else entry + STOP_LOSS_ATR_MULT * atr_v
            )
            tp = (
                entry + TAKE_PROFIT_ATR_MULT * atr_v if pos == 1
                else entry - TAKE_PROFIT_ATR_MULT * atr_v
            )
            hit_sl = (pos == 1 and price <= sl) or (pos == -1 and price >= sl)
            hit_tp = (pos == 1 and price >= tp) or (pos == -1 and price <= tp)
            exit_sg = (pos != sig and sig != 0)

            if hit_sl or hit_tp or exit_sg:
                fee = pos_size * price * FEE_RATE
                pnl = (
                    pos_size * (price - entry) if pos == 1
                    else pos_size * (entry - price)
                ) - fee
                capital += pnl
                trades.append({
                    "pnl": pnl,
                    "exit_reason": "SL" if hit_sl else "TP" if hit_tp else "Sig",
                })
                pos = 0
                peak = max(peak, capital)

        if peak > 0 and (peak - capital) / peak >= MAX_DRAWDOWN_PCT:
            equity.append(capital)
            continue

        if pos == 0 and sig != 0 and pd.notna(atr_v) and atr_v > 0:
            entry = price * (1.0005 if sig == 1 else 0.9995)
            pos_size = (capital * RISK_PER_TRADE) / (atr_v * STOP_LOSS_ATR_MULT)
            capital -= pos_size * entry * FEE_RATE
            pos = int(sig)

        equity.append(capital)

    eq = pd.Series(equity, index=df.index[: len(equity)])
    ret = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
    rets = eq.pct_change().dropna()
    sharpe = (
        (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
    )
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    if losses:
        pf = sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))
    else:
        pf = float("inf") if wins else 0.0
    wr = len(wins) / len(trades) if trades else 0.0
    bh_ret = (
        (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]
    )

    exit_reasons: dict = {}
    for t in trades:
        exit_reasons[t["exit_reason"]] = exit_reasons.get(t["exit_reason"], 0) + 1

    return {
        "n_candles": len(df),
        "n_trades": len(trades),
        "return_total": float(ret),
        "sharpe_ratio": float(sharpe) if pd.notna(sharpe) else 0.0,
        "max_drawdown": float(dd) if pd.notna(dd) else 0.0,
        "win_rate": float(wr),
        "profit_factor": float(pf) if np.isfinite(pf) else float("inf"),
        "final_capital": float(capital),
        "bh_return": float(bh_ret),
        "alpha_vs_bh": float(ret - bh_ret),
        "exit_reasons": exit_reasons,
        "start": str(df.index[0].date()),
        "end": str(df.index[-1].date()),
    }


def _print_backtest_report(metrics: dict, symbol: str = "") -> None:
    """Imprime tabela de métricas no estilo do backtest standalone."""
    if not metrics:
        return
    ret = metrics["return_total"]
    bh_ret = metrics["bh_return"]
    print(f"\n{'─'*60}")
    print(f"{'MÉTRICA':<28} {'BOT':>10} {'BUY & HOLD':>12}")
    print(f"{'─'*60}")
    print(f"{'Retorno Total':<28} {ret:>+9.1%} {bh_ret:>+11.1%}")
    print(f"{'Sharpe Ratio':<28} {metrics['sharpe_ratio']:>10.3f} {'—':>12}")
    print(f"{'Max Drawdown':<28} {metrics['max_drawdown']:>+9.1%} {'—':>12}")
    print(f"{'Win Rate':<28} {metrics['win_rate']:>9.1%} {'—':>12}")
    pf = metrics["profit_factor"]
    pf_str = f"{pf:>10.3f}" if np.isfinite(pf) else f"{'inf':>10}"
    print(f"{'Profit Factor':<28} {pf_str} {'—':>12}")
    print(f"{'Nº de Trades':<28} {metrics['n_trades']:>10} {'—':>12}")
    print(f"{'Alpha vs B&H':<28} {metrics['alpha_vs_bh']:>+9.1%} {'—':>12}")
    print(f"{'Capital Final':<28} ${metrics['final_capital']:>9,.2f} {'—':>12}")
    print(f"{'─'*60}")
    print(f"Saídas: {metrics.get('exit_reasons', {})}")
    if symbol:
        print(f"{'='*60}\n")


def run_backtest_on_df(
    df_full: pd.DataFrame,
    metric_start: str,
    metric_end: str | None = None,
    params: dict | None = None,
    quiet: bool = False,
    symbol: str = "",
    data_source: str = "",
) -> dict:
    """
    Executa backtest sobre um DataFrame já carregado (inclui warm-up anterior).

    Sinais são calculados em df_full; métricas só entre metric_start e metric_end.
    """
    if df_full is None or len(df_full) < 50:
        return {}

    p = {**default_strategy_params(), **(params or {})}
    signals_full = compute_signals(
        df_full,
        st_period=p["st_period"],
        st_mult=p["st_mult"],
        rsi_period=p["rsi_period"],
        rsi_low=p["rsi_low"],
        rsi_high=p["rsi_high"],
        macd_fast=p["macd_fast"],
        macd_slow=p["macd_slow"],
        macd_sig=p["macd_sig"],
    )

    start_ts = pd.Timestamp(metric_start)
    if metric_end:
        end_ts = pd.Timestamp(metric_end)
        mask = (signals_full.index >= start_ts) & (signals_full.index <= end_ts)
    else:
        mask = signals_full.index >= start_ts

    df = df_full.loc[mask].copy()
    signals = signals_full.loc[mask].copy()

    if len(df) < 10:
        return {}

    metrics = simulate_strategy(df, signals)
    if not metrics:
        return {}

    metrics.update({
        "symbol": symbol,
        "data_source": data_source,
        "params": p,
        "metric_start": metric_start,
        "metric_end": metric_end or str(df.index[-1].date()),
    })

    if not quiet:
        _print_backtest_report(metrics, symbol=symbol)

    return metrics


def run_backtest(
    symbol: str,
    start: str,
    end: str | None = None,
    params: dict | None = None,
    quiet: bool = False,
) -> dict:
    """
    Executa backtest da estratégia Supertrend + RSI + MACD.

    ✅ Pré-aquecimento: busca WARMUP_DAYS candles extras antes de `start`
       para garantir que RSI, MACD e Supertrend estejam estabilizados.
    """
    if not quiet:
        print(f"\n{'='*60}")
        print(f"KRYPTON BACKTEST: {symbol}")
        print(f"Período: {start} → {end or 'hoje'}")
        print(f"{'='*60}")

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    warmup_str = (start_dt - timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")

    if not quiet:
        print(
            f"Baixando dados históricos (incl. {WARMUP_DAYS}d de aquecimento)...",
            flush=True,
        )

    df_full, data_source = get_ohlcv(symbol, warmup_str, end)

    if len(df_full) < 50:
        if not quiet:
            print(
                f"\n❌ Dados insuficientes ({len(df_full)} candles). "
                f"Verifique o símbolo e as datas."
            )
        return {}

    if not quiet:
        print(f"\nFonte usada: {data_source}")
        print(f"✓ {len(df_full)} candles carregados (aquecimento incluso).")
        print(f"  {df_full.index[0].date()} → {df_full.index[-1].date()}")

    # Pré-visualiza o tamanho da janela (sem aquecimento) antes do relatório
    start_ts = pd.Timestamp(start)
    if end:
        end_ts = pd.Timestamp(end)
        window = df_full.loc[(df_full.index >= start_ts) & (df_full.index <= end_ts)]
    else:
        window = df_full.loc[df_full.index >= start_ts]

    if len(window) < 10:
        if not quiet:
            print("❌ Período de backtest muito curto após remover aquecimento.")
        return {}

    if not quiet:
        print(
            f"\nPeríodo de backtest (sem aquecimento): "
            f"{window.index[0].date()} → {window.index[-1].date()} "
            f"({len(window)} candles)"
        )

    return run_backtest_on_df(
        df_full,
        metric_start=start,
        metric_end=end,
        params=params,
        quiet=quiet,
        symbol=symbol,
        data_source=data_source,
    )


def run_backtest_with_params(
    symbol: str,
    start: str,
    end: str | None,
    params: dict,
    quiet: bool = False,
) -> dict:
    """
    Executa backtest com parâmetros customizados da estratégia.

    params = {
        'st_period', 'st_mult', 'rsi_period', 'rsi_low', 'rsi_high',
        'macd_fast', 'macd_slow', 'macd_sig'
    }
    """
    return run_backtest(symbol, start, end, params=params, quiet=quiet)


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Krypton TradeBot — Backtest Standalone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python backtest.py --symbol SOLUSDT --start 2022-01-01 --end 2026-06-01
  python backtest.py --symbol BTCUSDT --start 2024-01-01
  python backtest.py  # SOLUSDT desde 2022-01-01
        """,
    )
    parser.add_argument(
        "--symbol", default="SOLUSDT",
        choices=["SOLUSDT", "BTCUSDT", "ETHUSDT", "BNBUSDT"],
        help="Par de trading (padrão: SOLUSDT)",
    )
    parser.add_argument(
        "--start", default="2022-01-01",
        help="Data de início YYYY-MM-DD (padrão: 2022-01-01)",
    )
    parser.add_argument(
        "--end", default=None,
        help="Data de fim YYYY-MM-DD (padrão: hoje)",
    )
    args = parser.parse_args()
    run_backtest(args.symbol, args.start, args.end)
