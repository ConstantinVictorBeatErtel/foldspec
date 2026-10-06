from __future__ import annotations

import json
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from .cad import DATA_DIR, default_spec, export_build
from .models import BuildResult, DesignProposal, DisplayUnits, PartSpec, Project, TemplateId
from .store import connect, get, get_revision, initialize, list_projects, list_revisions, save


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

app = FastAPI(title="Foldspec", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="foldspec-cad")
futures: dict[str, Future] = {}
lock = threading.Lock()


class CreateProject(BaseModel):
    name: str = "Untitled part"
    template_id: TemplateId = TemplateId.RECT_PLATE


class EditProject(BaseModel):
    name: str | None = None
    display_units: DisplayUnits | None = None


class EditSpec(BaseModel):
    based_on_revision: int
    spec: PartSpec


class ChatInput(BaseModel):
    message: str
    based_on_revision: int


class ProposalEnvelope(BaseModel):
    """Strict-schema envelope; the spec JSON is independently parsed as PartSpec."""

    model_config = ConfigDict(extra="forbid")
    message: str
    questions: list[str]
    proposed_changes: list[str]
    spec_json: str | None
    based_on_revision: int


def _job(job_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "project_id": row["project_id"], "revision": row["revision"], "status": row["status"], "result": json.loads(row["result"]) if row["result"] else None}


def _run_build(job_id: str, project_id: str, revision: int, spec_json: str) -> None:
    with connect() as db:
        db.execute("UPDATE jobs SET status='running' WHERE id=?", (job_id,))
    result = export_build(PartSpec.model_validate_json(spec_json))
    with connect() as db:
        db.execute("UPDATE jobs SET status=?, result=? WHERE id=?", ("succeeded" if result.geometry_status == "valid" else "failed", result.model_dump_json(), job_id))
    project = get(project_id)
    if project and project.revision == revision and result.geometry_status == "valid":
        project.build = result
        save(project)


def _queue_build(project: Project) -> dict:
    from uuid import uuid4
    job_id = str(uuid4())
    with connect() as db:
        db.execute("INSERT INTO jobs(id, project_id, revision, status, spec_json) VALUES (?, ?, ?, 'queued', ?)", (job_id, project.id, project.revision, project.spec.model_dump_json()))
    future = executor.submit(_run_build, job_id, project.id, project.revision, project.spec.model_dump_json())
    with lock:
        futures[job_id] = future
    return _job(job_id) or {"id": job_id, "status": "queued"}


@app.on_event("startup")
def startup() -> None:
    initialize()
    with connect() as db:
        db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        pending = db.execute("SELECT jobs.id, projects.id AS project_id, jobs.revision, jobs.spec_json FROM jobs JOIN projects ON projects.id=jobs.project_id WHERE jobs.status='queued'").fetchall()
    for row in pending:
        executor.submit(_run_build, row["id"], row["project_id"], row["revision"], row["spec_json"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "ai_configured": bool(os.getenv("OPENROUTER_API_KEY")), "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-5.4-mini")}


@app.get("/api/templates")
def templates() -> list[dict]:
    return [{"id": item.value, "label": item.value.replace("_", " ").title(), "spec": default_spec(item).model_dump()} for item in TemplateId]


@app.get("/api/suppliers/sendcutsend/profile")
def supplier_profile() -> dict:
    from .cad import _profile
    return _profile("sendcutsend-5052-h32-0.063in")


@app.get("/api/projects")
def projects() -> list[Project]:
    return list_projects()


@app.post("/api/projects")
def create_project(body: CreateProject) -> Project:
    project = Project(name=body.name, spec=default_spec(body.template_id))
    save(project)
    return project


@app.get("/api/projects/{project_id}")
def read_project(project_id: str) -> Project:
    project = get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, body: EditProject) -> Project:
    project = get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if body.name is not None:
        project.name = body.name[:100]
    if body.display_units is not None:
        project.display_units = body.display_units
    return save(project)


@app.get("/api/projects/{project_id}/revisions")
def revisions(project_id: str) -> list[Project]:
    if not get(project_id):
        raise HTTPException(404, "Project not found")
    return list_revisions(project_id)


@app.post("/api/projects/{project_id}/restore/{revision}")
def restore_revision(project_id: str, revision: int) -> Project:
    project = get(project_id)
    previous = get_revision(project_id, revision)
    if not project or not previous:
        raise HTTPException(404, "Project or revision not found")
    project.spec = previous.spec
    project.spec.revision = project.revision + 1
    project.conversation.append({"role": "system", "content": f"Restored design from revision {revision}."})
    save(project, new_revision=True)
    return project


