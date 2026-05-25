import { sqliteTable, text, integer, real, index } from 'drizzle-orm/sqlite-core';

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
}, (table) => ({
  emailIdx: index('email_idx').on(table.email),
  usernameIdx: index('username_idx').on(table.username),
}));

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
  bondingCurveProgress: real('bonding_curve_progress').default(0), // 0-100%
  marketCapSol: real('market_cap_sol').default(0),
  liquiditySol: real('liquidity_sol').default(0),
  devHoldingPercent: real('dev_holding_percent').default(0),
  topHoldersConcentration: real('top_holders_concentration').default(0),
  isRugRisk: integer('is_rug_risk').default(0),
  lastPriceSol: real('last_price_sol').default(0),
}, (table) => ({
  scoreIdx: index('score_idx').on(table.score),
  firstSeenIdx: index('first_seen_idx').on(table.firstSeen),
}));

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
  status: text('status', { enum: ['pending', 'confirmed', 'failed', 'cancelled'] }).default('pending'),
  executedAt: text('executed_at').default('CURRENT_TIMESTAMP'),
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
  strategyId: text('strategy_id'), // link to strategy used
  notes: text('notes'),
}, (table) => ({
  userIdIdx: index('trades_user_id_idx').on(table.userId),
  tokenMintIdx: index('trades_token_mint_idx').on(table.tokenMint),
  executedAtIdx: index('trades_executed_at_idx').on(table.executedAt),
}));

export const userSettings = sqliteTable('user_settings', {
  userId: text('user_id').primaryKey().references(() => users.id),
  autoTrade: integer('auto_trade').default(1),
  maxBuySol: real('max_buy_sol').default(0.1),
  minScore: integer('min_score').default(60),
  slippagePercent: integer('slippage_percent').default(10),
  maxSlippagePercent: integer('max_slippage_percent').default(25),
  takeProfitPercent: real('take_profit_percent').default(50),
  stopLossPercent: real('stop_loss_percent').default(20),
  maxOpenPositions: integer('max_open_positions').default(5),
  maxDailyLossSol: real('max_daily_loss_sol').default(1.0),
  riskPerTradePercent: real('risk_per_trade_percent').default(2.0), // of portfolio
  notificationsEnabled: integer('notifications_enabled').default(1),
  pushToken: text('push_token'),
  telegramChatId: text('telegram_chat_id'),
  jitoTipLamports: integer('jito_tip_lamports').default(10000),
  useJito: integer('use_jito').default(1),
  backupRpcUrls: text('backup_rpc_urls'), // JSON array
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
  updatedAt: text('updated_at').default('CURRENT_TIMESTAMP'),
});

export const auditLogs = sqliteTable('audit_logs', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id),
  action: text('action').notNull(),
  details: text('details'),
  ipAddress: text('ip_address'),
  traceId: text('trace_id'),
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
}, (table) => ({
  userIdIdx: index('audit_user_id_idx').on(table.userId),
  createdAtIdx: index('audit_created_at_idx').on(table.createdAt),
}));

// === EVOLVED TABLES: Ultimate Feature Completeness ===

export const strategies = sqliteTable('strategies', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  name: text('name').notNull(),
  type: text('type', { enum: ['snipe', 'copy_trade', 'volume_breakout', 'mean_reversion', 'post_raydium_momentum', 'custom'] }).notNull(),
  params: text('params'), // JSON string of strategy-specific params
  isActive: integer('is_active').default(1),
  priority: integer('priority').default(0),
  winRate: real('win_rate').default(0),
  expectancy: real('expectancy').default(0),
  sharpe: real('sharpe').default(0),
  maxDrawdown: real('max_drawdown').default(0),
  totalTrades: integer('total_trades').default(0),
  totalProfitSol: real('total_profit_sol').default(0),
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
  updatedAt: text('updated_at').default('CURRENT_TIMESTAMP'),
}, (table) => ({
  userIdIdx: index('strategies_user_id_idx').on(table.userId),
  typeIdx: index('strategies_type_idx').on(table.type),
}));

