from fastapi import APIRouter

router = APIRouter()

@router.post('/checkout')
async def checkout(payload: dict):
    return {'accepted': True, 'payload': payload}

