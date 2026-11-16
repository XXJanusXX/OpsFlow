import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()
@dataclass(frozen=True)
class Settings:
 ollama_base_url:str=os.getenv("OLLAMA_BASE_URL","http://localhost:11434")
 ollama_model:str=os.getenv("OLLAMA_MODEL","llama3.2:3b")
 ollama_timeout_seconds:float=float(os.getenv("OLLAMA_TIMEOUT_SECONDS","45"))
 database_path:str=os.getenv("DATABASE_PATH","./opsflow.db")
settings=Settings()
