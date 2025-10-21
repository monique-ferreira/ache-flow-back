# main.py
from fastapi import FastAPI, HTTPException, Body, Query, Depends, status, Request, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Optional
from beanie import PydanticObjectId, operators
from contextlib import asynccontextmanager
from datetime import date, datetime
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

# Importa a lógica de autenticação, IA e os modelos
import auth
from ia_generativa import inicializar_ia, gerar_resposta_ia
from database import db
from models import (
    Funcionario, Projeto, Tarefa, Calendario, Token,
    FuncionarioCreate, ProjetoCreate, TarefaCreate, CalendarioCreate,
    FuncionarioUpdate, ProjetoUpdate, TarefaUpdate, CalendarioUpdate,
    StatusTarefa, PrioridadeTarefa, TokenData,
    ChatRequest, AIResponse
)

# NOVOS módulos
from ingest import ingest_file, ingest_from_doc_link, ingest_from_doc_links, ingest_from_sheet_or_csv_url  # NOVO
from command_router import handle_command

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    inicializar_ia()
    yield

app = FastAPI(
    lifespan=lifespan,
    title="API de Gerenciamento de Projetos e Tarefas",
    description="API com CRUD completo, autenticação e IA Generativa.",
    version="9.1.0"  # IA + comandos + ingestão universal + múltiplos links
)

# CORS amplo (ajuste se necessário)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LÓGICA CENTRAL DA IA ---
async def obter_resposta_ia(pergunta: str, current_user: Funcionario) -> AIResponse:
    nome_usuario = current_user.nome

    # 1. Coletar contexto
    projetos_usuario = await Projeto.find(Projeto.responsavel.id == current_user.id).to_list()
    tarefas_pendentes = await Tarefa.find(
        Tarefa.responsavel.id == current_user.id,
        Tarefa.status != StatusTarefa.CONCLUIDA
    ).sort(+Tarefa.prazo).to_list()
    todos_funcionarios = await Funcionario.find_all().to_list()

    # 2. Montar contexto
    contexto_formatado = f"**Dados do usuário logado ({nome_usuario}):**\n"
    if projetos_usuario:
        contexto_formatado += "Projetos sob sua responsabilidade:\n" + "\n".join([f"- {p.nome}" for p in projetos_usuario])
    else:
        contexto_formatado += "Nenhum projeto encontrado.\n"

    contexto_formatado += "\n\nTarefas Pendentes:\n"
    if tarefas_pendentes:
        contexto_formatado += "\n".join(
            [f"- Título: '{t.nome}', Status: '{t.status.value}', Prazo: {t.prazo.strftime('%d/%m/%Y')}" for t in tarefas_pendentes]
        )
    else:
        contexto_formatado += "Nenhuma tarefa pendente."

    contexto_formatado += f"\n\n**Lista de todos os funcionários na empresa:**\n"
    if todos_funcionarios:
        contexto_formatado += "\n".join(
            [f"- Nome: {f.nome} {f.sobrenome}, Cargo: {f.cargo or 'Não informado'}, Departamento: {f.departamento or 'Não informado'}" for f in todos_funcionarios]
        )
    else:
        contexto_formatado += "Nenhum funcionário cadastrado."

    # 3. Chamar IA
    texto_gerado_pela_ia = await gerar_resposta_ia(
        contexto=contexto_formatado,
        pergunta=pergunta,
        nome_usuario=nome_usuario
    )

    return AIResponse(
        tipo_resposta="TEXTO",
        conteudo_texto=texto_gerado_pela_ia,
        dados=None
    )

