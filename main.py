from fastapi import FastAPI, HTTPException, Body
from typing import List
from beanie import PydanticObjectId
from contextlib import asynccontextmanager
from datetime import date, datetime

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

@app.post("/calendario", response_model=Calendario, tags=["Calendário"])
async def agendar_evento_calendario(calendario_data: CalendarioCreate = Body(...)):
    projeto_link = None
    tarefa_link = None

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

@app.post("/webhook", tags=["Dialogflow"])
async def dialogflow_webhook(request: Request):
    payload = await request.json()
    
    intent = payload.get("intentInfo", {}).get("displayName", "")
    params = payload.get("sessionInfo", {}).get("parameters", {})
    
    pessoa_nome = params.get("Pessoa")
    status_tarefa_dialogflow = params.get("StatusTarefa")
    date_period_param = params.get("date-period")
    
    query_conditions = []

    if pessoa_nome:
        responsavel = await Funcionario.find_one(Funcionario.nome == pessoa_nome.capitalize())
        if responsavel:
            query_conditions.append(Tarefa.responsavel.id == responsavel.id)
        else:
            query_conditions.append(Tarefa.responsavel.id == PydanticObjectId("000000000000000000000000"))

    if status_tarefa_dialogflow:
        status_map = {
            "Em Andamento": StatusTarefa.EM_ANDAMENTO,
            "Congelada": StatusTarefa.CONGELADA,
            "Não Iniciada": StatusTarefa.NAO_INICIADA,
            "Concluída": StatusTarefa.CONCLUIDA,
        }
        if status_tarefa_dialogflow == "Atrasada":
            query_conditions.append(Tarefa.prazo < date.today())
            query_conditions.append(Tarefa.status != StatusTarefa.CONCLUIDA)
        elif status_tarefa_dialogflow in status_map:
            query_conditions.append(Tarefa.status == status_map[status_tarefa_dialogflow])

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
        contagem = await Tarefa.find(*query_conditions).count()
        if contagem == 0:
            resposta_texto = "Não encontrei nenhuma tarefa com esses critérios."
        elif contagem == 1:
            resposta_texto = f"Encontrei 1 tarefa com esses critérios."
        else:
            resposta_texto = f"Encontrei um total de {contagem} tarefas com esses critérios."

    response_json = {
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [resposta_texto]}}
            ]
        }
    }
    
    return response_json

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Bem-vindo à API v2! Acesse /docs para a documentação."}