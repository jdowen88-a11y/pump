import { Hono } from 'hono';
import { z } from 'zod';
import { zValidator } from '@hono/zod-validator';
import type { Env } from '../types';

const telemetryRouter = new Hono<{ Bindings: Env }>();

const telemetrySchema = z.object({
  type: z.string().default('telemetry'),
  ts: z.number().optional(),
  payload: z.record(z.any()),
});

const latestKeyFor = (userId: string) => `telemetry:latest:${userId}`;
const eventsKeyFor = (userId: string) => `telemetry:events:${userId}`;

telemetryRouter.get('/latest', async (c) => {
  const userId = c.get('userId') as string;
  const raw = await c.env.KV.get(latestKeyFor(userId));
  if (!raw) return c.json({ ok: true, telemetry: null });
  return c.json({ ok: true, telemetry: JSON.parse(raw) });
});

telemetryRouter.get('/events', async (c) => {
  const userId = c.get('userId') as string;
  const raw = await c.env.KV.get(eventsKeyFor(userId));
  return c.json({ ok: true, events: raw ? JSON.parse(raw) : [] });
});

telemetryRouter.post('/ingest', zValidator('json', telemetrySchema), async (c) => {
  const userId = c.get('userId') as string;
  const body = c.req.valid('json');
  const event = {
    ...body,
    ts: body.ts ?? Date.now(),
  };

  const existingRaw = await c.env.KV.get(eventsKeyFor(userId));
  const existing = existingRaw ? JSON.parse(existingRaw) as unknown[] : [];
  const next = [event, ...existing].slice(0, 100);

  await c.env.KV.put(latestKeyFor(userId), JSON.stringify(event));
  await c.env.KV.put(eventsKeyFor(userId), JSON.stringify(next));

  return c.json({ ok: true, accepted: true, event });
});

export default telemetryRouter;
