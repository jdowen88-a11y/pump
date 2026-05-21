import { Hono } from 'hono';
import { drizzle } from 'drizzle-orm/d1';
import { eq, desc, gte } from 'drizzle-orm';
import { tokens } from '../db/schema';
import { analyzeToken } from '../services/scorer';

type Env = { DB: D1Database; KV: KVNamespace; SOLANA_RPC_URL: string; HELIUS_API_KEY: string };

const tokenRoutes = new Hono<{ Bindings: Env }>();

tokenRoutes.get('/top-picks', async (c) => {
const db = drizzle(c.env.DB);

const topTokens = await db.select()
.from(tokens)
.where(gte(tokens.score, 40))
.orderBy(desc(tokens.score))
.limit(5)
.all();

return c.json(topTokens);
});

tokenRoutes.get('/feed', async (c) => {
const db = drizzle(c.env.DB);
const limit = Math.min(parseInt(c.req.query('limit') || '20'), 100);
const offset = Math.max(parseInt(c.req.query('offset') || '0'), 0);

const feed = await db.select()
.from(tokens)
.orderBy(desc(tokens.firstSeen))
.limit(limit)
.offset(offset)
.all();

const total = await db.select({ count: tokens.mint }).from(tokens).all();

return c.json({ data: feed, total: total.length, limit, offset });
});

tokenRoutes.get('/search', async (c) => {
const query = c.req.query('q');
if (!query || query.length < 2) {
return c.json({ error: 'Search query too short' }, 400);
}

const db = drizzle(c.env.DB);

const results = await db.select()
.from(tokens)
.where(eq(tokens.symbol, query.toUpperCase()))
.or(eq(tokens.name, query))
.limit(10)
.all();

return c.json(results);
});

tokenRoutes.get('/:mint', async (c) => {
const mint = c.req.param('mint');
const db = drizzle(c.env.DB);

const token = await db.select().from(tokens).where(eq(tokens.mint, mint)).get();
if (!token) {
return c.json({ error: 'Token not found' }, 404);
}

return c.json(token);
});

tokenRoutes.post('/:mint/analyze', async (c) => {
const mint = c.req.param('mint');

try {
const score = await analyzeToken(mint, c.env);
return c.json({ mint, score });
} catch (error: any) {
return c.json({ error: 'Analysis failed', details: error.message }, 500);
}
});

tokenRoutes.get('/:mint/chart', async (c) => {
const mint = c.req.param('mint');
const db = drizzle(c.env.DB);

const token = await db.select({ chartData: tokens.chartData }).from(tokens).where(eq(tokens.mint, mint)).get();
if (!token || !token.chartData) {
return c.json({ error: 'No chart data available' }, 404);
}

try {
const chartData = JSON.parse(token.chartData);
return c.json(chartData);
} catch {
return c.json({ error: 'Invalid chart data' }, 500);
}
});

export default tokenRoutes;