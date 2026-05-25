import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq, gte, desc, and } from 'drizzle-orm';
import { tokens } from '../db/schema';
import { PUMPFUN_WS_URL, SCAM_THRESHOLD, PROFIT_SCORE_THRESHOLD } from '../utils/constants';
import type { Env } from '../types';

/**
 * Token Routes
 * GET /api/protected/tokens           - recent tokens, filterable by score
 * GET /api/protected/tokens/:mint     - single token detail
 * POST /api/protected/tokens/discover - trigger/status of live discovery feed
 * GET /api/protected/tokens/hot       - top scoring, low scam tokens right now
 */

const tokensRouter = new Hono<{ Bindings: Env }>();

tokensRouter.get('/', async (c) => {
  const orm = drizzle(c.env.DB);
  const minScore = parseFloat(c.req.query('minScore') ?? String(PROFIT_SCORE_THRESHOLD));
  const limit = parseInt(c.req.query('limit') ?? '50');

  const rows = await orm
    .select()
    .from(tokens)
    .where(gte(tokens.score, minScore))
    .orderBy(desc(tokens.firstSeen))
    .limit(Math.min(limit, 200))
    .all();

  return c.json(rows);
});

tokensRouter.get('/hot', async (c) => {
  const orm = drizzle(c.env.DB);
  const rows = await orm
    .select()
    .from(tokens)
    .where(and(gte(tokens.score, PROFIT_SCORE_THRESHOLD), gte(tokens.scamScore, 0)))
    .orderBy(desc(tokens.score))
    .limit(20)
    .all();

  // Filter out rug risk
  const safe = rows.filter((t) => (t.scamScore ?? 0) < SCAM_THRESHOLD && !t.isRugRisk);
  return c.json(safe);
});

tokensRouter.get('/:mint', async (c) => {
  const mint = c.req.param('mint');
  const orm = drizzle(c.env.DB);
  const token = await orm.select().from(tokens).where(eq(tokens.mint, mint)).get();
  if (!token) return c.json({ error: 'Token not found' }, 404);
  return c.json(token);
});

// Discovery feed status / trigger
tokensRouter.post('/discover', async (c) => {
  // The Python master_bot.py or a Durable Object monitors pump.fun WS.
  // This endpoint returns connection info for the client to subscribe directly,
  // or triggers a background discovery job if you have a DO runner.
  return c.json({
    wsUrl: PUMPFUN_WS_URL,
    note: 'Subscribe to pump.fun WS via master_bot.py or StrategyRunner DO for real-time discovery. Tokens are written to DB as they are found.',
    status: 'operational',
  });
});

export default tokensRouter;
