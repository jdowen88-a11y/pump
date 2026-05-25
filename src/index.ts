import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { prettyJSON } from 'hono/pretty-json';
import { z } from 'zod';
import { zValidator } from '@hono/zod-validator';
import { v4 as uuidv4 } from 'uuid';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and } from 'drizzle-orm';

import { authMiddleware } from './middleware/auth';
import { rateLimiter } from './middleware/rateLimiter';
import { errorHandler } from './middleware/errorHandler';
import { calculateBondingCurvePrice, createRobustConnection } from './utils/solana';
import { checkTradeRisk } from './utils/risk';
import { notify, buildTradeMessage } from './utils/notifier';
import { getPortfolioMetrics } from './utils/analytics';
import { insertAlert } from './routes/alerts';
import type { Env } from './types';

import authRoutes from './routes/auth';
import analyticsRouter from './routes/analytics';
import settingsRouter from './routes/settings';
import strategiesRouter from './routes/strategies';
import tokensRouter from './routes/tokens';
import alertsRouter from './routes/alerts';

import { trades, tokens, positions, userSettings, auditLogs } from './db/schema';

// ============================================================
// Durable Object: StrategyRunner - per-user persistent runner
// ============================================================
export class StrategyRunner {
  private state: DurableObjectState;
  private env: Env;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname.endsWith('/ws')) {
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair) as [WebSocket, WebSocket];
      this.state.acceptWebSocket(server);
      server.send(JSON.stringify({ type: 'connected', msg: 'StrategyRunner DO active' }));
      return new Response(null, { status: 101, webSocket: client });
    }
    return new Response(JSON.stringify({ status: 'StrategyRunner operational' }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// ============================================================
// App + Middleware
// ============================================================
const app = new Hono<{ Bindings: Env }>().use('*', errorHandler);
app.use('*', logger());
app.use('*', prettyJSON());
app.use('*', cors({ origin: '*', allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allowHeaders: ['Authorization', 'Content-Type', 'X-API-Key', 'X-Trace-Id'] }));
app.use('/api/*', rateLimiter({ limit: 120, windowSeconds: 60 }));

// ============================================================
// Public Routes
// ============================================================
app.get('/health', (c) =>
  c.json({
    status: 'OK',
    version: '3.0.0-evolved',
    ts: new Date().toISOString(),
    features: ['auth', 'risk-engine', 'trade-queue', 'analytics', 'strategies', 'alerts', 'ws', 'do', 'notifier'],
  })
);

app.get('/metrics', async (c) => {
  // Basic aggregate metrics (unauthenticated; no per-user data)
  return c.json({ ok: true, uptime: Date.now(), note: 'Per-user metrics at /api/protected/analytics/metrics' });
});

// ============================================================
// Auth Routes (public)
// ============================================================
app.route('/api/auth', authRoutes);

// ============================================================
// Protected middleware boundary
// ============================================================
app.use('/api/protected/*', authMiddleware);

// ============================================================
// Protected: Me
// ============================================================
app.get('/api/protected/me', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const user = await orm.select().from(users).where(eq(users.id, userId)).get();
  if (!user) return c.json({ error: 'User not found' }, 404);
  return c.json({ id: user.id, email: user.email, username: user.username, solanaWallet: user.solanaWallet });
});

// ============================================================
// Protected: Settings, Strategies, Tokens, Analytics, Alerts
// ============================================================
app.route('/api/protected/settings', settingsRouter);
app.route('/api/protected/strategies', strategiesRouter);
app.route('/api/protected/tokens', tokensRouter);
app.route('/api/protected/analytics', analyticsRouter);
app.route('/api/protected/alerts', alertsRouter);

// ============================================================
// Protected: Snipe - Full trade lifecycle
// ============================================================
const snipeSchema = z.object({
  mint: z.string().min(32).max(44),
  amountSol: z.number().positive().max(100),
  slippageBps: z.number().int().min(1).max(5000).optional().default(500),
  strategyId: z.string().optional(),
  useJito: z.boolean().optional(),
});

app.post('/api/protected/snipe', zValidator('json', snipeSchema), async (c) => {
  const { mint, amountSol, slippageBps, strategyId, useJito } = c.req.valid('json');
  const userId = c.get('userId') as string;
  const traceId = c.get('traceId') as string ?? uuidv4();

  // Pre-flight risk check (fast, no queue needed)
  const riskResult = await checkTradeRisk({ userId, amountSol, tokenMint: mint, db: c.env.DB });
  if (!riskResult.ok) {
    await insertAlert(c.env.DB, { userId, type: 'risk_breach', message: `Snipe blocked: ${riskResult.reason}` });
    return c.json({ ok: false, blocked: true, reason: riskResult.reason, traceId }, 422);
  }

  // Ensure token row exists (upsert minimal record)
  const orm = drizzle(c.env.DB);
  const existingToken = await orm.select({ mint: tokens.mint }).from(tokens).where(eq(tokens.mint, mint)).get();
  if (!existingToken) {
    await orm.insert(tokens).values({
      mint,
      firstSeen: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
    });
  }

  // Create pending trade
  const tradeId = uuidv4();
  await orm.insert(trades).values({
    id: tradeId,
    userId,
    tokenMint: mint,
    action: 'buy',
    amountSol,
    slippage: slippageBps ? slippageBps / 100 : 5,
    strategyId: strategyId ?? null,
    status: 'pending',
    createdAt: new Date().toISOString(),
    executedAt: new Date().toISOString(),
  });

  // Enqueue for execution
  await c.env.TRADE_QUEUE.send({
    type: 'snipe',
    tradeId,
    userId,
    mint,
    amountSol,
    slippageBps,
    strategyId,
    useJito,
    traceId,
  });

  // Audit log
  await orm.insert(auditLogs).values({
    id: uuidv4(),
    userId,
    action: 'snipe_queued',
    details: JSON.stringify({ tradeId, mint, amountSol }),
    traceId,
    createdAt: new Date().toISOString(),
  });

  return c.json({ ok: true, queued: true, tradeId, mint, amountSol, traceId });
});

// ============================================================
// Protected: Cancel pending trade
// ============================================================
app.post('/api/protected/trades/:id/cancel', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);

  const trade = await orm.select().from(trades).where(and(eq(trades.id, id), eq(trades.userId, userId))).get();
  if (!trade) return c.json({ error: 'Trade not found' }, 404);
  if (trade.status !== 'pending') return c.json({ error: `Cannot cancel trade with status: ${trade.status}` }, 400);

  await orm.update(trades).set({ status: 'cancelled', notes: 'Cancelled by user' }).where(eq(trades.id, id));
  return c.json({ ok: true, tradeId: id, status: 'cancelled' });
});

