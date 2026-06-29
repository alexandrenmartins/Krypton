# backtest.py — Backtesting Standalone com Dados do Yahoo Finance
# Krypton TradeBot | Estratégia: Supertrend + RSI + MACD Filter
#
# Uso:
#   python backtest.py --symbol SOLUSDT --start 2022-01-01 --end 2026-06-01
#   python backtest.py --symbol BTCUSDT --start 2024-01-01
#   python backtest.py  # usa defaults (SOLUSDT, 2022-01-01)
#
# Resultados do backtest original (grid search 1.612 dias):
#   SOLUSDT: +37,7% | Sharpe 0,932 | MaxDD -5,0% | WR 54,0% | PF 1,748

import argparse
from datetime import date

import numpy as np
import pandas as pd
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
    SUPERTREND_MULTIPLIER,
    SUPERTREND_PERIOD,
)
from indicators import compute_atr, compute_signals

# Mapeamento de símbolo Binance → Yahoo Finance
SYMBOL_MAP = {
    "SOLUSDT" : "SOL-USD",
    "BTCUSDT" : "BTC-USD",
    "ETHUSDT" : "ETH-USD",
    "BNBUSDT" : "BNB-USD",
}


def run_backtest(symbol: str, start: str, end: str | None = None) -> dict:
    """
    Executa backtest standalone da estratégia Supertrend + RSI + MACD.

    Simula execução diária com:
      - Position sizing ATR-based (1% de risco por trade)
      - Stop Loss: 2× ATR(14)
      - Take Profit: 3× ATR(14)
      - Taxas: 0,1% por lado
      - Halt automático em max drawdown (-20%)

    Retorna
    -------
    dict com todas as métricas de performance.
    """
    yf_sym = SYMBOL_MAP.get(symbol.upper(), symbol)

    print(f"\n{'='*60}")
    print(f"KRYPTON BACKTEST: {symbol} ({yf_sym})")
    print(f"Período: {start} → {end or 'hoje'}")
    print(f"{'='*60}")
    print("Baixando dados históricos...", end=" ", flush=True)

    df = yf.download(
        yf_sym,
        start        = start,
        end          = end,
        interval     = "1d",
        auto_adjust  = True,
        progress     = False,
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].dropna()

    if len(df) < 50:
        print(f"❌ Dados insuficientes ({len(df)} candles). Verifique o símbolo e as datas.")
        return {}

    print(f"✓ {len(df)} candles carregados.")

    # Calcula sinais da estratégia
    signals = compute_signals(
        df,
        st_period  = SUPERTREND_PERIOD,
        st_mult    = SUPERTREND_MULTIPLIER,
        rsi_period = RSI_PERIOD,
        rsi_low    = RSI_LOW,
        rsi_high   = RSI_HIGH,
        macd_fast  = MACD_FAST,
        macd_slow  = MACD_SLOW,
        macd_sig   = MACD_SIGNAL,
    )

    # ─── Simulação de Trading ─────────────────────────────────────────────────
    capital  = 10_000.0
    peak     = capital
    equity   = [capital]
    trades   = []
    pos      = 0      # posição atual: +1, -1 ou 0
    entry    = 0.0
    pos_size = 0.0

    for i in range(1, len(df)):
        price = df["close"].iloc[i]
        sig   = signals.iloc[i]
        atr_v = compute_atr(df["high"], df["low"], df["close"]).iloc[i]

        # Verificar SL/TP/Saída por sinal para posição aberta
        if pos != 0:
            sl      = entry - 2 * atr_v if pos == 1 else entry + 2 * atr_v
            tp      = entry + 3 * atr_v if pos == 1 else entry - 3 * atr_v
            hit_sl  = (pos == 1 and price <= sl)  or (pos == -1 and price >= sl)
            hit_tp  = (pos == 1 and price >= tp)  or (pos == -1 and price <= tp)
            exit_sg = (pos != sig and sig != 0)   # reversão de sinal

            if hit_sl or hit_tp or exit_sg:
                exit_price = price
                fee        = pos_size * exit_price * FEE_RATE
                pnl        = (
                    pos_size * (exit_price - entry) if pos == 1
                    else pos_size * (entry - exit_price)
                ) - fee
                capital += pnl
                trades.append({
                    "pnl"        : pnl,
                    "exit_reason": "SL" if hit_sl else "TP" if hit_tp else "Sig",
                    "pnl_pct"    : pnl / (pos_size * entry) * 100,
                })
                pos  = 0
                peak = max(peak, capital)

        # Halt por max drawdown
        if peak > 0 and (peak - capital) / peak >= MAX_DRAWDOWN_PCT:
            equity.append(capital)
            continue

        # Abrir nova posição se há sinal
        if pos == 0 and sig != 0 and pd.notna(atr_v) and atr_v > 0:
            entry    = price * (1.0005 if sig == 1 else 0.9995)  # slippage estimado
            pos_size = (capital * RISK_PER_TRADE) / (atr_v * 2)
            capital -= pos_size * entry * FEE_RATE  # taxa de entrada
            pos      = int(sig)

        equity.append(capital)

    # ─── Cálculo de Métricas ──────────────────────────────────────────────────
    total_return = date_range = None
    eq     = pd.Series(equity, index=df.index[:len(equity)])
    ret    = (capital - 10_000) / 10_000
    rets   = eq.pct_change().dropna()
    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0
    dd     = ((eq - eq.cummax()) / eq.cummax()).min()

    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    pf     = (
        sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))
        if losses else float("inf")
    )
    wr     = len(wins) / len(trades) if trades else 0

    # Buy & Hold para comparação
    bh_ret = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]

    results = {
        "symbol"        : symbol,
        "start"         : start,
        "end"           : end or str(date.today()),
        "n_candles"     : len(df),
        "n_trades"      : len(trades),
        "return_total"  : ret,
        "sharpe_ratio"  : sharpe,
        "max_drawdown"  : dd,
        "win_rate"      : wr,
        "profit_factor" : pf,
        "final_capital" : capital,
        "bh_return"     : bh_ret,
        "alpha_vs_bh"   : ret - bh_ret,
    }

    # ─── Impressão dos Resultados ─────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"{'MÉTRICA':<25} {'BOT':>12} {'BUY & HOLD':>12}")
    print(f"{'─'*60}")
    print(f"{'Retorno Total':<25} {ret:>+11.1%} {bh_ret:>+11.1%}")
    print(f"{'Sharpe Ratio':<25} {sharpe:>12.3f} {'—':>12}")
    print(f"{'Max Drawdown':<25} {dd:>+11.1%} {'—':>12}")
    print(f"{'Win Rate':<25} {wr:>11.1%} {'—':>12}")
    print(f"{'Profit Factor':<25} {pf:>12.3f} {'—':>12}")
    print(f"{'Nº de Trades':<25} {len(trades):>12} {'—':>12}")
    print(f"{'Alpha vs B&H':<25} {ret - bh_ret:>+11.1%} {'—':>12}")
    print(f"{'Capital Final':<25} ${capital:>10,.2f} {'—':>12}")
    print(f"{'─'*60}")

    exit_reasons = {}
    for t in trades:
        exit_reasons[t["exit_reason"]] = exit_reasons.get(t["exit_reason"], 0) + 1
    print(f"\nSaídas: {exit_reasons}")
    print(f"{'='*60}\n")

    return results


# ─── Entry Point ──────────────────────────────────────────────────────────────
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
    parser.add_argument("--symbol", default="SOLUSDT",
                        choices=["SOLUSDT", "BTCUSDT", "ETHUSDT", "BNBUSDT"],
                        help="Par de trading (padrão: SOLUSDT)")
    parser.add_argument("--start",  default="2022-01-01",
                        help="Data de início (YYYY-MM-DD, padrão: 2022-01-01)")
    parser.add_argument("--end",    default=None,
                        help="Data de fim (YYYY-MM-DD, padrão: hoje)")
    args = parser.parse_args()
    run_backtest(args.symbol, args.start, args.end)
