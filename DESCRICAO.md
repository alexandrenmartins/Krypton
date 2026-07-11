# Krypton TradeBot — Descrição detalhada

## O que é

O **Krypton** é um **bot de trading algorítmico de criptomoedas** em Python, voltado à **Binance Spot**. Ele une:

1. **Estratégia técnica** com confirmação tripla
2. **Backtest** histórico com métricas de performance
3. **Execução automática** (testnet ou produção)
4. **Gestão de risco** em várias camadas

Propósito central: **automatizar trades seletivos em timeframe diário**, com risco controlado e validação prévia em dados históricos. O projeto se posiciona como **educacional/pesquisa** (há avisos explícitos de risco de perda total).

---

## Problema que tenta resolver

- Reduzir decisões emocionais e inconsistentes
- Aplicar regras de risco de forma mecânica
- Validar a estratégia no passado **antes** de arriscar capital real
- Operar vários pares (BTC, ETH, SOL, BNB) com alocação definida

---

## Estratégia: Supertrend + RSI + MACD

A lógica vive em `indicators.py` (`compute_signals`). Só abre posição quando **os três filtros concordam**:

| # | Indicador | LONG | SHORT |
|---|-----------|------|-------|
| 1 | **Supertrend** (período 7, mult. 3.0) | direção +1 (alta) | direção −1 (baixa) |
| 2 | **RSI** (14, Wilder) | 40 ≤ RSI ≤ 70 | 30 ≤ RSI ≤ 60 |
| 3 | **MACD** (12, 26, 9) | linha MACD > sinal | linha MACD < sinal |

Detalhes importantes:

- **RSI assimétrico** (faixas diferentes para long e short) — resultado de otimização por grid search.
- Se o Supertrend **reverte** e a posição fica na direção oposta, o sinal vira **FLAT (0)** e espera nova confirmação.
- Timeframe: **candle diário (`1d`)** — poucos trades, menos ruído.
- Ordens: **somente limit** (nunca market), com slippage máximo de **0,5%** vs mid-price.

---

## Pares e alocação de capital

Em `config.py`:

| Par | Alocação | Motivo (segundo o projeto) |
|-----|----------|----------------------------|
| **BTCUSDT** | 40% | Maior liquidez, menor risco |
| **SOLUSDT** | 25% | Melhor alpha no backtest |
| **ETHUSDT** | 20% | Diversificação |
| **BNBUSDT** | 15% | Diversificação / taxas |

Máximo de **4 posições simultâneas** (1 por par).

---

## Gestão de risco

Em `risk_manager.py` (e espelhada no backtest):

| Camada | Valor | Efeito |
|--------|-------|--------|
| Risco por trade | **1%** do capital | perda máxima planejada no SL |
| Stop Loss | **2× ATR(14)** | saída por volatilidade |
| Take Profit | **3× ATR(14)** | R:R ≈ 1,5:1 |
| Circuit breaker | **−4%** no dia | pausa o trading até o reset diário |
| Max drawdown | **−20%** desde o pico | **halt total** (exige intervenção manual) |
| Taxas (simulação) | 0,1% por lado | alinhado à taxa spot Binance |

**Position sizing (ATR-based):**

```text
Quantity = (Capital × 1%) / (ATR(14) × 2.0)
```

Quanto maior a volatilidade, menor a quantidade — o risco em dólares fica próximo de 1% se o stop for atingido.

---

## Arquitetura do software

| Arquivo | Função |
|---------|--------|
| `config.py` | API keys (via `.env`), pares, parâmetros, risco |
| `indicators.py` | RSI, MACD, ATR, Supertrend e geração de sinais |
| `risk_manager.py` | Sizing, circuit breaker, max drawdown |
| `binance_client.py` | Dados de mercado, saldo, ordens limit |
| `tradebot.py` | Loop principal ao vivo |
| `backtest.py` | Simulação histórica standalone |
| `README.md` | Visão geral, deploy, métricas, avisos |
| `BINANCE_API.md` | Como criar e proteger as API keys |
| `OTIMIZACAO.md` | Ideias de otimização de parâmetros (grid search, walk-forward, etc.) |
| `DESCRICAO.md` | Este arquivo — descrição detalhada do projeto |

