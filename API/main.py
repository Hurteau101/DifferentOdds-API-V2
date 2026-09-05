from contextlib import asynccontextmanager
from API.rfq_parlay import router as rfq_parlay
from Database.base_db import async_engine
from Redis.redis_manager import RedisAsyncManager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from API.dfs import router as dfs
from API.sportsbooks import router as sportsbooks
from API.sgp import router as sgp
from API.liquidity import router as liquidity


BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = {
        "dfs": RedisAsyncManager(database=0),
        "sportsbooks": RedisAsyncManager(database=0),
        "sgp_mapped_ids": RedisAsyncManager(database=2),
        "sgp_auth": RedisAsyncManager(database=1),
        "auto_sgp": RedisAsyncManager(database=3),
        "prediction_liquidity": RedisAsyncManager(database=0),
    }

    async_engine()

    try:
        yield
    finally:
        await async_engine().dispose()

        for redis in app.state.redis.values():
            await redis.close_for_shutdown()

app = FastAPI(
    title="Different Odds API",
    description=(
        "An API for accessing and aggregating sports data from multiple sportsbooks. "
        "For detailed usage instructions, see the [documentation](/docs/api). "
        "\n\n**Note:** Some endpoints may return large datasets. For the best experience, we recommend using Postman or another API client."
    ),
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    version="V2.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/",
)


# Helps for larger responses - compress them
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=1)

@app.get("/docs/api", include_in_schema=False)
async def custom_docs():
    return FileResponse(BASE_DIR / "Static" / "api_docs.html")

app.include_router(dfs)
app.include_router(sportsbooks)
app.include_router(sgp)
app.include_router(rfq_parlay)
app.include_router(liquidity)
