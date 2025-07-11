"""Simple test router to debug routing issues"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/simple-test")
async def simple_test():
    return {"message": "Simple test working", "status": "success"}