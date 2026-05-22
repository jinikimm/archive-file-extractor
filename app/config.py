import os

class Config:

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        (
            "postgresql://"
            f"{os.environ.get('DB_USER', 'testuser')}:"
            f"{os.environ.get('DB_PASSWORD', 'test')}@"
            f"{os.environ.get('DB_HOST', 'localhost')}:"
            f"{os.environ.get('DB_PORT', '5432')}/"
            f"{os.environ.get('DB_NAME', 'testdb')}"
        ),
    )

    PORT = int(os.environ.get("PORT", 5000))
    CONCURRENCY = int(os.environ.get("CONCURRENCY", 4))