import os
from pydantic_settings import BaseSettings

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_base_dir, 'course_scheduler.db')}"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "imamu-course-scheduler-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    UNIVERSITY_XML: str = os.getenv("UNIVERSITY_XML", "university.xml")


settings = Settings()
