import { Context, Next } from 'hono';

const RATE_LIMIT_WINDOW = 60; // seconds
const MAX_REQUESTS = 120; // per window

export async function rateLimiter(c: Context, next: Next) {
const userId = c.get('userId') || c.req.header('CF-Connecting-IP') || 'anonymous';
const key = ratelimit:${userId};

const current = await c.env.KV.get(key);
const now = Math.floor(Date.now() / 1000);

if (current) {
const { count, resetTime } = JSON.parse(current as string);
if (now < resetTime && count >= MAX_REQUESTS) {
return c.json({ error: 'Rate limit exceeded. Please slow down.' }, 429);
}
if (now >= resetTime) {
await c.env.KV.put(key, JSON.stringify({ count: 1, resetTime: now + RATE_LIMIT_WINDOW }), { expirationTtl: RATE_LIMIT_WINDOW });
} else {
await c.env.KV.put(key, JSON.stringify({ count: count + 1, resetTime }), { expirationTtl: RATE_LIMIT_WINDOW });
}
} else {
await c.env.KV.put(key, JSON.stringify({ count: 1, resetTime: now + RATE_LIMIT_WINDOW }), { expirationTtl: RATE_LIMIT_WINDOW });
}

await next();
}