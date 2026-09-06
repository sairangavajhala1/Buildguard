/**
 * Application configuration loaded from environment variables.
 * All values have safe defaults so the app runs out of the box.
 */
export const config = {
  port: Number(process.env.PORT ?? 3000),
  host: process.env.HOST ?? '127.0.0.1',
  logLevel: process.env.LOG_LEVEL ?? 'info',
};