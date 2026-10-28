# Lovable frontend prompt (paste into Lovable)

Build **ReverseX Engineer**, a polished dark-mode React + TypeScript + Tailwind frontend for a software behavioral investigation tool. Use charcoal backgrounds, restrained violet accents, refined developer-tool typography, responsive panels. No generic chatbot.

Pages: landing page and investigation workspace. Workspace sections: authorized local target URL (read-only `http://127.0.0.1:8001` for this phase), investigation mode ("Scripted browser smoke test" or "Live Muse Spark investigation"), Start button, status timeline, observations, last browser screenshot placeholder, and clearly labeled incomplete features (Specification, Reconstruction, Validation: "Coming in the next build phase").

Create a typed API client configured via `VITE_REVERSEX_API_BASE_URL` (default `http://127.0.0.1:8000`), using:
- GET `/health`
- POST `/api/investigations` with `{ "mode": "scripted" | "muse" }`
- GET `/api/investigations/{id}` (poll every 1.5 seconds until `completed`, `partial`, or `failed`)

Show real server statuses, error messages, and JSON evidence events. Never fake model runs or display an invented validation score. The backend is FastAPI and is separately implemented. Do not implement Meta AI calls or browser automation in Lovable. Do not add Supabase, authentication, payments, or any public arbitrary-URL capability.

This is a local hackathon demo. A hosted Lovable URL cannot call someone's localhost backend; for deployment we'll need to host the API securely and add an approved origin.
