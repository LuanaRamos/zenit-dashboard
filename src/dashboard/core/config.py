from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    META_APP_ID: str = Field(..., description="ID do Aplicativo no Meta for Developers")
    META_APP_SECRET: str = Field(..., description="Chave Secreta do Aplicativo")
    META_REDIRECT_URI: str = Field("http://localhost:8501/", description="URL de redirecionamento após o login")
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
