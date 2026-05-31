from fastapi import APIRouter
from fastapi import HTTPException

from data_engine.services.token.token_image_service import TokenImageService

router = APIRouter(prefix="/tokens", tags=["Tokens"])

service = TokenImageService()


@router.get("/{symbol}/image")
async def get_token_image(symbol: str):
    image = service.get_image(symbol)

    if not image:
        raise HTTPException(status_code=404, detail="Token not found")

    return {
        "symbol": symbol.upper(), "image": image
    }


@router.get("/images")
async def get_images():
    return service.get_all_images()
