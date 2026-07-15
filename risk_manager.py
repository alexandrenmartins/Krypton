# risk_manager.py — Gestão de Risco e Dimensionamento de Posição
# Krypton TradeBot | Estratégia: Supertrend + RSI + MACD Filter
#
# Camadas de proteção implementadas:
#   1. Stop Loss por trade    → 2× ATR(14)
#   2. Take Profit por trade  → 3× ATR(14)  | R:R = 1,5:1
#   3. Circuit Breaker diário → -4% no dia  → pausa 24h
#   4. Max Drawdown Stop      → -20% total  → halt manual obrigatório
#
# Position Sizing (ATR-based):
#   Quantity = (Capital × 1%) / (ATR(14) × 2.0)
#   Garante risco em $ constante de 1% do capital por trade.

import logging
from config import (
    RISK_PER_TRADE,
    STOP_LOSS_ATR_MULT,
    TAKE_PROFIT_ATR_MULT,
    CIRCUIT_BREAKER_PCT,
    MAX_DRAWDOWN_PCT,
)

logger = logging.getLogger("Krypton.Risk")


class RiskManager:
    """
    Gerencia risco individual por trade, circuit breaker diário e
    halt por max drawdown total.

    Hierarquia de proteções (prioridade de execução):
      1ª  Stop Loss por trade      — fecha posição individual imediatamente
      2ª  Take Profit por trade    — fecha posição individual com lucro
      3ª  Circuit Breaker diário   — fecha TUDO + pausa 24h
      4ª  Max Drawdown Stop        — halt completo → requer intervenção manual
    """

    def __init__(self, initial_capital: float):
        self.initial_capital  = initial_capital
        self.peak_capital     = initial_capital
        self.daily_start_cap  = initial_capital
        self.halted           = False   # ativado pelo max drawdown stop
        self.circuit_breaker  = False   # ativado pela perda diária

    # ─── Reset & Atualização ──────────────────────────────────────────────────

    def reset_daily(self, current_capital: float) -> None:
        """Chamar às 00:00 UTC no início de cada novo dia."""
        self.daily_start_cap = current_capital
        self.circuit_breaker = False
        logger.info(f"Reset diário. Capital: ${current_capital:,.2f}")

    def update_peak(self, current_capital: float) -> None:
        """Atualiza o pico de capital para cálculo de drawdown."""
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital

    # ─── Verificações de Risco ────────────────────────────────────────────────

    def check_circuit_breaker(self, current_capital: float) -> bool:
        """
        Ativa circuit breaker se a perda diária atingir CIRCUIT_BREAKER_PCT (-4%).
        Retorna True se ativo.
        """
        if self.daily_start_cap <= 0:
            return self.circuit_breaker
        daily_loss = (self.daily_start_cap - current_capital) / self.daily_start_cap
        if daily_loss >= CIRCUIT_BREAKER_PCT and not self.circuit_breaker:
            self.circuit_breaker = True
            logger.warning(
                f"CIRCUIT BREAKER ativado! "
                f"Perda diária: {daily_loss:.1%} | "
                f"Limite: {CIRCUIT_BREAKER_PCT:.0%}"
            )
        return self.circuit_breaker

    def check_max_drawdown(self, current_capital: float) -> bool:
        """
        Ativa halt se o drawdown desde o pico atingir MAX_DRAWDOWN_PCT (-20%).
        Retorna True se ativo. Requer intervenção manual para reiniciar.
        """
        if self.peak_capital <= 0:
            return self.halted
        drawdown = (self.peak_capital - current_capital) / self.peak_capital
        if drawdown >= MAX_DRAWDOWN_PCT and not self.halted:
            self.halted = True
            logger.critical(
                f"MAX DRAWDOWN atingido! "
                f"DD: {drawdown:.1%} | "
                f"Capital: ${current_capital:,.2f} | "
                f"Pico: ${self.peak_capital:,.2f} | "
                f"HALT completo — intervenção manual necessária."
            )
        return self.halted

    def can_trade(self, current_capital: float) -> bool:
        """
        Verifica todos os checks de risco antes de abrir nova posição.
        Retorna False se qualquer proteção estiver ativa.
        """
        self.update_peak(current_capital)
        if self.halted:
            logger.warning("Trading HALTED — max drawdown atingido. Intervenção manual necessária.")
            return False
        if self.check_circuit_breaker(current_capital):
            logger.warning("Trading pausado — circuit breaker ativo. Retoma amanhã às 00:00 UTC.")
            return False
        return True

    # ─── Position Sizing ──────────────────────────────────────────────────────

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        atr: float,
    ) -> dict:
        """
        Calcula o tamanho da posição baseado em risco fixo de 1% do capital.

        Fórmula ATR-based:
          sl_distance  = ATR(14) × STOP_LOSS_ATR_MULT   (2.0)
          tp_distance  = ATR(14) × TAKE_PROFIT_ATR_MULT (3.0)
          risk_amount  = capital × RISK_PER_TRADE        (1%)
          quantity     = risk_amount / sl_distance

        Exemplo (SOLUSDT):
          Capital = $10.000 | Preço SOL = $150 | ATR = $8,50
          sl_distance = 8,50 × 2,0  = $17,00
          risk_amount = 10.000 × 1% = $100,00
          quantity    = $100 / $17  = 5,88 SOL  (~$882 = 8,82% do capital)
          Stop Loss   = $150 - $17  = $133,00  (-11,3%)
          Take Profit = $150 + $25,50 = $175,50 (+17,0%)

        Retorna
        -------
        dict com todos os valores calculados.
        """
        sl_distance = atr * STOP_LOSS_ATR_MULT
        tp_distance = atr * TAKE_PROFIT_ATR_MULT
        risk_amount = capital * RISK_PER_TRADE
        quantity    = risk_amount / sl_distance if sl_distance > 0 else 0.0

        return {
            "quantity"          : round(quantity, 6),
            "sl_distance"       : sl_distance,
            "tp_distance"       : tp_distance,
            "stop_loss_long"    : round(entry_price - sl_distance, 4),
            "take_profit_long"  : round(entry_price + tp_distance, 4),
            "stop_loss_short"   : round(entry_price + sl_distance, 4),
            "take_profit_short" : round(entry_price - tp_distance, 4),
            "risk_amount_usd"   : round(risk_amount, 2),
            "rr_ratio"          : round(tp_distance / sl_distance, 2),
        }

    # ─── Resumo do Estado ─────────────────────────────────────────────────────

    def status(self, current_capital: float) -> dict:
        """Retorna dicionário com status atual do gerenciador de risco."""
        drawdown = (
            (self.peak_capital - current_capital) / self.peak_capital
            if self.peak_capital > 0 else 0.0
        )
        daily_loss = (
            (self.daily_start_cap - current_capital) / self.daily_start_cap
            if self.daily_start_cap > 0 else 0.0
        )
        return {
            "current_capital"   : round(current_capital, 2),
            "peak_capital"      : round(self.peak_capital, 2),
            "current_drawdown"  : f"{drawdown:.2%}",
            "daily_loss"        : f"{daily_loss:.2%}",
            "circuit_breaker"   : self.circuit_breaker,
            "halted"            : self.halted,
            "can_trade"         : not (self.halted or self.circuit_breaker),
        }
