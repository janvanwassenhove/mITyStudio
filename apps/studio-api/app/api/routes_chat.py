from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.operations import ChatRequest, ChatResponse, OperationResult
from ..services import operation_applier, operation_planner, project_repo
from ..services.project_repo import ProjectNotFound

router = APIRouter(prefix="/api/projects", tags=["chat"])


# pipeline handoff acknowledgement, in the four app languages
_GEN_REPLY = {
    "en": "On it — I'm generating the full song in the background. You'll "
          "see the progress below; the tracks appear when it's done.",
    "nl": "Ik ben ermee bezig — het volledige nummer wordt in de achtergrond "
          "gegenereerd. Hieronder zie je de voortgang; de sporen verschijnen "
          "zodra het klaar is.",
    "fr": "C'est parti — je génère la chanson complète en arrière-plan. La "
          "progression s'affiche ci-dessous ; les pistes apparaîtront une "
          "fois terminé.",
    "de": "Bin dran — der komplette Song wird im Hintergrund generiert. "
          "Unten siehst du den Fortschritt; die Spuren erscheinen, sobald "
          "er fertig ist.",
}


@router.post("/{project_id}/chat")
def chat(project_id: str, req: ChatRequest) -> ChatResponse:
    try:
        project = project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")

    # a full-song request on an EMPTY project goes to the pipeline (producer
    # → skeleton → parallel composers → metrics → critic): complete by
    # construction, with per-part token budgets — the one-shot plan below is
    # where truncated half-songs came from. Projects with content keep the
    # normal chat flow (edits must stay conversational and instant), and the
    # MOCK provider keeps the synchronous planner too: it is instant and
    # deterministic, so the pipeline's async machinery buys nothing there.
    from ..services import song_pipeline
    if song_pipeline.detect_full_song_intent(req.message) \
            and song_pipeline._llm_available() \
            and not any(t.clips for t in project.tracks):
        job = song_pipeline.start(project_id, req.message,
                                  language=req.language)
        return ChatResponse(
            reply=_GEN_REPLY.get(req.language, _GEN_REPLY["en"]),
            operations=[], project=project.model_dump(), usage=None,
            job={"kind": "generate_song", "job_id": job["id"]})

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
