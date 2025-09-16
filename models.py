from datetime import datetime, date, time
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
    prazo: date
    projeto: Link[Projeto]
    responsavel: Link[Funcionario]

    class Settings:
        name = "tarefas"

class Calendario(Document):
    tipoEvento: str
    data_hora_evento: datetime
    projeto: Optional[Link[Projeto]] = None
    tarefa: Optional[Link[Tarefa]] = None

    class Settings:
        name = "calendario"

class FuncionarioCreate(BaseModel):
    nome: str
    sobrenome: str
    email: EmailStr
    senha: str
    cargo: Optional[str] = None
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

class CalendarioCreate(BaseModel):
    tipoEvento: str
    data_hora_evento: datetime