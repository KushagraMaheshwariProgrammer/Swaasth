# Swaasth

Swaasth (also branded as BillCheck in the product UI) helps users review hospital
bills and healthcare documents for possible billing irregularities and related
next steps.

## License

This project is free software under the **GNU Affero General Public License
v3.0** (`AGPL-3.0`). See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Because Swaasth is offered as a network service and uses **PyMuPDF / MuPDF**
(AGPL), the complete corresponding source for the service is this public
repository:

**https://github.com/KushagraMaheshwariProgrammer/Swaasth**  
Default branch: `galaxy-store-code`

In the running app, the same offer is linked from **Account settings → Open
source**, the site footer, and the `/source` route.

## Repository layout

- `frontend/` — React web / Capacitor client
- `backend/` — FastAPI API (document extraction, audits, report PDFs)
- `docs/` — deployment and secrets notes (no production secrets)

## Running locally

See `frontend/.env.example`, `backend/.env.example`, and `docs/SECRETS.md`.
Do not commit real API keys or `backend/firebase-service-account.json`.
