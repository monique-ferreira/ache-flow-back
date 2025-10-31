from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from beanie import PydanticObjectId

import security
from database import db
from models import (
    Funcionario, Projeto, Tarefa, Calendario,
    TarefaCreate, TarefaUpdate, ProjetoCreate, ProjetoUpdate,
    StatusTarefa, Token
)
from command_router import handle_command
from ingest import ingest_xlsx, ingest_from_url
import io
import pandas as pd

from fastapi.security import OAuth2PasswordRequestForm
import security

# ---------------------------
# Lifespan / App
# ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    yield

app = FastAPI(title="AcheFlow API", version="4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ache-flow.vercel.app"
    ],
    allow_credentials=True,  # ou False se não for usar cookies/aut com credenciais
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Utils
# ---------------------------
def _doc(obj):
    if obj is None:
        return None
    d = obj.dict()
    # normaliza IDs linkados
    if hasattr(obj, "id"):
        d["id"] = str(obj.id)
    if "projeto" in d and d["projeto"] and hasattr(d["projeto"], "id"):
        d["projeto_id"] = str(d["projeto"].id)
    if "responsavel" in d and d["responsavel"] and hasattr(d["responsavel"], "id"):
        d["responsavel_id"] = str(d["responsavel"].id)
    return d

async def _recalcular_situacao_projeto(proj_id: PydanticObjectId):
    proj = await Projeto.get(proj_id, fetch_links=True)
    if not proj:
        return
    tarefas = await Tarefa.find(Tarefa.projeto.id == proj_id).to_list()
    if not tarefas:
        proj.situacao = "não iniciado"
    else:
        media = round(sum(t.porcentagem or 0 for t in tarefas) / len(tarefas))
        if media == 100:
            proj.situacao = "concluído"
        elif media == 0:
            proj.situacao = "não iniciado"
        else:
            proj.situacao = "em andamento"
    await proj.save()


# ---------------------------
# Health
# ---------------------------
@app.get("/health")
async def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}


# ---------------------------
# Dependência de Auth
# ---------------------------
get_user = security.get_usuario_logado  # usa seu fluxo real (Bearer)


# ---------------------------
# IA / Chat
# ---------------------------
class AIResponse:
    def __init__(self, conteudo_texto: str, tipo_resposta: str = "TEXTO"):
        self.conteudo_texto = conteudo_texto
        self.tipo_resposta = tipo_resposta

async def obter_resposta_ia(pergunta: str, current_user: Funcionario) -> AIResponse:
    # plugue sua ia_generativa se quiser
    return AIResponse(f"(IA) {pergunta}")

@app.post("/ai/chat", tags=["IA Generativa"])
async def processar_chat_ia(
    pergunta: str,
    current_user: Funcionario = Depends(get_user)
):
    cmd_result = await handle_command(pergunta)
    if cmd_result:
        msg_cmd = cmd_result["mensagem"]
        ai = await obter_resposta_ia(f"{pergunta}\n\nResumo: {msg_cmd}", current_user)
        return {"tipo": "ACOES+TEXTO", "mensagem": msg_cmd, "ia": ai.conteudo_texto}
    ai = await obter_resposta_ia(pergunta, current_user)
    return {"tipo": "TEXTO", "ia": ai.conteudo_texto}


# ---------------------------
# Ingest
# ---------------------------
@app.post("/ai/ingest/xlsx", tags=["IA Generativa"])
async def ia_ingest_xlsx(
    file: UploadFile = File(...),
    current_user: Funcionario = Depends(get_user)
):
    data = await ingest_xlsx(await file.read(), usar_pdf_para_como_fazer=True)
    ok = data.get("criadas", 0)
    erros = data.get("erros", [])
    resumo = f"Inseri {ok} tarefas."
    if erros:
        resumo += f" {len(erros)} linha(s) com erro."
    return {"mensagem": resumo, "detalhes": data}

