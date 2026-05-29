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
import runConfigRouter from './routes/runConfig';
import telemetryRouter from './routes/telemetry';

import { trades, tokens, positions, userSettings, auditLogs, users } from './db/schema';

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

const app = new Hono<{ Bindings: Env }>().use('*', errorHandler);
app.use('*', logger());
app.use('*', prettyJSON());
app.use('*', cors({ origin: '*', allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allowHeaders: ['Authorization', 'Content-Type', 'X-API-Key', 'X-Trace-Id'] }));
app.use('/api/*', rateLimiter({ limit: 120, windowSeconds: 60 }));

app.get('/health', (c) =>
  c.json({
    status: 'OK',
    version: '3.0.0-evolved',
    ts: new Date().toISOString(),
    features: ['auth', 'risk-engine', 'trade-queue', 'analytics', 'strategies', 'alerts', 'ws', 'do', 'notifier', 'run-config', 'telemetry'],
  })
);

app.get('/metrics', async (c) => {
  return c.json({ ok: true, uptime: Date.now(), note: 'Per-user metrics at /api/protected/analytics/metrics' });
});

app.route('/api/auth', authRoutes);

app.use('/api/protected/*', authMiddleware);

app.get('/api/protected/me', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const user = await orm.select().from(users).where(eq(users.id, userId)).get();
  if (!user) return c.json({ error: 'User not found' }, 404);
  return c.json({ id: user.id, email: user.email, username: user.username, solanaWallet: user.solanaWallet });
});

app.route('/api/protected/settings', settingsRouter);
app.route('/api/protected/strategies', strategiesRouter);
app.route('/api/protected/tokens', tokensRouter);
app.route('/api/protected/analytics', analyticsRouter);
app.route('/api/protected/alerts', alertsRouter);
app.route('/api/protected/run-config', runConfigRouter);
app.route('/api/protected/telemetry', telemetryRouter);

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

  const riskResult = await checkTradeRisk({ userId, amountSol, tokenMint: mint, db: c.env.DB });
  if (!riskResult.ok) {
    await insertAlert(c.env.DB, { userId, type: 'risk_breach', message: `Snipe blocked: ${riskResult.reason}` });
    return c.json({ ok: false, blocked: true, reason: riskResult.reason, traceId }, 422);
  }

  const orm = drizzle(c.env.DB);
  const existingToken = await orm.select({ mint: tokens.mint }).from(tokens).where(eq(tokens.mint, mint)).get();
  if (!existingToken) {
    await orm.insert(tokens).values({
      mint,
      firstSeen: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
    });
  }

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

app.get('/ws', async (c) => {
  const upgrade = c.req.header('Upgrade');
  if (upgrade !== 'websocket') return c.text('Upgrade required', 426);

  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair) as [WebSocket, WebSocket];
  server.accept();

  server.send(
    JSON.stringify({
      type: 'welcome',
      msg: 'pump-sniper v3 real-time feed. Events: token_discovered | trade_queued | trade_confirmed | trade_failed | risk_breach | run_config_updated | telemetry',
      ts: Date.now(),
    })
  );

  return new Response(null, {
    status: 101,
    webSocket: client,
  });
});

export default app;
