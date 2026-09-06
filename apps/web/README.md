# Aegis Code Review UI

This is the canonical, component-driven Angular application for the Aegis code-review workspace.

## Structure

- `core/` — API contracts, HTTP/SSE client, and application review store.
- `ui/` — domain-independent design-system primitives such as the app header, status pills, and surface cards.
- `review/` — reusable review-domain components such as review rows and agent cards.
- `pages/` — route-level composition for Workspace, Review Archive, and Review Detail.

Route pages own layout. Shared components own repeated behavior and presentation. API access stays outside visual components.

## Local development

Run the application on port 4200:

```bash
npm start -- --host 127.0.0.1 --port 4200
```

The development proxy forwards `/api/v1` requests to the existing backend.
