import os
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (como GOOGLE_APPLICATION_CREDENTIALS) do arquivo .env
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1") # Ex: us-central1

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Carrega o modelo generativo Gemini
model = GenerativeModel("gemini-2.0-flash")

async def gerar_resposta_ia(contexto: str, pergunta: str, nome_usuario: str) -> str:
    """
    Monta o prompt mestre com um CONTEXTO completo e a PERGUNTA do usuário.
    """
    # --- O NOVO MASTER PROMPT ---
    prompt_completo = f"""
    **PERSONA:** Você é o 'Ache', um assistente de produtividade virtual.

    **TOM E ESTILO:**
    - Seja sempre polido, positivo, prestativo e use emojis. 😊
    - Responda de forma curta e direta.
    - Use uma linguagem clara e simples.
    - Formate sua resposta usando quebras de linha para facilitar a leitura.
    - NUNCA use markdown, asteriscos (*) ou negrito.
    - Comece sempre se dirigindo ao funcionário pelo nome.

    **INFORMAÇÕES DISPONÍVEIS (CONTEXTO):**
    Você tem acesso aos seguintes dados sobre o trabalho do(a) {nome_usuario}:
    ---
    {contexto}
    ---

    **TAREFA PRINCIPAL:**
    Sua tarefa é usar as INFORMAÇÕES DISPONÍVEIS para responder à PERGUNTA DO USUÁRIO de forma precisa e amigável. Analise o contexto para encontrar a resposta.
    - Se a pergunta for sobre "priorizar", analise as tarefas com prazo mais próximo.
    - Se a pergunta for sobre tarefas "congeladas", filtre a lista de tarefas por esse status.
    - Se a pergunta for sobre tarefas "não iniciadas", filtre a lista de tarefas por esse status.
    - Se a pergunta for sobre tarefas "em andamento", filtre a lista de tarefas por esse status.
    - Se a pergunta for sobre tarefas "concluídas", filtre a lista de tarefas por esse status.
    - Se a pergunta for sobre tarefas "urgentes", analise as tarefas com prazo mais próximo e alta prioridade.
    - Se a pergunta for sobre projetos, use a lista de projetos.
    - Se a pergunta for sobre funcionários, use a lista de funcionários.
    - Se a pergunta for sobre prazos, use as datas fornecidas.
    - Se a pergunta for sobre prioridades, use os níveis de prioridade fornecidos.
    - Se a pergunta for sobre status, use os status fornecidos.
    - Se você não encontrar a resposta no contexto, diga que não encontrou a informação.

    **PERGUNTA DO USUÁRIO:**
    "{pergunta}"

    **Agora, gere a sua resposta para o(a) {nome_usuario}:**
    """

    try:
        response = await model.generate_content_async(prompt_completo)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API do Vertex AI: {e}")
        return "Desculpe, tive um problema ao tentar gerar sua resposta. Por favor, tente novamente."