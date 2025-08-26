from fastapi import FastAPI

from Mapper.database import Database
from . import dfs
from contextlib import asynccontextmanager

# Establish a lifespan for the app to manage startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = Database()
    await app.state.db.ensure_ready()
    try:
        yield
    finally:
        await app.state.db.pool.close()
app = FastAPI(
    title="Different Odds API",
    description="""
    This API acts like a middleware to fetch sports betting odds. It retrieves data from various sportsbooks and serves it in a unified format.
    """,
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan
)




app.include_router(dfs.router)

#FcqmZM9ZNPgn0namhot2aMyZQVPcASAj