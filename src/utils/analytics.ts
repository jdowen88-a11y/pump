import type { D1Database } from '@cloudflare/workers-types';
import { drizzle } from 'drizzle-orm/d1';
import { eq, and, gte, sql } from 'drizzle-orm';
import { trades, positions, performanceSnapshots } from '../db/schema';

/**
 * Analytics Engine
 * Computes real-time P&L, win rate, equity, and other key metrics from D1.
 */

export interface PortfolioMetrics {
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  totalRealizedPnlSol: number;
  totalUnrealizedPnlSol: number;
  openPositions: number;
  dailyPnlSol: number;
  avgWinSol: number;
  avgLossSol: number;
  profitFactor: number;
  bestTrade: number;
  worstTrade: number;
}

export async function getPortfolioMetrics(db: D1Database, userId: string): Promise<PortfolioMetrics> {
  const orm = drizzle(db);

  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  const [allTrades, openPos, dailyRow] = await Promise.all([
    orm
      .select()
      .from(trades)
      .where(and(eq(trades.userId, userId), eq(trades.status, 'confirmed')))
      .all(),
    orm
      .select({ count: sql<number>`count(*)`, totalUnrealized: sql<number>`COALESCE(SUM(unrealized_pnl_sol), 0)` })
      .from(positions)
      .where(and(eq(positions.userId, userId), eq(positions.status, 'open')))
      .get(),
    orm
      .select({ total: sql<number>`COALESCE(SUM(profit_sol), 0)` })
      .from(trades)
      .where(and(eq(trades.userId, userId), eq(trades.status, 'confirmed'), gte(trades.executedAt, todayStart.toISOString())))
      .get(),
  ]);

  const confirmedTrades = allTrades.filter((t) => t.profitSol !== null && t.profitSol !== undefined);
  const wins = confirmedTrades.filter((t) => (t.profitSol ?? 0) > 0);
  const losses = confirmedTrades.filter((t) => (t.profitSol ?? 0) < 0);

  const totalRealizedPnl = confirmedTrades.reduce((s, t) => s + (t.profitSol ?? 0), 0);
  const winPnl = wins.reduce((s, t) => s + (t.profitSol ?? 0), 0);
  const lossPnl = losses.reduce((s, t) => s + (t.profitSol ?? 0), 0);
  const profitFactor = lossPnl < 0 ? winPnl / Math.abs(lossPnl) : winPnl > 0 ? Infinity : 0;

  const pnlValues = confirmedTrades.map((t) => t.profitSol ?? 0);

  return {
    totalTrades: confirmedTrades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: confirmedTrades.length > 0 ? wins.length / confirmedTrades.length : 0,
    totalRealizedPnlSol: totalRealizedPnlSol ?? totalRealizedPnl,
    totalUnrealizedPnlSol: openPos?.totalUnrealized ?? 0,
    openPositions: openPos?.count ?? 0,
    dailyPnlSol: dailyRow?.total ?? 0,
    avgWinSol: wins.length > 0 ? winPnl / wins.length : 0,
    avgLossSol: losses.length > 0 ? lossPnl / losses.length : 0,
    profitFactor,
    bestTrade: pnlValues.length > 0 ? Math.max(...pnlValues) : 0,
    worstTrade: pnlValues.length > 0 ? Math.min(...pnlValues) : 0,
  };
}

export async function snapshotPerformance(db: D1Database, userId: string, metrics: PortfolioMetrics): Promise<void> {
  const orm = drizzle(db);
  const { v4: uuidv4 } = await import('uuid');
  await orm.insert(performanceSnapshots).values({
    id: uuidv4(),
    userId,
    totalEquitySol: metrics.totalRealizedPnlSol + metrics.totalUnrealizedPnlSol,
    realizedPnlSol: metrics.totalRealizedPnlSol,
    unrealizedPnlSol: metrics.totalUnrealizedPnlSol,
    openPositionsCount: metrics.openPositions,
    dailyPnlSol: metrics.dailyPnlSol,
    metrics: JSON.stringify(metrics),
    snapshotAt: new Date().toISOString(),
  });
}
