# main.py
from fastapi import FastAPI, HTTPException, Body, Query, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from beanie import PydanticObjectId, operators
from contextlib import asynccontextmanager
from datetime import date, datetime
import re
from jose import JWTError, jwt

# Importa a lógica de autenticação e os modelos
import auth
from database import db
from models import (
    Funcionario, Projeto, Tarefa, Token,
    FuncionarioCreate, ProjetoCreate, TarefaCreate,
    FuncionarioUpdate, ProjetoUpdate, TarefaUpdate,
    StatusTarefa
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    yield

app = FastAPI(
    lifespan=lifespan,
    title="API de Gerenciamento de Projetos e Tarefas",
    description="Backend refatorado com autenticação, CRUD completo e webhook inteligente.",
    version="4.0.0"
)

# --- ENDPOINT DE AUTENTICAÇÃO ---

@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_para_obter_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint de login. Recebe email (no campo username) e senha.
    Retorna um token de acesso se as credenciais estiverem corretas.
    """
    funcionario = await Funcionario.find_one(Funcionario.email == form_data.username)
    if not funcionario or not auth.verificar_senha(form_data.password, funcionario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_acesso = auth.criar_token_acesso(
        data={"sub": funcionario.email}
    )
    return {"access_token": token_acesso, "token_type": "bearer"}


# --- CRUD Completo: Funcionários (com segurança) ---

@app.post("/funcionarios", response_model=Funcionario, tags=["Funcionários"], summary="Criar um novo funcionário (Registro)")
async def criar_funcionario(funcionario_data: FuncionarioCreate):
    if await Funcionario.find_one(Funcionario.email == funcionario_data.email):
        raise HTTPException(status_code=400, detail="Um funcionário com este email já existe.")
    
    senha_hashed = auth.gerar_hash_senha(funcionario_data.senha)
    
    funcionario_dict = funcionario_data.dict(exclude={"senha"})
    funcionario = Funcionario(**funcionario_dict, senha=senha_hashed)
    
    await funcionario.insert()
    return funcionario

@app.get("/funcionarios/me", response_model=Funcionario, tags=["Funcionários"], summary="Obter dados do usuário logado")
async def ler_usuario_logado(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    """Retorna as informações do funcionário que está autenticado."""
    return current_user

@app.get("/funcionarios", response_model=List[Funcionario], tags=["Funcionários"], summary="Listar todos os funcionários")
async def listar_funcionarios(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return await Funcionario.find_all().to_list()

@app.get("/funcionarios/{id}", response_model=Funcionario, tags=["Funcionários"], summary="Obter um funcionário por ID")
async def obter_funcionario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return funcionario

@app.put("/funcionarios/{id}", response_model=Funcionario, tags=["Funcionários"], summary="Atualizar um funcionário")
async def atualizar_funcionario(id: PydanticObjectId, update_data: FuncionarioUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    
    update_data_dict = update_data.dict(exclude_unset=True)
    for key, value in update_data_dict.items():
        setattr(funcionario, key, value)
        
    await funcionario.save()
    return funcionario

@app.delete("/funcionarios/{id}", status_code=204, tags=["Funcionários"], summary="Deletar um funcionário")
async def deletar_funcionario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    await funcionario.delete()
    return None

# --- CRUD Completo: Projetos (protegido) ---

@app.post("/projetos", response_model=Projeto, tags=["Projetos"], summary="Criar um novo projeto")
async def criar_projeto(projeto_data: ProjetoCreate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    responsavel = await Funcionario.get(PydanticObjectId(projeto_data.responsavel_id))
    if not responsavel:
        raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")
    
    projeto = Projeto(**projeto_data.dict(exclude={"responsavel_id"}), responsavel=responsavel)
    await projeto.insert()
    return projeto

@app.get("/projetos", response_model=List[Projeto], tags=["Projetos"], summary="Listar todos os projetos")
async def listar_projetos(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return await Projeto.find_all(fetch_links=True).to_list()

@app.get("/projetos/{id}", response_model=Projeto, tags=["Projetos"], summary="Obter um projeto por ID")
async def obter_projeto(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(id, fetch_links=True)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return projeto

@app.put("/projetos/{id}", response_model=Projeto, tags=["Projetos"], summary="Atualizar um projeto")
async def atualizar_projeto(id: PydanticObjectId, update_data: ProjetoUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(id, fetch_links=True)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    update_data_dict = update_data.dict(exclude_unset=True)

    if "responsavel_id" in update_data_dict:
        novo_responsavel = await Funcionario.get(PydanticObjectId(update_data_dict["responsavel_id"]))
        if not novo_responsavel:
            raise HTTPException(status_code=404, detail="Novo funcionário responsável não encontrado.")
        projeto.responsavel = novo_responsavel
        del update_data_dict["responsavel_id"]

    for key, value in update_data_dict.items():
        setattr(projeto, key, value)
        
    await projeto.save()
    return await Projeto.get(id, fetch_links=True)

@app.delete("/projetos/{id}", status_code=204, tags=["Projetos"], summary="Deletar um projeto")
async def deletar_projeto(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    await projeto.delete()
    return None

# --- CRUD Completo: Tarefas (protegido) ---

@app.post("/tarefas", response_model=Tarefa, tags=["Tarefas"], summary="Criar uma nova tarefa")
async def criar_tarefa(tarefa_data: TarefaCreate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(PydanticObjectId(tarefa_data.projeto_id))
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    responsavel = await Funcionario.get(PydanticObjectId(tarefa_data.responsavel_id))
    if not responsavel:
        raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")
    
    tarefa = Tarefa(**tarefa_data.dict(exclude={"projeto_id", "responsavel_id"}), projeto=projeto, responsavel=responsavel)
    await tarefa.insert()
    return tarefa

@app.get("/tarefas/{id}", response_model=Tarefa, tags=["Tarefas"], summary="Obter uma tarefa por ID")
async def obter_tarefa(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id, fetch_links=True)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return tarefa

@app.put("/tarefas/{id}", response_model=Tarefa, tags=["Tarefas"], summary="Atualizar uma tarefa")
async def atualizar_tarefa(id: PydanticObjectId, update_data: TarefaUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id, fetch_links=True)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    update_data_dict = update_data.dict(exclude_unset=True)
    
    if "responsavel_id" in update_data_dict:
        novo_responsavel = await Funcionario.get(PydanticObjectId(update_data_dict["responsavel_id"]))
        if not novo_responsavel:
            raise HTTPException(status_code=404, detail="Novo funcionário responsável não encontrado.")
        tarefa.responsavel = novo_responsavel
        del update_data_dict["responsavel_id"]
    
    if "status" in update_data_dict and update_data_dict["status"] == StatusTarefa.CONCLUIDA:
        tarefa.dataConclusao = date.today()
    
    for key, value in update_data_dict.items():
        setattr(tarefa, key, value)
        
    await tarefa.save()
    return await Tarefa.get(id, fetch_links=True)

@app.delete("/tarefas/{id}", status_code=204, tags=["Tarefas"], summary="Deletar uma tarefa")
async def deletar_tarefa(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    await tarefa.delete()
    return None

# --- ENDPOINT DE FILTRO AVANÇADO DE TAREFAS (protegido) ---
@app.get("/tarefas", response_model=List[Tarefa], tags=["Tarefas"], summary="Listar tarefas com filtros e ordenação avançada")
async def listar_tarefas_filtradas(
    departamento: Optional[str] = Query(None, description="Filtrar por departamento do responsável"),
    projeto_id: Optional[PydanticObjectId] = Query(None, description="Filtrar por ID do projeto"),
    responsavel_id: Optional[PydanticObjectId] = Query(None, description="Filtrar por ID do responsável"),
    urgencia: Optional[bool] = Query(False, description="Destacar e ordenar tarefas por urgência (prazo terminando)"),
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    query_conditions = []
    
    if responsavel_id:
        query_conditions.append(Tarefa.responsavel.id == responsavel_id)

    if projeto_id:
        query_conditions.append(Tarefa.projeto.id == projeto_id)
        
    if departamento:
        funcionarios_no_dpto = await Funcionario.find(Funcionario.departamento == departamento).to_list()
        ids_funcionarios = [f.id for f in funcionarios_no_dpto]
        if not ids_funcionarios:
             return []
        query_conditions.append(operators.In(Tarefa.responsavel.id, ids_funcionarios))
    
    sort_expression = []
    if urgencia:
        sort_expression.extend([("prazo", 1), ("prioridade", -1)])

    tarefas = await Tarefa.find(*query_conditions, fetch_links=True).sort(*sort_expression).to_list()
    
    return tarefas


# --- WEBHOOK INTELIGENTE E SEGURO ---

@app.post("/webhook", tags=["Dialogflow"])
async def dialogflow_webhook(request: Request):
    """
    Webhook que agora identifica o usuário logado a partir do token enviado
    na carga útil (payload) do Dialogflow.
    """
    payload = await request.json()
    
    # --- Lógica de Identificação do Usuário ---
    usuario_logado = None
    token = payload.get("sessionInfo", {}).get("parameters", {}).get("token")

    if token:
        try:
            token_payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            email: str = token_payload.get("sub")
            if email:
                usuario_logado = await Funcionario.find_one(Funcionario.email == email)
        except JWTError:
            usuario_logado = None

    # --- Processamento dos Parâmetros do Dialogflow ---
    intent = payload.get("intentInfo", {}).get("displayName", "")
    params = payload.get("sessionInfo", {}).get("parameters", {})
    
    funcionario_nome_dialogflow = params.get("funcionario")
    
    responsavel_final = None

    # **REGRA PRINCIPAL: Prioriza o usuário logado**
    if funcionario_nome_dialogflow:
        # Se um nome foi DITO explicitamente, busca por esse funcionário
        nome_regex = re.compile(f"^{re.escape(str(funcionario_nome_dialogflow))}$", re.IGNORECASE)
        responsavel_final = await Funcionario.find_one({"nome": nome_regex})
    elif usuario_logado:
        # Se NENHUM nome foi dito, usa o usuário do TOKEN como padrão
        responsavel_final = usuario_logado
    
    # --- Construção da Query de Tarefas ---
    query_conditions = []
    
    if responsavel_final:
        query_conditions.append(Tarefa.responsavel.id == responsavel_final.id)
    elif intent in ["ListarTarefas", "ContarTarefas"]:
         # Se não há usuário logado nem nome especificado, a busca não terá um responsável.
         response_json = {
            "fulfillment_response": {
                "messages": [{"text": {"text": ["Por favor, especifique um funcionário ou faça login para ver suas próprias tarefas."]}}]
            }
         }
         return response_json

    status_tarefa_dialogflow = params.get("statustarefa")
    date_period_param = params.get("date-period")

    if status_tarefa_dialogflow:
        status_normalizado = str(status_tarefa_dialogflow).capitalize()
        status_map = {
            "Em andamento": StatusTarefa.EM_ANDAMENTO,
            "Congelada": StatusTarefa.CONGELADA,
            "Não iniciada": StatusTarefa.NAO_INICIADA,
            "Concluída": StatusTarefa.CONCLUIDA,
        }
        if status_normalizado == "Atrasada":
            query_conditions.append(Tarefa.prazo < date.today())
            query_conditions.append(Tarefa.status != StatusTarefa.CONCLUIDA)
        elif status_normalizado in status_map:
            query_conditions.append(Tarefa.status == status_map[status_normalizado])
            
    if date_period_param:
        start_str = date_period_param.get("startDate")
        end_str = date_period_param.get("endDate")
        if start_str and end_str:
            data_inicio = datetime.fromisoformat(start_str.split('T')[0]).date()
            data_fim = datetime.fromisoformat(end_str.split('T')[0]).date()
            query_conditions.append(Tarefa.prazo >= data_inicio)
            query_conditions.append(Tarefa.prazo <= data_fim)

    # Lógica de resposta
    resposta_texto = "Desculpe, não consegui processar sua solicitação."
    
    if intent == "ListarTarefas":
        tarefas_encontradas = await Tarefa.find(*query_conditions, fetch_links=True).to_list()
        if not tarefas_encontradas:
            resposta_texto = "Não encontrei nenhuma tarefa com esses critérios."
        else:
            nomes_tarefas = [f"'{t.nome}'" for t in tarefas_encontradas]
            resposta_texto = f"Encontrei as seguintes tarefas: {', '.join(nomes_tarefas)}."

    elif intent == "ContarTarefas":
        contagem = await Tarefa.find(*query_conditions).count()
        if contagem == 0:
            resposta_texto = "Não encontrei nenhuma tarefa com esses critérios."
        elif contagem == 1:
            tarefa_encontrada = await Tarefa.find_one(*query_conditions, fetch_links=True)
            resposta_texto = f"Encontrei 1 tarefa: '{tarefa_encontrada.nome}'."
        else:
            resposta_texto = f"Encontrei um total de {contagem} tarefas com esses critérios."
    
    # --- Resposta Final para o Dialogflow ---
    response_json = {
        "fulfillment_response": {
            "messages": [{"text": {"text": [resposta_texto]}}]
        },
        # Limpa os parâmetros para a próxima interação
        "sessionInfo": {
            "parameters": {
                "funcionario": None,
                "statustarefa": None,
                "date-period": None
                # Não limpe o token, pois ele deve persistir na sessão
            }
        }
    }
    
    return response_json