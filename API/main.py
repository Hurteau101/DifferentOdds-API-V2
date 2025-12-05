from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.gzip import GZipMiddleware
from Mapper.database import Database
from Redis.redis_manager import RedisManager
from . import dfs
from . import sgp
from . import pph
from contextlib import asynccontextmanager
from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = Database()

    # Create shared RedisManager
    app.state.redis = RedisManager(db=0)
    try:
        yield
    finally:
        await app.state.db.engine.dispose()
        await app.state.redis.close()

app = FastAPI(
    title="Different Odds API",
    description=(
        "An API for accessing and aggregating sports data from multiple sportsbooks. "
        "For detailed usage instructions, see the [documentation](/docs/api). "
        "\n\n**Note:** Some endpoints may return large datasets. For the best experience, we recommend using Postman or another API client."
    ),
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
    version="V2.0.0",
    default_response_class=ORJSONResponse,
    docs_url="/",
)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=1)


@app.get("/docs/api", include_in_schema=False)
async def custom_docs():
    return FileResponse(BASE_DIR / "static" / "api_docs.html")

app.include_router(dfs.router)
app.include_router(sgp.router)
app.include_router(pph.router)


