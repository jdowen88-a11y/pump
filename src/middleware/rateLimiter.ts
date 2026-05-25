import { Context, Next } from 'hono';
import type { Env } from '../types';

/**
 * Ultimate Rate Limiter Middleware
 * Sliding window via KV for per-user or per-IP.
 * Protects against abuse on snipe/config endpoints.
 * Returns 429 with Retry-After.
 */
export const rateLimiter = (options: { limit?: number; windowSeconds?: number } = {}) => {
  const limit = options.limit || 60; // requests
  const windowSec = options.windowSeconds || 60;

  return async (c: Context<{ Bindings: Env }>, next: Next) => {
    const userId = c.get('userId') || c.req.header('CF-Connecting-IP') || 'anonymous';
    const key = `ratelimit:${userId}:${Math.floor(Date.now() / (windowSec * 1000))}`;

    try {
      const current = (await c.env.KV.get(key, 'text')) || '0';
      const count = parseInt(current, 10) + 1;

      if (count > limit) {
        c.header('Retry-After', windowSec.toString());
        return c.json({ error: 'Rate limit exceeded', limit, window: windowSec, traceId: c.get('traceId') }, 429);
      }

      await c.env.KV.put(key, count.toString(), { expirationTtl: windowSec });
      c.header('X-RateLimit-Limit', limit.toString());
      c.header('X-RateLimit-Remaining', (limit - count).toString());
      await next();
    } catch (e) {
      console.error('Rate limiter KV error (fail open):', e);
      await next(); // fail open for resilience
    }
  };
};
