import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import _normalized, analyze_with_provider, get_ai_config
from .ai_settings import delete_local_ai_settings, read_local_ai_settings, write_local_ai_settings
from .database import Base, engine, ensure_person_identity_schema, get_db
from .models import Case, Finding, Link, Person, PersonIdentity, Source, UsernameHandle, UsernameScan, UsernameScanResult
from .username_search import MAX_SITES_PER_SEARCH, list_sites as list_username_sites, run_username_checks
from .schemas import (
    AIAnalysisOut,
    AIAnalysisRequest,
    AIClaimOut,
    AISettingsOut,
    AISettingsUpdate,
    AISourceRef,
    CaseCreate,
    CaseOut,
    EvidenceOut,
    FindingCreate,
    FindingOut,
    GlobalPersonOut,
    UsernameHandlesCreate,
    UsernameHandleOut,
    UsernameSiteOut,
    UsernameSearchRequest,
    UsernameScanOut,
    UsernameScanResultOut,
    GraphEdge,
    GraphNode,
    GraphOut,
    PersonCreate,
    PersonOut,
    RelationshipCreate,
    RelationshipOut,
    SourceCreate,
    SourceOut,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_person_identity_schema()
    yield


app = FastAPI(
    title="Fieldnotes — Research Graph",
    description=(
        "A local-first workspace for researcher-entered, source-backed public-interest research. "
        "Claims are not verified facts; review sources and identities independently."
    ),
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "local-first", "automated_collection": False}


def require_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return case


def _ai_settings_summary() -> dict:
    try:
        saved = read_local_ai_settings()
    except ValueError:
        return {
            "provider_name": "Saved local provider settings",
            "base_url": "",
            "model": "",
            "enabled": False,
            "api_key_configured": False,
            "source": "local",
        }
    if saved is not None:
        return {
            "provider_name": saved["provider_name"],
            "base_url": saved["base_url"],
            "model": saved["model"],
            "enabled": saved["enabled"],
            "api_key_configured": bool(saved["api_key"]),
            "source": "local",
        }
    config = get_ai_config()
    environment_configured = any(os.getenv(key) for key in ("AI_BASE_URL", "AI_MODEL", "AI_API_KEY"))
    raw_url = os.getenv("AI_BASE_URL", "")
    parsed = urlsplit(raw_url) if raw_url else None
    safe_url = raw_url if parsed and parsed.scheme in {"http", "https"} and parsed.hostname and not (parsed.username or parsed.password or parsed.query or parsed.fragment) else ""
    return {
        "provider_name": os.getenv("AI_PROVIDER_NAME", "OpenAI-compatible provider"),
        "base_url": safe_url,
        "model": os.getenv("AI_MODEL", ""),
        "enabled": config.enabled,
        "api_key_configured": bool(os.getenv("AI_API_KEY")),
        "source": "environment" if environment_configured else "none",
    }


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin.rstrip("/") != expected:
            raise HTTPException(status_code=403, detail="Cross-origin settings changes are not allowed")


def _validate_ai_endpoint(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="Use a provider base URL without embedded credentials, query, or fragment")
    host = parsed.hostname.lower()
    if parsed.scheme == "https":
        return value
    if parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}:
        return value
    raise HTTPException(status_code=422, detail="Provider URL must use HTTPS; HTTP is allowed only for localhost")


@app.get("/api/ai/settings", response_model=AISettingsOut)
def ai_settings():
    return _ai_settings_summary()


