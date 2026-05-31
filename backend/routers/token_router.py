from datetime import datetime, timezone

from fastapi import APIRouter, Query
from fastapi import HTTPException

from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.token.token_image_service import TokenImageService
from shared.databases.mongo_client import MongoConnection

router = APIRouter(prefix="/tokens", tags=["Tokens"])

service = TokenImageService()


@router.get("/images")
async def get_images():
    return service.get_all_images()


@router.get("/{symbol}/history")
async def get_token_price_history(symbol: str, days: int = Query(default=30, ge=1, le=365)):
    pricing = PricingService(MongoConnection.get_database())

    try:
        token = pricing.get_token_info(symbol)
    except Exception:
        raise HTTPException(status_code=404, detail="Token not found")

    coingecko_id = token.get("coingeckoId")
    if not coingecko_id:
        raise HTTPException(status_code=404, detail="Token history not configured")

    now = int(datetime.now(timezone.utc).timestamp())
    from_ts = now - days * 86400
    rows = pricing.get_histories([coingecko_id], from_ts).get(coingecko_id, [])
    prices = [float(row.get("price") or 0) for row in rows if float(row.get("price") or 0) > 0]
    current_price = float(token.get("price") or (prices[-1] if prices else 0))
    first_price = prices[0] if prices else current_price
    seven_day_price = prices[max(len(prices) - 8, 0)] if prices else current_price
    max_price = max(prices) if prices else current_price
    min_price = min(prices) if prices else current_price

    return {
        "symbol": pricing.normalize_symbol(symbol),
        "name": token.get("name"),
        "image": token.get("image"),
        "currentPrice": current_price,
        "change7dPct": round((current_price - seven_day_price) / seven_day_price * 100, 4) if seven_day_price else 0,
        "change30dPct": round((current_price - first_price) / first_price * 100, 4) if first_price else 0,
        "high": max_price,
        "low": min_price,
        "history": [
            {
                "timestamp": row.get("timestamp"),
                "price": float(row.get("price") or 0),
            }
            for row in rows
        ],
    }


@router.get("/{symbol}/image")
async def get_token_image(symbol: str):
    image = service.get_image(symbol)

    if not image:
        raise HTTPException(status_code=404, detail="Token not found")

    return {
        "symbol": symbol.upper(), "image": image
    }
