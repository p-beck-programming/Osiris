# Osiris Architecture Direction

## Product boundary

Osiris is a **life-management assistant and personal context system**, not a general autonomous coding agent or large-project management platform.

Its job is to make it easier to capture, understand, organize, connect, and act on the user's personal context: ideas, lightweight projects, routines, workouts, meals, groceries, goals, and similar domains.

External systems can eventually handle domains outside Osiris through exports, integrations, or plugins.

## Version philosophy

### V0 — Osiris remembers my thoughts

Implemented here:

- Idea capture
- Persistent note timeline
- Phone/laptop access to the same local state
- Optional voice transcription

### V1 — Osiris helps organize my thoughts

Likely additions:

- AI assistant mode, initially advisory
- Tags / lightweight classifications
- Idea linking
- Idea-to-project promotion
- Several Ideas may relate to one Project
- Better dashboard context

### V2 — Osiris helps manage my life

Potential modules:

- Projects / tasks
- Cooking / groceries
- Workouts / routines
- Goals

### V3 — Osiris creates the tools I need to manage my life

- Declarative module definitions
- User-configurable navigation
- AI-assisted module creation and editing
- Sandboxed module boundaries
- Preview / approval workflow before changes

## Future ontology

The long-term conceptual model has four ideas.

### Things

Persistent objects in the user's life.

Examples: Idea, Project, Recipe, Workout, Goal, Trip.

### Events

Something that happened over time.

Examples: note added, workout completed, idea status changed, meal cooked.

### Relationships

Connections between Things.

Examples:

```text
Idea A ----\
Idea B -----+--> Project
Idea C ----/

Recipe ----> Ingredient
Task ------> Project
```

Relationships should preserve source information instead of destructively converting it. Promoting an Idea to a Project should not erase the original Idea history.

### Modules

Specialized views and operations for areas of life. A future module defines what is special about its domain instead of rebuilding persistence, search, AI access, history, and navigation from scratch.

```text
Osiris Core
├── context
├── things / events / relationships
├── module registry
├── AI action boundary
└── persistence

Modules
├── Ideas
├── Cooking
├── Fitness
└── user-created modules
```

## Why V0 does not implement the ontology

Creating generic `things`, `events`, and `relationships` tables before real use cases exist would force abstractions before we know their shape.

V0 therefore uses direct `ideas` and `notes` tables. The important architectural seams are preserved:

- UUID identifiers instead of database-local integer identity
- `owner_id` on Ideas, despite only one local owner today
- append-oriented Notes
- no hard delete API
- network transport outside the application core
- voice provider isolated behind `voice.py`
- API boundary between UI and persistence

When a second or third real domain appears, we can extract the generic primitives from concrete requirements rather than guess them now.

## AI authority model

Start at **Assistant**:

- user asks
- Osiris proposes or performs an explicit requested operation

Graduate to **Semi-autonomous**:

- Osiris may prepare changes or structure context
- user reviews significant changes

Do not make autonomous self-directed lifestyle/project decisions a core product goal.

## Module isolation

Future modules should be independently bounded so a broken lifestyle module does not destabilize the Osiris core or unrelated modules.

The V0 frontend is intentionally monolithic because two tabs do not justify a plugin framework yet. The API and persistence layers are already separated so the frontend can be decomposed later without rewriting storage.