@app.put("/api/ai/settings", response_model=AISettingsOut)
def update_ai_settings(payload: AISettingsUpdate, request: Request):
    _require_same_origin(request)
    api_key = payload.api_key.get_secret_value().strip()
    if len(api_key) > 8192 or "\\n" in api_key or "\\r" in api_key:
        raise HTTPException(status_code=422, detail="API key format is invalid")
    try:
        current = read_local_ai_settings()
    except ValueError:
        current = None
    api_key = api_key or (current or {}).get("api_key", "") or os.getenv("AI_API_KEY", "")
    if payload.enabled and not api_key:
        raise HTTPException(status_code=422, detail="Paste an API key before enabling AI")
    local_settings = {
        "provider_name": payload.provider_name.strip(),
        "base_url": _validate_ai_endpoint(payload.base_url),
        "model": payload.model.strip(),
        "api_key": api_key,
        "enabled": payload.enabled,
    }
    write_local_ai_settings(local_settings)
    return _ai_settings_summary()


@app.delete("/api/ai/settings", response_model=AISettingsOut)
def clear_ai_settings(request: Request):
    _require_same_origin(request)
    delete_local_ai_settings()
    return _ai_settings_summary()


@app.get("/api/ai/status")
def ai_status():
    config = get_ai_config()
    return {
        "enabled": config.enabled,
        "provider_name": config.provider_name,
        "model": config.model if config.enabled else "",
        "reason": config.reason,
        "uses_live_search": False,
        "stores_ai_responses": False,
    }


@app.post("/api/cases/{case_id}/ai/analyze", response_model=AIAnalysisOut)
def analyze_case_material(
    case_id: str,
    payload: AIAnalysisRequest,
    db: Session = Depends(get_db),
):
    config = get_ai_config()
    if not config.enabled:
        raise HTTPException(status_code=503, detail="AI analysis is not configured on this server")
    if not payload.confirm_provider_share:
        raise HTTPException(status_code=422, detail="Confirm that selected material may be sent to the configured provider")
    if len(set(payload.source_ids)) != len(payload.source_ids):
        raise HTTPException(status_code=422, detail="Select each source only once")

    require_case(db, case_id)
    selected_sources = list(
        db.scalars(
            select(Source).where(Source.case_id == case_id, Source.id.in_(payload.source_ids))
        )
    )
    source_by_id = {source.id: source for source in selected_sources}
    if len(source_by_id) != len(payload.source_ids):
        raise HTTPException(status_code=404, detail="One or more sources were not found in this investigation")

    selected_ids = set(payload.source_ids)
    people = list(db.scalars(select(Person).where(Person.case_id == case_id)))
    person_names = {person.id: person.name for person in people}
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.case_id == case_id, Finding.source_id.in_(selected_ids))
            .order_by(Finding.created_at.desc())
            .limit(30)
        )
    )
    relationships = list(
        db.scalars(
            select(Link)
            .where(Link.case_id == case_id, Link.source_id.in_(selected_ids))
            .order_by(Link.created_at.desc())
            .limit(30)
        )
    )

    materials: list[dict] = []
    excerpts_by_source: dict[str, list[str]] = {source_id: [] for source_id in selected_ids}
    for source_id in payload.source_ids:
        source = source_by_id[source_id]
        source_findings = [finding for finding in findings if finding.source_id == source_id][:3]
        source_relationships = [link for link in relationships if link.source_id == source_id][:3]
        finding_material = []
        for finding in source_findings:
            excerpt = finding.excerpt[:1200]
            finding_material.append({
                "person_name": person_names.get(finding.person_id, ""),
                "claim_already_recorded": finding.claim[:500],
                "excerpt": excerpt,
            })
            if excerpt:
                excerpts_by_source[source_id].append(excerpt)
        relationship_material = []
        for link in source_relationships:
            relationship_material.append({
                "person_a": person_names.get(link.source_person_id, ""),
                "person_b": person_names.get(link.target_person_id, ""),
                "label_already_recorded": link.label[:240],
                "notes": link.details[:500],
            })
        materials.append({
            "source_id": source.id,
            "title": source.title,
            "publisher": source.publisher,
            "published_on": source.published_on.isoformat() if source.published_on else None,
            "findings": finding_material,
            "relationships": relationship_material,
        })

    result = analyze_with_provider(config, payload.question, materials, case_id)
    allowed_ids = set(source_by_id)
    claims = []
    for claim in result.claims:
        cited_ids = [source_id for source_id in claim.source_ids if source_id in allowed_ids]
        quote = claim.evidence_quote.strip()
        quote_normalized = _normalized(quote)
        quote_verified = bool(quote_normalized) and any(
            quote_normalized in _normalized(excerpt)
            for source_id in cited_ids
            for excerpt in excerpts_by_source[source_id]
        )
        claims.append(AIClaimOut(
            text=claim.text,
            source_ids=cited_ids,
            evidence_quote=quote,
            confidence=claim.confidence,
            quote_verified=quote_verified,
        ))

    return AIAnalysisOut(
        provider_name=config.provider_name,
        model=config.model,
        summary=result.summary,
        claims=claims,
        open_questions=result.open_questions,
        sources=[
            AISourceRef(id=source.id, title=source.title, url=source.url, retrieved_on=source.retrieved_on)
            for source in selected_sources
        ],
        saved=False,
        disclaimer="AI-generated draft based only on selected saved material. Verify every claim and quotation against the source; this result is not saved automatically.",
    )


