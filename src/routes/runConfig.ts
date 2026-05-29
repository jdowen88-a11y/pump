import { Hono } from 'hono';
import { z } from 'zod';
import { zValidator } from '@hono/zod-validator';
import type { Env } from '../types';

const runConfigRouter = new Hono<{ Bindings: Env }>();

const runConfigSchema = z.object({
  betUsd: z.number().positive().max(100000),
  buySol: z.number().positive().max(1000),
  targetProfitPercent: z.number().min(0).max(100000),
  stopLossPercent: z.number().min(0).max(100),
  takeProfitPercent: z.number().min(0).max(100000),
  slippagePercent: z.number().min(0).max(100),
  minScore: z.number().min(0).max(100),
  maxDevWalletPercent: z.number().min(0).max(100),
  maxSnipers: z.number().int().min(0).max(100000),
  maxTopTenPercent: z.number().min(0).max(100),
  rounds: z.number().int().min(1).max(1000000),
  requestedMode: z.enum(['dry', 'live']),
  realismMode: z.enum(['soft', 'realistic', 'full']),
  keepSeedOnly: z.boolean(),
  harshMode: z.boolean(),
});

type RunConfig = z.infer<typeof runConfigSchema>;

const keyFor = (userId: string) => `run-config:${userId}`;

runConfigRouter.get('/', async (c) => {
  const userId = c.get('userId') as string;
  const raw = await c.env.KV.get(keyFor(userId));
  if (!raw) return c.json({ ok: true, config: null });
  return c.json({ ok: true, config: JSON.parse(raw) as RunConfig });
});

runConfigRouter.post('/validate', zValidator('json', runConfigSchema), async (c) => {
  const config = c.req.valid('json');
  return c.json({ ok: true, config, warnings: buildWarnings(config) });
});

runConfigRouter.post('/', zValidator('json', runConfigSchema), async (c) => {
  const userId = c.get('userId') as string;
  const config = c.req.valid('json');
  const saved = {
    ...config,
    updatedAt: new Date().toISOString(),
  };

  await c.env.KV.put(keyFor(userId), JSON.stringify(saved));

  return c.json({ ok: true, config: saved, warnings: buildWarnings(config) });
});

function buildWarnings(config: RunConfig): string[] {
  const warnings: string[] = [];
  if (config.requestedMode === 'live') warnings.push('Live mode selected. Confirm wallet, RPC, slippage, and loss limits before execution.');
  if (config.slippagePercent > 25) warnings.push('Slippage above 25% is extremely aggressive.');
  if (config.stopLossPercent > 50) warnings.push('Stop loss above 50% allows very deep drawdown.');
  if (config.maxDevWalletPercent > 20) warnings.push('Max dev wallet percent above 20% allows concentrated deployer risk.');
  if (config.maxTopTenPercent > 20) warnings.push('Top 10 holder concentration above 20% allows whale-heavy supply.');
  if (config.minScore < 50) warnings.push('Minimum score below 50 allows weak setups.');
  return warnings;
}

export default runConfigRouter;
