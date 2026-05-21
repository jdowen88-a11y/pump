import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq, desc, and } from 'drizzle-orm';
import { trades, userSettings, tokens } from '../db/schema';
import { executeSwap } from '../services/executor';
import { v4 as uuidv4 } from 'uuid';

type Env = { DB: D1Database; KV: KVNamespace; SOLANA_RPC_URL: string; PRIVATE_KEY: string };

const tradeRoutes = new Hono<{ Bindings: Env }>();

const buySchema = z.object({
tokenMint: z.string().min(32).max(44),
amountSol: z.number().min(0.01).max(100),
slippage: z.number().min(1).max(50).optional(),
});

const sellSchema = z.object({
tokenMint: z.string().min(32).max(44),
amountToken: z.number().min(0).optional(),
slippage: z.number().min(1).max(50).optional(),
});

tradeRoutes.post('/buy', zValidator('json', buySchema), async (c) => {
const userId = c.get('userId');
const { tokenMint, amountSol, slippage } = c.req.valid('json');
const db = drizzle(c.env.DB);

const settings = await db.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
if (!settings?.autoTrade) {
return c.json({ error: 'Auto-trade is disabled in your settings' }, 403);
}

if (amountSol > (settings?.maxBuySol || 0.1)) {
return c.json({ error: Amount exceeds your max buy limit of ${settings?.maxBuySol} SOL }, 400);
}

const token = await db.select({ score: tokens.score, scamScore: tokens.scamScore }).from(tokens).where(eq(tokens.mint, tokenMint)).get();
if (!token) {
return c.json({ error: 'Token not found in our database' }, 404);
}
if (token.scamScore && token.scamScore > 70) {
return c.json({ error: 'Token flagged as potential scam' }, 400);
}
if (token.score && token.score < (settings?.minScore || 60)) {
return c.json({ error: Token score (${token.score}) below your minimum threshold (${settings?.minScore || 60}) }, 400);
}

const tradeId = uuidv4();

try {
const txSignature = await executeSwap(
'So11111111111111111111111111111111111111112',
tokenMint,
amountSol,
slippage || settings?.slippagePercent || 10,
c.env
);

```
await db.insert(trades).values({
  id: tradeId,
  userId,
  tokenMint,
  action: 'buy',
  amountSol,
  slippage: slippage || settings?.slippagePercent || 10,
  txSignature,
  status: 'confirmed',
});

return c.json({
  tradeId,
  txSignature,
  status: 'confirmed',
  explorerUrl: `https://solscan.io/tx/${txSignature}`,
}, 201);
```

} catch (error: any) {
await db.insert(trades).values({
id: tradeId,
userId,
tokenMint,
action: 'buy',
amountSol,
status: 'failed',
});

```
return c.json({ error: 'Trade execution failed', details: error.message }, 500);
```

}
});

tradeRoutes.post('/sell', zValidator('json', sellSchema), async (c) => {
const userId = c.get('userId');
const { tokenMint, slippage } = c.req.valid('json');
const db = drizzle(c.env.DB);

const settings = await db.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
const tradeId = uuidv4();

try {
const txSignature = await executeSwap(
tokenMint,
'So11111111111111111111111111111111111111112',
0,
slippage || settings?.slippagePercent || 10,
c.env
);

```
await db.insert(trades).values({
  id: tradeId,
  userId,
  tokenMint,
  action: 'sell',
  amountSol: 0,
  txSignature,
  status: 'confirmed',
});

return c.json({
  tradeId,
  txSignature,
  status: 'confirmed',
  explorerUrl: `https://solscan.io/tx/${txSignature}`,
}, 201);
```

} catch (error: any) {
await db.insert(trades).values({
id: tradeId,
userId,
tokenMint,
action: 'sell',
amountSol: 0,
status: 'failed',
});

```
return c.json({ error: 'Trade execution failed', details: error.message }, 500);
```

}
});

tradeRoutes.get('/history', async (c) => {
const userId = c.get('userId');
const db = drizzle(c.env.DB);
const limit = Math.min(parseInt(c.req.query('limit') || '50'), 200);
const offset = Math.max(parseInt(c.req.query('offset') || '0'), 0);

const history = await db.select()
.from(trades)
.where(eq(trades.userId, userId))
.orderBy(desc(trades.executedAt))
.limit(limit)
.offset(offset)
.all();

const total = await db.select({ count: trades.id })
.from(trades)
.where(eq(trades.userId, userId))
.all();

return c.json({ data: history, total: total.length, limit, offset });
});

tradeRoutes.get('/stats', async (c) => {
const userId = c.get('userId');
const db = drizzle(c.env.DB);

const userTrades = await db.select().from(trades).where(eq(trades.userId, userId)).all();

const totalTrades = userTrades.length;
const winningTrades = userTrades.filter(t => t.profitSol && t.profitSol > 0).length;
const totalProfit = userTrades.reduce((sum, t) => sum + (t.profitSol || 0), 0);
const totalVolume = userTrades.reduce((sum, t) => sum + t.amountSol, 0);

return c.json({
totalTrades,
winningTrades,
winRate: totalTrades > 0 ? ((winningTrades / totalTrades) * 100).toFixed(1) : '0',
totalProfit: totalProfit.toFixed(6),
totalVolume: totalVolume.toFixed(2),
});
});

export default tradeRoutes;