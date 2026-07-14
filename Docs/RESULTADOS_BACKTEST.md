# Resultados Backtest - Krypton TradeBot

## Configuração Otimizada por Par (Walk-Forward)

| Parâmetro | Defaults | BTCUSDT | ETHUSDT |
|-----------|----------|---------|---------|
| SUPERTREND_PERIOD | 7 | **10** | 7 |
| SUPERTREND_MULTIPLIER | 3.0 | **2.5** | **2.5** |
| RSI_PERIOD | 14 | 14 | 14 |
| RSI_LOW | 40 | **35** | **35** |
| RSI_HIGH | 70 | **65** | **75** |
| MACD_FAST | 12 | 12 | 12 |
| MACD_SLOW | 26 | 26 | 26 |
| MACD_SIGNAL | 9 | 9 | 9 |

- **SOLUSDT / BNBUSDT:** Walk-Forward rejeitou → mantêm defaults globais
- **BTCUSDT / ETHUSDT:** Params otimizados via Walk-Forward (grid reduzido)

---

## Tabela Comparativa — BOT vs Buy & Hold

**Período:** 2022-01-01 → 2026-07-12 (1.654 candles diários)
**Capital inicial:** $10.000

### Retorno Total

| Par | BOT | Buy & Hold | Alpha (BOT − B&H) |
|-----|-----|------------|-------------------|
| **SOLUSDT** | +14.6% | -57.1% | **+71.7%** |
| **BTCUSDT** | +31.6% | +33.7% | -2.1% |
| **ETHUSDT** | +30.9% | -52.1% | **+83.0%** |
| **BNBUSDT** | +13.0% | +8.9% | **+4.1%** |

### Métricas de Risco/Retorno

| Par | Sharpe | Max Drawdown | Win Rate | Profit Factor | Trades |
|-----|--------|--------------|----------|---------------|--------|
| **SOLUSDT** | 0.434 | -10.4% | 46.2% | 1.311 | 65 |
| **BTCUSDT** | 0.876 | -5.0% | 54.1% | 1.932 | 61 |
| **ETHUSDT** | 0.765 | -7.8% | 50.0% | 1.652 | 76 |
| **BNBUSDT** | 0.415 | -9.4% | 50.0% | 1.369 | 50 |

### Capital Final

| Par | BOT | Buy & Hold | Ganho BOT vs B&H |
|-----|-----|------------|-------------------|
| **SOLUSDT** | $11.459 | $4.290 | **+$7.169** |
| **BTCUSDT** | $13.157 | $13.370 | -$213 |
| **ETHUSDT** | $13.089 | $4.790 | **+$8.299** |
| **BNBUSDT** | $11.295 | $10.890 | **+$405** |

### Saídas (TP/SL/Signal)

| Par | Take Profit | Stop Loss | Signal | Total |
|-----|-------------|-----------|--------|-------|
| **SOLUSDT** | 30 | 35 | 0 | 65 |
| **BTCUSDT** | 33 | 26 | 2 | 61 |
| **ETHUSDT** | 38 | 38 | 0 | 76 |
| **BNBUSDT** | 25 | 25 | 0 | 50 |

---

## Resumo por Par

### SOLUSDT — Defaults Globais

| Métrica | Valor |
|---------|-------|
| Retorno Total | +14.6% |
| Buy & Hold | -57.1% |
| Alpha vs B&H | **+71.7%** |
| Sharpe Ratio | 0.434 |
| Max Drawdown | -10.4% |
| Win Rate | 46.2% |
| Profit Factor | 1.311 |
| Capital Final | $11.459 |

> Walk-Forward rejeitou otimização (validação negativa). Config original já performa
> bem com forte alpha vs B&H em mercado bearish.

---

### BTCUSDT — ✅ Otimizado (Walk-Forward)

| Métrica | Valor |
|---------|-------|
| Retorno Total | +31.6% |
| Buy & Hold | +33.7% |
| Alpha vs B&H | -2.1% |
| Sharpe Ratio | 0.876 |
| Max Drawdown | -5.0% |
| Win Rate | 54.1% |
| Profit Factor | 1.932 |
| Capital Final | $13.157 |

> Params otimizados: `st_period=10, st_mult=2.5, rsi_low=35, rsi_high=65`
> Retorno próximo ao B&H mas com drawdown muito menor (-5% vs -12.5% do B&H).
> Maior Sharpe do portfolio (0.876).

---

### ETHUSDT — ✅ Otimizado (Walk-Forward)

| Métrica | Valor |
|---------|-------|
| Retorno Total | +30.9% |
| Buy & Hold | -52.1% |
| Alpha vs B&H | **+83.0%** |
| Sharpe Ratio | 0.765 |
| Max Drawdown | -7.8% |
| Win Rate | 50.0% |
| Profit Factor | 1.652 |
| Capital Final | $13.089 |

> Params otimizados: `st_period=7, st_mult=2.5, rsi_low=35, rsi_high=75`
> Maior alpha do portfolio (+83%). B&H perdeu mais da metade, bot lucrou +31%.

---

### BNBUSDT — Defaults Globais

| Métrica | Valor |
|---------|-------|
| Retorno Total | +13.0% |
| Buy & Hold | +8.9% |
| Alpha vs B&H | **+4.1%** |
| Sharpe Ratio | 0.415 |
| Max Drawdown | -9.4% |
| Win Rate | 50.0% |
| Profit Factor | 1.369 |
| Capital Final | $11.295 |

> Walk-Forward rejeitou otimização (Sharpe e PF abaixo do mínimo). Config original
> já supera B&H com drawdown controlado.

---

## Portfolio Consolidado

| Métrica | Valor |
|---------|-------|
| **Capital Total Final** | $48.999 (+$8.999) |
| **Retorno Médio** | +22.5% |
| **Sharpe Médio** | 0.623 |
| **Pior Max Drawdown** | -10.4% (SOLUSDT) |
| **Melhor Alpha** | +83.0% (ETHUSDT) |

> Capital inicial total: $40.000 ($10.000 × 4 pares)
> Capital final total: $48.999

---

## Conclusão

A estratégia **Supertrend + RSI + MACD** com otimização Walk-Forward por par:

1. **Supera Buy & Hold** em 3 de 4 pares (SOL +71.7%, ETH +83.0%, BNB +4.1%)
2. **BTC** acompanha B&H (+31.6% vs +33.7%) com drawdown 60% menor
3. **Drawdown controlado** — pior DD do portfolio é -10.4% vs -57.1% do B&H em SOL
4. **Win Rate** entre 46-54%, Profit Factor > 1.3 em todos os pares

---

## Implementação

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `config.py` | ✅ Atualizado | `PAIR_PARAMS` com configs otimizadas por par |
| `backtest.py` | ✅ Atualizado | Usa `PAIR_PARAMS` automaticamente no CLI |
| `tradebot.py` | ✅ Atualizado | Usa `PAIR_PARAMS` no cálculo de sinais ao vivo |
| `walk_forward.py` | ✅ Criado | Script de otimização Walk-Forward |
