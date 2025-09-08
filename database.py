# database.py
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# Importaremos os modelos aqui depois que os criarmos
from models import Premissa, Pessoa, Evento, Calculadora

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class Database:
    """
    Classe que gerencia a conexão com o MongoDB e a inicialização do Beanie.
    Usamos um padrão Singleton para garantir que haja apenas uma instância do cliente do banco de dados.
    """
    client: Optional[AsyncIOMotorClient] = None

    async def initialize(self):
        """
        Estabelece a conexão com o MongoDB e inicializa o Beanie com todos os modelos (Documentos).
        Esta função será chamada na inicialização do FastAPI.
        """
        # Pega a string de conexão do arquivo .env
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("A variável de ambiente MONGO_URI não foi definida.")

        self.client = AsyncIOMotorClient(mongo_uri)
        
        # O Beanie precisa saber quais modelos (Documentos) ele irá gerenciar.
        # Ele cria as coleções e índices necessários no banco de dados.
        await init_beanie(
            database=self.client.get_default_database(),  # Usa o nome do DB da URI de conexão
            document_models=[
                Premissa,
                Pessoa,
                Evento,
                Calculadora
            ]
        )
        print("Conexão com o banco de dados e inicialização do Beanie bem-sucedidas.")

# Instância global para ser usada em toda a aplicação
db = Database()