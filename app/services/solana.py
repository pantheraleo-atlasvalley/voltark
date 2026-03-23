import os
import secrets
import httpx
from solders.pubkey import Pubkey
from solders.signature import Signature
from dotenv import load_dotenv

load_dotenv()

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
ARKV_TOKEN_MINT = os.getenv("ARKV_TOKEN_MINT", "ABC64226vR9kHtjtYCDENostEbCFdtXYvY4o6Gwzpump")
ARKV_MIN_BALANCE = int(os.getenv("ARKV_MIN_BALANCE", "1"))


def generate_nonce() -> str:
    return secrets.token_hex(32)


def get_sign_message(nonce: str, wallet_address: str) -> str:
    return (
        f"Atlas Valley Portal - Login\n\n"
        f"Wallet: {wallet_address}\n"
        f"Nonce: {nonce}\n\n"
        f"Firmando questo messaggio confermi di essere il proprietario di questo wallet.\n"
        f"Questa firma non costa gas e non autorizza transazioni."
    )


def verify_signature(wallet_address: str, nonce: str, signature_b58: str) -> bool:
    try:
        pubkey = Pubkey.from_string(wallet_address)
        sig = Signature.from_string(signature_b58)
        message = get_sign_message(nonce, wallet_address)
        message_bytes = message.encode("utf-8")
        return sig.verify(pubkey, message_bytes)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


async def get_arkv_balance(wallet_address: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"mint": ARKV_TOKEN_MINT},
                    {"encoding": "jsonParsed"}
                ]
            }
            response = await client.post(SOLANA_RPC_URL, json=payload)
            data = response.json()
            accounts = data.get("result", {}).get("value", [])
            if not accounts:
                return 0
            total = 0
            for account in accounts:
                token_amount = (
                    account.get("account", {})
                    .get("data", {})
                    .get("parsed", {})
                    .get("info", {})
                    .get("tokenAmount", {})
                )
                total += int(token_amount.get("amount", 0))
            return total
    except Exception as e:
        print(f"Error fetching ARKV balance: {e}")
        return 0


def is_valid_solana_address(address: str) -> bool:
    try:
        Pubkey.from_string(address)
        return True
    except Exception:
        return False
