import os

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5434")
    DB_NAME = os.getenv("DB_NAME", "testdb")
    DB_USER = os.getenv("DB_USER", "testuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "test")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORT = int(os.getenv("PORT", 5000))
