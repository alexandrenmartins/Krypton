# Explicação: MACD_FAST, MACD_SLOW e MACD_SIGNAL

## O que é MACD (Moving Average Convergence Divergence)?

**MACD** significa **Moving Average Convergence Divergence** (Convergência e Divergência de Médias Móveis). É um indicador que identifica **mudanças de momentum** e **reversões de tendência** comparando duas médias móveis exponenciais de períodos diferentes.

### Como funciona:

O MACD é composto por **3 linhas**:

```
1. Linha MACD      = EMA(Período Rápido) - EMA(Período Lento)
2. Linha de Sinal  = EMA da Linha MACD
3. Histograma      = MACD - Sinal (mostra convergência/divergência)
```

### Componentes visuais:

```
	 Linha MACD (azul)
		  ╱╲    ╱╲    ╱╲
		 ╱  ╲  ╱  ╲  ╱  ╲
	────────────────────────  Linha de Sinal (vermelha)
		╱    ╲╱    ╲╱    ╲
	   ╱                    ╲
	───────────────────────────  Linha Zero
	   ╲                    ╱
		╲    ╱╲    ╱╲    ╱
		█████████████████████  Histograma (barras)
```

---

## MACD_FAST (período rápido = 12)

Define o **período da média móvel exponencial rápida** (EMA rápida).

### O que é EMA?

**EMA** = Exponential Moving Average (Média Móvel Exponencial)
- Dá mais peso aos candles recentes
- Reage mais rápido aos mudanças de preço que uma SMA (média simples)

### Exemplo com FAST = 12:

```
Últimos 12 candles e seus pesos na EMA:

Candle    Preço    Peso (%)
1         100.00   0.15%
2         101.50   0.27%
3         101.00   0.49%
4         102.00   0.87%
5         101.50   1.56%
6         103.00   2.78%
7         102.50   4.95%
8         104.00   8.82%
9         103.00  15.73%
10        105.00  28.07%
11        104.00  26.73%
12        107.00  ???  <- Peso maior (mais recente)

EMA(12) ≈ 103.50
		 ↑
	  Reage rápido a mudanças!
```

### Impacto do período rápido:

| Período | Sensibilidade | Tipo de Trader | Características |
|---------|---|---|---|
| **6-9** | ⚡ Ultra rápido | Scalpers | Muito sensível, muitos falsos sinais |
| **12** | ⚡ Rápido | Day/Swing traders | Padrão do MACD, recomendado |
| **20+** | ⚖️ Equilibrado | Investidores | Menos ruído |

**No Krypton: FAST = 12** → responsivo às mudanças recentes

---

## MACD_SLOW (período lento = 26)

Define o **período da média móvel exponencial lenta** (EMA lenta).

### Exemplo com SLOW = 26:

```
Últimos 26 candles:

EMA(26) leva em conta muito mais histórico
└─ Reage mais lentamente aos mudanças
└─ Representa a tendência de LONGO PRAZO
```

### Comparação Rápido vs Lento:

```
Preço oscilando:
	   ╱╲  ╱╲  ╱╲
	  ╱  ╲╱  ╲╱  ╲
	 ╱              ╲
	╱────────────────╲─  EMA(12) rápida (segue preço)
					  ╲  EMA(26) lenta (suave, lag)
```

### Impacto do período lento:

| Período | Tipo | Características |
|---------|---|---|
| **20-24** | Rápido/Normal | Menos lag, mais sensível |
| **26** | Normal/Padrão | Balanço entre rapidez e suavidade |
| **30+** | Lento | Muito suave, atraso no sinal |

**No Krypton: SLOW = 26** → tendência de médio prazo

---

## MACD_SIGNAL (período sinal = 9)

Define o **período da EMA da própria linha MACD** (linha de sinal).

### Como funciona:

```
Passo 1: Calcular MACD
	MACD = EMA(12) - EMA(26)

Passo 2: Calcular a Linha de Sinal
	Sinal = EMA(9) da linha MACD
				   ↑
			9 candles da linha MACD

Passo 3: Calcular Histograma
	Histograma = MACD - Sinal
				 ↑      ↑
			Diferença entre linhas
```

### Exemplo visual:

```
Candle 1  MACD = 0.50
Candle 2  MACD = 0.65
Candle 3  MACD = 0.45
Candle 4  MACD = 0.70
Candle 5  MACD = 0.55
Candle 6  MACD = 0.80
Candle 7  MACD = 0.60
Candle 8  MACD = 0.75
Candle 9  MACD = 0.85

Sinal (EMA9 desses valores) ≈ 0.64

Histograma = 0.85 - 0.64 = +0.21 (positivo, bullish)
```

### Impacto do período sinal:

| Período | Tipo | Características |
|---------|---|---|
| **5-7** | Rápido | Mais cruzamentos, mais sensível |
| **9** | Normal/Padrão | Balanço, recomendado |
| **14+** | Lento | Menos cruzamentos, mais confiável |

**No Krypton: SIGNAL = 9** → sinais equilibrados

---

## Como MACD Gera Sinais?

