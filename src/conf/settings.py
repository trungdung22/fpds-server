import os


class Settings:
    # database configurations
    # JWT
    secret_key: str = "secret"
    algorithm: str = "HS256"

    open_api_key: str = os.getenv("OPEN_API_KEY", "sk-proj--nnpwvRMHqg-bGS-")
    private_key_seed: str = "cb3eb1f686654e6d9655be816d159121"

    MONGO_URI: str = os.getenv("MONGO_URI", "")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "o9=-1@5T*4v1A*~P")
    ENCRYPTION_VECTOR: str = os.getenv("ENCRYPTION_VECTOR", "P@4n6+Q.Ol[0y)!~")

    class Config:
        env_file = ".env.dev"
        from_attributes = True