export const positions = sqliteTable('positions', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  tokenMint: text('token_mint').references(() => tokens.mint).notNull(),
  strategyId: text('strategy_id').references(() => strategies.id),
  entryPriceSol: real('entry_price_sol').notNull(),
  amountToken: real('amount_token').notNull(),
  amountSolInvested: real('amount_sol_invested').notNull(),
  currentPriceSol: real('current_price_sol').default(0),
  unrealizedPnlSol: real('unrealized_pnl_sol').default(0),
  realizedPnlSol: real('realized_pnl_sol').default(0),
  stopLossPrice: real('stop_loss_price'),
  takeProfitPrice: real('take_profit_price'),
  trailingStopPercent: real('trailing_stop_percent').default(0),
  status: text('status', { enum: ['open', 'closed', 'partial'] }).default('open'),
  openedAt: text('opened_at').default('CURRENT_TIMESTAMP'),
  closedAt: text('closed_at'),
  notes: text('notes'),
}, (table) => ({
  userIdIdx: index('positions_user_id_idx').on(table.userId),
  tokenMintIdx: index('positions_token_mint_idx').on(table.tokenMint),
  statusIdx: index('positions_status_idx').on(table.status),
}));

export const backtests = sqliteTable('backtests', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  strategyId: text('strategy_id').references(() => strategies.id),
  config: text('config'), // JSON: date range, initial capital, slippage model, etc.
  results: text('results'), // JSON: equity curve, trades, metrics
  totalReturn: real('total_return').default(0),
  sharpe: real('sharpe').default(0),
  sortino: real('sortino').default(0),
  maxDrawdown: real('max_drawdown').default(0),
  winRate: real('win_rate').default(0),
  profitFactor: real('profit_factor').default(0),
  status: text('status', { enum: ['running', 'completed', 'failed'] }).default('running'),
  startedAt: text('started_at').default('CURRENT_TIMESTAMP'),
  completedAt: text('completed_at'),
}, (table) => ({
  userIdIdx: index('backtests_user_id_idx').on(table.userId),
}));

export const alerts = sqliteTable('alerts', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  type: text('type', { enum: ['new_token', 'trade_fill', 'tp_hit', 'sl_hit', 'risk_breach', 'system', 'copy_trade_signal'] }).notNull(),
  condition: text('condition'), // JSON or description
  message: text('message').notNull(),
  triggeredAt: text('triggered_at').default('CURRENT_TIMESTAMP'),
  isRead: integer('is_read').default(0),
  channel: text('channel', { enum: ['telegram', 'discord', 'email', 'push', 'in_app'] }).default('in_app'),
}, (table) => ({
  userIdIdx: index('alerts_user_id_idx').on(table.userId),
  triggeredAtIdx: index('alerts_triggered_at_idx').on(table.triggeredAt),
}));

export const performanceSnapshots = sqliteTable('performance_snapshots', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  snapshotAt: text('snapshot_at').default('CURRENT_TIMESTAMP'),
  totalEquitySol: real('total_equity_sol').default(0),
  realizedPnlSol: real('realized_pnl_sol').default(0),
  unrealizedPnlSol: real('unrealized_pnl_sol').default(0),
  openPositionsCount: integer('open_positions_count').default(0),
  dailyPnlSol: real('daily_pnl_sol').default(0),
  metrics: text('metrics'), // JSON full metrics
}, (table) => ({
  userIdIdx: index('perf_user_id_idx').on(table.userId),
  snapshotAtIdx: index('perf_snapshot_at_idx').on(table.snapshotAt),
}));

export const watchedWallets = sqliteTable('watched_wallets', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  walletAddress: text('wallet_address').notNull(),
  label: text('label'),
  minTradeSizeSol: real('min_trade_size_sol').default(0.05),
  minSuccessRate: real('min_success_rate').default(0.6),
  maxCopyAmountSol: real('max_copy_amount_sol').default(0.5),
  isActive: integer('is_active').default(1),
  addedAt: text('added_at').default('CURRENT_TIMESTAMP'),
}, (table) => ({
  userIdIdx: index('watched_user_id_idx').on(table.userId),
  walletIdx: index('watched_wallet_idx').on(table.walletAddress),
}));

export const apiKeys = sqliteTable('api_keys', {
  id: text('id').primaryKey(),
  userId: text('user_id').references(() => users.id).notNull(),
  keyHash: text('key_hash').notNull(), // hashed
  name: text('name').notNull(),
  permissions: text('permissions'), // JSON scopes
  lastUsedAt: text('last_used_at'),
  expiresAt: text('expires_at'),
  isActive: integer('is_active').default(1),
  createdAt: text('created_at').default('CURRENT_TIMESTAMP'),
}, (table) => ({
  userIdIdx: index('apikeys_user_id_idx').on(table.userId),
}));
