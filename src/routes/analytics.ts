import { Hono } from 'hono';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and, desc, gte } from 'drizzle-orm';
import { trades, positions, performanceSnapshots } from '../db/schema';
import { getPortfolioMetrics } from '../utils/analytics';
import type { Env } from '../types';

/**
 * Analytics Routes
 * GET /api/protected/analytics/metrics   - live portfolio metrics
 * GET /api/protected/analytics/equity    - equity curve (snapshots)
 * GET /api/protected/analytics/trades    - trade history with filters
 * GET /api/protected/analytics/positions - open positions
 */

const analyticsRouter = new Hono<{ Bindings: Env }>();

analyticsRouter.get('/metrics', async (c) => {
  const userId = c.get('userId') as string;
  const metrics = await getPortfolioMetrics(c.env.DB, userId);
  return c.json(metrics);
});

analyticsRouter.get('/equity', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const limit = parseInt(c.req.query('limit') ?? '90');

  const snapshots = await orm
    .select()
    .from(performanceSnapshots)
    .where(eq(performanceSnapshots.userId, userId))
    .orderBy(desc(performanceSnapshots.snapshotAt))
    .limit(Math.min(limit, 365))
    .all();

  return c.json(snapshots.reverse());
});

analyticsRouter.get('/trades', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const limit = parseInt(c.req.query('limit') ?? '50');
  const since = c.req.query('since');

  const conditions: any[] = [eq(trades.userId, userId)];
  if (since) conditions.push(gte(trades.executedAt, since));

  const rows = await orm
    .select()
    .from(trades)
    .where(and(...conditions))
    .orderBy(desc(trades.executedAt))
    .limit(Math.min(limit, 500))
    .all();

  return c.json(rows);
});

analyticsRouter.get('/positions', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);

  const rows = await orm
    .select()
    .from(positions)
    .where(and(eq(positions.userId, userId), eq(positions.status, 'open')))
    .orderBy(desc(positions.openedAt))
    .all();

  return c.json(rows);
});

export default analyticsRouter;
