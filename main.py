from fastapi import FastAPI, HTTPException, Body, Request
from typing import List, Optional
from beanie import PydanticObjectId
from contextlib import asynccontextmanager
from datetime import date, datetime
import re

from database import db
from models import (
    Funcionario, Projeto, Tarefa, Calendario,
    FuncionarioCreate, ProjetoCreate, TarefaCreate, CalendarioCreate, StatusTarefa
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    yield

app = FastAPI(
    lifespan=lifespan,
    title="API de Gerenciamento de Projetos e Tarefas",
    description="Backend refatorado para gerenciar funcionários, projetos, tarefas e calendário.",
    version="2.0.0"
)

# --- Endpoints de Funcionários ---

@app.post("/funcionarios", response_model=Funcionario, tags=["Funcionários"])
async def criar_funcionario(funcionario_data: FuncionarioCreate = Body(...)):
    funcionario_existente = await Funcionario.find_one(Funcionario.email == funcionario_data.email)
    if funcionario_existente:
        raise HTTPException(status_code=400, detail="Um funcionário com este email já existe.")
    
    funcionario = Funcionario(**funcionario_data.dict())
    await funcionario.insert()
    return funcionario

@app.get("/funcionarios", response_model=List[Funcionario], tags=["Funcionários"])
async def listar_funcionarios():
    funcionarios = await Funcionario.find_all().to_list()
    return funcionarios

# --- NOVO ENDPOINT ADICIONADO ---
@app.get("/funcionarios/{funcionario_id}", response_model=Funcionario, tags=["Funcionários"])
async def obter_funcionario(funcionario_id: PydanticObjectId):
    funcionario = await Funcionario.get(funcionario_id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return funcionario

# --- Endpoints de Projetos ---

@app.post("/projetos", response_model=Projeto, tags=["Projetos"])
async def criar_projeto(projeto_data: ProjetoCreate = Body(...)):
    responsavel_id = PydanticObjectId(projeto_data.responsavel_id)
    responsavel = await Funcionario.get(responsavel_id)
    if not responsavel:
        raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")
    
    projeto = Projeto(
        **projeto_data.dict(exclude={"responsavel_id"}),
        responsavel=responsavel
    )
    await projeto.insert()
    return projeto

@app.get("/projetos", response_model=List[Projeto], tags=["Projetos"])
async def listar_projetos():
    projetos = await Projeto.find_all().to_list()
    return projetos

@app.get("/projetos/{projeto_id}", response_model=Projeto, tags=["Projetos"])
async def obter_projeto(projeto_id: PydanticObjectId):
    projeto = await Projeto.get(projeto_id, fetch_links=True)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return projeto

# --- Endpoints de Tarefas ---

@app.post("/tarefas", response_model=Tarefa, tags=["Tarefas"])
async def criar_tarefa(tarefa_data: TarefaCreate = Body(...)):
    projeto_id = PydanticObjectId(tarefa_data.projeto_id)
    responsavel_id = PydanticObjectId(tarefa_data.responsavel_id)

    projeto = await Projeto.get(projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
        
    responsavel = await Funcionario.get(responsavel_id)
    if not responsavel:
        raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")

    tarefa = Tarefa(
        **tarefa_data.dict(exclude={"projeto_id", "responsavel_id"}),
        projeto=projeto,
        responsavel=responsavel
    )
    await tarefa.insert()
    return tarefa

@app.get("/projetos/{projeto_id}/tarefas", response_model=List[Tarefa], tags=["Tarefas"])
async def listar_tarefas_do_projeto(projeto_id: PydanticObjectId):
    projeto = await Projeto.get(projeto_id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    
    tarefas = await Tarefa.find(Tarefa.projeto.id == projeto_id, fetch_links=True).to_list()
    return tarefas

# --- NOVO ENDPOINT ADICIONADO ---
@app.get("/tarefas/{tarefa_id}", response_model=Tarefa, tags=["Tarefas"])
async def obter_tarefa(tarefa_id: PydanticObjectId):
    tarefa = await Tarefa.get(tarefa_id, fetch_links=True)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return tarefa

# --- Endpoints de Calendário ---

@app.post("/calendario", response_model=Calendario, tags=["Calendário"])
async def agendar_evento_calendario(calendario_data: CalendarioCreate = Body(...)):
    projeto_link = None
    tarefa_link = None

    projeto_id: Optional[str] = None
    tarefa_id: Optional[str] = None
    
    if calendario_data.projeto_id:
        projeto_id = PydanticObjectId(calendario_data.projeto_id)
        projeto_link = await Projeto.get(projeto_id)
        if not projeto_link:
            raise HTTPException(status_code=404, detail="Projeto para agendamento não encontrado.")

    if calendario_data.tarefa_id:
        tarefa_id = PydanticObjectId(calendario_data.tarefa_id)
        tarefa_link = await Tarefa.get(tarefa_id)
        if not tarefa_link:
            raise HTTPException(status_code=404, detail="Tarefa para agendamento não encontrada.")

    evento_calendario = Calendario(
        **calendario_data.dict(exclude={"projeto_id", "tarefa_id"}),
        projeto=projeto_link,
        tarefa=tarefa_link
    )
    await evento_calendario.insert()
    return evento_calendario

# --- NOVO ENDPOINT ADICIONADO ---
@app.get("/calendario/{calendario_id}", response_model=Calendario, tags=["Calendário"])
async def obter_evento_calendario(calendario_id: PydanticObjectId):
    evento = await Calendario.get(calendario_id, fetch_links=True)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento do calendário não encontrado.")
    return evento

# --- Endpoint do Webhook ---

@app.post("/webhook", tags=["Dialogflow"])
async def dialogflow_webhook(request: Request):
    payload = await request.json()
    
    intent = payload.get("intentInfo", {}).get("displayName", "")
    params = payload.get("sessionInfo", {}).get("parameters", {})
    
    funcionario_nome_dialogflow = params.get("funcionario")
    status_tarefa_dialogflow = params.get("statustarefa")
    date_period_param = params.get("date-period")
    
    query_conditions = []

    if funcionario_nome_dialogflow:
        responsavel = None
        name_parts = funcionario_nome_dialogflow.split()
        for i in range(len(name_parts), 0, -1):
            current_name_to_check = " ".join(name_parts[:i])
            nome_regex = re.compile(f"^{re.escape(current_name_to_check)}$", re.IGNORECASE)
            responsavel = await Funcionario.find_one({"nome": nome_regex})
            if responsavel:
                break

        if responsavel:
            query_conditions.append(Tarefa.responsavel.id == responsavel.id)
        else:
            query_conditions.append(Tarefa.responsavel.id == PydanticObjectId("000000000000000000000000"))

    if status_tarefa_dialogflow:
        status_normalizado = ""
        if isinstance(status_tarefa_dialogflow, str):
            status_normalizado = status_tarefa_dialogflow.capitalize()
        
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
            data_inicio = datetime.fromisoformat(start_str).date()
            data_fim = datetime.fromisoformat(end_str).date()
            query_conditions.append(Tarefa.prazo >= data_inicio)
            query_conditions.append(Tarefa.prazo <= data_fim)

    resposta_texto = "Desculpe, não consegui processar sua solicitação."

    if intent == "ListarTarefas":
        tarefas_encontradas = await Tarefa.find(*query_conditions, fetch_links=True).to_list()
        if not tarefas_encontradas:
            resposta_texto = "Não encontrei nenhuma tarefa com esses critérios."
        else:
            nomes_tarefas = [f"'{t.nome}' (Responsável: {t.responsavel.nome})" for t in tarefas_encontradas]
            resposta_texto = f"Encontrei as seguintes tarefas: {', '.join(nomes_tarefas)}."

    elif intent == "ContarTarefas":
        tarefas_encontradas = await Tarefa.find(*query_conditions, fetch_links=True).to_list()
        contagem = len(tarefas_encontradas)
        if contagem == 0:
            resposta_texto = "Não encontrei nenhuma tarefa com esses critérios."
        elif contagem == 1:
            nomes_tarefas = [f"'{t.nome}' (Responsável: {t.responsavel.nome})" for t in tarefas_encontradas]
            resposta_texto = f"Encontrei 1 tarefa com esses critérios: {nomes_tarefas[0]}."
        elif contagem <= 3:
            nomes_tarefas = [f"'{t.nome}'" for t in tarefas_encontradas]
            resposta_texto = f"Encontrei um total de {contagem} tarefas: {', '.join(nomes_tarefas)}."
        else:
            resposta_texto = f"Encontrei um total de {contagem} tarefas com esses critérios."

    response_json = {
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [resposta_texto]}}
            ]
        },
        "sessionInfo": {
            "parameters": {
                "funcionario": None,
                "statustarefa": None,
                "date-period": None
            }
        }
    }
    
    return response_json  
  
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Bem-vindo à API v2! Acesse /docs para a documentação."}