import type { D1Database } from '@cloudflare/workers-types';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and, gte, sql } from 'drizzle-orm';
import { userSettings, trades, positions } from '../db/schema';

/**
 * Risk Engine
 * Validates any trade attempt against user settings and portfolio state.
 * Returns { ok: true } or { ok: false, reason: string }.
 */

export interface RiskCheckResult {
  ok: boolean;
  reason?: string;
}

export interface RiskCheckInput {
  userId: string;
  amountSol: number;
  tokenMint: string;
  db: D1Database;
}

export async function checkTradeRisk(input: RiskCheckInput): Promise<RiskCheckResult> {
  const { userId, amountSol, tokenMint, db } = input;
  const orm = drizzle(db);

  // 1. Load user settings
  const settings = await orm
    .select()
    .from(userSettings)
    .where(eq(userSettings.userId, userId))
    .get();

  if (!settings) {
    return { ok: false, reason: 'No user settings found. Please configure your risk parameters.' };
  }

  // 2. Auto-trade gate
  if (!settings.autoTrade) {
    return { ok: false, reason: 'Auto-trade is disabled in your settings.' };
  }

  // 3. Per-trade size limit
  const maxBuy = settings.maxBuySol ?? 0.1;
  if (amountSol > maxBuy) {
    return { ok: false, reason: `Trade size ${amountSol} SOL exceeds max_buy_sol ${maxBuy} SOL.` };
  }

  // 4. Open position count limit
  const openCount = await orm
    .select({ count: sql<number>`count(*)` })
    .from(positions)
    .where(and(eq(positions.userId, userId), eq(positions.status, 'open')))
    .get();

  const maxOpen = settings.maxOpenPositions ?? 5;
  if ((openCount?.count ?? 0) >= maxOpen) {
    return { ok: false, reason: `Max open positions (${maxOpen}) reached.` };
  }

  // 5. Daily loss limit
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  const todayLoss = await orm
    .select({ total: sql<number>`COALESCE(SUM(profit_sol), 0)` })
    .from(trades)
    .where(
      and(
        eq(trades.userId, userId),
        eq(trades.status, 'confirmed'),
        gte(trades.executedAt, todayStart.toISOString())
      )
    )
    .get();

  const dailyPnl = todayLoss?.total ?? 0;
  const maxDailyLoss = settings.maxDailyLossSol ?? 1.0;
  if (dailyPnl < 0 && Math.abs(dailyPnl) >= maxDailyLoss) {
    return { ok: false, reason: `Daily loss limit of ${maxDailyLoss} SOL reached. Pausing new trades.` };
  }

  return { ok: true };
}

export async function getUserSettings(db: D1Database, userId: string) {
  const orm = drizzle(db);
  return orm.select().from(userSettings).where(eq(userSettings.userId, userId)).get();
}
