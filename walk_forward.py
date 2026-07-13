# walk_forward.py — Walk-Forward Optimization para Krypton TradeBot
# Estratégia: Supertrend + RSI + MACD Filter
#
# Divide dados em treino (70%) e validação (30%), otimiza parâmetros
# no treino e valida se generalizam na validação.
#
# Uso:
#   python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --grid reduced
#   python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --grid full
#   python walk_forward.py --all --start 2022-01-01 --grid reduced
#   python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --metric profit_factor

import argparse
import itertools
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

from backtest import (
    default_strategy_params,
    get_ohlcv,
    run_backtest_on_df,
    WARMUP_DAYS,
    _print_backtest_report,
)
from config import OPTIMIZATION


# ── Grid Generation ────────────────────────────────────────────────────────────

def generate_param_grid(grid_type: str = "reduced") -> list[dict]:
    """
    Gera lista de combinações de parâmetros a partir do grid do config.py.

    Parametros
    ----------
    grid_type : str
        'reduced' para grid rápido (~243 combinações)
        'full' para grid completo (~20k combinações)

    Retorna
    -------
    list[dict]: Lista de dicts com combinações de parâmetros.
    """
    grid_key = f"param_grid_{grid_type}"
    if grid_key not in OPTIMIZATION:
        print(f"❌ Grid '{grid_type}' não encontrado no config.py.")
        print(f"   Chaves disponíveis: {[k for k in OPTIMIZATION if k.startswith('param_grid')]}")
        sys.exit(1)

    param_grid = OPTIMIZATION[grid_key]
    keys = list(param_grid.keys())
    values = list(param_grid.values())

    combinations = list(itertools.product(*values))
    param_list = [dict(zip(keys, combo)) for combo in combinations]

    print(f"  Grid '{grid_type}': {len(param_list)} combinações de parâmetros")
    return param_list


# ── Optimization Engine ────────────────────────────────────────────────────────

