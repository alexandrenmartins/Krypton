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
    PAIR_PARAMS,
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
    """
    Para que serve: Converte uma data em formato string para timestamp em milissegundos.
    O que faz: Transforma a string "YYYY-MM-DD" em milissegundos (formato exigido pela API Binance).
    Como faz: Usa datetime.strptime() para parsear a data, converte para timestamp Unix,
              e multiplica por 1000 para obter milissegundos.
    
    Args:
        value (str): Data no formato "YYYY-MM-DD"
    
    Returns:
        int: Timestamp em milissegundos
    """
    return int(datetime.strptime(value, "%Y-%m-%d").timestamp() * 1000)


def _klines_to_df(klines: list) -> pd.DataFrame:
    """
    Para que serve: Converter dados brutos de candles (klines) da API Binance em um DataFrame limpo.
    O que faz: Transforma a resposta JSON da Binance em um DataFrame Pandas com colunas padronizadas.
    Como faz: 
        1. Valida se há dados na lista
        2. Cria DataFrame com todas as colunas retornadas pela Binance
        3. Converte open_time para datetime e o define como índice
        4. Converte valores numéricos para float
        5. Retorna apenas as colunas essenciais: open, high, low, close, volume
    
    Args:
        klines (list): Lista de candles brutos da API Binance
    
    Returns:
        pd.DataFrame: DataFrame com OHLCV limpo e indexado por data
    """
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
    Para que serve: Baixar dados históricos de uma criptomoeda da API Binance em lotes.
    O que faz: Realiza múltiplas requisições à API Binance para coletar 1000 candles por vez
               até acumular todo o período solicitado.
    Como faz:
        1. Valida/mapeia o símbolo se necessário (ex: SOLUSDT → SOLUSD para Binance US)
        2. Converte datas de entrada para timestamps em milissegundos
        3. Loop: faz requisição de 1000 candles até atingir a data final ou sem mais dados
        4. Adiciona pausa (rate limiting) entre requisições para não sobrecarregar a API
        5. Converte todos os klines coletados em um DataFrame limpo
    
    Args:
        symbol (str): Símbolo do ativo (ex: "SOLUSDT")
        start_str (str): Data inicial "YYYY-MM-DD"
        end_str (str | None): Data final "YYYY-MM-DD" (None = até hoje)
        base_url (str): URL base da API Binance
        symbol_map (dict | None): Mapa para traduzir símbolos (ex: SOLUSDT → SOLUSD)
    
    Returns:
        pd.DataFrame: DataFrame OHLCV com todos os candles coletados
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
    Para que serve: Baixar dados históricos via Yahoo Finance como alternativa/fallback.
    O que faz: Utiliza a biblioteca yfinance para obter dados de criptomoedas quando Binance
               não está disponível ou tem dados limitados.
    Como faz:
        1. Mapeia o símbolo para o formato Yahoo (ex: SOLUSDT → SOL-USD)
        2. Faz download usando yfinance.download() com intervalo de 1 dia
        3. Renomeia colunas para manter padrão (Open→open, Close→close, etc)
        4. Valida se todos os dados essenciais estão presentes
        5. Remove linhas com valores faltantes (NaN) e retorna DataFrame limpo
    
    Args:
        symbol (str): Símbolo do ativo (ex: "SOLUSDT")
        start_str (str): Data inicial "YYYY-MM-DD"
        end_str (str | None): Data final "YYYY-MM-DD" (None = até hoje)
    
    Returns:
        pd.DataFrame: DataFrame OHLCV ou DataFrame vazio se falhar
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
    Para que serve: Obter dados OHLCV de múltiplas fontes automaticamente.
    O que faz: Tenta baixar dados em ordem de preferência (Binance Global → Binance US → Yahoo)
               e retorna a fonte que conseguiu mais candles.
    Como faz:
        1. Define lista de sources (funções que baixam dados de cada fonte)
        2. Itera por cada fonte, tentando carregar dados
        3. Se uma fonte retorna ≥50 candles, retorna imediatamente (ótima qualidade)
        4. Caso contrário, guarda a com mais candles e continua tentando
        5. Ao final, retorna o DataFrame com mais candles e a fonte usada
    
    Args:
        symbol (str): Símbolo do ativo (ex: "SOLUSDT")
        start_str (str): Data inicial "YYYY-MM-DD"
        end_str (str | None): Data final "YYYY-MM-DD" (None = até hoje)
    
    Returns:
        tuple[pd.DataFrame, str]: (DataFrame OHLCV, nome da fonte usada)
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
    """
    Para que serve: Retornar os parâmetros padrão da estratégia (baseline).
    O que faz: Coleta todos os parâmetros globais da estratégia Supertrend+RSI+MACD
               do arquivo config.py e os retorna em um dicionário.
    Como faz: Monta um dict com todos os parâmetros dos indicadores técnicos
              lendo as constantes importadas de config.py.
    
    Returns:
        dict: Dicionário com chaves: st_period, st_mult, rsi_period, rsi_low, rsi_high,
              macd_fast, macd_slow, macd_sig
    """
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
    Para que serve: Simular a execução da estratégia de trading em um período histórico.
    O que faz: Itera candle a candle, entra em posições quando há sinal, gerencia stop loss/
               take profit e calcula métricas de performance (retorno, Sharpe, drawdown, etc).
    Como faz:
        1. Para cada candle, verifica se há sinal (1=long, -1=short, 0=sem posição)
        2. Se em posição: verifica se atingiu SL, TP ou sinal de saída
        3. Se fechou posição: calcula P&L, deduz fees e atualiza capital
        4. Se sem posição e novo sinal: calcula tamanho da posição baseado em risco (ATR)
        5. Mantém histórico de equity para calcular Sharpe, drawdown, win rate, profit factor
        6. Compara retorno com buy & hold do período
    
    Args:
        df (pd.DataFrame): DataFrame OHLCV com dados do período
        signals (pd.Series): Série com sinais da estratégia (-1, 0 ou 1)
    
    Returns:
        dict: Métricas incluindo: n_trades, return_total, sharpe_ratio, max_drawdown,
              win_rate, profit_factor, final_capital, bh_return, alpha_vs_bh, etc
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
    """
    Para que serve: Exibir um relatório formatado das métricas do backtest.
    O que faz: Imprime uma tabela comparativa entre o bot e buy & hold com todas
               as métricas principais de performance.
    Como faz:
        1. Valida se há métricas para exibir
        2. Cria tabela com delimitadores (─ e =)
        3. Exibe cada métrica em colunas alinhadas: Bot vs Buy & Hold
        4. Formata números (percentuais, decimais, inteiros) com cores apropriadas
        5. Mostra razões de saída de trades (SL, TP, Sinal)
    
    Args:
        metrics (dict): Dicionário com as métricas do backtest
        symbol (str): Símbolo do ativo (opcional, para cabeçalho)
    
    Returns:
        None (apenas imprime no console)
    """
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
    Para que serve: Executar o backtest sobre um DataFrame já carregado com aquecimento.
    O que faz: Calcula os sinais sobre todo o DataFrame, depois filtra apenas o período
               solicitado para contabilizar as métricas (descarta o aquecimento).
    Como faz:
        1. Valida se há dados suficientes
        2. Resolve parâmetros (usa passados ou defaults)
        3. Calcula sinais de estratégia sobre TODO o DataFrame (incluindo aquecimento)
        4. Filtra apenas candles entre metric_start e metric_end
        5. Simula a estratégia sobre o período filtrado
        6. Imprime relatório (se não estiver em modo quiet)
        7. Retorna dicionário com métricas enriquecidas
    
    Args:
        df_full (pd.DataFrame): DataFrame com histórico completo (incl. aquecimento)
        metric_start (str): Data inicial do período de métrica "YYYY-MM-DD"
        metric_end (str | None): Data final do período de métrica (None = até o fim)
        params (dict | None): Parâmetros customizados da estratégia
        quiet (bool): Se True, não imprime relatório
        symbol (str): Símbolo do ativo (para relatório)
        data_source (str): Fonte de dados usada (para relatório)
    
    Returns:
        dict: Métricas do backtest com campos: symbol, data_source, params, etc
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
    Para que serve: Executar um backtest completo da estratégia Supertrend+RSI+MACD.
    O que faz: Orquestra todo o processo: busca dados com aquecimento, calcula sinais
               sobre o período inteiro (com warm-up), filtra para o período solicitado
               e retorna as métricas.
    Como faz:
        1. Resolve parâmetros (usa PAIR_PARAMS otimizados se disponíveis)
        2. Calcula data de início do aquecimento (WARMUP_DAYS antes de start)
        3. Baixa dados históricos de múltiplas fontes
        4. Valida se há dados suficientes
        5. Executa backtest sobre os dados com aquecimento
        6. Exibe informações de progresso (se não quiet)
    
    Args:
        symbol (str): Símbolo do ativo (ex: "SOLUSDT")
        start (str): Data inicial "YYYY-MM-DD"
        end (str | None): Data final "YYYY-MM-DD" (None = até hoje)
        params (dict | None): Parâmetros customizados (None = usa PAIR_PARAMS ou defaults)
        quiet (bool): Se True, suprime prints
    
    Returns:
        dict: Métricas completas do backtest ou {} se falhar
    """
    resolved = _resolve_params(symbol, params)

    if not quiet:
        print(f"\n{'='*60}")
        print(f"KRYPTON BACKTEST: {symbol}")
        print(f"Período: {start} → {end or 'hoje'}")
        print(f"{'='*60}")
        if symbol in PAIR_PARAMS and params is None:
            print(f"Usando parâmetros otimizados (Walk-Forward) para {symbol}")

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
        params=resolved,
        quiet=quiet,
        symbol=symbol,
        data_source=data_source,
    )


def _resolve_params(symbol: str, params: dict | None = None) -> dict:
    """
    Para que serve: Resolver qual conjunto de parâmetros usar para o backtest.
    O que faz: Prioriza parâmetros passados explicitamente, depois tenta PAIR_PARAMS
               otimizados do config, e finalmente usa os defaults globais.
    Como faz:
        1. Se params foi passado, retorna imediatamente (maior prioridade)
        2. Busca parâmetros específicos do ativo em PAIR_PARAMS
        3. Para cada parâmetro, tenta obter do PAIR_PARAMS, senão usa default
    
    Args:
        symbol (str): Símbolo do ativo
        params (dict | None): Parâmetros explícitos (maior prioridade)
    
    Returns:
        dict: Dicionário final com todos os parâmetros necessários
    """
    if params is not None:
        return params
    pp = PAIR_PARAMS.get(symbol, {})
    return {
        "st_period":  pp.get("st_period",  SUPERTREND_PERIOD),
        "st_mult":    pp.get("st_mult",    SUPERTREND_MULTIPLIER),
        "rsi_period": pp.get("rsi_period", RSI_PERIOD),
        "rsi_low":    pp.get("rsi_low",    RSI_LOW),
        "rsi_high":   pp.get("rsi_high",   RSI_HIGH),
        "macd_fast":  pp.get("macd_fast",  MACD_FAST),
        "macd_slow":  pp.get("macd_slow",  MACD_SLOW),
        "macd_sig":   pp.get("macd_sig",   MACD_SIGNAL),
    }


def run_backtest_with_params(
    symbol: str,
    start: str,
    end: str | None,
    params: dict,
    quiet: bool = False,
) -> dict:
    """
    Para que serve: Executar backtest com parâmetros de estratégia customizados.
    O que faz: Wrapper que chama run_backtest passando parâmetros explícitos.
    Como faz: Simplesmente delega para run_backtest com os parâmetros fornecidos.
    
    Args:
        symbol (str): Símbolo do ativo
        start (str): Data inicial "YYYY-MM-DD"
        end (str | None): Data final "YYYY-MM-DD"
        params (dict): Parâmetros da estratégia:
                       - st_period: Período do Supertrend
                       - st_mult: Multiplicador do Supertrend
                       - rsi_period: Período do RSI
                       - rsi_low: Limite inferior do RSI
                       - rsi_high: Limite superior do RSI
                       - macd_fast: Período fast do MACD
                       - macd_slow: Período slow do MACD
                       - macd_sig: Período da signal do MACD
        quiet (bool): Se True, suprime output
    
    Returns:
        dict: Métricas do backtest
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