@app.post("/ingest/xlsx")
async def ingest_endpoint(
    file: UploadFile = File(...),
    current_user: Funcionario = Depends(get_user)
):
    data = await ingest_xlsx(await file.read(), usar_pdf_para_como_fazer=True)
    return data

@app.post("/ingest/url")
async def ingest_url_endpoint(
    url: str,
    current_user: Funcionario = Depends(get_user)
):
    data = await ingest_from_url(url)
    return data


# ---------------------------
# FUNCIONÁRIOS CRUD
# ---------------------------
@app.get("/funcionarios")
async def listar_funcionarios(
    search: str = "",
    limit: int = 50,
    skip: int = 0,
    current_user: Funcionario = Depends(get_user)
):
    q = {}
    if search:
        # fuzzy básico por nome/email
        res = await Funcionario.find(
            {"$or": [{"nome": {"$regex": search, "$options": "i"}},
                     {"email": {"$regex": search, "$options": "i"}}]}
        ).skip(skip).limit(limit).to_list()
    else:
        res = await Funcionario.find_all().skip(skip).limit(limit).to_list()
    return [_doc(x) for x in res]

@app.post("/funcionarios")
async def criar_funcionario(
    data: Dict[str, Any],
    current_user: Funcionario = Depends(get_user)
):
    if not data.get("email"): raise HTTPException(400, "email é obrigatório")
    if await Funcionario.find_one(Funcionario.email == data["email"]):
        raise HTTPException(400, "email já cadastrado")
    f = Funcionario(**data)
    await f.insert()
    return {"id": str(f.id)}

