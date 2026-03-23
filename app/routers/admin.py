from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from pydantic import BaseModel
from typing import Optional
import os

from app.database import get_db
from app.models.models import User, Announcement, Proposal
from app.services.auth import decode_token
from app.config import is_admin_wallet

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(request: Request):
    token = request.cookies.get("atlas_session")
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    payload = decode_token(token)
    if not payload or not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Accesso negato — solo admin")
    return payload


# ── Annunci ───────────────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title: str
    content: str
    pinned: bool = False


@router.post("/announcements")
async def create_announcement(
    body: AnnouncementCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    result = await db.execute(select(User).where(User.wallet_address == admin["sub"]))
    user = result.scalar_one_or_none()
    ann = Announcement(title=body.title, content=body.content, pinned=body.pinned, author_id=user.id)
    db.add(ann)
    await db.commit()
    return {"success": True, "id": ann.id}


@router.get("/announcements")
async def get_announcements(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Announcement).order_by(Announcement.pinned.desc(), Announcement.created_at.desc()))
    anns = result.scalars().all()
    return [{"id": a.id, "title": a.title, "content": a.content, "pinned": a.pinned, "created_at": str(a.created_at)} for a in anns]


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(Announcement).where(Announcement.id == ann_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    await db.delete(ann)
    await db.commit()
    return {"success": True}


# ── Proposte governance ───────────────────────────────────────────────────────

class ProposalCreate(BaseModel):
    title: str
    description: str
    closes_at: Optional[str] = None


@router.post("/proposals")
async def create_proposal(
    body: ProposalCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin)
):
    result = await db.execute(select(User).where(User.wallet_address == admin["sub"]))
    user = result.scalar_one_or_none()
    proposal = Proposal(title=body.title, description=body.description, author_id=user.id)
    db.add(proposal)
    await db.commit()
    return {"success": True, "id": proposal.id}


# ── Utenti ────────────────────────────────────────────────────────────────────

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.arkv_balance.desc()))
    users = result.scalars().all()
    return [{
        "id": u.id,
        "wallet_address": u.wallet_address,
        "username": u.username,
        "arkv_balance": u.arkv_balance,
        "is_admin": u.is_admin,
        "is_banned": u.is_banned,
        "created_at": str(u.created_at),
        "last_seen": str(u.last_seen),
    } for u in users]


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: str, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if is_admin_wallet(user.wallet_address):
        raise HTTPException(status_code=403, detail="Non puoi bannare un admin")
    user.is_banned = True
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/unban")
async def unban_user(user_id: str, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    user.is_banned = False
    await db.commit()
    return {"success": True}


# ── Impostazioni ──────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    total_users = await db.execute(select(func.count(User.id)))
    banned_users = await db.execute(select(func.count(User.id)).where(User.is_banned == True))
    total_proposals = await db.execute(select(func.count(Proposal.id)))
    return {
        "total_users": total_users.scalar(),
        "banned_users": banned_users.scalar(),
        "total_proposals": total_proposals.scalar(),
    }