### Sinal 1: Cruzamento MACD/Sinal

```python
# Cruzamento Bullish (de baixo para cima)
if MACD(anterior) < Sinal(anterior) and MACD(atual) > Sinal(atual):
	Sinal = COMPRA ▲ (momentum positivo)

# Cruzamento Bearish (de cima para baixo)
elif MACD(anterior) > Sinal(anterior) and MACD(atual) < Sinal(atual):
	Sinal = VENDA ▼ (momentum negativo)
```

### Sinal 2: Cruzamento com Linha Zero

```python
# MACD cruza linha zero de baixo para cima
if MACD(anterior) < 0 and MACD(atual) > 0:
	Sinal = COMPRA forte ▲▲ (momentum muda)

# MACD cruza linha zero de cima para baixo
elif MACD(anterior) > 0 and MACD(atual) < 0:
	Sinal = VENDA forte ▼▼ (momentum muda)
```

### Sinal 3: Histograma

```python
# Histograma positivo e crescente
if Histograma > 0 and Histograma(atual) > Histograma(anterior):
	Momentum BULLISH ▲ (força crescente)

# Histograma negativo e decrescente
elif Histograma < 0 and abs(Histograma(atual)) > abs(Histograma(anterior)):
	Momentum BEARISH ▼ (força decrescente)
```

---

## Visualização: MACD em Ação

```
Preço
	105 ┌─────╱╲─────╱╲
	104 │    ╱  ╲   ╱  ╲
	103 │───╱────╲─╱────╲
	102 │  ╱      ╲      ╲
	101 │ ╱        ╲      ╲
		│
MACD    │      ╱╲       ╱╲
  0.50  ├─────╱──╲─────╱──╲───  MACD (azul)
  0.30  │    ╱    ╲   ╱    ╲
  0.10  │───╱──────╲─╱──────╲─  Sinal (vermelha)
  0.00  ├──────────────────────
 -0.10  │        ╱╲    ╱╲
		│       ╱  ╲  ╱  ╲
		│      ╱    ╲╱    ╲
		│
Histo   │ ████ ░░░ ████ ░░░░
		│ +    -    +    -

Legend: ████ = Histograma positivo (bullish)
		░░░░ = Histograma negativo (bearish)
```

---

## Parâmetros no Krypton

```python
# config.py
MACD_FAST = 12          # EMA rápida (12 candles)
MACD_SLOW = 26          # EMA lenta (26 candles)
MACD_SIGNAL = 9         # EMA do MACD (9 candles)

# backtest.py / tradebot.py
signals = compute_signals(
	df,
	macd_fast=MACD_FAST,      # 12
	macd_slow=MACD_SLOW,      # 26
	macd_sig=MACD_SIGNAL,     # 9
	...
)
```

---

## Exemplo Prático Completo

### Cenário 1: Cruzamento Bullish (COMPRA)

```
Anterior:
  MACD = 0.10
  Sinal = 0.15
  MACD < Sinal (MACD abaixo da sinal)

Atual:
  MACD = 0.25
  Sinal = 0.20
  MACD > Sinal (MACD cruzou acima!)

✅ SINAL DE COMPRA ▲
   Razão: MACD cruzou a linha de sinal de baixo para cima
   Momentum: Mudando para POSITIVO
```

### Cenário 2: Cruzamento Bearish (VENDA)

```
Anterior:
  MACD = 0.50
  Sinal = 0.45
  MACD > Sinal (MACD acima da sinal)

Atual:
  MACD = 0.30
  Sinal = 0.35
  MACD < Sinal (MACD cruzou abaixo!)

✅ SINAL DE VENDA ▼
   Razão: MACD cruzou a linha de sinal de cima para baixo
   Momentum: Mudando para NEGATIVO
```

### Cenário 3: Cruzamento da Linha Zero (FORTE)

```
Anterior:
  MACD = -0.10 (negativo)

Atual:
  MACD = +0.05 (cruzou zero!)

✅ SINAL FORTE DE COMPRA ▲▲
   Razão: MACD passou de negativo para positivo
   Significado: Reversão completa do momentum
   Confiança: Muito alta
```

---

## Divergências MACD (Padrões Avançados)

### Divergência Bullish (sinal de reversão de alta):

```
Preço faz novo MÍNIMO
Mas MACD NÃO faz novo mínimo
└─ Força de venda está enfraquecendo
└─ Provável reversão para alta ▲
```
```
Preço:    48 → 47 → 46 (novo mínimo)
MACD:    -0.40 → -0.30 → -0.25 (não fez novo mínimo!)
				↑
		Divergência bullish
```

### Divergência Bearish (sinal de reversão de baixa):

```
Preço faz novo MÁXIMO
Mas MACD NÃO faz novo máximo
└─ Força de compra está enfraquecendo
└─ Provável reversão para baixa ▼
```
```
Preço:    52 → 53 → 54 (novo máximo)
MACD:     +0.50 → +0.45 → +0.40 (não fez novo máximo!)
				 ↑
		Divergência bearish
```

---

