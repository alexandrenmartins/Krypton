# Explicação: RSI_PERIOD, RSI_LOW e RSI_HIGH

## O que é RSI (Relative Strength Index)?

**RSI** significa **Relative Strength Index** (Índice de Força Relativa). É um indicador que mede a **força** e a **velocidade** dos movimentos de preço, identificando se um ativo está **sobrecomprado** ou **sobrevendido**.

### Como funciona:

O RSI compara os ganhos médios com as perdas médias em um período específico:

```
RSI = 100 - (100 / (1 + RS))

Onde:
RS = Ganho médio / Perda média (em valor absoluto)
```

### Escala do RSI:

```
	0 ───────────────────────────────────────── 100
	│                                           │
	│  0-30: Sobrevendido 🔴                    │
	│  (possível compra)                        │
	│                                           │
	│  30-70: Zona neutra ⚖️                    │
	│  (sem extremo)                            │
	│                                           │
	│                      70-100: Sobrecomprado 🟢
	│                      (possível venda)
```

---

## RSI_PERIOD (período = 14)

Define **quantos candles** são usados para calcular a força relativa.

### Exemplo com PERIOD = 14:

```
Candles 1-14 (últimas 14 barras):

Candle   Fechamento   Variação
1        100.00       
2        101.50       +1.50 (ganho)
3        101.00       -0.50 (perda)
4        102.00       +1.00 (ganho)
5        101.50       -0.50 (perda)
6        103.00       +1.50 (ganho)
7        102.50       -0.50 (perda)
8        104.00       +1.50 (ganho)
9        103.00       -1.00 (perda)
10       105.00       +2.00 (ganho)
11       104.00       -1.00 (perda)
12       106.00       +2.00 (ganho)
13       105.00       -1.00 (perda)
14       107.00       +2.00 (ganho)

Ganho médio = (1.50 + 1.00 + 1.50 + 1.50 + 2.00 + 2.00 + 2.00) / 14 = 1.64
Perda média = (0.50 + 0.50 + 0.50 + 1.00 + 1.00 + 1.00) / 14 = 0.64

RS = 1.64 / 0.64 = 2.56
RSI = 100 - (100 / (1 + 2.56)) = 100 - 28 = 72
```

### Impacto do período:

| Período | Sensibilidade | Tipo de Trader | Características |
|---------|---|---|---|
| **7-9** | ⚡ Alta (mais rápido) | Day traders, scalpers | Muitos sinais, mais falsos positivos |
| **14** | ⚖️ Equilibrado | Swing traders | Padrão da indústria, recomendado |
| **21-30** | 🐢 Baixa (mais lento) | Investidores | Menos sinais, mais confiáveis |

**No Krypton: PERIOD = 14** → padrão de mercado, amplamente testado

---

## RSI_LOW (limite inferior = 30)

Define o **nível de sobrevendido**. Quando RSI cai abaixo deste valor, o ativo está sobrevendido.

### O que significa sobrevendido?

```
RSI < 30 → Ativo foi vendido demais
		 → Possível reversão de alta
		 → Sinal potencial de COMPRA ▲
```

### Exemplo prático:

```
RSI = 25 (abaixo de 30)
└─ Muitos traders venderam
└─ Preço caiu muito
└─ Possibilidade de COMPRA (recuperação)
```

### Interpretação:

- ✅ RSI = 20 → muito sobrevendido, forte sinal de compra
- ✅ RSI = 28 → sobrevendido, considerar compra
- ⚠️  RSI = 35 → começando a sair da zona de sobrevendido

---

## RSI_HIGH (limite superior = 70)

Define o **nível de sobrecomprado**. Quando RSI sobe acima deste valor, o ativo está sobrecomprado.

### O que significa sobrecomprado?

```
RSI > 70 → Ativo foi comprado demais
		→ Possível reversão de baixa
		→ Sinal potencial de VENDA ▼
```

### Exemplo prático:

```
RSI = 78 (acima de 70)
└─ Muitos traders compraram
└─ Preço subiu muito
└─ Possibilidade de VENDA (queda/consolidação)
```

### Interpretação:

- ✅ RSI = 85 → muito sobrecomprado, forte sinal de venda
- ✅ RSI = 72 → sobrecomprado, considerar venda
- ⚠️  RSI = 68 → começando a sair da zona de sobrecomprado

---

## Como RSI Gera Sinais no Krypton?

```python
# Pseudocódigo da estratégia
if RSI < RSI_LOW (30):
	Sinal potencial = COMPRA ▲ (sobrevendido)

elif RSI > RSI_HIGH (70):
	Sinal potencial = VENDA ▼ (sobrecomprado)

else:
	Sinal = ESPERAR (RSI na zona neutra)
```

### Filtro no Krypton:

No Krypton, RSI é usado como **filtro** junto com Supertrend e MACD:

```python
# Apenas CONFIRMA sinais, não gera sozinho
if supertrend_signal == LONG and RSI < 50:
	Comprar (RSI confirma força de compra)

elif supertrend_signal == SHORT and RSI > 50:
	Vender (RSI confirma força de venda)
```

---

## Visualização: RSI em Ação

