# config.py — Configurações do TradeBot Krypton
# Estratégia Vencedora: Supertrend + RSI + MACD Filter
# Backtest: Jan/2022 – Mai/2026 | +37,7% retorno | -5,0% max drawdown | Sharpe 0.932
#
# ⚠️  NUNCA commitar este arquivo com chaves reais — use o arquivo .env
# ⚠️  Adicionar .env ao .gitignore antes do primeiro commit

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys (carregadas do .env) ────────────────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ─── Pares de Trading & Alocação de Capital ───────────────────────────────────
# Alocação baseada no backtest: SOL lidera por maior alpha (+91,6 p.p. vs B&H)
TRADING_PAIRS = {
    "SOLUSDT": 0.25,   # 25% do capital — par primário (melhor performance)
    "BTCUSDT": 0.40,   # 40% do capital — maior liquidez, menor risco
    "ETHUSDT": 0.20,   # 20% do capital
    "BNBUSDT": 0.15,   # 15% do capital
}

# ─── Parâmetros da Estratégia (Otimizados via Grid Search — 1.612 dias) ───────
# Supertrend
SUPERTREND_PERIOD     = 7    # Períodos do ATR | Sensibilidade média-alta
SUPERTREND_MULTIPLIER = 3.0  # Multiplicador ATR | Bandas amplas = menos whipsaws

# RSI (Wilder)
RSI_PERIOD  = 14   # Padrão Wilder — mais estável que EMA simples
RSI_LOW     = 40   # Threshold mínimo para entrada LONG (zona neutro-bullish)
RSI_HIGH    = 70   # Threshold máximo para entrada LONG (evita sobrecompra)
# Filtro assimétrico para SHORT: 30 ≤ RSI ≤ 60 (resultado da otimização)

# MACD (padrão Binance/TradingView)
MACD_FAST   = 12   # EMA rápida
MACD_SLOW   = 26   # EMA lenta
MACD_SIGNAL = 9    # EMA da linha de sinal

# ─── Gestão de Risco ──────────────────────────────────────────────────────────
RISK_PER_TRADE         = 0.01   # 1% do capital por trade (máxima perda aceita)
STOP_LOSS_ATR_MULT     = 2.0    # Stop Loss = 2× ATR(14) | Amplo p/ ruído diário
TAKE_PROFIT_ATR_MULT   = 3.0    # Take Profit = 3× ATR(14) | R:R ratio = 1,5:1
CIRCUIT_BREAKER_PCT    = 0.04   # -4% no dia → fecha posições + pausa 24h
MAX_DRAWDOWN_PCT       = 0.20   # -20% desde o pico → halt completo (manual)
MAX_SIMULTANEOUS_POS   = 4      # Máximo de posições simultâneas (1 por par)

# ─── Execução de Ordens ───────────────────────────────────────────────────────
TIMEFRAME           = "1d"    # Candle diário — melhor relação sinal/ruído
SLIPPAGE_LIMIT_PCT  = 0.005   # Máx 0,5% desvio do mid-price (limit orders)
FEE_RATE            = 0.001   # 0,1% por lado (taxa spot Binance padrão)

# ─── Ambiente ─────────────────────────────────────────────────────────────────
USE_TESTNET = True   # True = Binance Testnet | False = Produção real
                     # ⚠️  Obrigatório: 30 dias em Testnet antes de produção

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE = "tradebot.log"

# ─── Configuração de Otimização (Walk-Forward) ────────────────────────────────
# Usado por walk_forward.py. Não altera a estratégia live até copiar params
# manualmente para as constantes SUPERTREND_*/RSI_*/MACD_* acima.
OPTIMIZATION = {
    "train_ratio": 0.7,
    "validation_ratio": 0.3,
    "optimization_metric": "sharpe_ratio",
    # Critérios de aceitação na validação (OTIMIZACAO_WalkForward.md)
    "acceptance": {
        "min_sharpe": 0.3,
        "max_drawdown_abs": 0.15,   # |DD| < 15%
        "min_win_rate": 0.45,
        "min_profit_factor": 1.2,
        "min_return": 0.0,
    },
    # Grid reduzido (default) — rápido o bastante para smoke tests
    "param_grid_reduced": {
        "st_period":  [7, 10, 14],
        "st_mult":    [2.5, 3.0, 3.5],
        "rsi_period": [14],
        "rsi_low":    [35, 40, 45],
        "rsi_high":   [65, 70, 75],
        "macd_fast":  [12],
        "macd_slow":  [26],
        "macd_sig":   [9],
    },
    # Grid completo do documento de otimização (~20k combinações)
    "param_grid_full": {
        "st_period":  [5, 7, 10, 14],
        "st_mult":    [2.0, 2.5, 3.0, 3.5],
        "rsi_period": [10, 14, 20],
        "rsi_low":    [30, 35, 40, 45],
        "rsi_high":   [65, 70, 75, 80],
        "macd_fast":  [8, 10, 12],
        "macd_slow":  [20, 26, 30],
        "macd_sig":   [7, 9, 12],
    },
}
