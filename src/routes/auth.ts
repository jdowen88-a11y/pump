import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { drizzle } from 'drizzle-orm/d1';
import { eq } from 'drizzle-orm';
import { users, userSettings } from '../db/schema';
import bcrypt from 'bcryptjs';
import { sign } from '../utils/jwt';
import { v4 as uuidv4 } from 'uuid';

type Env = { DB: D1Database; KV: KVNamespace; JWT_SECRET: string };

const auth = new Hono<{ Bindings: Env }>();

const registerSchema = z.object({
email: z.string().email().max(255),
username: z.string().min(3).max(30).regex(/^[a-zA-Z0-9_]+$/, 'Username can only contain letters, numbers, and underscores'),
password: z.string().min(8).max(100).regex(/^(?=.[a-z])(?=.[A-Z])(?=.*\d)/, 'Password must contain uppercase, lowercase, and number'),
});

const loginSchema = z.object({
email: z.string().email(),
password: z.string().min(1),
});

auth.post('/register', zValidator('json', registerSchema), async (c) => {
const { email, username, password } = c.req.valid('json');
const db = drizzle(c.env.DB);

const existingEmail = await db.select({ id: users.id }).from(users).where(eq(users.email, email.toLowerCase())).get();
if (existingEmail) {
return c.json({ error: 'Email already registered' }, 409);
}

const existingUsername = await db.select({ id: users.id }).from(users).where(eq(users.username, username)).get();
if (existingUsername) {
return c.json({ error: 'Username already taken' }, 409);
}

const passwordHash = await bcrypt.hash(password, 12);
const userId = uuidv4();

await db.batch([
db.insert(users).values({
id: userId,
email: email.toLowerCase(),
username,
passwordHash,
}),
db.insert(userSettings).values({
userId,
}),
]);

const token = await sign({ sub: userId, email: email.toLowerCase(), username }, c.env.JWT_SECRET, '7d');

return c.json({
token,
user: { id: userId, email: email.toLowerCase(), username },
}, 201);
});

auth.post('/login', zValidator('json', loginSchema), async (c) => {
const { email, password } = c.req.valid('json');
const db = drizzle(c.env.DB);

const user = await db.select().from(users).where(eq(users.email, email.toLowerCase())).get();
if (!user) {
return c.json({ error: 'Invalid email or password' }, 401);
}

const valid = await bcrypt.compare(password, user.passwordHash);
if (!valid) {
return c.json({ error: 'Invalid email or password' }, 401);
}

await db.update(users).set({ lastLogin: new Date().toISOString() }).where(eq(users.id, user.id));

const token = await sign({ sub: user.id, email: user.email, username: user.username }, c.env.JWT_SECRET, '7d');

return c.json({
token,
user: { id: user.id, email: user.email, username: user.username },
});
});

auth.get('/me', async (c) => {
const userId = c.get('userId');
const db = drizzle(c.env.DB);

const user = await db.select({
id: users.id,
email: users.email,
username: users.username,
solanaWallet: users.solanaWallet,
createdAt: users.createdAt,
isActive: users.isActive,
}).from(users).where(eq(users.id, userId)).get();

if (!user) {
return c.json({ error: 'User not found' }, 404);
}

return c.json(user);
});

auth.post('/logout', async (c) => {
return c.json({ message: 'Logged out successfully' });
});

export default auth;