// ============================================================
// WebSocket: Real-time feed (delegated to StrategyRunner DO in prod)
// ============================================================
app.get('/ws', async (c) => {
  const upgrade = c.req.header('Upgrade');
  if (upgrade !== 'websocket') return c.text('Upgrade required', 426);

  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair) as [WebSocket, WebSocket];
  server.accept();
  server.send(
    JSON.stringify({
      type: 'welcome',
      msg: 'pump-sniper v3 real-time feed. Events: token_discovered | trade_queued | trade_confirmed | trade_failed | risk_breach',
      ts: Date.now(),
    })
  );
  return new Response(null, { status: 101, webSocket: client });
});

// ============================================================
// Default export: Worker entrypoint + Queue handler
// ============================================================
export default {
  fetch: app.fetch,
  StrategyRunner,

  async queue(batch: any, env: Env): Promise<void> {
    const orm = drizzle(env.DB);

    for (const msg of batch.messages) {
      try {
        const payload = msg.body as any;

        if (payload?.type === 'snipe') {
          const { tradeId, userId, mint, amountSol, slippageBps, strategyId, traceId } = payload;

          // Load trade
          const trade = await orm.select().from(trades).where(eq(trades.id, tradeId)).get();
          if (!trade) {
            console.error(`[queue][${traceId}] Trade not found: ${tradeId}`);
            msg.ack();
            continue;
          }

          if (trade.status === 'cancelled') {
            console.log(`[queue][${traceId}] Trade cancelled before execution: ${tradeId}`);
            msg.ack();
            continue;
          }

          // Risk re-check in queue (settings may have changed since enqueue)
          const riskResult = await checkTradeRisk({ userId, amountSol: trade.amountSol, tokenMint: mint, db: env.DB });
          if (!riskResult.ok) {
            await orm.update(trades).set({ status: 'failed', notes: `Risk check failed: ${riskResult.reason}` }).where(eq(trades.id, tradeId));
            await insertAlert(env.DB, { userId, type: 'risk_breach', message: `Trade ${tradeId} blocked in queue: ${riskResult.reason}` });

            const settings = await orm.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
            if (settings?.notificationsEnabled && settings.telegramChatId && env.TELEGRAM_BOT_TOKEN) {
              await notify({
                message: buildTradeMessage({ action: 'buy', mint, amountSol, status: 'failed', reason: riskResult.reason }),
                channel: 'telegram',
                telegramBotToken: env.TELEGRAM_BOT_TOKEN,
                telegramChatId: settings.telegramChatId,
              });
            }

            msg.ack();
            continue;
          }

          // -----------------------------------------------------------------
          // EXECUTION GATE
          // In production: decode TRADER_PRIVATE_KEY from env, call executeSnipe.
          // Kept as a configurable gate so you can toggle paper/live mode.
          // -----------------------------------------------------------------
          const privateKey = (env as any).TRADER_PRIVATE_KEY as string | undefined;
          let txSig: string | null = null;
          let execStatus: 'confirmed' | 'failed' = 'confirmed';
          let execNotes = 'paper_trade';

          if (privateKey) {
            try {
              const connection = createRobustConnection(env.SOLANA_RPC_URL);
              // TODO: Decode bs58 private key and call executeSnipe
              // const wallet = Keypair.fromSecretKey(bs58.decode(privateKey));
              // txSig = await executeSnipe(connection, wallet, new PublicKey(mint), amountSol, slippageBps ?? 500, ...);
              execNotes = 'live_trade_stub';
              console.log(`[queue][${traceId}] Live execution placeholder for tradeId ${tradeId} - wire executeSnipe here.`);
            } catch (execErr: any) {
              execStatus = 'failed';
              execNotes = `execution_error: ${execErr?.message}`;
              console.error(`[queue][${traceId}] executeSnipe error:`, execErr);
            }
          } else {
            console.log(`[queue][${traceId}] TRADER_PRIVATE_KEY not set - paper trade mode. TradeId: ${tradeId}`);
          }

          // Update trade record
          await orm.update(trades).set({
            status: execStatus,
            txSignature: txSig,
            notes: execNotes,
            executedAt: new Date().toISOString(),
          }).where(eq(trades.id, tradeId));

          // Open position record on success
          if (execStatus === 'confirmed') {
            const { v4: uuid } = await import('uuid');
            const settings = await orm.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
            const entryPrice = trade.priceSol ?? 0;
            const stopLossPrice = entryPrice > 0 && settings?.stopLossPercent
              ? entryPrice * (1 - settings.stopLossPercent / 100)
              : undefined;
            const takeProfitPrice = entryPrice > 0 && settings?.takeProfitPercent
              ? entryPrice * (1 + settings.takeProfitPercent / 100)
              : undefined;

            await orm.insert(positions).values({
              id: uuid(),
              userId,
              tokenMint: mint,
              strategyId: strategyId ?? null,
              entryPriceSol: entryPrice,
              amountToken: trade.amountToken ?? 0,
              amountSolInvested: amountSol,
              stopLossPrice: stopLossPrice ?? null,
              takeProfitPrice: takeProfitPrice ?? null,
              status: 'open',
              openedAt: new Date().toISOString(),
            });

            // Alert
            await insertAlert(env.DB, {
              userId,
              type: 'trade_fill',
              message: `Buy filled: ${amountSol} SOL into ${mint}${txSig ? ` TX: ${txSig}` : ' (paper)'}`,
            });

            if (settings?.notificationsEnabled && settings.telegramChatId && env.TELEGRAM_BOT_TOKEN) {
              await notify({
                message: buildTradeMessage({ action: 'buy', mint, amountSol, txSig: txSig ?? undefined, status: 'confirmed' }),
                channel: 'telegram',
                telegramBotToken: env.TELEGRAM_BOT_TOKEN,
                telegramChatId: settings.telegramChatId,
              });
            }
          }

          // Audit
          await orm.insert(auditLogs).values({
            id: uuidv4(),
            userId,
            action: `trade_${execStatus}`,
            details: JSON.stringify({ tradeId, mint, amountSol, txSig, notes: execNotes }),
            traceId,
            createdAt: new Date().toISOString(),
          });

          console.log(`[queue][${traceId}] Trade ${execStatus}: ${tradeId}`);
        } else {
          console.warn(`[queue] Unknown message type: ${payload?.type}`);
        }
      } catch (err: any) {
        console.error('[queue] Unhandled error:', err?.message, err?.stack?.split('\n')[0]);
      } finally {
        msg.ack();
      }
    }
  },
};