@app.get("/api/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db)):
    return list(db.scalars(select(Case).order_by(Case.created_at.desc())))


@app.post("/api/cases", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    case = Case(title=payload.title.strip(), purpose=payload.purpose.strip())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get("/api/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    return require_case(db, case_id)


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    db.delete(case)
    db.commit()
    return Response(status_code=204)


@app.get("/api/people", response_model=list[GlobalPersonOut])
def search_global_people(
    q: str = Query(default="", max_length=140),
    db: Session = Depends(get_db),
):
    statement = select(PersonIdentity)
    if q.strip():
        statement = statement.where(PersonIdentity.canonical_name.ilike(f"%{q.strip()}%"))
    return list(db.scalars(statement.order_by(PersonIdentity.canonical_name).limit(50)))


@app.get("/api/cases/{case_id}/people", response_model=list[PersonOut])
def list_people(
    case_id: str,
    q: str = Query(default="", max_length=140),
    db: Session = Depends(get_db),
):
    require_case(db, case_id)
    statement = select(Person).where(Person.case_id == case_id)
    if q.strip():
        statement = statement.where(Person.name.ilike(f"%{q.strip()}%"))
    return list(db.scalars(statement.order_by(Person.name)))


@app.post("/api/cases/{case_id}/people", response_model=PersonOut, status_code=201)
def create_person(case_id: str, payload: PersonCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    identity = None
    if payload.identity_id:
        identity = db.get(PersonIdentity, payload.identity_id)
        if identity is None:
            raise HTTPException(status_code=404, detail="Shared person identity not found")
        existing_membership = db.scalar(
            select(Person).where(Person.case_id == case_id, Person.identity_id == identity.id)
        )
        if existing_membership is not None:
            raise HTTPException(status_code=409, detail="This shared person is already in the investigation")
    else:
        identity = PersonIdentity(canonical_name=payload.name)
        db.add(identity)
        db.flush()

    relationship_payload = payload.initial_relationship
    other_person = None
    relationship_source = None
    if relationship_payload:
        other_person = db.scalar(
            select(Person).where(
                Person.case_id == case_id,
                Person.id == relationship_payload.other_person_id,
            )
        )
        relationship_source = db.scalar(
            select(Source).where(
                Source.case_id == case_id,
                Source.id == relationship_payload.source_id,
            )
        )
        if other_person is None or relationship_source is None:
            raise HTTPException(status_code=404, detail="Connection person or supporting source not found in this investigation")
        if identity.id == other_person.identity_id:
            raise HTTPException(status_code=422, detail="A person cannot be connected to the same shared identity")

    person = Person(
        case_id=case_id,
        identity_id=identity.id,
        name=payload.name,
        aliases=payload.aliases,
        notes=payload.notes,
    )
    db.add(person)
    db.flush()
    if relationship_payload and other_person and relationship_source:
        db.add(Link(
            case_id=case_id,
            source_person_id=person.id,
            target_person_id=other_person.id,
            source_id=relationship_source.id,
            label=relationship_payload.label,
            details=relationship_payload.details,
            confidence=relationship_payload.confidence,
            status=relationship_payload.status,
        ))
    db.commit()
    db.refresh(person)
    return person


@app.get("/api/username/sites", response_model=list[UsernameSiteOut])
def get_username_sites():
    return list_username_sites()


@app.get("/api/cases/{case_id}/people/{person_id}/usernames", response_model=list[UsernameHandleOut])
def list_person_usernames(case_id: str, person_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    person = db.scalar(select(Person).where(Person.case_id == case_id, Person.id == person_id))
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in this investigation")
    return list(db.scalars(
        select(UsernameHandle)
        .where(UsernameHandle.case_id == case_id, UsernameHandle.person_id == person_id)
        .order_by(UsernameHandle.created_at)
    ))


@app.post("/api/cases/{case_id}/people/{person_id}/usernames", response_model=list[UsernameHandleOut], status_code=201)
def add_person_usernames(
    case_id: str,
    person_id: str,
    payload: UsernameHandlesCreate,
    db: Session = Depends(get_db),
):
    require_case(db, case_id)
    person = db.scalar(select(Person).where(Person.case_id == case_id, Person.id == person_id))
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found in this investigation")
    existing = set(db.scalars(
        select(UsernameHandle.username).where(
            UsernameHandle.case_id == case_id,
            UsernameHandle.person_id == person_id,
            UsernameHandle.username.in_(payload.usernames),
        )
    ))
    if existing:
        raise HTTPException(status_code=409, detail=f"Already saved username(s): {', '.join(sorted(existing))}")
    handles = [UsernameHandle(case_id=case_id, person_id=person_id, username=username) for username in payload.usernames]
    db.add_all(handles)
    db.commit()
    for handle in handles:
        db.refresh(handle)
    return handles


@app.get(
    "/api/cases/{case_id}/people/{person_id}/usernames/{handle_id}/searches",
    response_model=list[UsernameScanOut],
)
def list_username_searches(case_id: str, person_id: str, handle_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    handle = db.scalar(select(UsernameHandle).where(
        UsernameHandle.id == handle_id,
        UsernameHandle.case_id == case_id,
        UsernameHandle.person_id == person_id,
    ))
    if handle is None:
        raise HTTPException(status_code=404, detail="Username not found for this person in this investigation")
    scans = list(db.scalars(
        select(UsernameScan)
        .where(UsernameScan.handle_id == handle_id, UsernameScan.case_id == case_id)
        .order_by(UsernameScan.created_at.desc())
    ))
    return [
        {
            "id": scan.id,
            "handle_id": handle.id,
            "username": handle.username,
            "site_names": scan.site_names,
            "created_at": scan.created_at,
            "results": scan.results,
        }
        for scan in scans
    ]


@app.delete(
    "/api/cases/{case_id}/people/{person_id}/usernames/{handle_id}",
    status_code=204,
)
def delete_person_username(case_id: str, person_id: str, handle_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    handle = db.scalar(select(UsernameHandle).where(
        UsernameHandle.id == handle_id,
        UsernameHandle.case_id == case_id,
        UsernameHandle.person_id == person_id,
    ))
    if handle is None:
        raise HTTPException(status_code=404, detail="Username not found for this person in this investigation")
    db.delete(handle)
    db.commit()
    return Response(status_code=204)


@app.post(
    "/api/cases/{case_id}/people/{person_id}/usernames/{handle_id}/search",
    response_model=UsernameScanOut,
)
async def search_person_username(
    case_id: str,
    person_id: str,
    handle_id: str,
    payload: UsernameSearchRequest,
    db: Session = Depends(get_db),
):
    require_case(db, case_id)
    handle = db.scalar(select(UsernameHandle).where(
        UsernameHandle.id == handle_id,
        UsernameHandle.case_id == case_id,
        UsernameHandle.person_id == person_id,
    ))
    if handle is None:
        raise HTTPException(status_code=404, detail="Username not found for this person in this investigation")
    supported = {site["name"] for site in list_username_sites()}
    if any(site_name not in supported for site_name in payload.site_names):
        raise HTTPException(status_code=422, detail="One or more selected sites are not supported")
    try:
        checked = await run_username_checks(handle.username, payload.site_names)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    scan = UsernameScan(
        case_id=case_id,
        person_id=person_id,
        handle_id=handle.id,
        site_names=payload.site_names,
        authorization_acknowledged=payload.confirm_authorized,
    )
    db.add(scan)
    db.flush()
    results = [
        UsernameScanResult(scan_id=scan.id, **item)
        for item in checked
    ]
    db.add_all(results)
    db.commit()
    db.refresh(scan)
    return {
        "id": scan.id,
        "handle_id": handle.id,
        "username": handle.username,
        "site_names": scan.site_names,
        "created_at": scan.created_at,
        "results": results,
    }


@app.get("/api/cases/{case_id}/sources", response_model=list[SourceOut])
def list_sources(case_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    return list(db.scalars(select(Source).where(Source.case_id == case_id).order_by(Source.retrieved_on.desc())))


@app.post("/api/cases/{case_id}/sources", response_model=SourceOut, status_code=201)
def create_source(case_id: str, payload: SourceCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    source = Source(case_id=case_id, **payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.get("/api/cases/{case_id}/findings", response_model=list[FindingOut])
def list_findings(case_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    rows = db.execute(
        select(Finding, Person, Source)
        .join(Person, Finding.person_id == Person.id)
        .join(Source, Finding.source_id == Source.id)
        .where(Finding.case_id == case_id)
        .order_by(Finding.created_at.desc())
    ).all()
    return [
        FindingOut(
            id=finding.id,
            case_id=finding.case_id,
            person_id=finding.person_id,
            person_name=person.name,
            source_id=source.id,
            claim=finding.claim,
            excerpt=finding.excerpt,
            confidence=finding.confidence,
            status=finding.status,
            created_at=finding.created_at,
            source=EvidenceOut(id=source.id, title=source.title, url=source.url, retrieved_on=source.retrieved_on),
        )
        for finding, person, source in rows
    ]


@app.post("/api/cases/{case_id}/findings", response_model=FindingOut, status_code=201)
def create_finding(case_id: str, payload: FindingCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    person = db.scalar(select(Person).where(Person.id == payload.person_id, Person.case_id == case_id))
    source = db.scalar(select(Source).where(Source.id == payload.source_id, Source.case_id == case_id))
    if person is None or source is None:
        raise HTTPException(status_code=404, detail="Person or source not found in this investigation")
    finding = Finding(case_id=case_id, **payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return FindingOut(
        id=finding.id,
        case_id=finding.case_id,
        person_id=finding.person_id,
        person_name=person.name,
        source_id=source.id,
        claim=finding.claim,
        excerpt=finding.excerpt,
        confidence=finding.confidence,
        status=finding.status,
        created_at=finding.created_at,
        source=EvidenceOut(id=source.id, title=source.title, url=source.url, retrieved_on=source.retrieved_on),
    )


@app.get("/api/cases/{case_id}/relationships", response_model=list[RelationshipOut])
def list_relationships(case_id: str, db: Session = Depends(get_db)):
    require_case(db, case_id)
    rows = db.execute(
        select(Link, Source)
        .join(Source, Link.source_id == Source.id)
        .where(Link.case_id == case_id)
        .order_by(Link.created_at.desc())
    ).all()
    return [
        RelationshipOut(
            id=link.id,
            case_id=link.case_id,
            source_person_id=link.source_person_id,
            target_person_id=link.target_person_id,
            source_id=source.id,
            label=link.label,
            details=link.details,
            confidence=link.confidence,
            status=link.status,
            created_at=link.created_at,
            source=EvidenceOut(id=source.id, title=source.title, url=source.url, retrieved_on=source.retrieved_on),
        )
        for link, source in rows
    ]


@app.post("/api/cases/{case_id}/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(case_id: str, payload: RelationshipCreate, db: Session = Depends(get_db)):
    require_case(db, case_id)
    if payload.source_person_id == payload.target_person_id:
        raise HTTPException(status_code=422, detail="A relationship must connect two different people")
    people = db.scalars(
        select(Person).where(
            Person.case_id == case_id,
            Person.id.in_([payload.source_person_id, payload.target_person_id]),
        )
    ).all()
    source = db.scalar(select(Source).where(Source.id == payload.source_id, Source.case_id == case_id))
    if len(people) != 2 or source is None:
        raise HTTPException(status_code=404, detail="People or source not found in this investigation")
    link = Link(case_id=case_id, **payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return RelationshipOut(
        id=link.id,
        case_id=link.case_id,
        source_person_id=link.source_person_id,
        target_person_id=link.target_person_id,
        source_id=source.id,
        label=link.label,
        details=link.details,
        confidence=link.confidence,
        status=link.status,
        created_at=link.created_at,
        source=EvidenceOut(id=source.id, title=source.title, url=source.url, retrieved_on=source.retrieved_on),
    )


@app.get("/api/cases/{case_id}/graph", response_model=GraphOut)
def get_graph(
    case_id: str,
    q: str = Query(default="", max_length=140),
    db: Session = Depends(get_db),
):
    require_case(db, case_id)
    people_statement = select(Person).where(Person.case_id == case_id)
    if q.strip():
        people_statement = people_statement.where(Person.name.ilike(f"%{q.strip()}%"))
    people = list(db.scalars(people_statement.order_by(Person.name)))
    person_ids = [person.id for person in people]
    findings = list(db.scalars(select(Finding).where(Finding.case_id == case_id)))
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.person_id] = counts.get(finding.person_id, 0) + 1
    nodes = [
        GraphNode(
            id=person.id,
            name=person.name,
            aliases=person.aliases,
            notes=person.notes,
            findings_count=counts.get(person.id, 0),
        )
        for person in people
    ]
    edge_rows = db.execute(
        select(Link, Source)
        .join(Source, Link.source_id == Source.id)
        .where(Link.case_id == case_id)
        .order_by(Link.created_at)
    ).all()
    edges = [
        GraphEdge(
            id=link.id,
            source=link.source_person_id,
            target=link.target_person_id,
            label=link.label,
            details=link.details,
            confidence=link.confidence,
            status=link.status,
            source_title=source.title,
            source_url=source.url,
            retrieved_on=source.retrieved_on,
        )
        for link, source in edge_rows
        if link.source_person_id in person_ids and link.target_person_id in person_ids
    ]
    return GraphOut(
        case_id=case_id,
        nodes=nodes,
        edges=edges,
        findings_count=len(findings),
        sources_count=len(db.scalars(select(Source).where(Source.case_id == case_id)).all()),
    )


@app.get("/api/cases/{case_id}/export")
def export_case(case_id: str, db: Session = Depends(get_db)):
    case = require_case(db, case_id)
    graph = get_graph(case_id, q="", db=db)
    return {
        "case": CaseOut.model_validate(case).model_dump(mode="json"),
        "people": [PersonOut.model_validate(person).model_dump(mode="json") for person in case.people],
        "sources": [SourceOut.model_validate(source).model_dump(mode="json") for source in case.sources],
        "findings": [finding.model_dump(mode="json") for finding in list_findings(case_id, db=db)],
        "relationships": [relationship.model_dump(mode="json") for relationship in list_relationships(case_id, db=db)],
        "graph": graph.model_dump(mode="json"),
        "exported_on": date.today().isoformat(),
    }


static_dir = Path(__file__).resolve().parent / "static"
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def home():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend has not been built yet. See /docs for the API."}