# --- AUTENTICAÇÃO ---
@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_para_obter_token(form_data: OAuth2PasswordRequestForm = Depends()):
    funcionario = await Funcionario.find_one(Funcionario.email == form_data.username)
    if not funcionario or not auth.verificar_senha(form_data.password, funcionario.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha incorretos")
    token_acesso = auth.criar_token_acesso(data={"sub": funcionario.email})
    return {"access_token": token_acesso, "token_type": "bearer"}

# --- CHAT IA + COMANDOS ---
# --- CHAT IA + COMANDOS ---
@app.post(
    "/ai/chat",
    response_model=AIResponse,
    tags=["IA Generativa"],
    summary="Processa pergunta usando IA. Se detectar comando, executa antes."
)
async def processar_chat_ia(
    chat_request: ChatRequest,
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    pergunta = chat_request.pergunta or ""

    # 1) Tenta executar um comando (ação direta)
    try:
        cmd_result = await handle_command(pergunta)
    except Exception as e:
        cmd_result = {"executado": False, "mensagem": f"Falha ao processar comando: {e}"}

    if cmd_result is not None:
        # ✅ CURTO-CIRCUITO: não chama a IA quando existe retorno do roteador
        # (se executou ou se falhou, retorna a mensagem explicativa)
        tipo = "ACOES" if cmd_result.get("executado") else "ACOES_FALHOU"
        return AIResponse(
            tipo_resposta=tipo,
            conteudo_texto=cmd_result.get("mensagem", "Comando processado."),
            dados=None
        )

    # 2) Sem comando → chama a IA normalmente
    try:
        return await obter_resposta_ia(pergunta, current_user)
    except Exception:
        # Resposta de fallback única (sem duplicar erro)
        return AIResponse(
            tipo_resposta="ERRO",
            conteudo_texto="Desculpe, tive um problema ao tentar gerar sua resposta. Por favor, tente novamente.",
            dados=None
        )

# --- CRUDs (existentes) ---
@app.post("/funcionarios", response_model=Funcionario, tags=["Funcionários"])
async def criar_funcionario(funcionario_data: FuncionarioCreate):
    if await Funcionario.find_one(Funcionario.email == funcionario_data.email):
        raise HTTPException(status_code=400, detail="Um funcionário com este email já existe.")
    senha_hashed = auth.gerar_hash_senha(funcionario_data.senha)
    funcionario_dict = funcionario_data.dict(exclude={"senha"})
    funcionario = Funcionario(**funcionario_dict, senha=senha_hashed)
    await funcionario.insert()
    return funcionario

@app.get("/funcionarios/me", response_model=Funcionario, tags=["Funcionários"])
async def ler_usuario_logado(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return current_user

@app.get("/funcionarios", response_model=List[Funcionario], tags=["Funcionários"])
async def listar_funcionarios(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return await Funcionario.find_all().to_list()

@app.get("/funcionarios/{id}", response_model=Funcionario, tags=["Funcionários"])
async def obter_funcionario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return funcionario

@app.put("/funcionarios/{id}", response_model=Funcionario, tags=["Funcionários"])
async def atualizar_funcionario(id: PydanticObjectId, update_data: FuncionarioUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    update_data_dict = update_data.dict(exclude_unset=True)
    for key, value in update_data_dict.items():
        setattr(funcionario, key, value)
    await funcionario.save()
    return funcionario

@app.delete("/funcionarios/{id}", status_code=204, tags=["Funcionários"])
async def deletar_funcionario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    funcionario = await Funcionario.get(id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    await funcionario.delete()
    return None

@app.post("/projetos", response_model=Projeto, tags=["Projetos"])
async def criar_projeto(projeto_data: ProjetoCreate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    responsavel = await Funcionario.get(PydanticObjectId(projeto_data.responsavel_id))
    if not responsavel:
        raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")
    projeto = Projeto(**projeto_data.dict(exclude={"responsavel_id"}), responsavel=responsavel)
    await projeto.insert()
    return projeto

@app.get("/projetos", response_model=List[Projeto], tags=["Projetos"])
async def listar_projetos(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return await Projeto.find_all(fetch_links=True).to_list()

@app.get("/projetos/{id}", response_model=Projeto, tags=["Projetos"])
async def obter_projeto(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(id, fetch_links=True)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return projeto

@app.put("/projetos/{id}", response_model=Projeto, tags=["Projetos"])
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

@app.delete("/projetos/{id}", status_code=204, tags=["Projetos"])
async def deletar_projeto(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(id)
    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    await projeto.delete()
    return None

@app.post("/tarefas", response_model=Tarefa, tags=["Tarefas"])
async def criar_tarefa(tarefa_data: TarefaCreate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto = await Projeto.get(PydanticObjectId(tarefa_data.projeto_id))
    if not projeto: raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    responsavel = await Funcionario.get(PydanticObjectId(tarefa_data.responsavel_id))
    if not responsavel: raise HTTPException(status_code=404, detail="Funcionário responsável não encontrado.")
    tarefa_dict = tarefa_data.dict(exclude={"projeto_id", "responsavel_id"})
    tarefa = Tarefa(**tarefa_dict, projeto=projeto, responsavel=responsavel)
    await tarefa.insert()
    return tarefa

@app.get("/tarefas", response_model=List[Tarefa], tags=["Tarefas"])
async def listar_tarefas_filtradas(
    departamento: Optional[str] = Query(None, description="Filtrar por departamento do responsável"),
    projeto_id: Optional[PydanticObjectId] = Query(None, description="Filtrar por ID do projeto"),
    responsavel_id: Optional[PydanticObjectId] = Query(None, description="Filtrar por ID do responsável"),
    urgencia: Optional[bool] = Query(False, description="Ordenar tarefas por urgência"),
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    query_conditions = []
    if responsavel_id: query_conditions.append(Tarefa.responsavel.id == responsavel_id)
    if projeto_id: query_conditions.append(Tarefa.projeto.id == projeto_id)
    if departamento:
        funcionarios_no_dpto = await Funcionario.find(Funcionario.departamento == departamento).to_list()
        ids_funcionarios = [f.id for f in funcionarios_no_dpto]
        if not ids_funcionarios: return []
        query_conditions.append(operators.In(Tarefa.responsavel.id, ids_funcionarios))
    sort_expression = []
    if urgencia: sort_expression.extend([("prazo", 1), ("prioridade", -1)])
    tarefas = await Tarefa.find(*query_conditions, fetch_links=True).sort(*sort_expression).to_list()
    return tarefas

@app.get("/tarefas/{id}", response_model=Tarefa, tags=["Tarefas"])
async def obter_tarefa(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id, fetch_links=True)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return tarefa

@app.put("/tarefas/{id}", response_model=Tarefa, tags=["Tarefas"])
async def atualizar_tarefa(id: PydanticObjectId, update_data: TarefaUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id, fetch_links=True)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    update_data_dict = update_data.dict(exclude_unset=True)
    if "responsavel_id" in update_data_dict:
        novo_responsavel = await Funcionario.get(PydanticObjectId(update_data_dict["responsavel_id"]))
        if not novo_responsavel: raise HTTPException(status_code=404, detail="Novo funcionário responsável não encontrado.")
        tarefa.responsavel = novo_responsavel
        del update_data_dict["responsavel_id"]
    if "status" in update_data_dict and update_data_dict["status"] == StatusTarefa.CONCLUIDA:
        tarefa.dataConclusao = date.today()
    for key, value in update_data_dict.items():
        setattr(tarefa, key, value)
    await tarefa.save()
    return await Tarefa.get(id, fetch_links=True)

@app.delete("/tarefas/{id}", status_code=204, tags=["Tarefas"])
async def deletar_tarefa(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefa = await Tarefa.get(id)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    await tarefa.delete()
    return None

# --- Calendário (existente) ---
@app.post("/calendario", response_model=Calendario, tags=["Calendário"])
async def criar_evento_calendario(calendario_data: CalendarioCreate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    projeto_link = tarefa_link = None
    if calendario_data.projeto_id:
        projeto_link = await Projeto.get(PydanticObjectId(calendario_data.projeto_id))
        if not projeto_link: raise HTTPException(status_code=404, detail="Projeto para agendamento não encontrado.")
    if calendario_data.tarefa_id:
        tarefa_link = await Tarefa.get(PydanticObjectId(calendario_data.tarefa_id))
        if not tarefa_link: raise HTTPException(status_code=404, detail="Tarefa para agendamento não encontrada.")
    evento = Calendario(**calendario_data.dict(exclude={"projeto_id", "tarefa_id"}), projeto=projeto_link, tarefa=tarefa_link)
    await evento.insert()
    return evento

@app.get("/calendario", response_model=List[Calendario], tags=["Calendário"])
async def listar_eventos_calendario(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    return await Calendario.find_all(fetch_links=True).to_list()

@app.get("/calendario/{id}", response_model=Calendario, tags=["Calendário"])
async def obter_evento_calendario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    evento = await Calendario.get(id, fetch_links=True)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento do calendário não encontrado.")
    return evento

@app.put("/calendario/{id}", response_model=Calendario, tags=["Calendário"])
async def atualizar_evento_calendario(id: PydanticObjectId, update_data: CalendarioUpdate, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    evento = await Calendario.get(id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento do calendário não encontrado.")
    update_dict = update_data.dict(exclude_unset=True)
    if "projeto_id" in update_dict:
        evento.projeto = await Projeto.get(PydanticObjectId(update_dict["projeto_id"])) if update_dict["projeto_id"] else None
    if "tarefa_id" in update_dict:
        evento.tarefa = await Tarefa.get(PydanticObjectId(update_dict["tarefa_id"])) if update_dict["tarefa_id"] else None
    for key, value in update_dict.items():
        if key not in ["projeto_id", "tarefa_id"]:
            setattr(evento, key, value)
    await evento.save()
    return await Calendario.get(id, fetch_links=True)

@app.delete("/calendario/{id}", status_code=204, tags=["Calendário"])
async def deletar_evento_calendario(id: PydanticObjectId, current_user: Funcionario = Depends(auth.get_usuario_logado)):
    evento = await Calendario.get(id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    await evento.delete()
    return None

# --- Exportação/Importação de Tarefas (existente) ---
@app.get("/tarefas/exportar", tags=["Tarefas"])
async def exportar_tarefas_excel(current_user: Funcionario = Depends(auth.get_usuario_logado)):
    tarefas = await Tarefa.find_all(fetch_links=True).to_list()
    if not tarefas:
        raise HTTPException(status_code=404, detail="Nenhuma tarefa encontrado para exportar.")
    tarefas_data = [{
        "ID da Tarefa": str(t.id),
        "Nome da Tarefa": t.nome,
        "Descrição": t.descricao,
        "Prioridade": t.prioridade.value,
        "Status": t.status.value,
        "Prazo": t.prazo.isoformat(),
        "Projeto": t.projeto.nome if t.projeto else None,
        "Responsável": f"{t.responsavel.nome} {t.responsavel.sobrenome}" if t.responsavel else None,
        "Email Responsável": t.responsavel.email if t.responsavel else None,
        "Número": t.numero,
        "Classificação": t.classificacao,
        "Fase": t.fase,
        "Condição": t.condicao,
        "Documento de Referência": t.documento_referencia,
        "Concluído": t.concluido
    } for t in tarefas]
    df = pd.DataFrame(tarefas_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Tarefas')
    output.seek(0)
    headers = {'Content-Disposition': 'attachment; filename="tarefas.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- NOVO: Import universal (xlsx/csv/docx) + Link(s) de DOC ---
@app.post("/ingest/arquivo", tags=["Ingestão"], summary="Envia .xlsx, .csv ou .docx; auto-roteia para tarefas/projetos/funcionários")
async def ingest_arquivo(file: UploadFile = File(...), current_user: Funcionario = Depends(auth.get_usuario_logado)):
    contents = await file.read()
    result = await ingest_file(file.filename, contents)
    return JSONResponse(result)

@app.post("/ingest/link", tags=["Ingestão"], summary="Um DOC (Google Docs/Word publicado) com hyperlinks para Sheets/Excel/CSV")
async def ingest_link(
    url: str = Body(..., embed=True, description="URL do documento que contém hyperlinks"),
    pegar_indice: Optional[int] = Body(None, embed=True, description="Ex.: 3 para 'terceira planilha'"),
    limitar_linhas: Optional[int] = Body(None, embed=True, description="Limite de linhas ao ler a planilha"),
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    result = await ingest_from_doc_link(url, pick_index=pegar_indice, limit_rows=limitar_linhas)
    return JSONResponse(result)

@app.post(
    "/ingest/links",
    tags=["Ingestão"],
    summary="Vários DOCs (Google Docs/Word publicado), cada um com hyperlinks para Sheets/Excel/CSV"
)
async def ingest_links(
    payload: dict = Body(
        ...,
        example={
            "urls": [
                "https://docs.google.com/document/d/AAA...",
                "https://docs.google.com/document/d/BBB..."
            ],
            "pegar_indice": None,
            "limitar_linhas": 100
        },
        description=(
            "Envie 'urls' como lista de documentos (cada um contendo hyperlinks para planilhas).\n"
            "Opcionalmente, 'pegar_indice' (ex.: 3 para 'terceira planilha') e 'limitar_linhas' (inteiro)."
        ),
    ),
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    urls = payload.get("urls")
    if not urls or not isinstance(urls, list):
        raise HTTPException(status_code=400, detail="Campo 'urls' deve ser uma lista com ao menos um link.")
    pegar_indice = payload.get("pegar_indice")
    limitar_linhas = payload.get("limitar_linhas")
    result = await ingest_from_doc_links(urls, pick_index=pegar_indice, limit_rows=limitar_linhas)
    return JSONResponse(result)

@app.post("/ingest/planilha", tags=["Ingestão"])
async def ingest_planilha_por_url(
    payload: dict = Body(..., example={"url": "https://docs.google.com/spreadsheets/d/..../edit?usp=sharing", "limitar_linhas": 100}),
    current_user: Funcionario = Depends(auth.get_usuario_logado)
):
    url = payload.get("url")
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Campo 'url' é obrigatório.")
    limitar_linhas = payload.get("limitar_linhas")
    result = await ingest_from_sheet_or_csv_url(url, limit_rows=limitar_linhas)
    return JSONResponse(result)


# --- Webhook (Dialogflow) ---
@app.post("/webhook", tags=["Dialogflow"])
async def dialogflow_webhook(request: Request):
    payload = await request.json()
    pergunta = payload.get("text") or payload.get("sessionInfo", {}).get("parameters", {}).get("pergunta", "pergunta não encontrada")
    token = payload.get("sessionInfo", {}).get("parameters", {}).get("token")
    usuario_logado = None
    if token:
        try:
            payload_token = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            email = payload_token.get("sub")
            if email:
                usuario_logado = await Funcionario.find_one(Funcionario.email == email)
        except JWTError:
            pass
    if not usuario_logado:
        return {"fulfillment_response": {"messages": [{"text": {"text": ["Sessão inválida. Por favor, faça login novamente."]}}]}}
    cmd_result = await handle_command(pergunta)
    if cmd_result:
        ai = await obter_resposta_ia(pergunta, usuario_logado)
        texto = f"{cmd_result['mensagem']}\n\n{ai.conteudo_texto}"
    else:
        ai = await obter_resposta_ia(pergunta, usuario_logado)
        texto = ai.conteudo_texto
    response_json = {
        "fulfillment_response": {
            "messages": [
                {"text": {"text": [texto]}},
                {"payload": ai.dict()}
            ]
        }
    }
    return response_json
