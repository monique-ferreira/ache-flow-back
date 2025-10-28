# models.py
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from beanie import Document, Link
from beanie.odm.fields import PydanticObjectId
from pydantic import BaseModel, Field, EmailStr


# =========================
# ENUNS
# =========================
class StatusTarefa(str, Enum):
    NAO_INICIADA = "não iniciada"
    EM_ANDAMENTO = "em andamento"
    CONGELADA = "congelada"
    CONCLUIDA = "concluída"


class PrioridadeTarefa(str, Enum):
    BAIXA = "baixa"
    MEDIA = "média"
    ALTA = "alta"


class CondicaoTarefa(str, Enum):
    SEMPRE = "sempre"
    A = "A"
    B = "B"
    C = "C"


# =========================
# DOCUMENTOS
# =========================
class Funcionario(Document):
    nome: str
    sobrenome: Optional[str] = None
    email: EmailStr
    cargo: Optional[str] = None

    class Settings:
        name = "funcionarios"


class Projeto(Document):
    nome: str
    descricao: Optional[str] = None
    # categoria: Optional[str] = None   # REMOVIDO
    situacao: str = "não iniciado"      # será recalculada pela média de tarefas
    prazo: Optional[date] = None
    responsavel: Link[Funcionario]

    class Settings:
        name = "projetos"


class Tarefa(Document):
    # básicos
    nome: str
    projeto: Link[Projeto]
    responsavel: Link[Funcionario]

    # novos/renomeados
    como_fazer: Optional[str] = None             # antes: descricao
    prioridade: Optional[PrioridadeTarefa] = None  # opcional (só se vier do arquivo)
    condicao: CondicaoTarefa = CondicaoTarefa.SEMPRE
    categoria: Optional[str] = None              # antes: classificacao
    porcentagem: int = 0                         # antes: concluido (bool)

    # datas
    data_inicio: Optional[date] = None           # novo, editável
    data_fim: date                                # novo, editável (substitui “prazo”)

    # audit/status
    status: StatusTarefa = StatusTarefa.NAO_INICIADA
    dataCriacao: datetime = Field(default_factory=datetime.utcnow)
    dataConclusao: Optional[datetime] = None
    documento_referencia: Optional[str] = None
    fase: Optional[str] = None

    # ---- Compat: manter "prazo" como alias de data_fim ----
    @property
    def prazo(self) -> date:
        return self.data_fim

    @prazo.setter
    def prazo(self, v: date):
        self.data_fim = v

    class Settings:
        name = "tarefas"


class Calendario(Document):
    tipoEvento: str
    data_hora_evento: datetime
    projeto: Optional[Link[Projeto]] = None
    tarefa: Optional[Link[Tarefa]] = None

    class Settings:
        name = "calendario"


# =========================
# SCHEMAS (API)
# =========================
class TarefaBase(BaseModel):
    nome: str
    projeto_id: PydanticObjectId
    responsavel_id: PydanticObjectId
    como_fazer: Optional[str] = None
    prioridade: Optional[PrioridadeTarefa] = None
    condicao: Optional[CondicaoTarefa] = CondicaoTarefa.SEMPRE
    categoria: Optional[str] = None
    porcentagem: Optional[int] = 0
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None  # preferencial
    # compat
    prazo: Optional[date] = None     # alias de data_fim
    status: Optional[StatusTarefa] = StatusTarefa.NAO_INICIADA
    documento_referencia: Optional[str] = None
    fase: Optional[str] = None


class TarefaCreate(TarefaBase):
    pass


class TarefaUpdate(BaseModel):
    nome: Optional[str] = None
    como_fazer: Optional[str] = None
    prioridade: Optional[PrioridadeTarefa] = None
    condicao: Optional[CondicaoTarefa] = None
    categoria: Optional[str] = None
    porcentagem: Optional[int] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    prazo: Optional[date] = None
    status: Optional[StatusTarefa] = None
    documento_referencia: Optional[str] = None
    fase: Optional[str] = None
    projeto_id: Optional[PydanticObjectId] = None
    responsavel_id: Optional[PydanticObjectId] = None


class ProjetoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    prazo: Optional[date] = None
    responsavel_id: PydanticObjectId


class ProjetoUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    prazo: Optional[date] = None
    responsavel_id: Optional[PydanticObjectId] = None
