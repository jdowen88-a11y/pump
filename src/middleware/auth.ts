import { Context, Next } from 'hono';
import { verify } from '../utils/jwt';

export async function authMiddleware(c: Context, next: Next) {
const authHeader = c.req.header('Authorization');

if (!authHeader || !authHeader.startsWith('Bearer ')) {
return c.json({ error: 'Missing or invalid authorization header' }, 401);
}

const token = authHeader.split(' ')[1];

try {
const payload = await verify(token, c.env.JWT_SECRET);
c.set('userId', payload.sub as string);
c.set('userEmail', payload.email as string);
c.set('username', payload.username as string);
await next();
} catch (error) {
return c.json({ error: 'Invalid or expired token' }, 401);
}
}