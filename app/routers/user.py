from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.models import User, Announcement, Proposal, Vote
from app.services.auth import decode_token

router = APIRouter(prefix="/user", tags=["user"])


def get_current_user(request: Request):
    token = request.cookies.get("atlas_session")
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    return payload


# ── Profilo ───────────────────────────────────────────────────────────────────

class UsernameUpdate(BaseModel):
    username: str


@router.post("/username")
async def set_username(
    body: UsernameUpdate,
    db: AsyncSession = Depends(get_db),
    user_payload=Depends(get_current_user)
):
    if len(body.username) < 3 or len(body.username) > 30:
        raise HTTPException(status_code=400, detail="Username deve essere tra 3 e 30 caratteri")

    # Controlla unicità
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username già in uso")

    result = await db.execute(select(User).where(User.wallet_address == user_payload["sub"]))
    user = result.scalar_one_or_none()
    user.username = body.username
    await db.commit()
    return {"success": True, "username": body.username}


# ── Annunci pubblici ──────────────────────────────────────────────────────────

@router.get("/announcements")
async def get_announcements(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(
        select(Announcement).order_by(Announcement.pinned.desc(), Announcement.created_at.desc())
    )
    anns = result.scalars().all()
    return [{"id": a.id, "title": a.title, "content": a.content,
             "pinned": a.pinned, "created_at": str(a.created_at)} for a in anns]


# ── Governance ────────────────────────────────────────────────────────────────

@router.get("/proposals")
async def get_proposals(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(
        select(Proposal).where(Proposal.status == "active").order_by(Proposal.created_at.desc())
    )
    proposals = result.scalars().all()
    return [{
        "id": p.id, "title": p.title, "description": p.description,
        "votes_yes": p.votes_yes, "votes_no": p.votes_no,
        "status": p.status, "closes_at": str(p.closes_at) if p.closes_at else None,
    } for p in proposals]


class VoteCreate(BaseModel):
    proposal_id: str
    choice: bool  # True=yes, False=no


@router.post("/vote")
async def cast_vote(
    body: VoteCreate,
    db: AsyncSession = Depends(get_db),
    user_payload=Depends(get_current_user)
):
    result = await db.execute(select(User).where(User.wallet_address == user_payload["sub"]))
    user = result.scalar_one_or_none()

    # Controlla se ha già votato
    existing_vote = await db.execute(
        select(Vote).where(Vote.user_id == user.id, Vote.proposal_id == body.proposal_id)
    )
    if existing_vote.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Hai già votato questa proposta")

    # Controlla che la proposta esista
    prop_result = await db.execute(select(Proposal).where(Proposal.id == body.proposal_id))
    proposal = prop_result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta non trovata")
    if proposal.status != "active":
        raise HTTPException(status_code=400, detail="Votazione chiusa")

    # Registra voto
    vote = Vote(user_id=user.id, proposal_id=body.proposal_id, choice=body.choice)
    db.add(vote)

    if body.choice:
        proposal.votes_yes += 1
    else:
        proposal.votes_no += 1

    await db.commit()
    return {"success": True, "choice": body.choice}


@router.get("/my-votes")
async def get_my_votes(db: AsyncSession = Depends(get_db), user_payload=Depends(get_current_user)):
    result = await db.execute(select(User).where(User.wallet_address == user_payload["sub"]))
    user = result.scalar_one_or_none()
    votes = await db.execute(select(Vote).where(Vote.user_id == user.id))
    return [{"proposal_id": v.proposal_id, "choice": v.choice, "created_at": str(v.created_at)}
            for v in votes.scalars().all()]