```
RSI = 100%
		 │   ╱╲      ╱╲      ╱╲
	70%  ├──╱──╲────╱──╲────╱──╲───  SOBRECOMPRADO 🟢
		 │      ╲╱      ╲╱      ╲╱
	50%  ├─────────────────────────  Neutro ⚖️
		 │      ╱╲      ╱╲      ╱╲
	30%  ├──────╲────╱──╲────╱──╱───  SOBREVENDIDO 🔴
		 │      ╱╲╱      ╱╲╱      ╱╲
	0%   └─────────────────────────
		 Tempo ───────────────────>
```

### Interpretação no gráfico:

- 🟢 Picos acima de 70 = vender (ganhos foram demais)
- 🔴 Vales abaixo de 30 = comprar (queda foi demais)
- ⚖️ RSI próximo de 50 = mercado equilibrado

---

## Parâmetros no Krypton

```python
# config.py
RSI_PERIOD = 14        # Últimos 14 candles
RSI_LOW = 30           # Limite de sobrevendido
RSI_HIGH = 70          # Limite de sobrecomprado

# backtest.py / tradebot.py
signals = compute_signals(
	df,
	rsi_period=RSI_PERIOD,     # 14
	rsi_low=RSI_LOW,           # 30
	rsi_high=RSI_HIGH,         # 70
	...
)
```

---

## Exemplo Prático Completo

### Cenário 1: Sinal de COMPRA

```
Preço: $50.00 (caiu muito)
RSI: 25 (sobrevendido)
Supertrend: LONG ▲
MACD: Bullish

✅ COMPRAR
   Razão: Preço caiu demais (RSI < 30)
   Risco: Baixo (confirmado por 3 indicadores)
```

### Cenário 2: Sinal de VENDA

```
Preço: $52.00 (subiu muito)
RSI: 82 (sobrecomprado)
Supertrend: SHORT ▼
MACD: Bearish

✅ VENDER
   Razão: Preço subiu demais (RSI > 70)
   Risco: Baixo (confirmado por 3 indicadores)
```

### Cenário 3: SEM SINAL (Falso positivo evitado)

```
Preço: $51.00 (em alta)
RSI: 65 (na zona neutra, não sobrecomprado)
Supertrend: SHORT ▼ (conflita!)
MACD: Bullish (conflita!)

❌ NÃO FAZER NADA
   Razão: RSI não confirma reversão
   Melhor esperar convergência dos indicadores
```

---

## Divergências RSI (Padrões Avançados)

### Divergência Bullish (sinal de reversão de alta):

```
Preço faz novo MÍNIMO
Mas RSI NÃO faz novo mínimo
└─ Força de venda está enfraquecendo
└─ Provável reversão para alta ▲
```
```
Preço: 48 → 47 → 46 (novo mínimo)
RSI:   28 → 32 → 35 (não fez novo mínimo!)
			↑
		Divergência bullish
```

### Divergência Bearish (sinal de reversão de baixa):

```
Preço faz novo MÁXIMO
Mas RSI NÃO faz novo máximo
└─ Força de compra está enfraquecendo
└─ Provável reversão para baixa ▼
```
```
Preço: 52 → 53 → 54 (novo máximo)
RSI:   75 → 72 → 68 (não fez novo máximo!)
			↑
		Divergência bearish
```

---

## Comparação: RSI vs Supertrend

| Aspecto | RSI | Supertrend |
|---|---|---|
| **O que mede** | Força/momentum | Tendência |
| **Escala** | 0-100 | Preço |
| **Sinais extremos** | RSI > 70 ou < 30 | Preço acima/abaixo da banda |
| **Melhor para** | Timing de entrada | Confirmação de tendência |
| **Período típico** | 14 | 7 |
| **Uso no Krypton** | Filtro | Sinal primário |

---

## Resumo Visual

```
┌─ RSI (Relative Strength Index) ──────────────┐
│                                              │
├─ RSI_PERIOD = 14 ───────────────────────────┤
│  Calcula força dos últimos 14 candles       │
│  Ganho médio / Perda média                  │
│                                              │
├─ RSI_LOW = 30 ──────────────────────────────┤
│  Abaixo de 30 = SOBREVENDIDO 🔴             │
│  Sinal de COMPRA potencial                  │
│                                              │
├─ RSI_HIGH = 70 ─────────────────────────────┤
│  Acima de 70 = SOBRECOMPRADO 🟢             │
│  Sinal de VENDA potencial                   │
│                                              │
└──────────────────────────────────────────────┘
```

---

## Analogia Simples

> 💭 RSI é como um **termômetro emocional do mercado**:
>
> - **RSI baixo (< 30)** = Mercado com medo 😨 (vendeu demais)
> - **RSI normal (30-70)** = Mercado calmo 😐 (equilibrado)
> - **RSI alto (> 70)** = Mercado ganancioso 🤑 (comprou demais)
>
> A reação natural das emoções extremas é sempre a volta ao normal!

---

## Boas Práticas

✅ **Faça:**
- Use RSI como **confirmação**, não como sinal único
- Combine com Supertrend e MACD (como no Krypton)
- Observe divergências para sinais avançados
- Período 14 é padrão e confiável

❌ **Não faça:**
- Não trade apenas com RSI
- Não ignore divergências RSI
- Não mude o período frequentemente
- Não confie em RSI em mercados muito ilegais (gaps)
