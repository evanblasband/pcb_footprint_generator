# Technical Decisions

This document records significant technical decisions made during implementation.

---

## TD-001: Output Format - DelphiScript (.pas)

**Date:** 2026-02-11
**Status:** Decided (Updated after testing)

### Context
Need to generate PCB footprint files that can be imported into Altium Designer 26.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| `.PcbLib` ASCII | Human-readable, easy to debug | **Does not work** - files open empty in AD26 |
| `.PcbLib` binary (OLE) | Native format | Complex binary structure, requires reverse engineering |
| **DelphiScript (.pas)** | Uses official Altium API, guaranteed compatibility | Requires user to run script manually |
| PADS ASCII import | Import wizard available | Different ecosystem, conversion loss |

### Decision
Use **DelphiScript (.pas)** files that users run inside Altium Designer.

### Rationale
1. **ASCII .PcbLib does not work** - files open but appear empty (native format is binary OLE)
2. DelphiScript uses Altium's official PCB API (`PCBServer`, `IPCB_Library`, etc.)
3. Guaranteed to create valid footprints since we use the same API Altium uses internally
4. Human-readable scripts that users can modify if needed

### Why Not ASCII .PcbLib
- **Tested and failed** - files open in Altium but contain no pads/tracks
- Native `.PcbLib` format is binary OLE compound document, not ASCII
- Altium's "ASCII export" feature creates a different format than what Altium imports

### User Workflow
1. Open Altium Designer 26
2. Open Script Project (`FootprintScripts.PrjScr`)
3. Create/open a PCB Library document
4. Run the desired `.pas` script via Run → Script
5. Footprint is created in the library

### Consequences
- Slightly more complex user workflow (must run script)
- Full access to Altium's pad/via/track creation API
- Future enhancement: Could automate script execution via Altium's command line

---

## TD-002: AI Model - Claude Haiku (Initial)

**Date:** 2026-02-11
**Status:** Decided

### Context
Need to extract structured dimensions from datasheet images using AI vision.

### Alternatives Considered

| Model | Input Cost | Output Cost | Vision Quality | Speed |
|-------|------------|-------------|----------------|-------|
| Claude Haiku | $0.25/1M | $1.25/1M | Good | Fast |
| Claude Sonnet | $3/1M | $15/1M | Better | Medium |
| Claude Opus | $15/1M | $75/1M | Best | Slower |
| GPT-4V | $10/1M | $30/1M | Excellent | Medium |
| Gemini Pro Vision | $0.25/1M | $0.50/1M | Good | Fast |

### Decision
Start with Claude Haiku, architecture allows model swapping.

### Rationale
1. Cost target is $0.01-0.05 per extraction - Haiku meets this
2. Datasheet images are typically well-structured engineering drawings
3. Can upgrade to Sonnet/Opus if accuracy insufficient
4. Model parameter is configurable in extraction.py for easy swapping

### Why Not Sonnet/Opus Initially
- 12x-60x more expensive per extraction
- Unknown if the accuracy improvement justifies cost for this use case
- Better to start cheap and upgrade only if needed
- User feedback will indicate if accuracy is insufficient

### Why Not GPT-4V or Gemini
- Anthropic API already integrated, consistent API surface
- Claude has strong structured output capabilities
- Avoid vendor lock-in to multiple AI providers in MVP
- Can add as alternatives later if needed

### Consequences
- May need to iterate on prompts for accuracy
- Complex table-variable correlations may need Sonnet
- User can trade cost for accuracy if needed

---

## TD-003: Frontend Framework - React + Tailwind

**Date:** 2026-02-11
**Status:** Decided

### Context
Need a frontend for image upload, dimension review, and 2D preview canvas.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| React + Tailwind + Vite | Large ecosystem, fast dev, good canvas libs | Requires Node.js tooling |
| Vue 3 + Tailwind | Simpler learning curve, good DX | Smaller ecosystem than React |
| Svelte + Tailwind | Excellent performance, less boilerplate | Smaller community, fewer libraries |
| Vanilla JS + CSS | No build step, simple | Slow development, manual state management |
| HTMX + Jinja | Server-rendered, Python-only stack | Limited interactivity for canvas preview |

### Decision
Use React with Tailwind CSS, bootstrapped with Vite.

### Rationale
1. Fast development with component-based architecture
2. Tailwind enables rapid styling without writing CSS files
3. Vite provides fast HMR and build times
4. Large ecosystem for drag-drop (react-dropzone), canvas (react-konva), etc.

### Why Not Vue/Svelte
- React has larger ecosystem for specialized components we need
- Team familiarity with React (assumed)
- More Stack Overflow answers and documentation available
- Not a strong reason against them; could work equally well

### Why Not HTMX
- 2D canvas preview requires significant client-side interactivity
- Drag-drop upload UX benefits from SPA approach
- Real-time confidence highlighting easier with React state

