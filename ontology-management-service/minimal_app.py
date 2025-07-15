"""Minimal FastAPI app for debugging"""
from fastapi import FastAPI

app = FastAPI(title = "Minimal Test App")

@app.get("/")
async def root():
 return {"message": "Hello World"}

@app.get("/test")
async def test():
 return {"message": "Test endpoint working", "status": "success"}

@app.get("/api/v1/test")
async def api_test():
 return {"message": "API v1 test working", "status": "success"}

if __name__ == "__main__":
 import uvicorn
 uvicorn.run(app, host = "0.0.0.0", port = 8000)
