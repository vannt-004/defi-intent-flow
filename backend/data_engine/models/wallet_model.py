from pydantic import BaseModel


class AddWalletRequest(BaseModel):
    wallet: str