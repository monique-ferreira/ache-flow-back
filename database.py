# database.py
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

from models import Funcionario, Projeto, Tarefa, Calendario

load_dotenv()

class Database:
    client: Optional[AsyncIOMotorClient] = None

    async def initialize(self):
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("A variável de ambiente MONGO_URI não foi definida.")

        self.client = AsyncIOMotorClient(mongo_uri)
        
        await init_beanie(
            database=self.client.get_default_database(),
            document_models=[
                Funcionario,
                Projeto,
                Tarefa,
                Calendario
            ]
        )
        print("Conexão com o banco de dados e inicialização do Beanie bem-sucedidas.")

db = Database()