def run_optimization(
    df_full: pd.DataFrame,
    start_date: str,
    end_date: str,
    param_list: list[dict],
    metric: str = "sharpe_ratio",
    quiet: bool = False,
) -> dict:
    """
    Executa Grid Search no período de treino.

    Parametros
    ----------
    df_full : pd.DataFrame
        DataFrame com dados completos (inclui warm-up anterior ao start_date).
    start_date : str
        Data de início do período de otimização.
    end_date : str
        Data de fim do período de otimização.
    param_list : list[dict]
        Lista de combinações de parâmetros.
    metric : str
        Métrica para selecionar o melhor resultado.
    quiet : bool
        Se True, suprime prints de progresso.

    Retorna
    -------
    dict com melhor_params, best_score, all_results.
    """
    total = len(param_list)
    best_score = -float("inf")
    best_params = None
    all_results = []

    if not quiet:
        print(f"\n  Otimizando {total} combinações...")
        print(f"  Métrica: {metric}")
        print(f"  Período: {start_date} → {end_date}")
        start_time = time.time()

    for i, params in enumerate(param_list):
        result = run_backtest_on_df(
            df_full,
            metric_start=start_date,
            metric_end=end_date,
            params=params,
            quiet=True,
        )

        if result:
            score = result.get(metric, -float("inf"))
            if score is None or np.isnan(score):
                score = -float("inf")
            result["score"] = score
            all_results.append(result)

            if score > best_score:
                best_score = score
                best_params = params

        if not quiet and (i + 1) % max(1, total // 10) == 0:
            elapsed = time.time() - start_time
            pct = (i + 1) / total * 100
            eta = (elapsed / (i + 1)) * (total - i - 1) if i > 0 else 0
            print(f"    {pct:5.1f}% ({i+1}/{total}) | "
                  f"Melhor {metric}: {best_score:.4f} | "
                  f"ETA: {eta:.0f}s")

    if not quiet:
        elapsed = time.time() - start_time
        print(f"  ✓ Concluído em {elapsed:.1f}s")

    if best_params is None:
        print("  ⚠️  Nenhum resultado válido encontrado.")
        return {"best_params": None, "best_score": None, "all_results": []}

    return {
        "best_params": best_params,
        "best_score": best_score,
        "all_results": all_results,
    }


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_params(
    df_full: pd.DataFrame,
    start_date: str,
    end_date: str,
    params: dict,
) -> dict:
    """
    Valida parâmetros no período de validação.

    Retorna
    -------
    dict com métricas da validação.
    """
    result = run_backtest_on_df(
        df_full,
        metric_start=start_date,
        metric_end=end_date,
        params=params,
        quiet=True,
    )
    return result


def check_acceptance(val_result: dict) -> tuple[bool, list[str]]:
    """
    Verifica se validação atende critérios de aceitação do config.py.

    Retorna
    -------
    tuple: (aprovado, lista de motivos de rejeição)
    """
    if not val_result:
        return False, ["Resultado de validação vazio"]

    acceptance = OPTIMIZATION.get("acceptance", {})
    reasons = []

    sharpe = val_result.get("sharpe_ratio", 0)
    if sharpe < acceptance.get("min_sharpe", 0.3):
        reasons.append(f"Sharpe {sharpe:.3f} < {acceptance['min_sharpe']}")

    dd = abs(val_result.get("max_drawdown", 0))
    if dd > acceptance.get("max_drawdown_abs", 0.15):
        reasons.append(f"|Drawdown| {dd:.1%} > {acceptance['max_drawdown_abs']:.0%}")

    wr = val_result.get("win_rate", 0)
    if wr < acceptance.get("min_win_rate", 0.45):
        reasons.append(f"Win Rate {wr:.1%} < {acceptance['min_win_rate']:.0%}")

    pf = val_result.get("profit_factor", 0)
    if pf < acceptance.get("min_profit_factor", 1.2):
        reasons.append(f"Profit Factor {pf:.3f} < {acceptance['min_profit_factor']}")

    ret = val_result.get("return_total", 0)
    if ret < acceptance.get("min_return", 0.0):
        reasons.append(f"Retorno {ret:.1%} < {acceptance['min_return']:.0%}")

    return len(reasons) == 0, reasons


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(
    symbol: str,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    train_result: dict,
    val_result: dict,
    best_params: dict,
    current_params: dict,
    current_result: dict,
    approved: bool,
    rejection_reasons: list[str],
    metric: str,
    grid_type: str,
) -> None:
    """Exibe relatório completo da otimização Walk-Forward."""

    print(f"\n{'='*68}")
    print(f"  WALK-FORWARD OPTIMIZATION: {symbol}")
    print(f"{'='*68}")

    # Períodos
    try:
        train_days = (pd.Timestamp(train_end) - pd.Timestamp(train_start)).days
        val_days = (pd.Timestamp(val_end) - pd.Timestamp(val_start)).days
    except Exception:
        train_days = "?"
        val_days = "?"

    print(f"\n  Período de Treino:     {train_start} → {train_end} ({train_days} dias)")
    print(f"  Período de Validação:  {val_start} → {val_end} ({val_days} dias)")
    print(f"  Grid: {grid_type} | Métrica: {metric}")

    # Parâmetros otimizados
    print(f"\n  {'─'*64}")
    print(f"  PARÂMETROS OTIMIZADOS:")
    print(f"  {'─'*64}")
    print(f"    Supertrend: period={best_params.get('st_period')}, "
          f"multiplier={best_params.get('st_mult')}")
    print(f"    RSI:        period={best_params.get('rsi_period')}, "
          f"low={best_params.get('rsi_low')}, high={best_params.get('rsi_high')}")
    print(f"    MACD:       fast={best_params.get('macd_fast')}, "
          f"slow={best_params.get('macd_slow')}, signal={best_params.get('macd_sig')}")

    # Resultados no treino
    if train_result:
        print(f"\n  {'─'*64}")
        print(f"  RESULTADOS NO TREINO:")
        print(f"  {'─'*64}")
        print(f"    Sharpe Ratio:   {train_result.get('sharpe_ratio', 0):>8.3f}")
        print(f"    Retorno Total:  {train_result.get('return_total', 0):>+7.1%}")
        print(f"    Max Drawdown:   {train_result.get('max_drawdown', 0):>+7.1%}")
        print(f"    Win Rate:       {train_result.get('win_rate', 0):>7.1%}")
        pf = train_result.get('profit_factor', 0)
        pf_str = f"{pf:.3f}" if np.isfinite(pf) else "inf"
        print(f"    Profit Factor:  {pf_str:>8}")
        print(f"    Nº de Trades:   {train_result.get('n_trades', 0):>8}")

    # Resultados na validação
    if val_result:
        print(f"\n  {'─'*64}")
        print(f"  RESULTADOS NA VALIDAÇÃO:")
        print(f"  {'─'*64}")
        print(f"    Sharpe Ratio:   {val_result.get('sharpe_ratio', 0):>8.3f}")
        print(f"    Retorno Total:  {val_result.get('return_total', 0):>+7.1%}")
        print(f"    Max Drawdown:   {val_result.get('max_drawdown', 0):>+7.1%}")
        print(f"    Win Rate:       {val_result.get('win_rate', 0):>7.1%}")
        pf = val_result.get('profit_factor', 0)
        pf_str = f"{pf:.3f}" if np.isfinite(pf) else "inf"
        print(f"    Profit Factor:  {pf_str:>8}")
        print(f"    Nº de Trades:   {val_result.get('n_trades', 0):>8}")

    # Comparação com configuração atual
    if current_result and val_result:
        print(f"\n  {'─'*64}")
        print(f"  COMPARAÇÃO: Config Atual vs Otimizado (Validação)")
        print(f"  {'─'*64}")
        print(f"  {'Métrica':<20} {'Atual':>10} {'Otimizado':>10} {'Δ':>10}")
        print(f"  {'─'*64}")

        comparisons = [
            ("Sharpe Ratio", "sharpe_ratio", ".3f", False),
            ("Retorno Total", "return_total", ".1%", True),
            ("Max Drawdown", "max_drawdown", ".1%", True),
            ("Win Rate", "win_rate", ".1%", False),
        ]

        for label, key, fmt, is_pct in comparisons:
            curr_val = current_result.get(key, 0)
            opt_val = val_result.get(key, 0)
            if is_pct:
                delta = opt_val - curr_val
                print(f"  {label:<20} {curr_val:>+9{fmt}} {opt_val:>+9{fmt}} {delta:>+9.1%}")
            else:
                delta = opt_val - curr_val
                pct_change = (delta / abs(curr_val) * 100) if curr_val != 0 else 0
                print(f"  {label:<20} {curr_val:>9{fmt}} {opt_val:>9{fmt}} {pct_change:>+8.1f}%")

        pf_curr = current_result.get('profit_factor', 0)
        pf_opt = val_result.get('profit_factor', 0)
        pf_curr_str = f"{pf_curr:.3f}" if np.isfinite(pf_curr) else "inf"
        pf_opt_str = f"{pf_opt:.3f}" if np.isfinite(pf_opt) else "inf"
        print(f"  {'Profit Factor':<20} {pf_curr_str:>10} {pf_opt_str:>10}")

    # Veredicto
    print(f"\n  {'─'*64}")
    if approved:
        print(f"  RECOMENDAÇÃO: ✅ APROVADO")
        print(f"  Parâmetros otimizados generalizam bem (treino ≈ validação)")
    else:
        print(f"  RECOMENDAÇÃO: ❌ REJEITADO")
        print(f"  Motivos:")
        for reason in rejection_reasons:
            print(f"    • {reason}")

    print(f"  {'─'*64}")

    # Parâmetros para copiar ao config.py
    if approved:
        print(f"\n  Para usar os parâmetros otimizados, copie para config.py:")
        print(f"  SUPERTREND_PERIOD     = {best_params.get('st_period')}")
        print(f"  SUPERTREND_MULTIPLIER = {best_params.get('st_mult')}")
        print(f"  RSI_PERIOD            = {best_params.get('rsi_period')}")
        print(f"  RSI_LOW               = {best_params.get('rsi_low')}")
        print(f"  RSI_HIGH              = {best_params.get('rsi_high')}")
        print(f"  MACD_FAST             = {best_params.get('macd_fast')}")
        print(f"  MACD_SLOW             = {best_params.get('macd_slow')}")
        print(f"  MACD_SIGNAL           = {best_params.get('macd_sig')}")

    print(f"\n{'='*68}\n")


# ── Main Flow ──────────────────────────────────────────────────────────────────

def walk_forward_optimize(
    symbol: str,
    start: str,
    end: str | None = None,
    grid_type: str = "reduced",
    metric: str | None = None,
) -> dict:
    """
    Executa otimização Walk-Forward completa para um par.

    Retorna
    -------
    dict com todos os resultados e metadados.
    """
    if metric is None:
        metric = OPTIMIZATION.get("optimization_metric", "sharpe_ratio")

    print(f"\n{'='*68}")
    print(f"  WALK-FORWARD OPTIMIZATION: {symbol}")
    print(f"{'='*68}")

    # 1. Carregar dados históricos (com warm-up)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    warmup_str = (start_dt - pd.Timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")

    print(f"\n  Carregando dados históricos...")
    print(f"  (incluindo {WARMUP_DAYS} dias de aquecimento antes de {start})")

    df_full, data_source = get_ohlcv(symbol, warmup_str, end)

    if len(df_full) < 100:
        print(f"  ❌ Dados insuficientes ({len(df_full)} candles).")
        return {}

    print(f"  ✓ {len(df_full)} candles carregados ({data_source})")
    print(f"    {df_full.index[0].date()} → {df_full.index[-1].date()}")

    # 2. Dividir treino (70%) e validação (30%)
    end_str = end or str(df_full.index[-1].date())
    end_dt = pd.Timestamp(end_str)
    start_ts = pd.Timestamp(start)

    total_days = (end_dt - start_ts).days
    train_days = int(total_days * OPTIMIZATION["train_ratio"])
    val_days = total_days - train_days

    train_end_ts = start_ts + pd.Timedelta(days=train_days)
    val_start_str = train_end_ts.strftime("%Y-%m-%d")
    val_end_str = end_str

    print(f"\n  Divisão de dados:")
    print(f"    Treino:     {start} → {val_start_str} ({train_days} dias)")
    print(f"    Validação:  {val_start_str} → {end_str} ({val_days} dias)")

    # 3. Gerar grid de parâmetros
    print(f"\n  Preparando grid de parâmetros...")
    param_list = generate_param_grid(grid_type)

    # 4. Otimizar no treino
    opt_result = run_optimization(
        df_full,
        start_date=start,
        end_date=val_start_str,
        param_list=param_list,
        metric=metric,
    )

    if opt_result["best_params"] is None:
        print("  ❌ Otimização falhou: nenhum resultado válido no treino.")
        return {}

    best_params = opt_result["best_params"]
    train_result = run_backtest_on_df(
        df_full,
        metric_start=start,
        metric_end=val_start_str,
        params=best_params,
        quiet=True,
    )

    print(f"\n  Melhor combinação encontrada no treino:")
    print(f"    {metric}: {opt_result['best_score']:.4f}")
    print(f"    Params: {best_params}")

    # 5. Validar na validação
    print(f"\n  Validando parâmetros no período de validação...")
    val_result = validate_params(df_full, val_start_str, val_end_str, best_params)

    if not val_result:
        print("  ❌ Validação falhou: sem dados suficientes no período.")
        return {}

    print(f"  ✓ Validação concluída")

    # 6. Verificar critérios de aceitação
    approved, rejection_reasons = check_acceptance(val_result)

    # 7. Resultado com configuração atual
    print(f"\n  Executando backtest com configuração atual (baseline)...")
    current_params = default_strategy_params()
    current_result = run_backtest_on_df(
        df_full,
        metric_start=start,
        metric_end=val_start_str,
        params=current_params,
        quiet=True,
    )
    # Validação da config atual
    current_val_result = run_backtest_on_df(
        df_full,
        metric_start=val_start_str,
        metric_end=val_end_str,
        params=current_params,
        quiet=True,
    )

    # 8. Gerar relatório completo
    print_report(
        symbol=symbol,
        train_start=start,
        train_end=val_start_str,
        train_result=train_result,
        val_start=val_start_str,
        val_end=val_end_str,
        val_result=val_result,
        best_params=best_params,
        current_params=current_params,
        current_result=current_val_result,
        approved=approved,
        rejection_reasons=rejection_reasons,
        metric=metric,
        grid_type=grid_type,
    )

    return {
        "symbol": symbol,
        "best_params": best_params,
        "train_result": train_result,
        "val_result": val_result,
        "current_result": current_val_result,
        "approved": approved,
        "rejection_reasons": rejection_reasons,
    }


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Krypton TradeBot — Walk-Forward Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --grid reduced
  python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --grid full
  python walk_forward.py --all --start 2022-01-01 --grid reduced
  python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --metric profit_factor
        """,
    )
    parser.add_argument(
        "--symbol",
        choices=["SOLUSDT", "BTCUSDT", "ETHUSDT", "BNBUSDT"],
        help="Par de trading (singular)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Otimizar todos os pares configurados",
    )
    parser.add_argument(
        "--start",
        default="2022-01-01",
        help="Data de início YYYY-MM-DD (padrão: 2022-01-01)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Data de fim YYYY-MM-DD (padrão: hoje)",
    )
    parser.add_argument(
        "--grid",
        choices=["reduced", "full"],
        default="reduced",
        help="Grid de parâmetros: reduced (~243) ou full (~20k) (padrão: reduced)",
    )
    parser.add_argument(
        "--metric",
        choices=["sharpe_ratio", "profit_factor", "return_total", "win_rate"],
        default=None,
        help="Métrica de otimização (padrão: sharpe_ratio do config)",
    )

    args = parser.parse_args()

    if not args.symbol and not args.all:
        parser.error("Especifique --symbol ou --all")

    symbols = []
    if args.all:
        from config import TRADING_PAIRS
        symbols = list(TRADING_PAIRS.keys())
    else:
        symbols = [args.symbol]

    results = {}
    for sym in symbols:
        result = walk_forward_optimize(
            symbol=sym,
            start=args.start,
            end=args.end,
            grid_type=args.grid,
            metric=args.metric,
        )
        results[sym] = result

    # Resumo final
    if len(symbols) > 1:
        print(f"\n{'='*68}")
        print(f"  RESUMO — Todos os Pares")
        print(f"{'='*68}")
        print(f"  {'Par':<12} {'Aprovado':>10} {'Sharpe Val':>12} {'Retorno Val':>12}")
        print(f"  {'─'*68}")
        for sym, res in results.items():
            if res and res.get("val_result"):
                status = "✅ SIM" if res.get("approved") else "❌ NÃO"
                sharpe = res["val_result"].get("sharpe_ratio", 0)
                ret = res["val_result"].get("return_total", 0)
                print(f"  {sym:<12} {status:>10} {sharpe:>12.3f} {ret:>+11.1%}")
            else:
                print(f"  {sym:<12} {'⚠️  FALHOU':>10}")
        print(f"  {'='*68}\n")


if __name__ == "__main__":
    main()
