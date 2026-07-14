# Configuração da API Binance para o Krypton TradeBot

## O que é a API da Binance?

A API (Application Programming Interface) da Binance é uma interface que permite que programas de computador se comuniquem diretamente com a plataforma de trading da Binance, sem precisar usar o site ou aplicativo.

O Krypton TradeBot usa essa API para:
1. Ler dados de mercado (preços, candles OHLCV, orderbook)
2. Consultar saldos da conta
3. Enviar ordens de compra/venda automaticamente (apenas limit orders)
4. Cancelar ordens pendentes

---

## Passo a Passo para Configurar

### 1. Criar Conta na Binance
- Acesse https://www.binance.com
- Crie uma conta e complete a verificação KYC (identidade)
- Ative a autenticação de dois fatores (2FA) — obrigatório

### 2. Criar a Chave de API
1. Faça login na Binance
2. Clique no ícone de perfil → API Management (Gerenciamento de API)
3. Clique em "Create API"
4. Dê um nome ao label (ex: "KryptonBot")
5. Clique em "Create API"

### 3. Configurar Permissões da API

| Permissão               | Status  | Motivo                                    |
|-------------------------|---------|-------------------------------------------|
| Enable Reading          | ✅ SIM  | O bot precisa ler preços e saldos         |
| Enable Spot & Margin    | ✅ SIM  | O bot precisa enviar ordens               |
| Enable Withdrawals      | ❌ NUNCA| Segurança — evitar saques não autorizados |
| Enable Futures          | ❌ NUNCA| O bot não usa futuros                     |

### 4. Restringir por IP (Obrigatório)
1. Na página da API, encontre "IP Access Restriction"
2. Selecione "Restrict access to trusted IPs only"
3. Adicione o IP público do seu VPS
   - Para descobrir o IP: `curl ifconfig.me`
4. Salve as alterações

### 5. Copiar as Chaves
- **API Key** — ex: `aBcDeFgHiJkLmNoPqRsT`
- **Secret Key** — ex: `xYzAbCdEfGhIjKlMnOpQrStUvWxYz`

⚠️ Anote a Secret Key agora! Ela só aparece uma vez.

### 6. Configurar no Projeto

```bash
cd Krypton
cp .env.example .env
```

Edite o arquivo `.env`:

```
BINANCE_API_KEY=sua_chave_api_aqui
BINANCE_API_SECRET=seu_secret_aqui
```

### 7. Testar na Testnet (Obrigatório)

1. Acesse https://testnet.binance.vision/
2. Faça login com sua conta Binance (GitHub login)
3. Gere uma API key separada para testnet
4. Substitua as chaves no `.env` pelas chaves da testnet
5. Execute por mínimo 30 dias antes de usar dinheiro real

```bash
python tradebot.py
```

### 8. Migrar para Produção (após 30 dias estável)

1. Em `config.py`: `USE_TESTNET = False`
2. Substitua as chaves no `.env` pelas chaves da produção
3. Reinicie o bot

---

## Por que só Ordens Limit?

O projeto usa apenas ordens limit (nunca market) porque:
- Controle de slippage — máximo 0,5% do mid-price
- Segurança — evita execução em preços adversos
- Previsibilidade — preço exato de compra/venda

---

## Dicas de Segurança

1. Nunca compartilhe suas chaves de API
2. Não commit o arquivo `.env` no Git (já está no `.gitignore`)
3. Monitore regularmente o histórico de trades
4. Revogue imediatamente a API se suspeitar de comprometimento
5. Use um VPS dedicado — não rode em computador pessoal

---

## Fluxo de Segurança Resumido

```
Criar conta Binance + KYC + 2FA
        ↓
Criar API key (leitura + spot trading)
        ↓
Restringir IP ao VPS
        ↓
Usar Testnet por ≥30 dias
        ↓
Só então usar Produção
        ↓
Nunca habilitar saques ou futuros
        ↓
Monitorar logs semanalmente
```
