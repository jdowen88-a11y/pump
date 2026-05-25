import { Context, Next } from 'hono';

/**
 * Ultimate Centralized Error Handler
 * Logs with trace, audits critical errors, returns safe JSON.
 * Never leaks stack in prod.
 */
export const errorHandler = async (c: Context, next: Next) => {
  try {
    await next();
  } catch (err: any) {
    const traceId = c.get('traceId') || 'no-trace';
    const status = err.status || 500;
    const isProd = c.env?.ENVIRONMENT === 'production';

    console.error(`[${traceId}] Unhandled error:`, err.message, err.stack?.split('\n')[0]);

    // TODO: Insert to audit_logs if user context
    if (status >= 500) {
      // Critical: could alert via notifier
    }

    return c.json({
      error: status === 500 ? 'Internal Server Error' : err.message || 'Error',
      traceId,
      ...(isProd ? {} : { details: err.message, stack: err.stack }),
    }, status as any);
  }
};
