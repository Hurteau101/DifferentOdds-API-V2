from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from typing import Optional, Dict
from typing import ClassVar

class RedisSelector(Enum):
    AUTH = 5
    MAPPER = 2

    @property
    def label(self) -> str:
        return self.name.lower()

    @property
    def redis_db(self) -> int:
        return self.value

# Handles APScheduler Details
@dataclass
class APSchedulerDetails:
    job_id: str
    interval: int
    name: str
    coalesce: bool = False
    max_instances: int = 1
    misfire_grace_time: int = 300

@dataclass
class BaseJobDict:
    job_type: RedisSelector
    job_active: bool
    ap_scheduler: APSchedulerDetails
    redis_db: Optional[int] = field(default=None, init=False)
    file_name: str
    class_name: str
    base_file_path: str
    # This will be created in post init, taking the base + path - Will allow us to dynamically extract the class instance.
    # With the help of the class name.
    class_path: Optional[str] = field(default=None, init=False)

    def __post_init__(self):
        self.redis_db = RedisSelector[self.job_type.name].redis_db

# Handles Auth Job Information (Primarily used for APScheduler)
@dataclass
class AuthJobDict(BaseJobDict):
    auth_redis_key: str
    def __post_init__(self):
        self.class_path = f"{self.base_file_path}.Authentication.{self.file_name}"

# Handles Mapper Job Information (Primarily used for APScheduler)
@dataclass
class MapperJobDict(BaseJobDict):
    requires_auth: bool
    mapper_redis_key: str

    def __post_init__(self):
        self.class_path = f"{self.base_file_path}.Mapping.{self.file_name}"


@dataclass
class BaseProvider:
    title: str
    name: str
    url: dict
    method: str
    # Ensures all children set the base path. Ex. Books.SGP.
    base_file_path: ClassVar[str]
    file_name: str
    class_name: str
    # This will be created in post init, taking the base + path - Will allow us to dynamically extract the class instance.
    # With the help of the class name.
    class_path: Optional[str] = field(default=None, init=False)
    headers: Optional[Dict] = None
    is_active: Optional[bool] = False
    curl_impersonation: Optional[str] = "chrome"
    auth_job_dict: Optional[AuthJobDict] = None
    mapper_job_dict: Optional[MapperJobDict] = None
    apscheduler_details: Optional[APSchedulerDetails] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "base_file_path" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} is missing a 'base_path' attribute")
        if cls.base_file_path.endswith("."):
            raise TypeError(f"{cls.__name__} class path must not end with '.'")

    def __post_init__(self):
        if not hasattr(type(self), "base_file_path"):
            raise TypeError(f"{type(self).__name__} has no base_file_path")

        self.class_path = f"{self.base_file_path}.{self.file_name or self.name}"
