# Foldspec local prototype

Foldspec turns a constrained sheet-metal specification into a model preview and an experimental fabrication package. The app runs locally; OpenRouter is used only for AI proposals. Generated packages are **not manufacturing validated**.

## Start the app

Requirements: macOS or Linux, Python 3.12, [`uv`](https://docs.astral.sh/uv/), and [`pnpm`](https://pnpm.io/).

```sh
cd outputs/foldspec
uv python install 3.12
uv sync --python 3.12
cd apps/web && pnpm install
cd ../..
uv run python scripts/generate_contracts.py
```

Set `OPENROUTER_API_KEY` in the ignored `.env` file if it is not already present.

In another terminal, from the same project directory:

```sh
cd outputs/foldspec/apps/web
pnpm dev -- --host 127.0.0.1
```

Run the backend from another terminal in the project root:

```sh
cd outputs/foldspec
uv run uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). CAD artifacts and the SQLite database stay in the ignored `data/` directory. The backend binds to loopback and only accepts the local Vite origins configured in the API.

## Current capabilities

- Five deterministic recipes: rectangular and circular plates, L-brackets, U-channels, and Z-brackets.
- 5052-H32 aluminum, 0.063 inch nominal stock, with a deliberately incomplete SendCutSend profile.
- Local project/revision persistence, form edits, chat proposals through OpenRouter, model inspection, and ZIP package downloads.
- Flat DXF and formed STEP with preview GLB, PDF, JSON, validation findings, instructions, and a SHA-256 artifact manifest.

Supplier acceptance, reviewed design ranges, independent CAD verification, physical samples, and customer pilot results are still outstanding. Every package is marked experimental.

Run `uv run python scripts/generate_contracts.py` after changing Pydantic contracts. Run backend regressions with `uv run pytest -q`.
