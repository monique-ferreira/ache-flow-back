# models.py
from datetime import datetime, date
from typing import Optional, List
from beanie import Document, Link
from pydantic import BaseModel, EmailStr

# --- Modelos que representam os documentos no MongoDB ---
# Usamos a classe 'Document' do Beanie

class Premissa(Document):
    """
    Representa a entidade 'Premissas' do diagrama.
    Contém as informações iniciais de autorização ou contexto.
    """
    nome: str
    sobrenome: str
    email: EmailStr
    setor: Optional[str] = None
    cargo: Optional[str] = None
    dataAuth: datetime = datetime.now()
    dataValidade: datetime

    class Settings:
        # Nome da coleção no MongoDB
        name = "premissas"

class Pessoa(Document):
    """
    Representa a entidade 'Pessoas'.
    O relacionamento 'criarPessoa(is)' é modelado aqui com uma referência (Link) à Premissa que a originou.
    Um Link no Beanie é uma referência a outro documento em outra coleção.
    """
    # Link para o documento Premissa que 'criou' esta Pessoa.
    # Isso representa a conexão '1..*' vinda de Premissas.
    premissa_original: Link[Premissa]
    
    nome: str
    sobrenome: str
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    pais: Optional[str] = None
    nasc: Optional[date] = None
    idDispositivo: Optional[str] = None
    
    # Para modelar o relacionamento 'vincular' com Eventos (que pode ser Muitos-para-Muitos),
    # armazenamos uma lista de referências (Links) para os eventos associados.
    eventos_vinculados: List[Link["Evento"]] = []

    class Settings:
        name = "pessoas"

class Evento(Document):
    """
    Representa a entidade 'Eventos'.
    """
    nome: str
    descricao: str
    periodoInicio: datetime
    periodoFim: datetime
    dataCriacao: datetime = datetime.now()
    pais: Optional[str] = None
    
    # Assim como em Pessoa, armazenamos uma lista de pessoas vinculadas a este evento.
    pessoas_vinculadas: List[Link[Pessoa]] = []

    class Settings:
        name = "eventos"

class Calculadora(Document):
    """
    Representa a entidade 'Calculadora', que parece ser um agendamento ou uma instância
    específica de um evento.
    O relacionamento '1..1 agendar' é modelado com uma referência única ao Evento.
    """
    # Link para o Evento que está sendo agendado
    evento_agendado: Link[Evento]
    
    data: date
    hora: str # Pode ser melhor usar datetime, mas mantendo como no diagrama
    nome: str # Nome específico para o agendamento
    relevancia: int
    duracao: str
    alerta: bool = False
    periodicidade: Optional[str] = None

    class Settings:
        name = "agendamentos" # Renomeei a coleção para clareza

# --- Modelos Pydantic para entrada de dados (Request Bodies) ---
# Usamos BaseModel do Pydantic para definir o formato do JSON que a API espera receber.
# Isso evita que o cliente envie o ID ou outros campos gerenciados pelo banco.

class PremissaCreate(BaseModel):
    nome: str
    sobrenome: str
    email: EmailStr
    setor: Optional[str] = None
    cargo: Optional[str] = None
    dataValidade: datetime

class PessoaCreate(BaseModel):
    nome: str
    sobrenome: str
    # A API vai exigir que o ID da premissa seja fornecido ao criar uma pessoa
    premissa_id: str
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    pais: Optional[str] = None
    nasc: Optional[date] = None
    idDispositivo: Optional[str] = None

class EventoCreate(BaseModel):
    nome: str
    descricao: str
    periodoInicio: datetime
    periodoFim: datetime
    pais: Optional[str] = None

class CalculadoraCreate(BaseModel):
    # A API vai exigir o ID do evento a ser agendado
    evento_id: str
    data: date
    hora: str
    nome: str
    relevancia: int
    duracao: str
    alerta: bool = False
    periodicidade: Optional[str] = None