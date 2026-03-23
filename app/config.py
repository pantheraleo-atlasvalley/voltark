# Wallet degli admin hardcoded — solo questi due hanno accesso al pannello admin
ADMIN_WALLETS = {
    "Gc9UQFcFBaeojxwbqsEM8fbsUYrrhtFK8bcfMB1UzEuq",  # panthera_leo
    "GB7vjrArPotcUzZ6J1Kiovd89Pr13A47iyeqNvYpEvBt",  # elf_wizard
}

def is_admin_wallet(wallet_address: str) -> bool:
    return wallet_address in ADMIN_WALLETS
