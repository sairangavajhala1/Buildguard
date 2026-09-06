import { Router } from 'express';
import { config } from '../config.js';

const startedAt = Date.now();

const router = Router();

router.get('/', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'dodo-backend',
    uptimeSeconds: Math.floor((Date.now() - startedAt) / 1000),
    timestamp: new Date().toISOString(),
    logLevel: config.logLevel,
  });
});

export default router;