### Consequences
- Need Node.js tooling alongside Python backend
- Two build processes (frontend + backend)
- Slightly more complex deployment

---

## TD-004: Backend Framework - FastAPI

**Date:** 2026-02-11
**Status:** Decided

### Context
Need a Python backend for Claude API calls and file generation.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| FastAPI | Async, auto OpenAPI docs, Pydantic built-in | Newer, less battle-tested |
| Flask | Simple, mature, huge ecosystem | No async, manual validation |
| Django | Batteries included, ORM, admin | Heavyweight for API-only service |
| Node.js Express | Same language as frontend | Lose Python ecosystem for file generation |

### Decision
Use FastAPI.

### Rationale
1. Async support for non-blocking AI API calls
2. Automatic OpenAPI documentation generation
3. Pydantic integration for request/response validation
4. Python ecosystem for file I/O and text processing

### Why Not Flask
- No native async support - AI API calls would block
- Manual request validation with marshmallow/etc adds boilerplate
- FastAPI is essentially "Flask with async and Pydantic"

### Why Not Django
- Overkill for a stateless API service
- ORM not needed (no database in MVP)
- Admin panel not useful for this use case

### Why Not Node.js
- Python has better libraries for text/file manipulation
- Anthropic Python SDK is well-maintained
- Keeps backend in single language

### Consequences
- Requires Python 3.8+ with type hints
- May need async anthropic client for best performance

---

## TD-005: Coordinate System

**Date:** 2026-02-11
**Status:** Decided

### Context
Need to define coordinate system for pad positions.

### Alternatives Considered

| Option | Description |
|--------|-------------|
| Altium convention | Origin at center, +X right, +Y up, mm |
| KiCad convention | Origin at top-left, +X right, +Y down, mm |
| Datasheet convention | Varies per manufacturer |
| Mils-based | Origin at center, imperial units |

### Decision
Use Altium convention:
- Origin at component center
- +X points right
- +Y points up
- Units in millimeters
- Rotations in degrees (0° = pad horizontal)

### Rationale
1. Matches Altium's internal representation exactly
2. Ground truth data uses this convention
3. No coordinate transformation needed on export
4. Industry standard for component-centric coordinates

### Why Not KiCad Convention
- Would require Y-axis flip on export to Altium
- Additional transformation = additional bugs
- Our target is Altium, not KiCad

### Why Not Mils
- Metric (mm) is more common in modern datasheets
- Altium handles mm natively
- Easier mental math for users

### Consequences
- AI extraction must output in this coordinate system
- Preview canvas must mirror this orientation (+Y up)
- Any future KiCad export would need coordinate transformation

---

## TD-006: Job Storage - In-Memory (MVP)

**Date:** 2026-02-11
**Status:** Decided

### Context
Need to store extraction results between API calls (upload → extract → confirm → generate).

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| In-memory dict | Simple, fast, no dependencies | Lost on restart, no scaling |
| Redis | Fast, TTL support, scalable | External dependency, overkill for MVP |
| SQLite | Persistent, no server needed | Slower, needs schema management |
| PostgreSQL | Full-featured, scalable | Heavy dependency for MVP |
| File-based | Persistent, simple | Slow, concurrency issues |

### Decision
Use in-memory dictionary for MVP, keyed by job_id (UUID).

### Rationale
1. Stateless design for MVP (no user accounts)
2. Simplest possible implementation
3. Jobs are short-lived (minutes, not hours)
4. Can migrate to Redis/database later if needed

### Why Not Redis
- External service to manage adds complexity
- No horizontal scaling needed for MVP
- Over-engineering for demo/prototype stage

### Why Not SQLite/PostgreSQL
- No persistence needed - jobs are ephemeral
- Database schema management overhead
- Would suggest permanence that isn't needed

### Consequences
- Jobs lost on server restart (acceptable for MVP)
- No persistence across sessions
- Memory usage scales with concurrent jobs (acceptable for low traffic)
- Clear migration path to Redis if scaling needed

---

## TD-007: Pin 1 Handling

**Date:** 2026-02-11
**Status:** Decided

### Context
Pin 1 identification is critical for correct footprint orientation. Wrong Pin 1 = unusable footprint.

### Alternatives Considered

| Option | UX | Accuracy | Complexity |
|--------|-----|----------|------------|
| Always manual | Extra click every time | 100% (user decides) | Low |
| AI only | Zero clicks | ~70-90% | Medium |
| AI + manual fallback | Usually zero clicks | ~95%+ | Medium |
| Shape inference only | Zero clicks | ~60% | Low |

### Decision
AI detection with fallback to manual selection.

### Rationale
1. AI can often detect Pin 1 from visual cues (dot, chamfer, pad shape)
2. User confirmation provides safety net for critical dimension
3. Interactive selection is intuitive UX (click on preview)
4. Reduces clicks for well-marked components

