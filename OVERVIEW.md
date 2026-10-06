# Foldspec: from an idea to a sheet-metal part

**Working name:** Foldspec  
**Tagline:** Describe it. Shape it. Make it.  
**Project stage:** Research and planning  
**Initial market:** Makers and small teams in the United States  
**Initial supplier profile:** SendCutSend

Foldspec helps people who do not know CAD describe a simple sheet-metal part, refine its dimensions, preview it, and download a checked package they can submit to a fabrication supplier. The name is a working choice; domain and trademark availability have not been checked.

## Product direction

The product turns a plain-language request into a structured, editable design. AI helps interpret the request and asks for missing information. A versioned template and deterministic CAD code create the actual part. Manufacturing checks explain what passes, what needs attention, and what has not yet been verified.

The intended workflow is:

1. A person describes the part and what it needs to fit or do.
2. Foldspec asks for missing measurements and makes assumptions visible.
3. The person selects or confirms a supported part family, material, and dimensions.
4. Foldspec generates a preview and checks the geometry against the chosen supplier profile.
5. The person reviews and confirms the design, then downloads the fabrication package.
6. The person uploads the package to the supplier and places the order there.

The AI may select a supported recipe and propose parameter changes. It must not produce or execute arbitrary CAD code. The confirmed specification is the source of truth; previews, drawings, exports, and validation results derive from the same revision. Editing a specification creates a new revision and invalidates earlier validation.

## Initial scope

The first release targets straightforward parts that can be cut from one sheet and, where applicable, bent using full-width parallel 90-degree bends. Supported families are rectangular mounting plates, circular plates, L-brackets, U-channels, and Z-brackets. Supported cut features are round holes, slots, rectangular cutouts, and simple repeated hole patterns. Bent parts have no more than two bends in the initial scope.

Begin manufacturing validation with SendCutSend 5052-H32 aluminum at its listed 0.063-inch stock thickness. The supplier lists this material and thickness with bending service. Preserve the supplier's stated stock and process values in the supplier profile; do not silently round them. Every additional material and thickness needs its own documented checks and validation before being enabled. [SendCutSend 5052-H32 aluminum](https://sendcutsend.com/materials/5052-aluminum/)

Initial exports:

- Flat parts: clean, full-scale DXF.
- Bent parts: formed STEP with one uniform-thickness solid.
- Every part: dimensioned PDF, specification JSON, validation report, and instructions for supplier submission.

