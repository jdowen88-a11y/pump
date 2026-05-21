import { Context, Next } from 'hono';

export async function corsMiddleware(c: Context, next: Next) {
c.header('Access-Control-Allow-Origin', 'https://sniper.yourdomain.com');
c.header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
c.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
c.header('Access-Control-Allow-Credentials', 'true');
c.header('Access-Control-Max-Age', '86400');

if (c.req.method === 'OPTIONS') {
return c.json({}, 204);
}

await next();
}