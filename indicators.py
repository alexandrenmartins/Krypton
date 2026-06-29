# indicators.py — Biblioteca de Indicadores Técnicos
# Krypton TradeBot | Estratégia: Supertrend + RSI + MACD Filter
#
# Indicadores implementados:
#   - RSI (método Wilder via EWM)
#   - MACD (EMA rápida / EMA lenta / linha de sinal)
#   - ATR (Average True Range, método Wilder)
#   - Supertrend (baseado em ATR)
#   - compute_signals() — integra os três e retorna +1, -1, 0

import pandas as pd
import numpy as np


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI padrão usando EMA (método Wilder).

    Parâmetros
    ----------
    series : pd.Series
        Série de preços de fechamento.
    period : int
        Período de suavização (padrão: 14).

    Retorna
    -------
    pd.Series com valores de RSI (0–100).
    """
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple:
    """
    MACD clássico (padrão Binance/TradingView).

    Retorna
    -------
    tuple: (macd_line, signal_line, histogram)
    """
    ema_fast    = series.ewm(span=fast, adjust=False).mean()
    ema_slow    = series.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average True Range (ATR) — suavização Wilder via EWM.

    True Range = max(H-L, |H-Cp|, |L-Cp|)
    """
    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def compute_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 7,
    multiplier: float = 3.0,
) -> tuple:
    """
    Supertrend Indicator.

    Parâmetros otimizados (grid search 2022-2026):
      period     = 7    → sensibilidade média-alta
      multiplier = 3.0  → bandas amplas = menos whipsaws

    Retorna
    -------
    tuple: (supertrend_line, direction)
      direction: pd.Series com +1 (bullish) ou -1 (bearish)
    """
    atr        = compute_atr(high, low, close, period)
    hl2        = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=close.index)
    direction  = pd.Series(0,      index=close.index, dtype=int)

    for i in range(1, len(close)):
        prev_st = supertrend.iloc[i - 1]

        # Upper band — nunca sobe se estava acima do close anterior
        ub = upper_band.iloc[i]
        if pd.notna(prev_st) and close.iloc[i - 1] <= prev_st:
            ub = min(ub, upper_band.iloc[i - 1])

        # Lower band — nunca cai se estava abaixo do close anterior
        lb = lower_band.iloc[i]
        if pd.notna(prev_st) and close.iloc[i - 1] >= prev_st:
            lb = max(lb, lower_band.iloc[i - 1])

        # Direção baseada no cruzamento com as bandas
        if close.iloc[i] > ub:
            direction.iloc[i]  = 1
            supertrend.iloc[i] = lb
        elif close.iloc[i] < lb:
            direction.iloc[i]  = -1
            supertrend.iloc[i] = ub
        else:
            direction.iloc[i]  = direction.iloc[i - 1]
            supertrend.iloc[i] = lb if direction.iloc[i] == 1 else ub

    return supertrend, direction


def compute_signals(
    df: pd.DataFrame,
    st_period: int   = 7,
    st_mult: float   = 3.0,
    rsi_period: int  = 14,
    rsi_low: float   = 40,
    rsi_high: float  = 70,
    macd_fast: int   = 12,
    macd_slow: int   = 26,
    macd_sig: int    = 9,
) -> pd.Series:
    """
    Gera sinais de trading combinando Supertrend + RSI + MACD.

    Confirmação tripla (todos os três filtros devem concordar):

    LONG  (+1):
      ① Supertrend bullish (direction == +1)
      ② RSI entre rsi_low (40) e rsi_high (70)   ← zona neutro-bullish
      ③ MACD line > Signal line                   ← momentum ascendente

    SHORT (-1):
      ① Supertrend bearish (direction == -1)
      ② RSI entre (100-rsi_high) e (100-rsi_low)  ← zona neutro-bearish (30–60)
      ③ MACD line < Signal line                   ← momentum descendente

    FLAT  (0): nenhuma condição satisfeita ou aguardando nova confirmação após reversão.

    Parâmetros
    ----------
    df : pd.DataFrame com colunas ['open','high','low','close','volume']

    Retorna
    -------
    pd.Series com valores +1, -1 ou 0.
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    rsi       = compute_rsi(close, rsi_period)
    macd_line, sig_line, _ = compute_macd(close, macd_fast, macd_slow, macd_sig)
    _, st_dir = compute_supertrend(high, low, close, st_period, st_mult)

    signals = pd.Series(0, index=df.index)
    current = 0  # posição atual: +1, -1 ou 0

    for i in range(len(df)):
        d  = st_dir.iloc[i]
        r  = rsi.iloc[i]
        ml = macd_line.iloc[i]
        sl = sig_line.iloc[i]

        # Aguarda dados suficientes para todos os indicadores
        if any(pd.isna(x) for x in [d, r, ml, sl]):
            signals.iloc[i] = current
            continue

        # Avalia condições de entrada
        long_ok  = (d == 1)  and (rsi_low  <= r <= rsi_high)        and (ml > sl)
        short_ok = (d == -1) and ((100 - rsi_high) <= r <= (100 - rsi_low)) and (ml < sl)

        if long_ok:
            current = 1
        elif short_ok:
            current = -1
        elif (d == 1 and current == -1) or (d == -1 and current == 1):
            # Reversão do Supertrend: sai da posição e aguarda nova confirmação
            current = 0

        signals.iloc[i] = current

    return signals
