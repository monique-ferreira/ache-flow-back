# main.py
from fastapi import FastAPI, HTTPException, Body
from typing import List
from beanie import PydanticObjectId

# Importa a instância do banco de dados e os modelos
from database import db
from models import Premissa, Pessoa, Evento, Calculadora
from models import PremissaCreate, PessoaCreate, EventoCreate, CalculadoraCreate

# Cria a aplicação FastAPI
app = FastAPI(
    title="API de Ações e Eventos",
    description="Backend baseado no diagrama UML para gerenciar premissas, pessoas, eventos e agendamentos.",
    version="1.0.0"
)

# --- Eventos de Ciclo de Vida da Aplicação ---

@app.on_event("startup")
async def start_database():
    """
    Esta função é executada quando a aplicação inicia.
    Ela chama nosso inicializador de banco de dados.
    """
    await db.initialize()

# --- Endpoints da API ---

@app.post("/premissas", response_model=Premissa, tags=["Premissas"])
async def criar_premissa(premissa_data: PremissaCreate = Body(...)):
    """
    Endpoint para 'criarFremi(as)'.
    Recebe os dados de uma nova premissa e a insere no banco de dados.
    """
    premissa = Premissa(**premissa_data.dict())
    await premissa.insert()
    return premissa

@app.post("/pessoas", response_model=Pessoa, tags=["Pessoas"])
async def cadastrar_pessoa(pessoa_data: PessoaCreate = Body(...)):
    """
    Endpoint para 'cadastrarPessoa(is)'.
    Recebe os dados de uma pessoa e o ID da premissa que a originou.
    Cria a pessoa e estabelece o vínculo com a premissa.
    """
    # Verifica se a premissa informada existe no banco de dados
    premissa_id = PydanticObjectId(pessoa_data.premissa_id)
    premissa_origem = await Premissa.get(premissa_id)
    if not premissa_origem:
        raise HTTPException(status_code=404, detail="Premissa não encontrada.")
    
    # Cria a instância da pessoa, já vinculando a premissa encontrada
    # Usamos o .dict() para converter o modelo Pydantic em um dicionário
    pessoa = Pessoa(
        **pessoa_data.dict(exclude={"premissa_id"}), # Exclui o premissa_id para não duplicar
        premissa_original=premissa_origem 
    )
    await pessoa.insert()
    return pessoa

@app.post("/eventos", response_model=Evento, tags=["Eventos"])
async def criar_evento(evento_data: EventoCreate = Body(...)):
    """
    Endpoint para 'criarEvento(is)'.
    Cria um novo evento no sistema.
    """
    evento = Evento(**evento_data.dict())
    await evento.insert()
    return evento

@app.post("/eventos/{evento_id}/vincular/{pessoa_id}", response_model=Evento, tags=["Eventos"])
async def vincular_pessoa_ao_evento(evento_id: PydanticObjectId, pessoa_id: PydanticObjectId):
    """
    Endpoint para 'vincularEvento(is)'.
    Estabelece uma relação Muitos-para-Muitos entre uma Pessoa e um Evento.
    """
    evento = await Evento.get(evento_id)
    pessoa = await Pessoa.get(pessoa_id)

    if not evento or not pessoa:
        raise HTTPException(status_code=404, detail="Evento ou Pessoa não encontrado(a).")
    
    # Adiciona a referência da pessoa ao evento e vice-versa para manter a consistência
    # O Beanie é inteligente e só adicionará se o link já não existir
    evento.pessoas_vinculadas.append(pessoa)
    pessoa.eventos_vinculados.append(evento)

    # Salva as alterações nos dois documentos
    await evento.save()
    await pessoa.save()

    return evento

@app.post("/agendamentos", response_model=Calculadora, tags=["Agendamentos"])
async def agendar_evento(agendamento_data: CalculadoraCreate = Body(...)):
    """
    Endpoint para 'agendarEvento()'.
    Cria um agendamento (Calculadora) baseado em um evento existente.
    """
    evento_id = PydanticObjectId(agendamento_data.evento_id)
    evento_original = await Evento.get(evento_id)
    if not evento_original:
        raise HTTPException(status_code=404, detail="Evento a ser agendado não encontrado.")
    
    agendamento = Calculadora(
        **agendamento_data.dict(exclude={"evento_id"}),
        evento_agendado=evento_original
    )
    await agendamento.insert()
    return agendamento

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Bem-vindo à API! Acesse /docs para ver a documentação interativa."}