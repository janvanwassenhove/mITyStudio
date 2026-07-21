from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.operations import ChatRequest, ChatResponse, OperationResult
from ..services import operation_applier, operation_planner, project_repo
from ..services.project_repo import ProjectNotFound

router = APIRouter(prefix="/api/projects", tags=["chat"])


@router.post("/{project_id}/chat")
def chat(project_id: str, req: ChatRequest) -> ChatResponse:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")

    reply, operations, warnings, usage = operation_planner.plan(
        project, req.message, language=req.language)
    sections_before = {s.id for s in project.sections}
    results = operation_applier.apply_operations(project, operations)
    if any(r.applied for r in results):
        # a generated song with voice + lyrics must SING — fill any vocal
        # track whose lyric sections still lack a melody
        from ..services.vocal_autofill import ensure_vocal_melodies
        for line in ensure_vocal_melodies(project):
            results.append(OperationResult(op_type="auto_sing", summary=line,
                                           applied=True))
        # completeness: sections added THIS turn inherit the parts that
        # content-bearing tracks already play — additive only, template-gated
        # (a clip the user deleted stays deleted)
        from ..services.arrangement import fill_new_sections
        new_ids = {s.id for s in project.sections} - sections_before
        for line in fill_new_sections(project, new_ids):
            results.append(OperationResult(op_type="auto_arrange",
                                           summary=line, applied=True))
        # objective arrangement digest — surfaces truncated/incomplete songs
        # instead of letting them pass silently
        from ..services import arrangement_metrics
        m = arrangement_metrics.analyse(project)
        if m["incomplete_reasons"] and any(
                o.op_type in ("create_song", "add_section") for o in operations):
            results.append(OperationResult(
                op_type="(arrangement)", applied=True,
                summary="song check: " + arrangement_metrics.summary_line(m)
                        + " — " + "; ".join(m["incomplete_reasons"][:3])))
    for w in warnings:
        results.append(OperationResult(op_type="(planner)", summary="",
                                       applied=False, error=w))

    if any(r.applied for r in results):
        # final referential validation before persisting
        errors = project_repo.validate_references(project)
        if errors:
            results.append(OperationResult(
                op_type="(validation)", summary="", applied=False,
                error="; ".join(errors)))
            project = project_repo.load_project(project_id)  # discard changes
        else:
            project_repo.save_project(project)

    return ChatResponse(reply=reply,
                        operations=results,
                        project=project.model_dump(),
                        usage=usage)
