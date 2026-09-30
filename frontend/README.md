# SignalHire frontend

Independent React + JavaScript application for the Resume Intelligence backend. It uses Vite, React Router, Tailwind CSS, Framer Motion, Lucide icons, Recharts, and Axios.

## Run locally

1. Start the backend on `http://localhost:8000` and configure a valid backend JWT secret and bootstrap/admin or HR login.
2. Copy `.env.example` to `.env` if the backend is not at its default URL.
3. Install and start the frontend:

   ```sh
   npm install
   npm run dev
   ```

Vite uses port `3000`, matching the backend's default CORS origin. If you change the frontend origin, add that origin to the backend `CORS_ORIGINS`. The API base URL defaults to `http://localhost:8000/api/v1` and can be changed with `VITE_API_BASE_URL`.

## Quality checks

```sh
npm test
npm run build
```

The test runner is configured to use one worker because the development environment has constrained memory.

## Backend contract notes

- Authentication uses `/auth/login`, `/auth/refresh`, `/auth/me`, password reset OTP endpoints, and `/auth/change-password`. Access tokens remain in memory; the refresh token is scoped to the current browser tab in `sessionStorage`.
- HR/admin access gates are a navigation convenience. The FastAPI backend remains the authorization boundary.
- Resume management lists the backend's paginated **candidate** pool because there is no resume-list endpoint. Uploads use `/resumes/upload` and `/resumes/bulk-upload`; the API enforces configured size limits and returns bulk job status.
- Job briefs support pasted/natural-language/structured text through `/jobs` and PDF, DOCX, or TXT uploads through `/jobs/upload`. Uploaded filenames remain visible on the saved brief; list/get are recruiter-scoped.
- Candidate search supports natural language, an owned job brief ID, and Top 3/Top 5. The backend does not accept skill or experience filters; the filters and sorting on the results screen operate only on the returned shortlist.
- Search history includes provider/fallback and evidence coverage from the existing search APIs. Candidate source/page information is shown only when the API returns it.
- HR users can label relevance and optional expected skill states (`matched`, `partial`, `missing`) for each query/candidate pair, then request an administrator-run evaluation. Results include ranking metrics, labeled skill classification metrics, and evidence grounding against persisted resume evidence; metrics are null when there is no applicable ground truth/claim set.
- The health endpoints report liveness/readiness, database, and Redis status. The admin endpoint returns configured provider names, not live provider checks, and does not report Celery worker health; the UI shows these limits explicitly.
- Profile editing includes only supported profile fields. Settings that have no defined backend contract are not presented as controls.

## Security and deployment notes

The browser cannot use HttpOnly cookies with the backend's current JSON token contract. The access token is held in JavaScript memory and the refresh token is held in tab-scoped session storage; an XSS vulnerability could still access JavaScript-readable state. Deploy with HTTPS, a restrictive Content Security Policy, and the backend's normal authorization controls. Do not put provider secrets in `VITE_*` variables: Vite exposes them to the browser bundle.

The visual theme uses CSS design tokens and includes responsive breakpoints, keyboard focus styles, accessible labels/status messaging, dialog semantics, and reduced-motion handling.
