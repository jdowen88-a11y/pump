import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and } from 'drizzle-orm';
import { strategies } from '../db/schema';
import { v4 as uuidv4 } from 'uuid';
import type { Env } from '../types';

/**
 * Strategies Routes
 * GET    /api/protected/strategies        - list user strategies
 * POST   /api/protected/strategies        - create strategy
 * GET    /api/protected/strategies/:id    - get single
 * PUT    /api/protected/strategies/:id    - update strategy
 * DELETE /api/protected/strategies/:id    - delete strategy
 * POST   /api/protected/strategies/:id/activate   - activate
 * POST   /api/protected/strategies/:id/deactivate - deactivate
 */

const strategiesRouter = new Hono<{ Bindings: Env }>();

const strategySchema = z.object({
  name: z.string().min(1).max(100),
  type: z.enum(['snipe', 'copy_trade', 'volume_breakout', 'mean_reversion', 'post_raydium_momentum', 'custom']),
  params: z.record(z.any()).optional(),
  isActive: z.boolean().optional().default(true),
  priority: z.number().int().optional().default(0),
});

strategiesRouter.get('/', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);
  const rows = await orm.select().from(strategies).where(eq(strategies.userId, userId)).all();
  return c.json(rows);
});

strategiesRouter.post('/', zValidator('json', strategySchema), async (c) => {
  const userId = c.get('userId') as string;
  const body = c.req.valid('json');
  const orm = drizzle(c.env.DB);

  const id = uuidv4();
  await orm.insert(strategies).values({
    id,
    userId,
    name: body.name,
    type: body.type,
    params: body.params ? JSON.stringify(body.params) : null,
    isActive: body.isActive ? 1 : 0,
    priority: body.priority ?? 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });

  const row = await orm.select().from(strategies).where(eq(strategies.id, id)).get();
  return c.json(row, 201);
});

strategiesRouter.get('/:id', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);

  const row = await orm.select().from(strategies).where(and(eq(strategies.id, id), eq(strategies.userId, userId))).get();
  if (!row) return c.json({ error: 'Strategy not found' }, 404);
  return c.json(row);
});

strategiesRouter.put('/:id', zValidator('json', strategySchema.partial()), async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const body = c.req.valid('json');
  const orm = drizzle(c.env.DB);

  const existing = await orm.select({ id: strategies.id }).from(strategies).where(and(eq(strategies.id, id), eq(strategies.userId, userId))).get();
  if (!existing) return c.json({ error: 'Strategy not found' }, 404);

  const patch: Record<string, any> = { updatedAt: new Date().toISOString() };
  if (body.name !== undefined) patch.name = body.name;
  if (body.type !== undefined) patch.type = body.type;
  if (body.params !== undefined) patch.params = JSON.stringify(body.params);
  if (body.isActive !== undefined) patch.isActive = body.isActive ? 1 : 0;
  if (body.priority !== undefined) patch.priority = body.priority;

  await orm.update(strategies).set(patch).where(eq(strategies.id, id));

  const updated = await orm.select().from(strategies).where(eq(strategies.id, id)).get();
  return c.json(updated);
});

strategiesRouter.delete('/:id', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);

  const existing = await orm.select({ id: strategies.id }).from(strategies).where(and(eq(strategies.id, id), eq(strategies.userId, userId))).get();
  if (!existing) return c.json({ error: 'Strategy not found' }, 404);

  await orm.delete(strategies).where(eq(strategies.id, id));
  return c.json({ ok: true });
});

strategiesRouter.post('/:id/activate', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);
  const existing = await orm.select({ id: strategies.id }).from(strategies).where(and(eq(strategies.id, id), eq(strategies.userId, userId))).get();
  if (!existing) return c.json({ error: 'Strategy not found' }, 404);
  await orm.update(strategies).set({ isActive: 1, updatedAt: new Date().toISOString() }).where(eq(strategies.id, id));
  return c.json({ ok: true, active: true });
});

strategiesRouter.post('/:id/deactivate', async (c) => {
  const userId = c.get('userId') as string;
  const id = c.req.param('id');
  const orm = drizzle(c.env.DB);
  const existing = await orm.select({ id: strategies.id }).from(strategies).where(and(eq(strategies.id, id), eq(strategies.userId, userId))).get();
  if (!existing) return c.json({ error: 'Strategy not found' }, 404);
  await orm.update(strategies).set({ isActive: 0, updatedAt: new Date().toISOString() }).where(eq(strategies.id, id));
  return c.json({ ok: true, active: false });
});

export default strategiesRouter;
