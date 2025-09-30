# ia_generativa.py

import os
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (como GOOGLE_APPLICATION_CREDENTIALS) do arquivo .env
load_dotenv()

# A biblioteca `vertexai` usa automaticamente as credenciais definidas na variável
# de ambiente GOOGLE_APPLICATION_CREDENTIALS que configuramos.
# Você só precisa garantir que o ID do projeto e a localização estão corretos.
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1") # Ex: us-central1

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Carrega o modelo generativo Gemini
model = GenerativeModel("gemini-2.5-flash")

async def gerar_resposta_ia(tarefas_usuario: str, nome_usuario: str) -> str:
    """
    Monta o prompt mestre e chama o Gemini para criar uma resposta humanizada.
    """

    # --- O MASTER PROMPT ---
    # Define a personalidade, o tom e o objetivo da IA.
    prompt_completo = f"""
    **PERSONA:** Você é o 'Ache', um assistente de produtividade virtual da empresa.

    **TOM E ESTILO:**
    - Seja sempre polido, positivo e prestativo.
    - Use uma linguagem clara, simples e amigável. Evite jargões técnicos.
    - Use quebras de linha e negrito para facilitar a leitura.
    - Comece sempre se dirigindo ao funcionário pelo nome.

    **CONTEXTO ATUAL:**
    - O funcionário '{nome_usuario}' pediu ajuda para priorizar suas tarefas.
    - Eu já busquei no banco de dados e encontrei as seguintes tarefas pendentes para ele, já ordenadas por prioridade (as mais urgentes primeiro).

    **DADOS (Tarefas do usuário):**
    {tarefas_usuario}

    **TAREFA:**
    Com base nos dados acima, gere uma resposta conversacional para o '{nome_usuario}'. A resposta deve:
    1. Cumprimentá-lo de forma amigável.
    2. Explicar que você analisou as tarefas dele.
    3. Apresentar um plano de ação claro, sugerindo uma ordem para ele atacar as 2 ou 3 tarefas mais críticas.
    4. Terminar com uma nota de encorajamento.

    **Agora, gere a sua resposta para o {nome_usuario}:**
    """

    try:
        # Chama a API do Gemini de forma assíncrona
        response = await model.generate_content_async(prompt_completo)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API do Vertex AI: {e}")
        return "Desculpe, tive um problema ao tentar gerar sua resposta. Por favor, tente novamente."