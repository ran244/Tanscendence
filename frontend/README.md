# Mystery Auctions frontend

React/Vite client derived from the `trance_claude` visual reference and wired
to the real same-origin REST and WebSocket contracts. It contains no mock data
and no card-payment flow; winning orders use cash-on-delivery confirmation.

The supported production build is the root Docker Compose stack:

```bash
docker compose up --build
```

The host in the evaluation environment has an obsolete Node version. For
standalone local development use Node 22, then run `npm ci` and `npm run dev`.
See the root README and `docs/backend-contract.md` for the full architecture.
