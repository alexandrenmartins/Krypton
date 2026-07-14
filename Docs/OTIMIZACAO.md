# Otimização de Parâmetros da Estratégia - Krypton TradeBot

## 1. Grid Search (Brute Force)

O README menciona que os parâmetros atuais foram otimizados via **Grid Search** sobre 1.612 dias. Este método testa **todas as combinações** de parâmetros em um intervalo definido.

### Parâmetros Otimizáveis

| Parâmetro | Atual | Faixa Sugerida |
|---|---|---|
| SUPERTREND_PERIOD | 7 | 5, 7, 10, 14, 20 |
| SUPERTREND_MULTIPLIER | 3.0 | 2.0, 2.5, 3.0, 3.5, 4.0 |
| RSI_PERIOD | 14 | 10, 14, 20 |
| RSI_LOW | 40 | 30, 35, 40, 45 |
| RSI_HIGH | 70 | 65, 70, 75, 80 |
| MACD_FAST | 12 | 8, 10, 12 |
| MACD_SLOW | 26 | 20, 26, 30 |
| MACD_SIGNAL | 9 | 7, 9, 12 |

### Exemplo de Uso

```bash
python backtest.py --symbol SOLUSDT --start 2022-01-01 --optimize
```

---

## 2. Walk-Forward Optimization (Recomendado)

Divide os dados em **períodos de treino e validação**:

- **Treino**: 2022-2024 (otimizar parâmetros)
- **Validação**: 2025-2026 (testar se funciona em dados não vistos)

**Vantagem:** Reduz overfitting (sobreajuste aos dados históricos)

### Passos

1. Separar dados em treino (70%) e validação (30%)
2. Otimizar parâmetros no período de treino
3. Validar no período de validação
4. Comparar resultados entre treino e validação
5. Se resultados são próximos = bom sinal de generalização

---

## 3. Otimização Multi-Objetivo

Otimiza para **múltiplas métricas simultaneamente**:

- Maximizar Sharpe Ratio E Profit Factor
- Minimizar Max Drawdown E manter retorno positivo
- Maximizar Win Rate E manter Profit Factor > 1.2

### Métricas para Otimizar

| Métrica | Objetivo | Peso Sugerido |
|---|---|---|
| Sharpe Ratio | Maximizar | 30% |
| Profit Factor | Maximizar | 25% |
| Max Drawdown | Minimizar | 25% |
| Return Total | Maximizar | 20% |

---

## 4. Otimização por Par (Personalizada)

Cada par pode ter parâmetros diferentes:

| Par | Característica | Abordagem |
|---|---|---|
| **SOLUSDT** | Maior volatilidade | Parâmetros mais agressivos |
| **BTCUSDT** | Maior liquidez | Parâmetros mais conservadores |
| **ETHUSDT** | Volatilidade média | Parâmetros intermediários |
| **BNBUSDT** | Menor drawdown | Parâmetros que favoreçam estabilidade |

---

## 5. Análise de Sensibilidade

Testa **quanto cada parâmetro afeta o resultado**:

- Se mudar RSI de 14 para 20 melhora ou piora?
- Se mudar Supertrend de 7 para 10 melhora ou piora?
- Identifica quais parâmetros são mais críticos

### Como Fazer

1. Manter todos os parâmetros fixos
2. Variar um parâmetro por vez
3. Observar impacto no Sharpe Ratio e Max Drawdown
4. Identificar parâmetros com maior impacto

---

## Riscos da Otimização

| Risco | Descrição | Mitigação |
|---|---|---|
| **Overfitting** | Parâmetros perfeitos no passado, mas não funcionam no futuro | Usar Walk-Forward |
| **Curva demais** | Muitos parâmetros = modelo complexo demais | Manter simples (3 indicadores) |
| **Dados insuficientes** | Otimizar em período curto = resultados não confiáveis | Usar dados de ≥2 anos |

---

## Recomendação

A **Walk-Forward Optimization** é a mais robusta porque:

1. Otimiza em dados de treino
2. Valida em dados de validação (não vistos)
3. Reduz risco de overfitting
4. Mais confiável para trading real

---

## Exemplo de Implementação

```python
# walk_forward.py - Exemplo de implementação

from itertools import product

def walk_forward_optimize(df, param_grid):
    """
    Otimiza parâmetros usando Walk-Forward.
    
    1. Divide dados em treino (70%) e validação (30%)
    2. Otimiza no treino
    3. Valida na validação
    4. Retorna melhores parâmetros
    """
    split = int(len(df) * 0.7)
    train = df[:split]
    valid = df[split:]
    
    best_params = None
    best_sharpe = -float('inf')
    
    # Grid Search no treino
    for params in product(*param_grid.values()):
        param_dict = dict(zip(param_grid.keys(), params))
        sharpe = run_backtest(train, **param_dict)['sharpe_ratio']
        
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = param_dict
    
    # Validar na validação
    valid_result = run_backtest(valid, **best_params)
    
    return best_params, valid_result
```
