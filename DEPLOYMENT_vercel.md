# Deployment on Vercel

This guide explains how to run the TOEFL feedback service on [Vercel](https://vercel.com) using the repository's FastAPI backend and static frontend.

## 1. Prerequisites

- A Vercel account (hobby plan is sufficient for testing).
- Vercel CLI installed locally: `npm i -g vercel`.
- A Gemini API key stored locally as `API_KEY` in your environment (the backend reads `.env` files via `python-dotenv`).
- Python 3.11 available locally if you want to reproduce the serverless runtime behaviour with `vercel dev`.

## 2. Project Layout for Vercel

- `index.html` is served as a static asset at `/`.
- `api/index.py` is the Serverless Function entry point. It loads `api.py` and exposes the FastAPI `app` to Vercel's ASGI runtime.
- `vercel.json` configures the Python runtime, dependency installation, and rewrites that route API traffic to the FastAPI app.
- `requirements.txt` declares the Python dependencies installed during deployment.

You can run `vercel dev` locally to confirm everything works before deploying.

```bash
pip install -r requirements.txt
vercel dev
```

The dev server will be available at http://localhost:3000. API traffic is proxied to the FastAPI app at the same origin.

## 3. Configure the Vercel Project

1. Authenticate with Vercel (`vercel login`) and link the repository directory (`vercel link` or `vercel`).
2. Set the required environment variable for the Gemini client:
   ```bash
   vercel env add API_KEY production
   vercel env add API_KEY preview
   ```
   Paste the Gemini API key when prompted. (Add a `development` value if you plan to use `vercel dev` with remote envs.)
3. Optional but recommended: increase the Serverless Function duration if you own a Pro account:
   ```bash
   vercel project update --maxDuration 120
   ```

## 4. Deploy

Run a preview deployment first:

```bash
vercel
```

Vercel will install dependencies, build the static assets (no custom build step), and provision the Python Serverless Function. Once satisfied, promote to production:

```bash
vercel --prod
```

The production domain will display `index.html`. The frontend already calls the FastAPI endpoints relative to the origin; rewrites in `vercel.json` proxy those calls to the serverless backend.

## 5. Notes and Troubleshooting

- **Streaming & timings**: the FastAPI endpoints stream NDJSON responses. Vercel's Python runtime supports streaming, but long-lived requests count toward the function duration quota. Monitor Vercel's function logs if requests terminate early.
- **Binary uploads**: endpoints accept multipart audio uploads. Vercel's 4 MB body limit applies to hobby accounts—upgrade if you need larger files.
- **Local `.env`**: when using `vercel dev`, you can create a local `.env` file with `API_KEY=...` to mimic production behaviour.
- **Custom domains**: adding a custom domain in Vercel does not require code changes; the rewrites continue to work because they are relative to the origin.

With the project linked and the environment variable set, subsequent code pushes can be deployed via `vercel --prod` or through the Vercel dashboard UI.
