# tradebot.py — Loop Principal do Krypton TradeBot
# Estratégia: Supertrend + RSI + MACD Filter
#
# Ciclo diário executado às 00:05 UTC (após fechamento do candle D1):
#   1. Verifica SL/TP das posições abertas
#   2. Reset diário do circuit breaker
#   3. Para cada par: calcula sinais e abre/fecha posições
#   4. Entre ciclos: verifica SL/TP a cada 5 minutos (tempo real)
#
# ⚠️  USE_TESTNET = True por padrão em config.py.
#     Mude para False SOMENTE após ≥30 dias em testnet sem erros.

import logging
import time
from datetime import datetime

import schedule

from binance_client import BinanceInterface
from config import (
    LOG_FILE,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MAX_SIMULTANEOUS_POS,
    PAIR_PARAMS,
    RSI_HIGH,
    RSI_LOW,
    RSI_PERIOD,
    SUPERTREND_MULTIPLIER,
    SUPERTREND_PERIOD,
    TIMEFRAME,
    TRADING_PAIRS,
    USE_TESTNET,
)
from indicators import compute_atr, compute_signals
from risk_manager import RiskManager

# ─── Configuração de Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("Krypton.Main")


class TradeBot:
    """
    Para que serve: Gerenciar a execução automática da estratégia Supertrend+RSI+MACD.
    
    O que faz: Executa ciclos diários (às 00:05 UTC), calcula sinais técnicos, 
               abre/fecha posições e verifica stop loss/take profit em tempo real.
    
    Como faz: Integra múltiplos módulos (BinanceInterface para API, RiskManager para risco,
              compute_signals para indicadores técnicos) em um loop principal que:
              - Agenda ciclos diários
              - Monitora SL/TP a cada 5 minutos
              - Gerencia portfolio de posições abertas
    
    Performance (backtest Jan/2022 – Mai/2026):
      Retorno Total : +37,7% (SOLUSDT)
      Sharpe Ratio  : 0,932
      Max Drawdown  : -5,0%
      Win Rate      : 54,0%
      Profit Factor : 1,748
    """

    def __init__(self):
        """
        Para que serve: Inicializar a instância do TradeBot com dependências.
        O que faz: Cria conexão Binance, carrega dados dos pares, inicializa RiskManager.
        Como faz: 
            1. Instancia BinanceInterface para comunicação com a API
            2. Inicializa dicionários vazios para posições e informações de símbolos
            3. Chama _initialize() para carregar capital, info dos pares e criar RiskManager
        """
        self.binance      = BinanceInterface()
        self.risk_manager : RiskManager | None = None
        self.positions    : dict = {}         # {symbol: {side, entry_price, quantity, sl, tp, order_id}}
        self.symbol_infos : dict = {}
        self._initialize()

    # ─── Inicialização ────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        """
        Para que serve: Configurar o estado inicial do bot (capital, símbolos, limites de risco).
        O que faz: Obtém capital USDT disponível, carrega informações de cada par e cria
                   o RiskManager com o capital inicial.
        Como faz:
            1. Consulta saldo USDT atual da conta Binance
            2. Para cada par em TRADING_PAIRS, busca informações (precision, lot size, etc)
            3. Cria instância RiskManager com capital inicial
            4. Log informativo sobre inicialização (modo testnet vs produção)
        
        Returns:
            None (apenas configura o estado interno)
        """
        usdt_balance = self.binance.get_account_balance("USDT")
        for sym in TRADING_PAIRS:
            self.symbol_infos[sym] = self.binance.get_symbol_info(sym)
        self.risk_manager = RiskManager(initial_capital=usdt_balance)
        logger.info(
            f"🟢 Krypton TradeBot inicializado | "
            f"Capital: ${usdt_balance:,.2f} USDT | "
            f"Modo: {'TESTNET ⚠️' if USE_TESTNET else 'PRODUÇÃO 🔴'}"
        )

    # ─── Cálculo de Capital ───────────────────────────────────────────────────

    def _get_current_capital(self) -> float:
        """
        Para que serve: Calcular o capital total (saldo USDT + valor das posições abertas).
        O que faz: Soma o USDT livre com o valor mark-to-market de todas as posições
                   abertas, fornecendo uma visão completa do patrimônio.
        Como faz:
            1. Obtém saldo USDT disponível na conta
            2. Para cada posição aberta:
               a. Busca preço atual do símbolo
               b. Calcula P&L não realizado (diferença entre preço atual e entrada)
               c. Adiciona ao capital o valor da posição ajustado pelo P&L
            3. Retorna capital total
        
        Returns:
            float: Capital total em USDT (saldo + posições)
        """
        usdt = self.binance.get_account_balance("USDT")
        for sym, pos in self.positions.items():
            price = self.binance.get_current_price(sym)
            if pos["side"] == "LONG":
                pnl = pos["quantity"] * (price - pos["entry_price"])
            else:
                pnl = pos["quantity"] * (pos["entry_price"] - price)
            usdt += pos["quantity"] * pos["entry_price"] + pnl
        return usdt

    # ─── Gerenciamento de Posições ────────────────────────────────────────────

    def _close_position(self, symbol: str, reason: str = "Signal") -> None:
        """
        Para que serve: Fechar uma posição aberta e registrar saída.
        O que faz: Executa ordem limit ao preço atual para sair da posição,
                   calcula P&L e remove a posição do dicionário interno.
        Como faz:
            1. Valida se posição existe
            2. Busca preço atual e determina lado oposto (LONG→SELL, SHORT→BUY)
            3. Coloca ordem limit com a quantidade exata da posição
            4. Calcula P&L em % (diferença entre saída e entrada)
            5. Log com detalhes (entry, exit, PnL, razão do fechamento)
            6. Remove posição do dicionário
        
        Args:
            symbol (str): Símbolo da moeda (ex: "SOLUSDT")
            reason (str): Motivo do fechamento ("Signal", "StopLoss", "TakeProfit", etc)
        
        Returns:
            None (modifica estado interno)
        """
        if symbol not in self.positions:
            return
        pos        = self.positions[symbol]
        price      = self.binance.get_current_price(symbol)
        close_side = "SELL" if pos["side"] == "LONG" else "BUY"
        order = self.binance.place_limit_order(
            symbol      = symbol,
            side        = close_side,
            quantity    = pos["quantity"],
            price       = price,
            symbol_info = self.symbol_infos[symbol],
        )
        if order:
            entry = pos["entry_price"]
            pnl_pct = (
                (price - entry) / entry * 100 if pos["side"] == "LONG"
                else (entry - price) / entry * 100
            )
            logger.info(
                f"📤 Posição fechada | {symbol} | Razão: {reason} | "
                f"Entry: {entry:.4f} | Exit: {price:.4f} | "
                f"PnL: {pnl_pct:+.2f}%"
            )
            del self.positions[symbol]

    def _open_position(
        self,
        symbol: str,
        direction: int,
        capital_allocation: float,
        atr: float,
    ) -> None:
        """
        Para que serve: Abrir uma nova posição long ou short com sizing baseado em risco.
        O que faz: Calcula o tamanho da posição (ATR-based), define SL e TP, coloca ordem
                   limit e registra a posição no dicionário interno.
        Como faz:
            1. Valida se não há posição já aberta nesse símbolo
            2. Verifica via RiskManager se pode tradear (capital, drawdown, etc)
            3. Calcula capital alocado para esse par (% do capital total)
            4. Busca preço atual
            5. Calcula tamanho da posição via RiskManager.calculate_position_size()
               (usa ATR para SL, e capital × risco para determinar quantidade)
            6. Define lado (BUY para long, SELL para short) e preço limit (0,05% favorável)
            7. Coloca ordem limit na Binance
            8. Se ordem bem-sucedida, armazena posição no dicionário com SL e TP
            9. Log com detalhes (entry, SL, TP, risco em USD, razão risco:recompensa)
        
        Args:
            symbol (str): Símbolo do par (ex: "SOLUSDT")
            direction (int): +1 para LONG, -1 para SHORT
            capital_allocation (float): Fração do capital para alocar (ex: 0.25 = 25%)
            atr (float): Valor do ATR atual (usado para dimensionar SL/TP)
        
        Returns:
            None (modifica estado interno)
        """
        if symbol in self.positions:
            return  # já tem posição neste par

        current_capital = self._get_current_capital()
        if not self.risk_manager.can_trade(current_capital):
            return

        pair_capital = current_capital * capital_allocation
        price        = self.binance.get_current_price(symbol)
        sizing       = self.risk_manager.calculate_position_size(pair_capital, price, atr)

        if sizing["quantity"] <= 0:
            logger.warning(f"Position size calculado como zero para {symbol}. Pulando.")
            return

        side = "BUY" if direction == 1 else "SELL"
        # Limit price ligeiramente favorável ao mercado (0,05%)
        limit_price = price * (1.0005 if direction == 1 else 0.9995)

        order = self.binance.place_limit_order(
            symbol      = symbol,
            side        = side,
            quantity    = sizing["quantity"],
            price       = limit_price,
            symbol_info = self.symbol_infos[symbol],
        )

        if order:
            sl = sizing["stop_loss_long"]  if direction == 1 else sizing["stop_loss_short"]
            tp = sizing["take_profit_long"] if direction == 1 else sizing["take_profit_short"]
            self.positions[symbol] = {
                "side"        : "LONG" if direction == 1 else "SHORT",
                "entry_price" : price,
                "quantity"    : sizing["quantity"],
                "stop_loss"   : sl,
                "take_profit" : tp,
                "order_id"    : order["orderId"],
            }
            logger.info(
                f"📥 Nova posição | {symbol} | {self.positions[symbol]['side']} | "
                f"Entry: {price:.4f} | SL: {sl:.4f} | TP: {tp:.4f} | "
                f"Risco: ${sizing['risk_amount_usd']:.2f} | R:R {sizing['rr_ratio']:.1f}"
            )

    # ─── Verificação de SL/TP ─────────────────────────────────────────────────

    def _check_sl_tp(self) -> None:
        """
        Para que serve: Monitorar posições abertas e fechar se atingirem SL ou TP.
        O que faz: A cada execução, verifica preço atual de cada posição e fecha
                   se bateu o stop loss ou take profit.
        Como faz:
            1. Itera sobre todas as posições abertas
            2. Para cada posição:
               a. Busca preço atual
               b. Verifica se atingiu SL (condição diferente para LONG vs SHORT)
               c. Verifica se atingiu TP (condição diferente para LONG vs SHORT)
               d. Se atingiu SL: fecha com razão "StopLoss 🔴"
               e. Se atingiu TP: fecha com razão "TakeProfit ✅"
        
        Returns:
            None (modifica posições se forem fechadas)
        """
        for symbol in list(self.positions.keys()):
            pos   = self.positions[symbol]
            price = self.binance.get_current_price(symbol)

            hit_sl = (
                (pos["side"] == "LONG"  and price <= pos["stop_loss"]) or
                (pos["side"] == "SHORT" and price >= pos["stop_loss"])
            )
            hit_tp = (
                (pos["side"] == "LONG"  and price >= pos["take_profit"]) or
                (pos["side"] == "SHORT" and price <= pos["take_profit"])
            )

            if hit_sl:
                self._close_position(symbol, "StopLoss 🔴")
            elif hit_tp:
                self._close_position(symbol, "TakeProfit ✅")

    # ─── Ciclo Diário Principal ───────────────────────────────────────────────

    def daily_cycle(self) -> None:
        """
        Para que serve: Executar o ciclo principal de trading (análise + decisões).
        O que faz: Verifica SL/TP, reseta circuit breaker, calcula sinais de todos os pares
                   e abre/fecha posições baseado na estratégia.
        Como faz:
            1. Log de início do ciclo com timestamp
            2. Obtém capital atual e exibe status via RiskManager
            3. Chama _check_sl_tp() para fechar posições que atingiram SL/TP
            4. Reseta contadores diários do RiskManager (max drawdown, stop loss count)
            5. Verifica se RiskManager permite trading (baseado em controles de risco)
            6. Para cada par em TRADING_PAIRS:
               a. Baixa últimos 300 candles
               b. Resolve parâmetros (PAIR_PARAMS customizados ou defaults globais)
               c. Calcula sinais (Supertrend+RSI+MACD)
               d. Obtém ATR para dimensionamento
               e. Verifica se sinal mudou em posição existente → fecha se necessário
               f. Se novo sinal e sem posição aberta → abre nova posição
               g. Respeita limite de posições simultâneas (MAX_SIMULTANEOUS_POS)
            7. Exibe resumo de posições abertas ao fim do ciclo
        
        Returns:
            None (modifica estado: abre/fecha posições, reseta contadores)
        """
        logger.info("=" * 70)
        logger.info(
            f"🔄 CICLO DIÁRIO | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        current_capital = self._get_current_capital()
        logger.info(f"💰 Capital atual: ${current_capital:,.2f} USDT")
        logger.info(f"📊 {self.risk_manager.status(current_capital)}")

        # Passo 1: Verificar SL/TP antes de qualquer decisão
        self._check_sl_tp()

        # Passo 2: Reset do circuit breaker (novo dia)
        self.risk_manager.reset_daily(current_capital)

        # Passo 3: Verificar se pode operar
        if not self.risk_manager.can_trade(current_capital):
            logger.warning("⛔ Trading pausado pelos controles de risco.")
            return

        # Passo 4: Processar cada par de trading
        for symbol, allocation in TRADING_PAIRS.items():
            try:
                df = self.binance.get_ohlcv(symbol, interval=TIMEFRAME, limit=300)

                # Parâmetros por par (Walk-Forward) ou defaults globais
                pp = PAIR_PARAMS.get(symbol, {})
                st_period  = pp.get("st_period",  SUPERTREND_PERIOD)
                st_mult    = pp.get("st_mult",    SUPERTREND_MULTIPLIER)
                rsi_period = pp.get("rsi_period", RSI_PERIOD)
                rsi_low    = pp.get("rsi_low",    RSI_LOW)
                rsi_high   = pp.get("rsi_high",   RSI_HIGH)
                macd_fast  = pp.get("macd_fast",  MACD_FAST)
                macd_slow  = pp.get("macd_slow",  MACD_SLOW)
                macd_sig   = pp.get("macd_sig",   MACD_SIGNAL)

                signals = compute_signals(
                    df,
                    st_period  = st_period,
                    st_mult    = st_mult,
                    rsi_period = rsi_period,
                    rsi_low    = rsi_low,
                    rsi_high   = rsi_high,
                    macd_fast  = macd_fast,
                    macd_slow  = macd_slow,
                    macd_sig   = macd_sig,
                )

                current_signal = int(signals.iloc[-1])
                current_atr    = compute_atr(
                    df["high"], df["low"], df["close"]
                ).iloc[-1]

                signal_label = {1: "LONG ▲", -1: "SHORT ▼", 0: "FLAT —"}
                logger.info(
                    f"  {symbol} | Sinal: {signal_label[current_signal]} | "
                    f"ATR: {current_atr:.4f}"
                )

                # Fechar posição se sinal reverteu
                if symbol in self.positions:
                    pos_dir = 1 if self.positions[symbol]["side"] == "LONG" else -1
                    if current_signal != pos_dir:
                        self._close_position(symbol, "Signal reversal")

                # Abrir nova posição se há sinal e nenhuma posição aberta
                if symbol not in self.positions and current_signal != 0:
                    if len(self.positions) < MAX_SIMULTANEOUS_POS:
                        self._open_position(symbol, current_signal, allocation, current_atr)
                    else:
                        logger.info(f"  {symbol}: máx de posições simultâneas atingido ({MAX_SIMULTANEOUS_POS}).")

            except Exception as e:
                logger.error(f"Erro no ciclo de {symbol}: {e}", exc_info=True)

        logger.info(
            f"📂 Posições abertas: {len(self.positions)}/{MAX_SIMULTANEOUS_POS} | "
            f"{list(self.positions.keys())}"
        )

    # ─── Loop de Execução ─────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Para que serve: Iniciar o bot e manter o loop principal de execução.
        O que faz: Executa ciclo imediato ao iniciar, agenda ciclos diários,
                   verifica SL/TP periodicamente e mantém bot rodando indefinidamente.
        Como faz:
            1. Exibe logs informativos (estratégia, pares, modo de operação)
            2. Executa daily_cycle() uma vez imediatamente
            3. Agenda execução automática do daily_cycle() às 00:05 UTC (via schedule)
            4. Entra em loop infinito:
               a. Verifica se há alguma tarefa agendada para executar (schedule.run_pending())
               b. Verifica SL/TP de posições abertas (_check_sl_tp())
               c. Dorme 5 minutos (300 segundos) antes da próxima iteração
            5. Entre ciclos diários, SL/TP são monitorados contínuamente (a cada 5 min)
        
        Returns:
            None (função bloqueante, executa indefinidamente)
        """
        logger.info("🚀 Krypton TradeBot iniciado!")
        logger.info(f"   Estratégia base: Supertrend({SUPERTREND_PERIOD},{SUPERTREND_MULTIPLIER}) + RSI({RSI_PERIOD}) + MACD({MACD_FAST},{MACD_SLOW},{MACD_SIGNAL})")
        if PAIR_PARAMS:
            logger.info(f"   Parâmetros por par (Walk-Forward): {list(PAIR_PARAMS.keys())}")
        logger.info(f"   Pares: {list(TRADING_PAIRS.keys())}")
        logger.info(f"   Modo: {'TESTNET ⚠️  — NÃO opera com dinheiro real' if USE_TESTNET else 'PRODUÇÃO 🔴 — capital real em risco'}")

        # Ciclo imediato ao iniciar
        self.daily_cycle()

        # Agendamento diário às 00:05 UTC
        schedule.every().day.at("00:05").do(self.daily_cycle)

        logger.info("⏰ Próximo ciclo agendado: 00:05 UTC")
        logger.info("   Verificando SL/TP a cada 5 minutos...")

        while True:
            schedule.run_pending()
            self._check_sl_tp()
            time.sleep(300)  # 5 minutos


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    """
    Para que serve: Definir o ponto de entrada do programa.
    O que faz: Cria instância do TradeBot e inicia o loop principal.
    Como faz:
        1. Instancia a classe TradeBot (o __init__ já executa _initialize())
        2. Chama bot.run() que inicia o loop infinito
    """
    bot = TradeBot()
    bot.run()
