# Foldspec project status

**Last updated:** October 4, 2026  
**Stage:** Local prototype implementation  
**Current milestone:** B — build and verify the first plate and L-bracket; in parallel, finish the inspection workspace.

This is an evidence tracker. Work is `Not started`, `In progress`, `Blocked`, or `Done`. Mark an item `Done` only when its acceptance criterion has evidence linked here. Owners remain explicitly unassigned.

## Current snapshot

- **Implemented locally:** React/TypeScript inspection workspace, FastAPI/Pydantic API, SQLite projects and immutable specification snapshots, one-at-a-time CAD jobs, five CadQuery recipes, generated GLB/DXF/STEP/PDF/ZIP artifacts, and OpenRouter structured proposals.
- **Smoke-tested:** all five default recipes export valid one-solid files and a through-hole on each cuts geometry. Thirteen backend tests pass, frontend production build passes, and a live OpenRouter proposal was applied in browser. Supplier profile is explicitly incomplete; all exports are experimental.
- **Not yet demonstrated:** independent CAD reopen and dimension audit, supplier upload acceptance, specialist review, physical samples, or customer pilot.

## Next three actions

1. Start the local app, exercise a live OpenRouter description-to-proposal flow, then apply a proposal and verify stale-revision handling.
2. Reopen the generated plate DXF and L-bracket STEP in independent CAD software, check units/dimensions, and record any repair needed.
3. Ask a sheet-metal specialist to review the sourced supplier profile and the recipe parameter limits, then submit representative files for supplier feedback.

## Work tracker

| ID | Priority | Status | Owner | Dependency | Acceptance criterion | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| FOLD-001 | P0 | In progress | Unassigned | Current supplier documentation | Dated profile captures stock, file formats, bend/feature/size limits, sources, unknowns, and review deadline; missing rules stay explicit. | [Profile](suppliers/sendcutsend/5052-h32-0.063.json) |
| FOLD-002 | P0 | In progress | Unassigned | FOLD-001 | Plate and L-bracket datums, dimensions, feature faces, parameter limits, and hand-authored examples are documented. | [CAD recipes](services/api/cad.py) |
| FOLD-003 | P0 | In progress | Unassigned | FOLD-002 | Plate DXF and bent L-bracket STEP reopen independently at the correct scale and match approved dimensions. | Local geometry smoke test passed; independent inspection pending. |
| FOLD-004 | P0 | Not started | Unassigned | FOLD-001, FOLD-003 | Supplier accepts representative flat and bent files for processing or quote; responses and file versions are recorded. | — |
| FOLD-005 | P0 | Not started | Unassigned | FOLD-001, FOLD-002 | Specialist reviews recipe ranges, bend assumptions, feature spacing, and checks. | — |
| FOLD-006 | P1 | Not started | Unassigned | FOLD-004, FOLD-005; sample budget | Representative parts are measured against documented dimensions, tolerance, and confirmed fit requirements. | — |
| FOLD-007 | P0 | Done | Unassigned | Contract decisions | Versioned DraftSpec, PartSpec, proposal, validation, build, and inspection contracts; generated JSON Schema and TypeScript types agree. | [Contract generator](scripts/generate_contracts.py); [generated schemas](contracts/); [generated TypeScript](apps/web/src/generated/contracts.ts). |
| FOLD-008 | P1 | In progress | Unassigned | FOLD-001, FOLD-002 | Five recipe families and supported cut features pass geometry, bounds, units, failure, and regression tests. | Five-family one-solid smoke test passed; committed tests pending. |
| FOLD-009 | P1 | In progress | Unassigned | FOLD-007, FOLD-008; specialist review | User can create, reopen, edit, revise, inspect, validate, and export with stale results clearly labeled. | [Web workspace](apps/web/src/App.tsx); browser walkthrough pending. |
| FOLD-010 | P2 | Not started | Unassigned | FOLD-006, FOLD-009; customer access | Five target users complete an assisted pilot; time, interventions, rejections, fit, cost, and willingness to pay are recorded. | — |
| FOLD-011 | P2 | Not started | Unassigned | FOLD-006, FOLD-010 | Every capability enabled for self-service has supplier acceptance and a measured sample for that family and stock combination. | — |

**Priority key:** P0 proves the manufacturing path and foundational contracts; P1 establishes reviewed product capability; P2 supports an evidence-based pilot and release decision.

## Current milestone