The v1 bent-part package does not include a production flat-pattern DXF. Flat patterns depend on supplier-specific bend parameters and need independent validation. SendCutSend identifies DXF as its preferred format for flat cuts and STEP/STP for parts with bends or forms. Its 3D requirements include one solid sheet-metal body, uniform thickness, and matching bend specifications. [SendCutSend file guidelines](https://sendcutsend.com/guidelines/sheet-cutting/) and [bending service guidelines](https://sendcutsend.com/services/cnc-bending/)

## Open problems and how the project addresses them

| Problem | Product or engineering response |
| --- | --- |
| A prompt can omit dimensions needed to make the part. | Ask focused questions about overall size, hole placement, fit, and use. Show assumptions; require confirmation of critical dimensions. |
| A generic 3D model may not be editable or suitable for a shop. | Create original parametric recipes with supported dimensions and manufacturing rules. Treat public models as references unless their licenses explicitly allow reuse. |
| Valid geometry can still be hard or impossible to fabricate. | Check supplier limits, bend geometry, feature spacing, and part size. Restrict recipes to ranges reviewed by a sheet-metal specialist. Flag conditions the software cannot verify. |
| Each shop, material, and thickness can have different rules. | Keep supplier rules in a versioned profile with source links, retrieval dates, and material/process identifiers. Block manufacturing export when a required rule is missing or stale. |
| A rendered preview can look right while dimensions or exports are wrong. | Build every representation from the same specification revision. Show critical dimensions and generate an explicit validation report. |
| An accepted upload does not prove the physical part will fit or perform safely. | Obtain expert review and inspect physical samples before self-service release. Do not claim structural suitability or support safety-critical or load-rated applications in v1. |
| Text-to-CAD and template builders already exist. | Focus on guided measurement capture, dependable edits, transparent checks, and supplier-specific preparation. See [Zoo's conversational CAD agent](https://docs.zoo.dev/zookeeper) and [SendCutSend's Parts Builder](https://sendcutsend.com/faq/how-to-use-the-parts-builder/). |

The initial commercial hypothesis is that makers and small teams will pay to avoid learning CAD and correcting rejected submissions. Validate that with pilot interviews and observed use before choosing a pricing model.

## Technical structure

The local prototype uses a React/TypeScript/Vite interface with React Three Fiber and Drei, a FastAPI/Pydantic service, SQLite project and revision storage, and CadQuery/OpenCascade geometry. OpenRouter handles model requests through its OpenAI-compatible Chat Completions API. The OpenRouter key stays in the ignored backend `.env` file. Generated CAD, meshes, drawings, and packages stay in the ignored local `data/` directory. See [README.md](README.md) for setup and start commands.

The prototype implements all five deterministic recipe families and creates a real single-solid STEP for formed parts or DXF for flat parts. It also emits a GLB preview, PDF, specification, validation findings, instructions, and an artifact-hash manifest. These are experimental exports; CadQuery format support alone does not establish supplier acceptance or manufacturing readiness. Bent-part cuts currently use the broad base web as their supported feature face. [CadQuery import and export](https://cadquery.readthedocs.io/en/stable/importexport.html)

Proposed repository layout:

```text
foldspec/
├── OVERVIEW.md, STATUS.md, README.md
├── apps/web/                 # Vite UI, guided edits, 3D review
├── services/api/             # FastAPI, Pydantic contracts, jobs, SQLite
├── suppliers/sendcutsend/    # Dated, incomplete supplier profile
├── data/                     # Ignored local DB, CAD artifacts, exports
└── tests/                    # Geometry and export regressions (in progress)
```

The current Pydantic interfaces are explicit and versioned. Run `make contracts` to write JSON Schemas and matching TypeScript definitions from the same backend contracts:

- **Part specification:** schema version, recipe and recipe version, dimensions and units, material/stock identifier, face-based hole and cutout features, quantity, supplier profile, and user-confirmed requirements.
- **Validation report:** status, errors, warnings, unverified checks, affected feature or dimension, and the supplier rule and source supporting each finding.
- **Build result:** specification revision, generator version, preview, manufacturing file(s), drawing, validation report, and export manifest.

Use millimeters as the internal geometry unit; accept inch or millimeter input and label them clearly. Label inside and outside dimensions explicitly. Anchor feature positions to stable recipe faces and datums instead of fragile face indices. The current prototype serializes CAD generation in one local worker and keeps project artifacts private. Process-level resource isolation and cancellation remain future hardening work.

The OpenRouter integration uses `OPENROUTER_API_KEY` and optional `OPENROUTER_MODEL` (default `openai/gpt-5.4-mini`), strict structured output with required provider parameters, and independent Pydantic validation. AI returns a proposal; deterministic recipe code creates geometry. The browser never receives the key.

## Validation and release gates

1. **Prove the manufacturing path.** Generate one flat plate and one L-bracket from hand-authored specifications. Reopen files in independent CAD software, verify scale and dimensions, and test supplier upload before building the guided AI workflow.
2. **Validate the recipes.** Add the remaining part families and supplier checks. Have a sheet-metal specialist review the supported ranges and manufacture representative samples.
3. **Build the guided workflow.** Add clarification, dimension editing, preview, revision history, validation explanations, and downloadable packages.
4. **Run an assisted pilot.** Work with five target users. Track completion time, expert intervention, rejected uploads, fit problems, generation cost, and willingness to pay.
5. **Enable capabilities from evidence.** Require supplier upload acceptance and a measured physical sample for each enabled recipe and material/thickness combination. Upload acceptance is one checkpoint, not proof of successful manufacture.

Checks should cover unit conversion, inside/outside dimensions, ambiguous requests, feature placement, minimum hole and cutout size, bend proximity, flange and part limits, self-intersection, invalid or stale supplier rules, CAD generation failures, and edits after review. Exports must reopen at the correct scale and match the confirmed specification. Samples must meet applicable documented tolerances and the user's confirmed fit requirements.

## Deferred from v1

Defer trays with intersecting bends, enclosed boxes, assemblies, welding, installed hardware, arbitrary CAD imports, integrated quoting or ordering, and automatic structural analysis. Also defer generated production flat patterns for bent parts until their bend calculation and exports are independently validated.

## Reference catalog

These sources inform the design and supplier rules; they are not an approved asset library.

- [SendCutSend bracket templates](https://sendcutsend.com/template-category/brackets/) — inspiration for common bracket use cases. Check each asset's terms before copying or distributing it.
- [FreeCAD SheetMetal Workbench](https://github.com/shaise/FreeCAD_SheetMetal) — reference for sheet-metal features and unfolding. Review its GPL-3.0 license before incorporating code or derived assets.
- [SendCutSend sheet-cutting guidelines](https://sendcutsend.com/guidelines/sheet-cutting/) — file formats, geometry requirements, and upload checks.
- [SendCutSend bending guidelines](https://sendcutsend.com/services/cnc-bending/) — supplier bend capabilities and design rules.
- [SendCutSend 5052-H32 material catalog](https://sendcutsend.com/materials/5052-aluminum/) — listed stock and service availability.
- [CadQuery documentation](https://cadquery.readthedocs.io/en/stable/importexport.html) — proposed programmatic CAD geometry and exchange formats.
- [Zoo conversational CAD](https://docs.zoo.dev/zookeeper) and [SendCutSend Parts Builder](https://sendcutsend.com/faq/how-to-use-the-parts-builder/) — adjacent products to consider during product discovery.

The long-term asset is the tested recipe and supplier-rule library, with manufacturing evidence and clear provenance—not a pile of generic 3D models.
