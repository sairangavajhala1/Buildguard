import { Router } from 'express';

/**
 * In-memory item store. This is a demonstration data layer;
 * swap it for a real database (e.g. Postgres) in production.
 */
const items = new Map();
let nextId = 1;

function validateItem(body) {
  if (typeof body?.name !== 'string' || body.name.trim() === '') {
    return 'name must be a non-empty string';
  }
  return null;
}

const router = Router();

// List all items.
router.get('/', (_req, res) => {
  res.json({ items: [...items.values()] });
});

// Get a single item.
router.get('/:id', (req, res) => {
  const item = items.get(Number(req.params.id));
  if (!item) {
    return res.status(404).json({ error: 'Item not found' });
  }
  return res.json(item);
});

// Create an item.
router.post('/', (req, res) => {
  const error = validateItem(req.body);
  if (error) {
    return res.status(400).json({ error });
  }
  const item = {
    id: nextId++,
    name: req.body.name.trim(),
    createdAt: new Date().toISOString(),
  };
  items.set(item.id, item);
  return res.status(201).json(item);
});

// Update an item.
router.put('/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!items.has(id)) {
    return res.status(404).json({ error: 'Item not found' });
  }
  const error = validateItem(req.body);
  if (error) {
    return res.status(400).json({ error });
  }
  const updated = { ...items.get(id), name: req.body.name.trim() };
  items.set(id, updated);
  return res.json(updated);
});

// Delete an item.
router.delete('/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!items.has(id)) {
    return res.status(404).json({ error: 'Item not found' });
  }
  items.delete(id);
  return res.status(204).end();
});

export default router;
export { items };