Milestone A (foundation) is complete: project docs, local configuration, persistence, immutable specification snapshots, generated contracts, and the dated supplier-profile structure are in place. Milestone B has all five experimental families and package exports, but independent CAD inspection and supplier feedback remain open. Milestone C's desktop and narrow-screen workspace, camera presets, display controls, feature selection, units, chat, forms, and revision display were exercised in a live browser. Further boundary and interaction coverage remains.

## Decisions recorded

| Date | Decision | Rationale or evidence |
| --- | --- | --- |
| 2026-10-04 | Use Foldspec as the working name. | User selected this direction; domain and trademark availability remain unverified. |
| 2026-10-04 | Local React/TypeScript/Vite UI, FastAPI/Pydantic API, SQLite, and CadQuery/OpenCascade. | Supports local project storage and deterministic geometry generation. |
| 2026-10-04 | Use OpenRouter Chat Completions for every model request. | Key remains backend-only; model ID is configurable, with `openai/gpt-5.4-mini` as default. |
| 2026-10-04 | Begin with US makers and teams, SendCutSend, and 5052-H32 0.063-inch stock. | Bounds the first material and supplier investigation; process limits remain unverified. |
| 2026-10-04 | Generate DXF for flat parts and STEP for bent parts. | Matches the supplier's published file guidance; files still require independent and supplier checks. |
| 2026-10-04 | Keep every generated package experimental until evidence supports a narrower validated capability. | Geometry, supplier acceptance, and physical fit are distinct evidence states. |
| 2026-10-04 | Defer ordering, bent-part flat-pattern DXF, assemblies, welding, arbitrary imports, and structural analysis. | These need separate process support and validation. |

## Dependencies and risks

- **Sheet-metal reviewer:** No specialist is assigned; reviewed parameter ranges and bend assumptions are outstanding.
- **Supplier evidence:** The current sourced profile lists known stock/file guidance and clearly marks limits that need direct confirmation. Refresh within 30 days before relying on it.
- **Independent CAD and supplier testing:** Locally valid geometry is not equivalent to exchange-file interoperability or supplier acceptance.
- **Physical samples and budget:** No budget or sample schedule is set. A single sample cannot validate every range.
- **Customer access and pricing:** The five-person assisted pilot and willingness-to-pay interviews have not started.
- **Security:** The user-provided OpenRouter credential is stored only in the ignored local `.env`; verify source/build/package scans before sharing this checkout.
- **Feature-face limitation:** Initial bent-part cuts apply to the broad base web. Side-flange holes and other bent-face features need explicit face mapping before support is claimed.
- **Isolation:** CAD jobs are serialized locally, but process-level resource isolation/cancellation and multi-user hardening remain future work.
- **Commercial/name validation:** Domain, trademark, pricing, and product-market hypotheses remain open.

## Risks

| Risk | Current handling | Next evidence |
| --- | --- | --- |
| AI invents dimensions or unsupported features. | Structured proposal schema, targeted prompt constraints, manual form edits, and Pydantic parsing. | Test ambiguous requests, unsupported asks, malformed responses, refusals, and API failures. |
| A preview obscures stale geometry. | Revision label, retained last successful model, current-revision-only export. | Exercise invalid build and interrupted-job scenarios in browser. |
| Generated solid is not supplier manufacturable. | Experimental labels and incomplete supplier profile; no validated claim. | Specialist review, upload acceptance, and measured samples. |
| Export package does not match approved geometry. | Export artifacts and preview originate from the same CadQuery solid/spec revision. | Independent reopen, scale audit, geometry comparison, and artifact hash check. |

## Dated progress

### 2026-10-04 — Implementation pass

- Built the local responsive interface and 3D inspector with model selection, camera/display controls, dimension inputs, chat proposals, and revision controls.
- Added local FastAPI and SQLite persistence, immutable specification snapshots, serialized CAD jobs, OpenRouter structured proposals, supplier profile data, and artifact downloads.
- Implemented five starter CadQuery recipes. Tests cover each one-solid recipe, face-local through-holes, out-of-bounds features, immutable restore revisions, and a hashed experimental STEP package.
- Built experimental DXF/STEP, GLB, PDF, JSON, and ZIP export paths. Manufacturing evidence and independent export checks remain open.
- Ran a live OpenRouter edit proposal in the browser, applied it as a revision, reopened it, and inspected desktop and narrow layouts. Frontend build and all 13 backend tests pass.

### 2026-10-04 — Research baseline

- Documented product direction, scope, references, initial supplier, and manufacturing validation gates.

## Update instructions

Update this file when evidence or decisions change. Link a reproducible artifact, supplier response, review record, or test result for each completed item. If blocked, name the blocker and what resolves it. Never change an unknown owner to a name without an explicit owner.
