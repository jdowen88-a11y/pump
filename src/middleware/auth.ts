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
      const configuredSecret = c.env.JWT_SECRET;
      if (!configuredSecret) return c.json({ error: 'Authentication not configured', traceId }, 503);
      const secret = new TextEncoder().encode(configuredSecret);
      const { payload } = await jwtVerify(token, secret);
      if (!payload.sub || typeof payload.sub !== 'string') {
        return c.json({ error: 'Invalid token subject', traceId }, 401);
      }
      c.set('userId', payload.sub);
      c.set('user', payload);
    } else if (apiKeyHeader) {
      // Fail closed until database-backed, hashed, scoped API-key checks exist.
      return c.json({ error: 'API key authentication is not configured', traceId }, 403);
    } else {
      return c.json({ error: 'Unsupported authorization scheme', traceId }, 401);
    }
    await next();
  } catch (err: any) {
    console.error(`[${traceId}] Auth failed:`, err.message);
    return c.json({ error: 'Auth failed', traceId }, 401);
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