### Fluxo do bot ao vivo (`tradebot.py`)

1. Conecta na Binance (`USE_TESTNET = True` por padrão).
2. Lê saldo USDT e info dos pares.
3. **Ciclo diário às 00:05 UTC** (após o candle D1):
   - confere SL/TP
   - reseta o circuit breaker do dia
   - para cada par: baixa ~300 candles → calcula sinal → fecha se reverteu → abre se houver sinal e não houver posição
4. **A cada 5 minutos:** verifica SL/TP em tempo real.
5. Loga em `tradebot.log` e no console.

### Fluxo do backtest (`backtest.py`)

1. Baixa OHLCV diário com fallback: **Binance Global → Binance US → Yahoo Finance**.
2. Usa **300 dias de aquecimento** antes do período pedido (indicadores estabilizados).
3. Simula $10.000, taxas, SL/TP, sizing ATR e halt de drawdown.
4. Compara o bot com **buy & hold** (retorno, Sharpe, DD, win rate, profit factor, alpha).

---

## Performance que o projeto documenta (backtest)

Números do README / código — **simulação, não garantia futura**.

**SOLUSDT (Jan/2022 – Mai/2026, ~1.612 dias, capital sim. $10k):**

| Métrica | Bot | Buy & Hold SOL |
|---------|-----|----------------|
| Retorno total | **+37,7%** | −53,9% |
| Sharpe | **0,932** | — |
| Max drawdown | **−5,0%** | −94,4% |
| Win rate | **54,0%** | — |
| Profit factor | **1,748** | — |
| Nº de trades | **74** | — |
| Alpha vs B&H | **+91,6 p.p.** | — |

**Portfólio multi-ativo** (pesos acima): bot **+18,5%** vs buy & hold **+4,0%** (conforme README).

Parâmetros da estratégia foram **otimizados via grid search** (mencionado em `config.py` e README).

---

## Segurança e modo de operação

O projeto enfatiza operação **cautelosa**:

1. Testnet ligada por padrão (`USE_TESTNET = True`)
2. Recomendação de **≥ 30 dias em testnet** antes de produção
3. Capital real sugerido a partir de **$500 USDT**, sem alavancagem
4. API só com **leitura + spot** — nunca saque nem futures
5. Restrição de IP no VPS; secrets no `.env` (fora do Git)
6. Avisos fortes de risco e uso educacional

---

## Documentação auxiliar

- **README.md** — o que é o bot, métricas, deploy passo a passo, monitoramento, disclaimers
- **BINANCE_API.md** — criar keys, permissões, IP, testnet → produção
- **OTIMIZACAO.md** — grid search, walk-forward, multi-objetivo, sensibilidade e riscos de overfitting
- **DESCRICAO.md** — visão completa e detalhada do propósito e funcionamento do projeto

---

## O que ainda é mais “plano” do que código

| Ideia na documentação | Estado no repositório |
|----------------------|------------------------|
| Flag `--optimize` / grid search automático | **Não** implementada em `backtest.py` |
| Walk-forward optimization | Só **exemplo** em markdown |
| PDF técnico citado no README | Não aparece na listagem atual do repo |

O **núcleo** (indicadores + risco + cliente Binance + bot + backtest) está implementado. A **otimização avançada de parâmetros** está descrita, mas não codificada como ferramenta pronta.

---

## Stack e dependências

- Python 3.11+
- `python-binance` — API Binance
- `pandas` / `numpy` — séries e métricas
- `ta` — listado em requirements (indicadores principais implementados manualmente em `indicators.py`)
- `schedule` — agendamento do ciclo diário
- `python-dotenv` — secrets
- `yfinance` / `requests` — dados no backtest

---

## Resumo em uma frase

O **Krypton** se propõe a ser um **sistema de trading algorítmico de tendência em cripto** (Supertrend + RSI + MACD no diário), multi-ativo na Binance Spot, com **sizing por risco/ATR**, **proteções de capital** (SL/TP, circuit breaker, halt de drawdown) e um **pipeline de backtest** para validar a ideia antes de operar com dinheiro real — com ênfase em segurança da API e operação em testnet primeiro.
