import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { prettyJSON } from 'hono/pretty-json';
import { z } from 'zod';
import { zValidator } from '@hono/zod-validator';

// Evolved imports
 import { authMiddleware, issueAccessToken } from './middleware/auth';
import { rateLimiter } from './middleware/rateLimiter';
import { errorHandler } from './middleware/errorHandler';
import { calculateBondingCurvePrice, executeSnipe, monitorNewPumpFunTokens } from './utils/solana';
import type { Env, Strategy, TradeEvent } from './types';

// Durable Object example (advanced stateful runner)
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
      const [client, server] = Object.values(pair);
      server.accept();
      server.send(JSON.stringify({ type: 'connected', msg: 'Ultimate strategy runner WS active' }));
      // In prod: persist state, subscribe to events, push P&L, signals
      return new Response(null, { status: 101, webSocket: client });
    }
    return new Response(JSON.stringify({ status: 'StrategyRunner DO operational' }), { headers: { 'Content-Type': 'application/json' } });
  }
}

// App with full middleware stack
const app = new Hono<{ Bindings: Env }>().use('*', errorHandler);

app.use('*', logger());
app.use('*', prettyJSON());
app.use('*', cors({ origin: '*', allowMethods: ['*'], allowHeaders: ['*'] })); // tighten prod

// Rate limit sensitive paths
app.use('/api/*', rateLimiter({ limit: 120, windowSeconds: 60 }));

// Health & Metrics (public)
app.get('/health', (c) => c.json({ status: 'ULTIMATE', version: '2.0.0-evolved', features: ['ws', 'do', 'queues', 'jito', 'copy', 'backtest', 'risk-engine'] }));
app.get('/metrics', (c) => c.json({ ok: true, note: 'Extend with real metrics from KV/D1' }));

// Auth
app.post('/api/auth/login', async (c) => {
  // TODO: validate body, check DB user, issue token
  const token = await issueAccessToken('demo-user-123', c.env.JWT_SECRET || 'dev');
  return c.json({ accessToken: token, expiresIn: 900 });
});

// Protected example with full stack
app.use('/api/protected/*', authMiddleware);

app.get('/api/protected/me', (c) => {
  const userId = c.get('userId');
  return c.json({ userId, traceId: c.get('traceId'), msg: 'Auth + rate limit + error handling all active' });
});

app.post('/api/protected/strategies', zValidator('json', z.object({ name: z.string(), type: z.string() })), async (c) => {
  const data = c.req.valid('json');
  // TODO: Drizzle insert to strategies, audit
  return c.json({ success: true, strategy: data });
});

// Real-time WS
app.get('/ws', async (c) => {
  // Delegate to DO in prod for per-user persistent
  const upgrade = c.req.header('Upgrade');
  if (upgrade !== 'websocket') return c.text('Upgrade required', 426);
  // Simple or DO stub
  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair);
  server.accept();
  server.send(JSON.stringify({ type: 'welcome', msg: 'pump-sniper ultimate real-time feed' }));
  return new Response(null, { status: 101, webSocket: client });
});

// Example snipe trigger (protected)
app.post('/api/protected/snipe', zValidator('json', z.object({ mint: z.string(), amountSol: z.number().positive() })), async (c) => {
  const { mint, amountSol } = c.req.valid('json');
  const userId = c.get('userId');
  // TODO: Load user settings, risk check via risk.ts, queue trade or direct executeSnipe
  // const sig = await executeSnipe(...);
  return c.json({ queued: true, mint, amountSol, userId, note: 'Integrate with TRADE_QUEUE + solana.ts' });
});

// Queue handler
export default {
  fetch: app.fetch,
  StrategyRunner,
  async queue(batch: any, env: Env) {
    for (const msg of batch.messages) {
      console.log('Queued trade processed:', msg.body);
      // TODO: risk check, executeSnipe, update positions/trades table, notify via notifier
      msg.ack();
    }
  }
};