## Integração no Krypton

### Como MACD é usado como FILTRO:

```python
# Em indicators.py
if supertrend_signal == 1:  # LONG
	# Verificar se MACD confirma bullish
	if macd > sinal and macd > 0:
		Sinal final = LONG ▲ (confirmado por MACD)
	else:
		Sinal final = ESPERAR (MACD não confirma)

elif supertrend_signal == -1:  # SHORT
	# Verificar se MACD confirma bearish
	if macd < sinal and macd < 0:
		Sinal final = SHORT ▼ (confirmado por MACD)
	else:
		Sinal final = ESPERAR (MACD não confirma)
```

### Vantagens da combinação:

```
Supertrend      MACD          Resultado
─────────────────────────────────────────
LONG ▲         +Bullish      ✅ COMPRA FORTE
LONG ▲         -Bearish      ⚠️ ESPERAR
SHORT ▼        -Bearish      ✅ VENDA FORTE
SHORT ▼        +Bullish      ⚠️ ESPERAR
```

---

## Comparação: MACD vs RSI vs Supertrend

| Aspecto | MACD | RSI | Supertrend |
|---|---|---|---|
| **O que mede** | Momentum/velocidade | Força/extremo | Tendência |
| **Melhor para** | Mudanças de tendência | Timing fino | Confirmação |
| **Sinais principais** | Cruzamentos | Níveis extremos | Preço vs banda |
| **Período típico** | 12/26/9 | 14 | 7/2 |
| **Lag** | Médio | Baixo | Muito baixo |
| **Uso no Krypton** | Filtro | Filtro | Sinal primário |

---

## Resumo Visual

```
┌─ MACD ────────────────────────────────────────┐
│                                               │
├─ MACD_FAST = 12 ──────────────────────────────┤
│  EMA rápida (últimos 12 candles)              │
│  Reage rápido a mudanças recentes             │
│                                               │
├─ MACD_SLOW = 26 ──────────────────────────────┤
│  EMA lenta (últimos 26 candles)               │
│  Suave, representa tendência de longo prazo  │
│                                               │
├─ MACD_SIGNAL = 9 ────────────────────────────┤
│  EMA do MACD (últimos 9 valores de MACD)      │
│  Usado para gerar cruzamentos                 │
│                                               │
├─ Histograma = MACD - Sinal ──────────────────┤
│  Barras que mostram diferença entre linhas    │
│  + = Bullish | - = Bearish                    │
│                                               │
└───────────────────────────────────────────────┘
```

---

## Fórmula Completa

```
Passo 1: Calcular EMAs
	EMA12 = Média Móvel Exponencial dos últimos 12 candles
	EMA26 = Média Móvel Exponencial dos últimos 26 candles

Passo 2: Calcular MACD
	MACD = EMA12 - EMA26

	Se EMA12 > EMA26 → MACD positivo (bullish)
	Se EMA12 < EMA26 → MACD negativo (bearish)

Passo 3: Calcular Linha de Sinal
	Sinal = EMA(9) dos valores do MACD

Passo 4: Calcular Histograma
	Histograma = MACD - Sinal

	Se Histograma > 0 → MACD acima da Sinal (bullish)
	Se Histograma < 0 → MACD abaixo da Sinal (bearish)
```

---

## Analogia Simples

> 💭 MACD é como um **acelerador de um carro**:
>
> - **EMA12** = Posição atual do pedal (reação imediata)
> - **EMA26** = Velocidade desejada (alvo de longo prazo)
> - **MACD** = Diferença entre eles (aceleração)
> - **Sinal** = Velocidade esperada (suavizada)
> - **Histograma** = Se está acelerando ou desacelerando
>
> Quando MACD (acelerador) está acima da Sinal (velocidade esperada),
> o carro está acelerando (momentum positivo)! 🚗💨

---

## Boas Práticas

✅ **Faça:**
- Use MACD como **filtro/confirmação**, não como sinal único
- Combine com Supertrend e RSI (como no Krypton)
- Observe divergências para sinais avançados
- Parâmetros 12/26/9 são padrão de mercado
- Espere confirmação (histograma positivo/negativo forte)

❌ **Não faça:**
- Não trade apenas com MACD
- Não ignore divergências
- Não mude os parâmetros frequentemente (12/26/9 é testado)
- Não trade cruzamentos de MACD em mercados muito voláteis sem confirmar com Supertrend
- Não confunda MACD com momentum absoluto (pode estar errado em tendências fortes)

---

## Parâmetros Alternativos

Se quiser ajustar MACD para diferentes estilos:

### Para Day Trading (mais rápido):
```
MACD_FAST = 8
MACD_SLOW = 17
MACD_SIGNAL = 9
└─ Mais sinais, mais falsos positivos
```

### Para Swing Trading (padrão Krypton):
```
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
└─ Equilíbrio entre rapidez e confiabilidade
```

### Para Position Trading (mais lento):
```
MACD_FAST = 19
MACD_SLOW = 39
MACD_SIGNAL = 9
└─ Menos sinais, mais confiáveis
```