### Why Not Always Manual
- Tedious for users when AI could easily detect it
- Many datasheets clearly mark Pin 1
- Unnecessary friction

### Why Not AI Only
- Pin 1 errors are catastrophic (board respin)
- AI confidence varies by datasheet quality
- User should always have override capability

### Why Not Shape Inference Only
- Not all Pin 1 pads have distinctive shapes
- Rounded rectangle isn't universal convention
- Too unreliable as sole method

### Consequences
- Need Pin1Selector component in frontend
- API must flag pin1_detected confidence
- UI flow branches based on detection result

---

## TD-008: Confidence Scoring

**Date:** 2026-02-11
**Status:** Decided

### Context
Need to communicate extraction uncertainty to users so they know what to verify.

### Alternatives Considered

| Option | User Experience | Implementation |
|--------|-----------------|----------------|
| No confidence display | Clean UI, user trusts all values | Simple |
| Binary (confident/uncertain) | Clear but loses nuance | Simple |
| Numeric score (0-100%) | Precise but overwhelming | Medium |
| Color-coded thresholds | Visual, scannable, intuitive | Medium |
| Detailed per-dimension breakdown | Maximum info, cluttered | Complex |

### Decision
- Per-pad confidence score (0-1)
- Overall extraction confidence score
- Visual highlighting: yellow (0.5-0.7), orange (<0.5), no highlight (>0.7)

### Rationale
1. Users need to know which values to double-check
2. Color coding is intuitive and fast to scan
3. Threshold-based highlighting is simple to implement
4. Numeric scores available for power users who want details

### Why Not No Confidence
- Users might blindly trust incorrect extractions
- Key differentiator from "dumb" tools
- Builds appropriate trust calibration

### Why Not Binary Only
- Loses useful gradation (0.51 vs 0.69 both "uncertain")
- Color thresholds give similar simplicity with more info

### Consequences
- AI prompt must output confidence per dimension
- Frontend must style based on confidence thresholds
- Users can trust high-confidence values, focus verification on low ones

---

---

## TD-009: Known Altium API Limitations (MVP)

**Date:** 2026-02-11
**Status:** Documented for future resolution

### Context
During Altium Designer 26 testing, several API limitations were discovered.

### Known Limitations

| Issue | Current Behavior | Workaround | Priority |
|-------|------------------|------------|----------|
| Rounded Rectangle pads | `eRoundRectShape` causes access violation crash | Using `eRectangular` as fallback | Medium |
| Slotted hole length | `HoleLength` property doesn't exist in AD26 | Using `HoleWidth` - **may not work correctly** | High |
| Script execution UX | Users must manually run scripts in Altium | Document clear procedure | Medium |

### Rounded Rectangle Issue
- Constant `eRoundRectShape` from documentation causes crashes
- Fallback: Generate as `eRectangular`, user manually sets corner radius
- Future: Research correct AD26 constant or use custom pad shape API

### Slotted Hole Issue
- `HoleLength` property is undeclared identifier in AD26
- Current attempt: Using `HoleWidth` property for slot length
- Need to verify if slots are created correctly
- Future: Research correct AD26 slot API properties

### Script Execution UX
- Current flow requires: Open project → Open library → Run script
- Not intuitive for first-time users
- Future: Consider Altium command-line automation or installer script

### Items to Revisit
1. [ ] Research AD26 rounded rectangle pad API
2. [ ] Verify slotted hole generation works correctly
3. [ ] Simplify user workflow for running scripts
4. [ ] Consider alternative output formats (PADS import, etc.)

---

## TD-010: Extraction Module Architecture

**Date:** 2026-02-11
**Status:** Implemented

### Context
Need to integrate Claude Vision API for extracting footprint dimensions from datasheet images.

### Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Response format | JSON schema in prompt | Ensures structured, parseable output |
| Error handling | Return ExtractionResponse with success flag | Explicit success/failure, no exceptions for user errors |
| Confidence scoring | Per-pad + overall | Matches UI requirements for uncertainty highlighting |
| Model flexibility | Model alias system | Easy swap between haiku/sonnet/opus |

### Key Components
- `FootprintExtractor` class - Main API wrapper
- `ExtractionResponse` dataclass - Result container
- `_response_to_footprint()` - Converts JSON to Pydantic models
- `estimate_cost()` - Cost estimation for UI display

### JSON Schema Approach
- Embed full schema in prompt with field descriptions
- Request "ONLY valid JSON, no other text"
- Parse response, handle markdown code block wrapping
- Validate against Pydantic models

### Consequences
- Consistent extraction format across models
- Easy to add validation rules
- Clear separation between API layer and business logic

---

## Future Decisions (To Be Made)

- **TD-011:** Production deployment strategy (Railway configuration)
- **TD-012:** Rate limiting and abuse prevention
- **TD-013:** Error recovery for partial extractions