@app.put("/api/projects/{project_id}/spec")
def update_spec(project_id: str, body: EditSpec) -> dict:
    project = get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if body.based_on_revision != project.revision:
        raise HTTPException(409, "This edit was based on an older revision. Refresh the project and try again.")
    proposed = body.spec
    proposed.revision = project.revision + 1
    # Validate candidate geometry before making the revision current.
    from .cad import build_part
    try:
        solid, _ = build_part(proposed)
        if not solid.val().isValid() or len(solid.val().Solids()) != 1:
            raise ValueError("The edit does not produce one valid solid.")
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    project.spec = proposed
    project.conversation.append({"role": "system", "content": f"Dimensions saved as revision {proposed.revision}."})
    save(project, new_revision=True)
    return {"project": project, "job": _queue_build(project)}


@app.post("/api/projects/{project_id}/build")
def build_project(project_id: str) -> dict:
    project = get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _queue_build(project)


@app.post("/api/projects/{project_id}/chat")
def chat(project_id: str, body: ChatInput) -> dict:
    project = get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.revision != body.based_on_revision:
        raise HTTPException(409, "This message refers to an older revision. Refresh the project and try again.")
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "OpenRouter is not configured. Add OPENROUTER_API_KEY to the ignored local .env file.")
    from .models import DesignProposal
    context = {"current_revision": project.revision, "specification": project.spec.model_dump(), "supported_templates": [t.value for t in TemplateId], "supported_features": ["round through-holes", "slots", "rectangular cutouts", "simple repeated hole patterns"]}
    messages = [{"role": "system", "content": "You help edit simple sheet metal parts. Return a proposal or clarification question only. Never claim a design is manufacturable or validated. Never invent critical dimensions. Preserve dimensions and features the user did not ask to change. Use only supported templates and parameters. Follow the provided JSON schema exactly. Current design context: " + json.dumps(context)}, *project.conversation[-12:], {"role": "user", "content": body.message}]
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=45, max_retries=1)
    try:
        schema = ProposalEnvelope.model_json_schema()
        # OpenAI-compatible strict schemas require every object property to be
        # required and disallow undeclared properties. The specification itself
        # is a JSON string here because its parameter map is recipe-dependent;
        # it is then parsed and fully validated by Pydantic below.
        def strictify(node: object) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                    node["required"] = list(node["properties"].keys())
                    node["additionalProperties"] = False
                for value in node.values():
                    strictify(value)
            elif isinstance(node, list):
                for value in node:
                    strictify(value)
        strictify(schema)
        response = client.chat.completions.create(model=os.getenv("OPENROUTER_MODEL", "openai/gpt-5.4-mini"), messages=messages, response_format={"type": "json_schema", "json_schema": {"name": "design_proposal", "strict": True, "schema": schema}}, extra_body={"provider": {"require_parameters": True}})
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("The model returned an empty response.")
        envelope = ProposalEnvelope.model_validate_json(raw)
        proposal = DesignProposal(message=envelope.message, questions=envelope.questions, proposed_changes=envelope.proposed_changes, spec=PartSpec.model_validate_json(envelope.spec_json) if envelope.spec_json else None, based_on_revision=envelope.based_on_revision)
        if proposal.based_on_revision != project.revision:
            raise ValueError("The model response refers to a stale revision.")
        if proposal.spec:
            proposal.spec.revision = project.revision + 1
            if proposal.spec.template_id not in TemplateId:
                raise ValueError("The model suggested an unsupported template.")
    except Exception as exc:
        detail = str(exc).replace(api_key, "[redacted]") if api_key else str(exc)
        raise HTTPException(502, f"OpenRouter could not return a valid design proposal: {detail[:600]}") from exc
    project.conversation.extend([{"role": "user", "content": body.message}, {"role": "assistant", "content": proposal.message}])
    save(project)
    return {"proposal": proposal, "project": project, "usage": response.usage.model_dump() if response.usage else None}


@app.get("/api/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    try:
        UUID(job_id)
    except ValueError as exc:
        raise HTTPException(404, "Job not found") from exc
    job = _job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/artifacts/{build_id}/{filename}")
def artifact(build_id: str, filename: str) -> FileResponse:
    try:
        UUID(hex=build_id)
    except ValueError as exc:
        raise HTTPException(404, "Artifact not found") from exc
    if filename not in {"model.glb", "foldspec-package.zip"}:
        raise HTTPException(404, "Artifact not found")
    target = DATA_DIR / "builds" / build_id / filename
    if not target.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(target, filename=filename)
