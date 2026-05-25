import { Context, Next } from 'hono';
import { jwtVerify } from 'jose';

import type { Env } from '../types';

/**
 * Evolved Auth Middleware (Ultimate)
 * Supports JWT (HS256 via jose) + API Key fallback.
 * Injects user context. Audits via trace.
 * Ready for RBAC expansion.
 */
export const authMiddleware = async (c: Context<{ Bindings: Env }>, next: Next) => {
  const authHeader = c.req.header('Authorization');
  const apiKeyHeader = c.req.header('X-API-Key');
  const traceId = c.req.header('X-Trace-Id') || crypto.randomUUID();

  c.set('traceId', traceId);

  if (!authHeader && !apiKeyHeader) {
    return c.json({ error: 'Unauthorized', message: 'Provide Bearer JWT or X-API-Key', traceId }, 401);
  }

  try {
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const secret = new TextEncoder().encode(c.env.JWT_SECRET || 'dev-secret-change-me');
      const { payload } = await jwtVerify(token, secret);
      c.set('userId', payload.sub as string);
      c.set('user', payload);
    } else if (apiKeyHeader) {
      // TODO: Verify against hashed api_keys in D1 + permissions check
      c.set('userId', `api-${apiKeyHeader.substring(0,8)}`);
      c.set('apiKey', apiKeyHeader);
    }
    await next();
  } catch (err: any) {
    console.error(`[${traceId}] Auth failed:`, err.message);
    return c.json({ error: 'Auth failed', message: err.message, traceId }, 401);
  }
};

// JWT issuer helper (use in /login)
export async function issueAccessToken(userId: string, secret: string, expiresInSeconds = 900) {
  const { SignJWT } = await import('jose');
  return await new SignJWT({ sub: userId, iat: Math.floor(Date.now()/1000) })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(`${expiresInSeconds}s`)
    .sign(new TextEncoder().encode(secret));
}
