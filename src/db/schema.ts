import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

export const users = sqliteTable('users', {
id: text('id').primaryKey(),
email: text('email').unique().notNull(),
username: text('username').unique().notNull(),
passwordHash: text('password_hash').notNull(),
solanaWallet: text('solana_wallet'),
createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
updatedAt: text('updated_at').default('CURRENT_TIMESTAMP'),
lastLogin: text('last_login'),
isActive: integer('is_active').default(1),
});

export const tokens = sqliteTable('tokens', {
mint: text('mint').primaryKey(),
name: text('name'),
symbol: text('symbol'),
pumpfunId: text('pumpfun_id'),
creatorAddress: text('creator_address'),
createdAtChain: text('created_at_chain'),
firstSeen: text('first_seen').default('CURRENT_TIMESTAMP'),
lastUpdated: text('last_updated').default('CURRENT_TIMESTAMP'),
score: real('score').default(0),
volume24h: real('volume_24h').default(0),
holderCount: integer('holder_count').default(0),
buyCount: integer('buy_count').default(0),
sellCount: integer('sell_count').default(0),
buyVolume24h: real('buy_volume_24h').default(0),
sellVolume24h: real('sell_volume_24h').default(0),
scamScore: real('scam_score').default(0),
rsi: real('rsi'),
macd: real('macd'),
macdSignal: real('macd_signal'),
volumeSpike: real('volume_spike'),
pattern: text('pattern'),
chartData: text('chart_data'),
});

export const trades = sqliteTable('trades', {
id: text('id').primaryKey(),
userId: text('user_id').references(() => users.id).notNull(),
tokenMint: text('token_mint').references(() => tokens.mint).notNull(),
action: text('action', { enum: ['buy', 'sell'] }).notNull(),
amountSol: real('amount_sol').notNull(),
amountToken: real('amount_token'),
priceSol: real('price_sol'),
slippage: real('slippage'),
txSignature: text('tx_signature'),
profitSol: real('profit_sol'),
status: text('status', { enum: ['pending', 'confirmed', 'failed'] }).default('pending'),
executedAt: text('executed_at').default('CURRENT_TIMESTAMP'),
createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
});

export const userSettings = sqliteTable('user_settings', {
userId: text('user_id').primaryKey().references(() => users.id),
autoTrade: integer('auto_trade').default(1),
maxBuySol: real('max_buy_sol').default(0.1),
minScore: integer('min_score').default(60),
slippagePercent: integer('slippage_percent').default(10),
maxSlippagePercent: integer('max_slippage_percent').default(25),
takeProfitPercent: real('take_profit_percent').default(50),
stopLossPercent: real('stop_loss_percent').default(20),
notificationsEnabled: integer('notifications_enabled').default(1),
pushToken: text('push_token'),
createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
updatedAt: text('updated_at').default('CURRENT_TIMESTAMP'),
});

export const auditLogs = sqliteTable('audit_logs', {
id: text('id').primaryKey(),
userId: text('user_id').references(() => users.id),
action: text('action').notNull(),
details: text('details'),
ipAddress: text('ip_address'),
createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
});