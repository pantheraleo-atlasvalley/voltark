from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import User, WalletNonce
from app.services.solana import (
    generate_nonce, verify_signature, get_arkv_balance,
    is_valid_solana_address, get_sign_message, ARKV_MIN_BALANCE,
)
from app.services.auth import create_access_token
from app.config import is_admin_wallet

router = APIRouter(prefix="/auth", tags=["auth"])


class NonceRequest(BaseModel):
    wallet_address: str

class VerifyRequest(BaseModel):
    wallet_address: str
    signature: str
    nonce: str


@router.post("/nonce")
async def request_nonce(body: NonceRequest, db: AsyncSession = Depends(get_db)):
    wallet = body.wallet_address.strip()
    if not is_valid_solana_address(wallet):
        raise HTTPException(status_code=400, detail="Indirizzo wallet non valido")
    result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = result.scalar_one_or_none()
    if not user:
        user = User(wallet_address=wallet, is_admin=is_admin_wallet(wallet))
        db.add(user)
        await db.flush()
    old_nonces = await db.execute(
        select(WalletNonce).where(WalletNonce.wallet_address == wallet, WalletNonce.used == False)
    )
    for old in old_nonces.scalars().all():
        old.used = True
    nonce = generate_nonce()
    db.add(WalletNonce(wallet_address=wallet, nonce=nonce))
    await db.commit()
    return {"nonce": nonce, "message": get_sign_message(nonce, wallet)}


@router.post("/verify")
async def verify_wallet(body: VerifyRequest, response: Response, db: AsyncSession = Depends(get_db)):
    wallet = body.wallet_address.strip()
    if not is_valid_solana_address(wallet):
        raise HTTPException(status_code=400, detail="Indirizzo wallet non valido")
    result = await db.execute(
        select(WalletNonce).where(
            WalletNonce.wallet_address == wallet,
            WalletNonce.nonce == body.nonce,
            WalletNonce.used == False,
        )
    )
    nonce_record = result.scalar_one_or_none()
    if not nonce_record:
        raise HTTPException(status_code=400, detail="Nonce non valido o già utilizzato")
    if not verify_signature(wallet, body.nonce, body.signature):
        raise HTTPException(status_code=401, detail="Firma non valida")
    nonce_record.used = True
    user_result = await db.execute(select(User).where(User.wallet_address == wallet))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    balance = await get_arkv_balance(wallet)
    user.arkv_balance = balance
    user.last_seen = datetime.now(timezone.utc)
    user.is_admin = is_admin_wallet(wallet)
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account bannato")
    await db.commit()
    if balance < ARKV_MIN_BALANCE and not user.is_admin:
        raise HTTPException(status_code=403, detail=f"Devi possedere almeno {ARKV_MIN_BALANCE} $ARKV")
    token = create_access_token(wallet_address=wallet, user_id=user.id, is_admin=user.is_admin)
    response.set_cookie(key="atlas_session", value=token, httponly=True, secure=True, samesite="lax", max_age=86400)
    return {"success": True, "wallet": wallet, "arkv_balance": balance, "username": user.username, "is_admin": user.is_admin}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("atlas_session")
    return {"success": True}


@router.get("/me")
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("atlas_session")
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    from app.services.auth import decode_token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    result = await db.execute(select(User).where(User.wallet_address == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"id": user.id, "wallet_address": user.wallet_address, "username": user.username,
            "arkv_balance": user.arkv_balance, "is_admin": user.is_admin, "created_at": user.created_at}
