# dodo-backend

Backend API service for the dodo application. Built with Node.js and Express.

## Requirements

- Node.js >= 20 (tested on Node 24)

## Getting started

```sh
npm install
npm run dev        # start with auto-reload
npm start          # plain start
npm test           # run the test suite
```

## Configuration

The server is configured through environment variables (see `.env.example`):

| Variable   | Default   | Description                          |
| ---------- | --------- | ------------------------------------ |
| `PORT`     | `3000`    | Port the HTTP server listens on      |
| `HOST`     | `127.0.0.1` | Bind address for the HTTP server   |
| `LOG_LEVEL`| `info`    | Logging verbosity (`info`/`debug`)   |

## API

| Method | Path              | Description                          |
| ------ | ----------------- | ------------------------------------ |
| `GET`  | `/`               | Service metadata                     |
| `GET`  | `/health`         | Health check (status, uptime)        |
| `GET`  | `/api/v1/items`   | List all items                       |
| `POST` | `/api/v1/items`   | Create an item `{ "name": string }`  |
| `GET`  | `/api/v1/items/:id` | Fetch a single item                |
| `PUT`  | `/api/v1/items/:id` | Update an item's name              |
| `DELETE` | `/api/v1/items/:id` | Delete an item                    |

## Layout

```
dodo-backend/
├── src/
│   ├── config.js        # env-driven configuration
│   ├── app.js           # Express app factory (testable)
│   ├── server.js        # bootstrap / listener
│   └── routes/
│       ├── health.js    # health endpoint
│       └── items.js     # in-memory item CRUD
└── test/
    └── app.test.js      # node:test suite (no extra deps)
```

The item store is in-memory (a `Map`) and intentionally minimal — swap it for a
real database (e.g. Postgres) when the data model is finalized.

## Known follow-ups

- Replace the in-memory item store with a persistent data layer.
- Add authentication/authorization.
- Add OpenAPI documentation.