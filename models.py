from datetime import datetime, date
from typing import Optional, List, Any, Dict
from beanie import Document, Link, PydanticObjectId
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class StatusTarefa(str, Enum):
    EM_ANDAMENTO = "em andamento"
    CONGELADA = "congelada"
    NAO_INICIADA = "não iniciada"
    CONCLUIDA = "concluída"

class PrioridadeTarefa(str, Enum):
    BAIXA = "baixa"
    MEDIA = "média"
    ALTA = "alta"

class Funcionario(Document):
    nome: str
    sobrenome: str
    email: EmailStr
    senha: str
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    fotoPerfil: Optional[str] = None
    dataCadastro: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "funcionarios"

class Projeto(Document):
    nome: str
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    situacao: str
    prazo: date
    responsavel: Link[Funcionario]

    class Settings:
        name = "projetos"

class Tarefa(Document):
    nome: str
    descricao: Optional[str] = None
    prioridade: PrioridadeTarefa = PrioridadeTarefa.MEDIA
    status: StatusTarefa = StatusTarefa.NAO_INICIADA
    dataCriacao: datetime = Field(default_factory=datetime.now)
    dataConclusao: Optional[date] = None
    prazo: date
    projeto: Link[Projeto]
    responsavel: Link[Funcionario]
    numero: Optional[str] = None
    classificacao: Optional[str] = None
    fase: Optional[str] = None
    condicao: Optional[str] = None
    documento_referencia: Optional[str] = None
    concluido: Optional[bool] = False

    class Settings:
        name = "tarefas"

class Calendario(Document):
    tipoEvento: str
    data_hora_evento: datetime
    projeto: Optional[Link[Projeto]] = None
    tarefa: Optional[Link[Tarefa]] = None

    class Settings:
        name = "calendario"

# --- Models para Update ---
class FuncionarioUpdate(BaseModel):
    nome: Optional[str] = None
    sobrenome: Optional[str] = None
    email: Optional[EmailStr] = None
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    fotoPerfil: Optional[str] = None

class ProjetoUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    situacao: Optional[str] = None
    prazo: Optional[date] = None
    responsavel_id: Optional[str] = None

class TarefaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    prioridade: Optional[PrioridadeTarefa] = None
    status: Optional[StatusTarefa] = None
    prazo: Optional[date] = None
    responsavel_id: Optional[str] = None

class CalendarioUpdate(BaseModel):
    tipoEvento: Optional[str] = None
    data_hora_evento: Optional[datetime] = None
    projeto_id: Optional[str] = None
    tarefa_id: Optional[str] = None

# --- Models para Create ---
class FuncionarioCreate(BaseModel):
    nome: str
    sobrenome: str
    email: EmailStr
    senha: str
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    fotoPerfil: Optional[str] = None

class ProjetoCreate(BaseModel):
    nome: str
    responsavel_id: str
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    situacao: str
    prazo: date

class TarefaCreate(BaseModel):
    nome: str
    projeto_id: str
    responsavel_id: str
    descricao: Optional[str] = None
    prioridade: PrioridadeTarefa = PrioridadeTarefa.MEDIA
    status: StatusTarefa = StatusTarefa.NAO_INICIADA
    prazo: date
    numero: Optional[str] = None
    classificacao: Optional[str] = None
    fase: Optional[str] = None
    condicao: Optional[str] = None
    documento_referencia: Optional[str] = None
    concluido: Optional[bool] = False

class CalendarioCreate(BaseModel):
    tipoEvento: str
    data_hora_evento: datetime
    projeto_id: Optional[str] = None
    tarefa_id: Optional[str] = None

# --- Models para Autenticação e Chat ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ChatRequest(BaseModel):
    pergunta: str

class AIResponse(BaseModel):
    tipo_resposta: str
    conteudo_texto: str
    dados: Optional[Dict[str, Any]] = None

class FuncionarioOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    nome: str
    sobrenome: str
    email: EmailStr
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    fotoPerfil: Optional[str] = None
    dataCadastro: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True

class ProjetoOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    nome: str
    descricao: Optional[str] = None
    categoria: Optional[str] = None
    situacao: str
    prazo: date
    responsavel: FuncionarioOut # <--- Resposta populada

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True

class TarefaOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    nome: str
    descricao: Optional[str] = None
    prioridade: PrioridadeTarefa
    status: StatusTarefa
    dataCriacao: datetime
    dataConclusao: Optional[date] = None
    prazo: date
    projeto: ProjetoOut       # <--- Resposta populada
    responsavel: FuncionarioOut # <--- Resposta populada
    numero: Optional[str] = None
    classificacao: Optional[str] = None
    fase: Optional[str] = None
    condicao: Optional[str] = None
    documento_referencia: Optional[str] = None
    concluido: Optional[bool] = False

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True

class CalendarioOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
    tipoEvento: str
    data_hora_evento: datetime
    projeto: Optional[ProjetoOut] = None # <--- Resposta populada
    tarefa: Optional[TarefaOut] = None  # <--- Resposta populada

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True