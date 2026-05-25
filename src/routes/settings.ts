import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq } from 'drizzle-orm';
import { userSettings, users } from '../db/schema';
import type { Env } from '../types';

/**
 * Settings Routes
 * GET  /api/protected/settings       - get user's risk + trading config
 * PUT  /api/protected/settings       - update user's risk + trading config
 * PUT  /api/protected/settings/wallet - update solana wallet address
 */

const settingsRouter = new Hono<{ Bindings: Env }>();

const settingsSchema = z.object({
  autoTrade: z.boolean().optional(),
  maxBuySol: z.number().positive().max(100).optional(),
  minScore: z.number().int().min(0).max(100).optional(),
  slippagePercent: z.number().int().min(1).max(50).optional(),
  maxSlippagePercent: z.number().int().min(1).max(100).optional(),
  takeProfitPercent: z.number().min(1).max(10000).optional(),
  stopLossPercent: z.number().min(1).max(100).optional(),
  maxOpenPositions: z.number().int().min(1).max(100).optional(),
  maxDailyLossSol: z.number().positive().optional(),
  riskPerTradePercent: z.number().min(0.1).max(100).optional(),
  notificationsEnabled: z.boolean().optional(),
  telegramChatId: z.string().optional(),
  jitoTipLamports: z.number().int().min(0).optional(),
  useJito: z.boolean().optional(),
});

settingsRouter.get('/', async (c) => {
  const userId = c.get('userId') as string;
  const orm = drizzle(c.env.DB);

  const s = await orm.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
  if (!s) return c.json({ error: 'Settings not found' }, 404);

  return c.json(s);
});

settingsRouter.put('/', zValidator('json', settingsSchema), async (c) => {
  const userId = c.get('userId') as string;
  const body = c.req.valid('json');
  const orm = drizzle(c.env.DB);

  const existing = await orm.select({ userId: userSettings.userId }).from(userSettings).where(eq(userSettings.userId, userId)).get();

  const patch: Record<string, any> = {};
  if (body.autoTrade !== undefined) patch.autoTrade = body.autoTrade ? 1 : 0;
  if (body.maxBuySol !== undefined) patch.maxBuySol = body.maxBuySol;
  if (body.minScore !== undefined) patch.minScore = body.minScore;
  if (body.slippagePercent !== undefined) patch.slippagePercent = body.slippagePercent;
  if (body.maxSlippagePercent !== undefined) patch.maxSlippagePercent = body.maxSlippagePercent;
  if (body.takeProfitPercent !== undefined) patch.takeProfitPercent = body.takeProfitPercent;
  if (body.stopLossPercent !== undefined) patch.stopLossPercent = body.stopLossPercent;
  if (body.maxOpenPositions !== undefined) patch.maxOpenPositions = body.maxOpenPositions;
  if (body.maxDailyLossSol !== undefined) patch.maxDailyLossSol = body.maxDailyLossSol;
  if (body.riskPerTradePercent !== undefined) patch.riskPerTradePercent = body.riskPerTradePercent;
  if (body.notificationsEnabled !== undefined) patch.notificationsEnabled = body.notificationsEnabled ? 1 : 0;
  if (body.telegramChatId !== undefined) patch.telegramChatId = body.telegramChatId;
  if (body.jitoTipLamports !== undefined) patch.jitoTipLamports = body.jitoTipLamports;
  if (body.useJito !== undefined) patch.useJito = body.useJito ? 1 : 0;
  patch.updatedAt = new Date().toISOString();

  if (!existing) {
    await orm.insert(userSettings).values({ userId, ...patch });
  } else {
    await orm.update(userSettings).set(patch).where(eq(userSettings.userId, userId));
  }

  const updated = await orm.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
  return c.json(updated);
});

settingsRouter.put('/wallet', zValidator('json', z.object({ solanaWallet: z.string().min(32).max(44) })), async (c) => {
  const userId = c.get('userId') as string;
  const { solanaWallet } = c.req.valid('json');
  const orm = drizzle(c.env.DB);
  await orm.update(users).set({ solanaWallet, updatedAt: new Date().toISOString() }).where(eq(users.id, userId));
  return c.json({ ok: true, solanaWallet });
});

export default settingsRouter;
