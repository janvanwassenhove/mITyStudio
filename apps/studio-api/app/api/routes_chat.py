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

    reply, operations, warnings = operation_planner.plan(project, req.message,
                                                         language=req.language)
    results = operation_applier.apply_operations(project, operations)
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
                        project=project.model_dump())
