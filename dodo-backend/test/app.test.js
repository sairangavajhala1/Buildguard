import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';

let server;
let baseUrl;

before(async () => {
  const app = createApp();
  server = app.listen(0);
  await new Promise((resolve) => server.once('listening', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(() => {
  server.close();
});

test('GET / returns service metadata', async () => {
  const res = await fetch(`${baseUrl}/`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.name, 'dodo-backend');
});

test('GET /health returns ok', async () => {
  const res = await fetch(`${baseUrl}/health`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, 'ok');
  assert.equal(body.service, 'dodo-backend');
  assert.equal(typeof body.uptimeSeconds, 'number');
});

test('items CRUD round-trip', async () => {
  // Empty initially.
  const listRes = await fetch(`${baseUrl}/api/v1/items`);
  assert.equal(listRes.status, 200);
  const { items } = await listRes.json();
  assert.ok(Array.isArray(items));

  // Create.
  const createRes = await fetch(`${baseUrl}/api/v1/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'first item' }),
  });
  assert.equal(createRes.status, 201);
  const created = await createRes.json();
  assert.equal(created.name, 'first item');
  assert.equal(typeof created.id, 'number');

  // Read single.
  const getRes = await fetch(`${baseUrl}/api/v1/items/${created.id}`);
  assert.equal(getRes.status, 200);
  assert.deepEqual(await getRes.json(), created);

  // Update.
  const updateRes = await fetch(`${baseUrl}/api/v1/items/${created.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'renamed item' }),
  });
  assert.equal(updateRes.status, 200);
  const updated = await updateRes.json();
  assert.equal(updated.name, 'renamed item');

  // Delete.
  const deleteRes = await fetch(`${baseUrl}/api/v1/items/${created.id}`, {
    method: 'DELETE',
  });
  assert.equal(deleteRes.status, 204);

  // Gone after delete.
  const goneRes = await fetch(`${baseUrl}/api/v1/items/${created.id}`);
  assert.equal(goneRes.status, 404);
});

test('create with invalid body is rejected', async () => {
  const res = await fetch(`${baseUrl}/api/v1/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: '   ' }),
  });
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.match(body.error, /name/);
});

test('unknown route returns 404', async () => {
  const res = await fetch(`${baseUrl}/api/v1/nope`);
  assert.equal(res.status, 404);
});