import os

from fastapi import FastAPI
from starlette.responses import RedirectResponse

from Mapper.database import Database
from Redis.redis_manager import RedisManager
from Settings.logger import FileLogger
from . import dfs
from . import sgp
from contextlib import asynccontextmanager

# Establish a lifespan for the app to manage startup and shutdown events
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     app.state.db = Database()
#     await app.state.db.ensure_ready()
#     try:
#         yield
#     finally:
#         await app.state.db.pool.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = Database()
    await app.state.db.ensure_ready()

    # Create shared RedisManager
    app.state.redis = RedisManager(db=0)
    try:
        yield
    finally:
        await app.state.db.pool.close()
        await app.state.redis.close()

app = FastAPI(
    title="Different Odds API",
    description="This API acts like a middleware to fetch sports betting odds. It retrieves data from various sportsbooks and serves it in a unified format.",
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
    docs_url="/",
)



app.include_router(dfs.router)
app.include_router(sgp.router)
