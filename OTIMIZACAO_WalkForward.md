# Walk-Forward Optimization - Krypton TradeBot

## Visão Geral

A Walk-Forward Optimization divide os dados históricos em **períodos de treino e validação** para encontrar parâmetros que generalizem bem, reduzindo o risco de overfitting.

---

## Arquivos a Criar/Modificar

| Arquivo | Ação | Descrição |
|---|---|---|
| `walk_forward.py` | **Criar** | Script principal de otimização walk-forward |
| `backtest.py` | **Modificar** | Adicionar função `run_backtest_with_params()` |
| `config.py` | **Modificar** | Adicionar seção de configuração de otimização |

---

## Estrutura do `walk_forward.py`

```python
# walk_forward.py — Walk-Forward Optimization para Krypton TradeBot

# Funcionalidades:
#   1. Dividir dados em treino (70%) e validação (30%)
#   2. Grid Search no período de treino
#   3. Validar melhores parâmetros no período de validação
#   4. Comparar com configuração atual
#   5. Gerar relatório de resultados

# Estrutura:
#   - walk_forward_optimize() — Função principal
#   - generate_param_grid() — Gera combinações de parâmetros
#   - run_optimization() — Executa grid search no treino
#   - validate_params() — Valida na validação
#   - print_report() — Exibe resultados comparativos
```

---

## Passos de Implementação

### Passo 1: Modificar `backtest.py`

Adicionar função que aceita parâmetros customizados:

```python
def run_backtest_with_params(symbol, start, end, params):
    """
    Executa backtest com parâmetros customizados.
    
    params = {
        'st_period': 7,
        'st_mult': 3.0,
        'rsi_period': 14,
        'rsi_low': 40,
        'rsi_high': 70,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_sig': 9
    }
    """
    # ... implementação
```

### Passo 2: Criar `walk_forward.py`

Estrutura principal:

```python
# 1. Carregar dados históricos
# 2. Dividir em treino (70%) e validação (30%)
# 3. Gerar grid de parâmetros
# 4. Otimizar no treino (encontrar melhores parâmetros)
# 5. Validar na validação (testar se generaliza)
# 6. Comparar com configuração atual
# 7. Exibir relatório
```

### Passo 3: Modificar `config.py`

Adicionar configuração de otimização:

```python
# ─── Configuração de Otimização ──────────────────────────────────────────────
OPTIMIZATION = {
    "train_ratio": 0.7,           # 70% para treino
    "validation_ratio": 0.3,      # 30% para validação
    "optimization_metric": "sharpe_ratio",  # Métrica para otimizar
    "param_grid": {
        "st_period": [5, 7, 10, 14],
        "st_mult": [2.0, 2.5, 3.0, 3.5],
        "rsi_period": [10, 14, 20],
        "rsi_low": [30, 35, 40, 45],
        "rsi_high": [65, 70, 75, 80],
        "macd_fast": [8, 10, 12],
        "macd_slow": [20, 26, 30],
        "macd_sig": [7, 9, 12]
    }
}
```

---

## Fluxo de Execução

```
┌─────────────────────────────────────────────────────────┐
│  1. Carregar dados históricos (SOLUSDT, 2022-2026)      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. Dividir: Treino (2022-2024) | Validação (2025-2026)│
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. Grid Search no Treino                               │
│     - Testar todas as combinações de parâmetros         │
│     - Selecionar melhor Sharpe Ratio                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  4. Validar na Validação                                │
│     - Usar melhores parâmetros do treino                │
│     - Testar em dados não vistos                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  5. Comparar Resultados                                 │
│     - Treino vs Validação                               │
│     - Parâmetros otimizados vs configuração atual       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  6. Gerar Relatório                                     │
│     - Melhores parâmetros encontrados                   │
│     - Métricas de performance                           │
│     - Recomendações                                     │
└─────────────────────────────────────────────────────────┘
```

---

## Métricas de Validação

| Métrica | Critério de Aceitação |
|---|---|
| **Sharpe Ratio** | Treino e validação > 0.3 |
| **Max Drawdown** | Validação < 15% |
| **Win Rate** | Validação > 45% |
| **Profit Factor** | Validação > 1.2 |
| **Retorno Total** | Validação > 0% |

---

## Comando de Uso

```bash
# Otimizar SOLUSDT
python walk_forward.py --symbol SOLUSDT --start 2022-01-01 --end 2026-06-01

# Otimizar todos os pares
python walk_forward.py --all --start 2022-01-01 --end 2026-06-01

# Usar métrica específica
python walk_forward.py --symbol SOLUSDT --metric profit_factor
```

---

## Relatório de Saída

```
============================================================
WALK-FORWARD OPTIMIZATION: SOLUSDT
============================================================

Período de Treino: 2022-01-01 → 2024-06-30 (912 dias)
Período de Validação: 2024-07-01 → 2026-06-01 (730 dias)

PARÂMETROS OTIMIZADOS:
  Supertrend: period=10, multiplier=2.5
  RSI: period=14, low=35, high=75
  MACD: fast=10, slow=26, signal=9

RESULTADOS NO TREINO:
  Sharpe Ratio: 0.85
  Retorno Total: +22.4%
  Max Drawdown: -6.8%
  Win Rate: 51.2%
  Profit Factor: 1.62

RESULTADOS NA VALIDAÇÃO:
  Sharpe Ratio: 0.72
  Retorno Total: +18.1%
  Max Drawdown: -8.2%
  Win Rate: 49.8%
  Profit Factor: 1.45

COMPARAÇÃO COM CONFIGURAÇÃO ATUAL:
  Métrica            Atual    Otimizado   Melhoria
  Sharpe Ratio       0.492    0.72        +46.3%
  Retorno Total      +16.2%   +18.1%      +1.9 p.p.
  Max Drawdown       -7.6%    -8.2%       -0.6 p.p.

RECOMENDAÇÃO: ✅ APROVADO
Parâmetros otimizados generalizam bem (treino ≈ validação)
```

---

## Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Overfitting | Walk-Forward já mitiga ao validar em dados não vistos |
| Muitas combinações | Usar parâmetros mais restritos ou Random Search |
| Dados insuficientes | Usar ≥3 anos de dados históricos |
| Resultados inconsistentes | Executar múltiplas vezes e verificar consistência |