@app.get("/funcionarios/{func_id}")
async def obter_funcionario(
    func_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    f = await Funcionario.get(func_id)
    if not f: raise HTTPException(404, "Funcionário não encontrado")
    return _doc(f)

@app.put("/funcionarios/{func_id}")
async def atualizar_funcionario(
    func_id: PydanticObjectId,
    data: Dict[str, Any],
    current_user: Funcionario = Depends(get_user)
):
    f = await Funcionario.get(func_id)
    if not f: raise HTTPException(404, "Funcionário não encontrado")
    for k, v in data.items():
        setattr(f, k, v)
    await f.save()
    return {"ok": True}

@app.delete("/funcionarios/{func_id}")
async def excluir_funcionario(
    func_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    f = await Funcionario.get(func_id)
    if not f: raise HTTPException(404, "Funcionário não encontrado")
    await f.delete()
    return {"ok": True}


# ---------------------------
# PROJETOS CRUD
# ---------------------------
@app.get("/projetos")
async def listar_projetos(
    search: str = "",
    limit: int = 50,
    skip: int = 0,
    current_user: Funcionario = Depends(get_user)
):
    if search:
        res = await Projeto.find({"nome": {"$regex": search, "$options": "i"}}).skip(skip).limit(limit).to_list()
    else:
        res = await Projeto.find_all().skip(skip).limit(limit).to_list()
    return [_doc(x) for x in res]

@app.post("/projetos")
async def criar_projeto(
    data: ProjetoCreate,
    current_user: Funcionario = Depends(get_user)
):
    resp = await Funcionario.get(data.responsavel_id)
    if not resp: raise HTTPException(400, "Responsável inválido.")
    proj = Projeto(nome=data.nome, descricao=data.descricao, prazo=data.prazo, responsavel=resp)
    await proj.insert()
    return {"id": str(proj.id)}

@app.get("/projetos/{proj_id}")
async def obter_projeto(
    proj_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    p = await Projeto.get(proj_id, fetch_links=True)
    if not p: raise HTTPException(404, "Projeto não encontrado")
    return _doc(p)

@app.put("/projetos/{proj_id}")
async def atualizar_projeto(
    proj_id: PydanticObjectId,
    data: ProjetoUpdate,
    current_user: Funcionario = Depends(get_user)
):
    proj = await Projeto.get(proj_id, fetch_links=True)
    if not proj:
        raise HTTPException(404, "Projeto não encontrado.")
    if data.nome is not None: proj.nome = data.nome
    if data.descricao is not None: proj.descricao = data.descricao
    if data.prazo is not None: proj.prazo = data.prazo
    if data.responsavel_id is not None:
        resp = await Funcionario.get(data.responsavel_id)
        if not resp: raise HTTPException(400, "Responsável inválido.")
        proj.responsavel = resp
    await proj.save()
    return {"ok": True}

@app.delete("/projetos/{proj_id}")
async def excluir_projeto(
    proj_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    p = await Projeto.get(proj_id)
    if not p: raise HTTPException(404, "Projeto não encontrado")
    await p.delete()
    return {"ok": True}


# ---------------------------
# TAREFAS CRUD
# ---------------------------
@app.get("/tarefas")
async def listar_tarefas(
    limit: int = 50,
    skip: int = 0,
    projeto_id: Optional[PydanticObjectId] = None,
    responsavel_id: Optional[PydanticObjectId] = None,
    status: Optional[str] = None,
    search: str = "",
    current_user: Funcionario = Depends(get_user)
):
    from beanie.operators import In
    q: Dict[str, Any] = {}
    if projeto_id:
        q["projeto.$id"] = projeto_id  # Beanie armazena Link como $id
    if responsavel_id:
        q["responsavel.$id"] = responsavel_id
    if status:
        q["status"] = status
    if search:
        q["nome"] = {"$regex": search, "$options": "i"}
    cur = Tarefa.find(q) if q else Tarefa.find_all()
    res = await cur.skip(skip).limit(limit).to_list()
    return [_doc(x) for x in res]

@app.post("/tarefas")
async def criar_tarefa(
    data: TarefaCreate,
    current_user: Funcionario = Depends(get_user)
):
    projeto = await Projeto.get(data.projeto_id)
    responsavel = await Funcionario.get(data.responsavel_id)
    if not projeto or not responsavel:
        raise HTTPException(400, "Projeto ou responsável inválido.")

    data_fim = data.data_fim or data.prazo
    if not data_fim:
        raise HTTPException(400, "Informe data_fim (ou prazo-compat).")

    status = data.status or (StatusTarefa.CONCLUIDA if (data.porcentagem or 0) == 100 else (StatusTarefa.EM_ANDAMENTO if (data.porcentagem or 0) > 0 else StatusTarefa.NAO_INICIADA))

    tarefa = Tarefa(
        nome=data.nome,
        projeto=projeto,
        responsavel=responsavel,
        como_fazer=data.como_fazer,
        prioridade=data.prioridade,
        condicao=data.condicao,
        categoria=data.categoria,
        porcentagem=data.porcentagem or 0,
        data_inicio=data.data_inicio,
        data_fim=data_fim,
        documento_referencia=data.documento_referencia,
        fase=data.fase,
        status=status,
    )
    if tarefa.status == StatusTarefa.CONCLUIDA:
        tarefa.dataConclusao = datetime.utcnow()

    await tarefa.insert()
    await _recalcular_situacao_projeto(projeto.id)
    return {"id": str(tarefa.id)}

@app.get("/tarefas/{tarefa_id}")
async def obter_tarefa(
    tarefa_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    t = await Tarefa.get(tarefa_id, fetch_links=True)
    if not t: raise HTTPException(404, "Tarefa não encontrada.")
    return _doc(t)

@app.put("/tarefas/{tarefa_id}")
async def atualizar_tarefa(
    tarefa_id: PydanticObjectId,
    data: TarefaUpdate,
    current_user: Funcionario = Depends(get_user)
):
    tarefa = await Tarefa.get(tarefa_id, fetch_links=True)
    if not tarefa:
        raise HTTPException(404, "Tarefa não encontrada.")

    if data.nome is not None: tarefa.nome = data.nome
    if data.como_fazer is not None: tarefa.como_fazer = data.como_fazer
    if data.prioridade is not None: tarefa.prioridade = data.prioridade
    if data.condicao is not None: tarefa.condicao = data.condicao
    if data.categoria is not None: tarefa.categoria = data.categoria
    if data.porcentagem is not None: tarefa.porcentagem = max(0, min(100, data.porcentagem))
    if data.data_inicio is not None: tarefa.data_inicio = data.data_inicio
    if data.data_fim is not None: tarefa.data_fim = data.data_fim
    if data.prazo is not None: tarefa.data_fim = data.prazo  # compat
    if data.documento_referencia is not None: tarefa.documento_referencia = data.documento_referencia
    if data.fase is not None: tarefa.fase = data.fase
    if data.status is not None: tarefa.status = data.status
    if data.projeto_id is not None:
        proj = await Projeto.get(data.projeto_id)
        if not proj: raise HTTPException(400, "Projeto inválido.")
        tarefa.projeto = proj
    if data.responsavel_id is not None:
        resp = await Funcionario.get(data.responsavel_id)
        if not resp: raise HTTPException(400, "Responsável inválido.")
        tarefa.responsavel = resp

    if data.porcentagem is not None and data.status is None:
        tarefa.status = (
            StatusTarefa.CONCLUIDA if tarefa.porcentagem == 100
            else (StatusTarefa.NAO_INICIADA if tarefa.porcentagem == 0 else StatusTarefa.EM_ANDAMENTO)
        )
    tarefa.dataConclusao = datetime.utcnow() if tarefa.status == StatusTarefa.CONCLUIDA else None

    await tarefa.save()
    await _recalcular_situacao_projeto(tarefa.projeto.id)
    return {"ok": True}

@app.delete("/tarefas/{tarefa_id}")
async def excluir_tarefa(
    tarefa_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    tarefa = await Tarefa.get(tarefa_id, fetch_links=True)
    if not tarefa:
        raise HTTPException(404, "Tarefa não encontrada.")
    proj_id = tarefa.projeto.id if tarefa.projeto else None
    await tarefa.delete()
    if proj_id:
        await _recalcular_situacao_projeto(proj_id)
    return {"ok": True}


# Exportar XLSX
@app.get("/tarefas/exportar")
async def exportar_tarefas(
    urgencia: Optional[bool] = Query(default=False),
    current_user: Funcionario = Depends(get_user)
):
    tarefas = await Tarefa.find_all(fetch_links=True).to_list()
    rows = []
    for t in tarefas:
        rows.append({
            "Nome do Projeto": t.projeto.nome if t.projeto else "",
            "Nome da Tarefa": t.nome,
            "Email Responsável": t.responsavel.email if t.responsavel else "",
            "Como fazer?": t.como_fazer,
            "Categoria": t.categoria,
            "Prioridade": t.prioridade.value if t.prioridade else None,
            "Condição": t.condicao.value if t.condicao else None,
            "Documento de Referência": t.documento_referencia,
            "Porcentagem": t.porcentagem,
            "Data de Início": t.data_inicio,
            "Data de Fim": t.data_fim,
            "Fase": t.fase,
            "Status": t.status.value if t.status else None,
        })
    df = pd.DataFrame(rows)
    if urgencia:
        df = df.sort_values(by=["Data de Fim", "Prioridade"], ascending=[True, False], na_position="last")
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="tarefas.xlsx"'}
    return StreamingResponse(buf, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------
# CALENDÁRIO CRUD
# ---------------------------
@app.get("/calendario")
async def listar_calendario(
    limit: int = 50,
    skip: int = 0,
    current_user: Funcionario = Depends(get_user)
):
    res = await Calendario.find_all(fetch_links=True).skip(skip).limit(limit).to_list()
    return [_doc(x) for x in res]

@app.post("/calendario")
async def criar_calendario(
    data: Dict[str, Any],
    current_user: Funcionario = Depends(get_user)
):
    # data: tipoEvento, data_hora_evento, projeto_id?, tarefa_id?
    projeto = None
    tarefa = None
    if data.get("projeto_id"):
        projeto = await Projeto.get(PydanticObjectId(str(data["projeto_id"])))
        if not projeto: raise HTTPException(400, "Projeto inválido.")
    if data.get("tarefa_id"):
        tarefa = await Tarefa.get(PydanticObjectId(str(data["tarefa_id"])))
        if not tarefa: raise HTTPException(400, "Tarefa inválida.")
    cal = Calendario(
        tipoEvento=data["tipoEvento"],
        data_hora_evento=datetime.fromisoformat(data["data_hora_evento"]),
        projeto=projeto,
        tarefa=tarefa
    )
    await cal.insert()
    return {"id": str(cal.id)}

@app.get("/calendario/{cal_id}")
async def obter_calendario(
    cal_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    c = await Calendario.get(cal_id, fetch_links=True)
    if not c: raise HTTPException(404, "Evento não encontrado.")
    return _doc(c)

@app.put("/calendario/{cal_id}")
async def atualizar_calendario(
    cal_id: PydanticObjectId,
    data: Dict[str, Any],
    current_user: Funcionario = Depends(get_user)
):
    c = await Calendario.get(cal_id, fetch_links=True)
    if not c: raise HTTPException(404, "Evento não encontrado.")
    if "tipoEvento" in data: c.tipoEvento = data["tipoEvento"]
    if "data_hora_evento" in data:
        c.data_hora_evento = datetime.fromisoformat(data["data_hora_evento"])
    if "projeto_id" in data and data["projeto_id"]:
        proj = await Projeto.get(PydanticObjectId(str(data["projeto_id"])))
        if not proj: raise HTTPException(400, "Projeto inválido.")
        c.projeto = proj
    if "tarefa_id" in data and data["tarefa_id"]:
        tar = await Tarefa.get(PydanticObjectId(str(data["tarefa_id"])))
        if not tar: raise HTTPException(400, "Tarefa inválida.")
        c.tarefa = tar
    await c.save()
    return {"ok": True}

@app.delete("/calendario/{cal_id}")
async def excluir_calendario(
    cal_id: PydanticObjectId,
    current_user: Funcionario = Depends(get_user)
):
    c = await Calendario.get(cal_id)
    if not c: raise HTTPException(404, "Evento não encontrado.")
    await c.delete()
    return {"ok": True}

# ========== AUTH ==========
# --- AUTENTICAÇÃO ---
@app.post("/token", response_model=Token, tags=["Autenticação"])
async def login_para_obter_token(form_data: OAuth2PasswordRequestForm = Depends()):
    funcionario = await Funcionario.find_one(Funcionario.email == form_data.username)
    if not funcionario or not security.verificar_senha(form_data.password, funcionario.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha incorretos")
    token_acesso = security.criar_token_acesso(data={"sub": funcionario.email})
    return {"access_token": token_acesso, "token_type": "bearer"}

@app.get("/funcionarios/me")
async def auth_me(current_user: Funcionario = Depends(security.get_usuario_logado)):
    """
    Retorna os dados do usuário autenticado (útil p/ o frontend).
    """
    return {
        "id": str(current_user.id),
        "nome": current_user.nome,
        "email": current_user.email,
        "cargo": getattr(current_user, "cargo", None),
    }

@app.post("/auth/register")
async def auth_register(payload: dict):
    """
    Cria usuário com senha (somente para dev/homolog).
    payload = { "nome": "...", "email": "...", "senha": "..." }
    """
    nome = payload.get("nome")
    email = payload.get("email")
    senha = payload.get("senha")
    if not (nome and email and senha):
        raise HTTPException(400, "nome, email e senha são obrigatórios")

    ja = await Funcionario.find_one(Funcionario.email == email)
    if ja:
        raise HTTPException(400, "email já cadastrado")

    u = Funcionario(nome=nome, email=email)
    # salva hash de senha no documento
    setattr(u, "senha_hash", security.get_password_hash(senha))
    await u.insert()
    return {"id": str(u.id), "email": u.email}

