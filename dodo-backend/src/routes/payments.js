import { Router } from 'express';
import { config } from '../config.js';

const router = Router();

/**
 * Payment integration status. Reports whether the payments API key
 * is configured — never exposes the key itself.
 */
router.get('/status', (_req, res) => {
  res.json({
    configured: config.payments.apiKey.length > 0,
  });
});

export default router;