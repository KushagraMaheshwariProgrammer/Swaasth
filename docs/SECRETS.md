# Secrets & environment setup

## Quick start (new teammate)

```bash
npm run setup:env
# Edit backend/.env and set GROQ_API_KEY
cd backend && ./run_dev.sh   # terminal 1
npm run dev                  # terminal 2 (from repo root)
```

## What lives on GitHub (shared)

| File | Purpose |
|------|---------|
| `frontend/google-services.json` | Firebase Android client config (required for auth & Firestore) |
| `google-services.json` | Copy at repo root for tooling |
| `frontend/.env.example` | Template for optional local overrides |
| `backend/.env.example` | Template for backend secrets |
| `firestore.rules` | Firestore security rules |

Firebase **client** API keys in `google-services.json` are designed to be bundled with the app. Protect your project with [Firestore rules](https://firebase.google.com/docs/firestore/security/get-started) and [API key restrictions](https://cloud.google.com/docs/authentication/api-keys#api_key_restrictions) in Google Cloud Console.

## What stays local only (never commit)

| File | Purpose |
|------|---------|
| `backend/.env` | `GROQ_API_KEY` for AI bill parsing |
| `frontend/.env` | Optional overrides only (usually empty) |
| `backend/firebase-service-account.json` | Firebase Admin SDK (only if added later) |

Share `GROQ_API_KEY` with teammates through a password manager or secure channel — not GitHub Issues, Slack channels, or commits.

## Rotating exposed keys

A `GROQ_API_KEY` was previously committed to git history and has been scrubbed. **Rotate the key** at [console.groq.com/keys](https://console.groq.com/keys), then update `backend/.env` locally and share the new key with teammates securely.

## After a history rewrite

If `git pull` fails after a force-push, reset to the remote:

```bash
git fetch origin
git reset --hard origin/main
```

Then run `npm run setup:env` if you are missing local `.env` files.
