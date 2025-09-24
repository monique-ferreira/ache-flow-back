# models.py
from datetime import datetime, date
from typing import Optional, List
from beanie import Document, Link
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

    class Settings:
        name = "tarefas"

# --- CLASSE QUE ESTAVA FALTANDO ---
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

# --- MODEL QUE ESTAVA FALTANDO ---
class CalendarioCreate(BaseModel):
    tipoEvento: str
    data_hora_evento: datetime
    projeto_id: Optional[str] = None
    tarefa_id: Optional[str] = None

# --- Models para Autenticação ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None