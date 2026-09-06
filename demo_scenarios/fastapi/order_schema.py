from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Order(BaseModel):
    quantity: int
    unit_price: float


@router.post('/orders')
async def create_order(order: Order) -> dict[str, float]:
    return {'total': order.quantity * order.unit_price}

