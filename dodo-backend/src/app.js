import express from 'express';
import healthRouter from './routes/health.js';
import itemsRouter from './routes/items.js';
import paymentsRouter from './routes/payments.js';
import { config } from './config.js';

/**
 * Build the Express application.
 * Kept separate from the listener so tests can mount the app
 * on an ephemeral port without binding to a process port.
 */
export function createApp() {
  const app = express();

  app.disable('x-powered-by');
  app.use(express.json());

  // Request logging (minimal, dependency-free).
  app.use((req, _res, next) => {
    if (config.logLevel === 'debug') {
      console.log(`${new Date().toISOString()} ${req.method} ${req.url}`);
    }
    next();
  });

  app.get('/', (_req, res) => {
    res.json({
      name: 'dodo-backend',
      version: '0.1.0',
      docs: '/health, /api/v1/items',
    });
  });

  app.use('/health', healthRouter);
  app.use('/api/v1/items', itemsRouter);
  app.use('/api/v1/payments', paymentsRouter);

  // 404 handler.
  app.use((req, res) => {
    res.status(404).json({ error: `Not found: ${req.method} ${req.path}` });
  });

  // Centralized error handler.
  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    console.error(err);
    res.status(500).json({ error: 'Internal server error' });
  });

  return app;
}