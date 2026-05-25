import { D1Database, KVNamespace, Queue, DurableObjectNamespace } from '@cloudflare/workers-types';

/**
 * Ultimate Type Definitions
 * All interfaces for the evolved architecture: strategies, risk params, events, etc.
 */

export interface Env {
  DB: D1Database;
  KV: KVNamespace;
  TRADE_QUEUE: Queue<any>;
  STRATEGY_RUNNER: DurableObjectNamespace;
  JWT_SECRET: string;
  SOLANA_RPC_URL: string;
  HELIUS_API_KEY: string;
  BIRDEYE_API_KEY?: string;
  JITO_RPC_URL?: string;
  TELEGRAM_BOT_TOKEN?: string;
  ENVIRONMENT: string;
}

export interface User {
  id: string;
  email: string;
  username: string;
  solanaWallet?: string;
}

export interface Strategy {
  id: string;
  userId: string;
  name: string;
  type: 'snipe' | 'copy_trade' | 'volume_breakout' | 'mean_reversion' | 'post_raydium_momentum' | 'custom';
  params?: Record<string, any>;
  isActive: boolean;
  // performance fields...
}

export interface Position {
  id: string;
  userId: string;
  tokenMint: string;
  entryPriceSol: number;
  amountToken: number;
  // ... full from schema
}

export interface TradeEvent {
  type: 'buy' | 'sell' | 'fill' | 'new_token';
  mint?: string;
  userId: string;
  amountSol?: number;
  txSig?: string;
  timestamp: number;
  traceId?: string;
}

// Add more: BacktestConfig, RiskParams, etc. as needed for full type safety
