# Explicação: SUPERTREND, PERIOD, MULTIPLIER e ATR

## O que é ATR (Average True Range)?

**ATR** significa **Average True Range** (Intervalo Verdadeiro Médio). É um indicador que mede a **volatilidade** do ativo.

### Como funciona:

1. **True Range (TR)** = a maior das 3 diferenças:
   - `High - Low` (máximo - mínimo do candle)
   - `|High - Close anterior|` (máximo atual vs fechamento anterior)
   - `|Low - Close anterior|` (mínimo atual vs fechamento anterior)

2. **ATR** = média móvel simples dos últimos N candles de TR

### Exemplo prático:

```
Candle de hoje:
  High: 50.00
  Low:  48.00
  Close anterior: 49.50

True Range = max(50-48, |50-49.5|, |48-49.5|)
		   = max(2.00, 0.50, 1.50)
		   = 2.00

Se ATR(14) = 1.50, significa que em média o ativo oscila 1.50 de amplitude por dia
```

**Interpretação:**
- ✅ ATR alto = ativo volatilidade alta (boas oportunidades, maior risco)
- ✅ ATR baixo = ativo com pouca volatilidade (mercado tranquilo, menor risco)

---

## O que é SUPERTREND?

**Supertrend** é um indicador que identifica **tendências e pontos de entrada/saída** usando o ATR.

### Componentes:

```
Supertrend = (High + Low) / 2 ± (MULTIPLIER × ATR)
```


- **HL/2** = preço médio do período
- **Multiplier × ATR** = banda de volatilidade

### Valores típicos:

```python
SUPERTREND_PERIOD = 7        # Período do ATR (7 candles)
SUPERTREND_MULTIPLIER = 2    # Multiplicador (2x a volatilidade)
```

---

## SUPERTREND_PERIOD (período = 7)

Define **quantos candles** são usados para calcular a média do ATR.

### Exemplo com PERIOD = 7:

```
Candle 1: TR = 1.50
Candle 2: TR = 1.80
Candle 3: TR = 1.20
Candle 4: TR = 2.00
Candle 5: TR = 1.70
Candle 6: TR = 1.90
Candle 7: TR = 1.60

ATR(7) = (1.50 + 1.80 + 1.20 + 2.00 + 1.70 + 1.90 + 1.60) / 7 = 1.67
```

### Impacto do período:

| Período | Sensibilidade | Tipo de Trader |
|---------|---|---|
| **3-7** | ⚡ Alta (mais rápido) | Day traders, scalpers |
| **10-14** | ⚖️ Equilibrado | Swing traders |
| **20+** | 🐢 Baixa (mais lento) | Investidores |

**No Krypton: PERIOD = 7** → estratégia reativa, sensível às mudanças rápidas

---

## SUPERTREND_MULTIPLIER (multiplicador = 2)

Define a **largura da banda** ao redor do preço médio.

### Exemplo com MULTIPLIER = 2:

```
Preço médio (HL/2)        = 50.00
ATR(7)                    = 1.67
Multiplicador             = 2

Banda alta = 50.00 + (2 × 1.67) = 50.00 + 3.34 = 53.34
Banda baixa = 50.00 - (2 × 1.67) = 50.00 - 3.34 = 46.66

Supertrend oscila entre 46.66 e 53.34
```

### Impacto do multiplicador:

| Multiplicador | Banda | Sinais | Risco |
|---|---|---|---|
| **1.0x** | 🔶 Estreita | ⚡ Muitos sinais (falsos) | 🔴 Alto |
| **2.0x** | ⚖️ Normal | ✅ Equilibrado | ✅ Moderado |
| **3.0x** | 🔵 Larga | 🐢 Poucos sinais | 🟢 Baixo |

**No Krypton: MULTIPLIER = 2** → equilíbrio entre sensibilidade e redução de falsos sinais

---

## Como Supertrend Gera Sinais?

```python
# Pseudocódigo
if preço > supertrend_upper:
	Sinal = LONG ▲    # Compra: preço acima da banda

elif preço < supertrend_lower:
	Sinal = SHORT ▼   # Venda: preço abaixo da banda

else:
	Sinal = FLAT —    # Aguardando confirmação
```

### Visualização (gráfico):

```
	   Supertrend Upper ──────────
		  (banda alta)      ╱╲     ╱╲
						  ╱  ╲   ╱  ╲  LONG ▲
	Preço médio ─────────────────────────────
						  ╲  ╱   ╲  ╱  SHORT ▼
	   Supertrend Lower ──────────
		  (banda baixa)      ╱╲     ╱╲
```

---

## Integração no Krypton

### Na estratégia:

```python
# config.py
SUPERTREND_PERIOD = 7          # Usa últimos 7 candles
SUPERTREND_MULTIPLIER = 2      # Banda = 2× ATR

# backtest.py / tradebot.py
signals = compute_signals(
	df,
	st_period=SUPERTREND_PERIOD,      # 7 candles
	st_mult=SUPERTREND_MULTIPLIER,    # 2× ATR
	...
)
```

### Uso prático no bot:

```python
# Em tradebot.py
current_atr = compute_atr(df["high"], df["low"], df["close"]).iloc[-1]

# Dimensionar posição baseado em volatilidade
if atr > 2.0:
	# Volatilidade alta → posição menor (mais risco)
	position_size = capital * 0.02  # 2% do capital
else:
	# Volatilidade baixa → posição maior (menos risco)
	position_size = capital * 0.05  # 5% do capital
```

---

## Resumo Visual

```
┌─ SUPERTREND ────────────────────────────────┐
│                                              │
│  Mede tendência usando volatilidade (ATR)   │
│                                              │
├─ ATR(7) ────────────────────────────────────┤
│  Volatilidade dos últimos 7 candles         │
│  Se ATR = 1.50 → mercado oscila 1.50/dia  │
│                                              │
├─ MULTIPLIER = 2 ────────────────────────────┤
│  Banda = Preço ± (2 × ATR)                  │
│  Preço > banda alta  → LONG ▲               │
│  Preço < banda baixa → SHORT ▼              │
│                                              │
└──────────────────────────────────────────────┘
```

---

## Analogia simples:

> 💭 Imagine que você está em uma rua com trânsito variável (volatilidade):
> 
> - **ATR** = a velocidade média dos carros (velocidade = volatilidade)
> - **SUPERTREND** = as faixas da rua que indicam a direção do trânsito
> - **MULTIPLIER** = a largura das faixas (2× mais larga = menos acidentes)
> - **PERIOD** = quantos minutos você observa para calcular a velocidade média
