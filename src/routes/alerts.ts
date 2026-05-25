import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and, desc } from 'drizzle-orm';
import { alerts } from '../db/schema';
import { v4 as uuidv4 } from 'uuid';
import type { Env } from '../types';

/**
 * Alerts Routes
 * GET  /api/protected/alerts              - list alerts (unread first)
 * POST /api/protected/alerts/:id/read     - mark read
 * POST /api/protected/alerts/read-all     - mark all read
 * DELETE /api/protected/alerts/:id        - delete alert
 */

const alertsRouter = new Hono<{ Bindings: Env }>();

alertRouter.get('/', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const limit = parseInt(c.req.query('limit') ?? '50');

  const rows = await orm
    .select()
    .from(alerts)
    .where(eq(alerts.userId, userId))
    .orderBy(desc(alerts.triggeredAt))
    .limit(Math.min(limit, 200))
    .all();

  return c.json(rows);
});

alertRouter.post('/:id/read', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);

  const existing = await orm.select({ id: alerts.id }).from(alerts).where(and(eq(alerts.id, id), eq(alerts.userId, userId))).get();
  if (!existing) return c.json({ error: 'Alert not found' }, 404);

  await orm.update(alerts).set({ isRead: 1 }).where(eq(alerts.id, id));
  return c.json({ ok: true });
});

alertRouter.post('/read-all', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  await orm.update(alerts).set({ isRead: 1 }).where(eq(alerts.userId, userId));
  return c.json({ ok: true });
});

alertRouter.delete('/:id', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);
  const existing = await orm.select({ id: alerts.id }).from(alerts).where(and(eq(alerts.id, id), eq(alerts.userId, userId))).get();
  if (!existing) return c.json({ error: 'Alert not found' }, 404);
  await orm.delete(alerts).where(eq(alerts.id, id));
  return c.json({ ok: true });
});

export default alertsRouter;

// Helper to insert an alert (called from queue handler, trade logic, etc.)
export async function insertAlert(db: D1Database, params: {
  userId: string;
  type: typeof alerts.$inferInsert['type'];
  message: string;
  channel?: typeof alerts.$inferInsert['channel'];
}) {
  const orm = drizzle(db);
  await orm.insert(alerts).values({
    id: uuidv4(),
    userId: params.userId,
    type: params.type,
    message: params.message,
    channel: params.channel ?? 'in_app',
    triggeredAt: new Date().toISOString(),
  });
}
