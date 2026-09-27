# Osiris V0

Osiris is a personal context system that starts with one primitive: **Ideas**.

V0 deliberately stays small:

- A continuously running local Python server
- SQLite persistence
- A responsive installable PWA for phone and laptop
- An Osiris landing/dashboard page
- Idea capture
- Persistent idea timelines made of notes
- Card/list idea browsing, search, archive/restore
- Optional local Whisper voice transcription
- Tailscale Serve helper for private HTTPS access from the phone

The long-term philosophy is larger than this codebase: Things, Events, Relationships, Modules, and context-aware assistance. V0 does **not** try to implement that ontology yet. It only avoids choices that would make the future model unnecessarily difficult.

## Architecture

```text
Phone / Laptop browser
        |
        | HTTPS on tailnet (optional)
        v
  Tailscale Serve
        |
        v
127.0.0.1:8787
  FastAPI / Osiris
        |
        +-- SQLite (data/osiris.db)
        |
        +-- Optional faster-whisper
```

The application itself is not coupled to Tailscale. Tailscale is transport around the local server.

## Project layout

```text
Osiris/
├── app/
│   ├── main.py             # FastAPI routes and API boundary
│   ├── database.py         # SQLite schema + persistence operations
│   ├── voice.py            # Optional local Whisper adapter
│   └── static/
│       ├── index.html      # V0 PWA shell
│       ├── app.css
│       ├── app.js
│       ├── manifest.webmanifest
│       └── service-worker.js
├── data/                   # SQLite database created here at runtime
├── docs/
│   └── ARCHITECTURE.md
├── tests/
│   └── test_database.py
├── requirements.txt
├── requirements-voice.txt
├── run.py
├── start-osiris.ps1
├── enable-voice.ps1
├── enable-tailscale-serve.ps1
└── stop-tailscale-serve.ps1
```

## Run on Windows

Prerequisite: Python 3.11+ is recommended.

From PowerShell in the project folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-osiris.ps1
```

Then open:

```text
http://127.0.0.1:8787
```

The first run creates `.venv`, installs the small base dependency set, initializes SQLite, and starts Osiris.

Once that setup has been completed, you can run Osiris as a hidden background process:

```powershell
.\start-osiris-background.ps1
```

Stop that background process with:

```powershell
.\stop-osiris.ps1
```

Runtime PID/log files live under `data/` and are ignored by Git.

### Manual start

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

## Access from your phone with Tailscale

Keep Osiris bound to `127.0.0.1`. With Tailscale installed and connected on the Windows laptop:

```powershell
.\enable-tailscale-serve.ps1
```

The helper runs:

```powershell
tailscale serve --bg http://127.0.0.1:8787
```

Then `tailscale serve status` shows the tailnet URL to open on your phone. Using HTTPS is also the right direction for browser microphone/PWA behavior.

To remove the Serve configuration:

```powershell
.\stop-tailscale-serve.ps1
```

## Enable local voice transcription

The base app boots without Whisper so V0 remains lightweight.

After the base environment exists:

```powershell
.\enable-voice.ps1
```

Restart Osiris. The microphone button will switch from `Whisper optional` to `Local Whisper ready`.

The default model is `base.en`. Change it with:

```powershell
$env:OSIRIS_WHISPER_MODEL = "small.en"
python run.py
```

The model is loaded lazily only when the first recording is transcribed.

## V0 data model

### Idea

```text
Idea
├── id
├── owner_id       # "local" for now; cheap future multi-user seam
├── title
├── status         # active | archived
├── source
├── created_at
└── updated_at
```

### Note

```text
Note
├── id
├── idea_id
├── content
├── source          # text | voice
└── created_at
```

An Idea is a persistent object. Notes append to its timeline. There is intentionally no hard-delete API in V0.

## API

FastAPI exposes interactive API docs while the server is running:

```text
http://127.0.0.1:8787/docs
```

Core endpoints:

```text
GET    /api/health
GET    /api/dashboard
GET    /api/ideas
POST   /api/ideas
GET    /api/ideas/{id}
PATCH  /api/ideas/{id}
POST   /api/ideas/{id}/notes
GET    /api/voice/status
POST   /api/transcribe
```

## Tests

From the activated virtual environment:

```powershell
python -m unittest discover -s tests -v
```

## What is deliberately not in V0

- AI chat/provider integration
- Projects
- Thing/Event/Relationship abstraction
- Generated modules
- Cooking/workout modules
- Multi-user authentication
- Offline write/sync
- Cloud deployment
- Autonomous changes

Those are deferred intentionally. See `docs/ARCHITECTURE.md` for the growth boundaries.

## Immediate V0 milestone

The first end-to-end target is:

1. Open Osiris on the phone over the tailnet.
2. Record or type a thought.
3. Save it as an Idea.
4. Open the same Osiris instance on the laptop.
5. See the Idea and append another timestamped note to its timeline.

That validates the persistent personal-context loop before adding intelligence.
