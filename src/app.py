from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(
    title="ViFood KG Builder Service",
    version="1.0.0"
)

app.include_router(router)
