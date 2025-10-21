# ingest.py
import io
import re
from typing import List, Optional, Tuple, Dict, Any, Iterable
from datetime import date
import pandas as pd
import requests
from bs4 import BeautifulSoup
from docx import Document  # para .docx
from beanie import PydanticObjectId

from models import (
    Funcionario, Projeto, Tarefa,
    TarefaCreate, ProjetoCreate, PrioridadeTarefa, StatusTarefa
)

# ---------------------------
# Utilidades de detecção
# ---------------------------
def _is_tasks_df(df: pd.DataFrame) -> bool:
    cols = set(c.lower() for c in df.columns)
    required = {"nome da tarefa", "prazo", "nome do projeto", "email responsável"}
    return required.issubset(cols)

def _is_projects_df(df: pd.DataFrame) -> bool:
    cols = set(c.lower() for c in df.columns)
    required = {"nome do projeto", "responsável (email)", "prazo", "situação"}
    return required.issubset(cols)

def _is_people_df(df: pd.DataFrame) -> bool:
    cols = set(c.lower() for c in df.columns)
    required = {"nome", "sobrenome", "email"}
    return required.issubset(cols)

def _normalize_bool(v: Any) -> bool:
    if isinstance(v, bool): return v
    if v is None: return False
    s = str(v).strip().lower()
    return s in {"true","1","sim","yes","verdadeiro"}

# ---------------------------
# Roteamento DataFrame -> DB
# ---------------------------
async def _ingest_tasks_df(df: pd.DataFrame) -> Dict[str, Any]:
    created, errors = 0, []
    for i, row in df.iterrows():
        try:
            projeto = await Projeto.find_one(Projeto.nome == row["Nome do Projeto"])
            if not projeto:
                errors.append(f"Linha {i+2}: Projeto '{row['Nome do Projeto']}' não encontrado.")
                continue
            responsavel = await Funcionario.find_one(Funcionario.email == row["Email Responsável"])
            if not responsavel:
                errors.append(f"Linha {i+2}: Responsável '{row['Email Responsável']}' não encontrado.")
                continue

            prioridade = str(row.get("Prioridade","média")).lower()
            if prioridade not in {"baixa","média","media","alta"}:
                prioridade = "média"
            if prioridade == "media": prioridade = "média"

            status = str(row.get("Status","não iniciada")).lower()
            if status not in {"em andamento","congelada","não iniciada","nao iniciada","concluída","concluida"}:
                status = "não iniciada"
            if status == "nao iniciada": status = "não iniciada"
            if status == "concluida": status = "concluída"

            concluido = _normalize_bool(row.get("Concluído", False))

            data = TarefaCreate(
                nome=row["Nome da Tarefa"],
                projeto_id=str(projeto.id),
                responsavel_id=str(responsavel.id),
                descricao=row.get("Descrição"),
                prioridade=PrioridadeTarefa(prioridade),
                status=StatusTarefa(status),
                prazo=pd.to_datetime(row["Prazo"]).date(),
                numero=row.get("Número"),
                classificacao=row.get("Classificação"),
                fase=row.get("Fase"),
                condicao=row.get("Condição"),
                documento_referencia=row.get("Documento de Referência"),
                concluido=concluido
            )
            tarefa = Tarefa(**data.dict(exclude={"projeto_id","responsavel_id"}),
                            projeto=projeto, responsavel=responsavel)
            await tarefa.insert()
            created += 1
        except Exception as e:
            errors.append(f"Linha {i+2}: {e}")
    return {"type":"tarefas", "criados": created, "erros": errors}

async def _ingest_projects_df(df: pd.DataFrame) -> Dict[str, Any]:
    created, errors = 0, []
    for i, row in df.iterrows():
        try:
            resp = await Funcionario.find_one(Funcionario.email == row["Responsável (email)"])
            if not resp:
                errors.append(f"Linha {i+2}: Responsável '{row['Responsável (email)']}' não encontrado.")
                continue
            data = ProjetoCreate(
                nome=row["Nome do Projeto"],
                responsavel_id=str(resp.id),
                descricao=row.get("Descrição"),
                categoria=row.get("Categoria"),
                situacao=row["Situação"],
                prazo=pd.to_datetime(row["Prazo"]).date()
            )
            projeto = Projeto(**data.dict(exclude={"responsavel_id"}), responsavel=resp)
            await projeto.insert()
            created += 1
        except Exception as e:
            errors.append(f"Linha {i+2}: {e}")
    return {"type":"projetos", "criados": created, "erros": errors}

async def _ingest_people_df(df: pd.DataFrame) -> Dict[str, Any]:
    created, errors, skipped_dupes = 0, [], 0
    for i, row in df.iterrows():
        try:
            email = row["Email"]
            exists = await Funcionario.find_one(Funcionario.email == email)
            if exists:
                skipped_dupes += 1
                continue
            fun = Funcionario(
                nome=row["Nome"],
                sobrenome=row["Sobrenome"],
                email=email,
                senha="hash-placeholder",  # substitua se quiser fluxo de login por ingestão
                cargo=row.get("Cargo"),
                departamento=row.get("Departamento"),
                fotoPerfil=row.get("Foto")
            )
            await fun.insert()
            created += 1
        except Exception as e:
            errors.append(f"Linha {i+2}: {e}")
    return {"type":"funcionarios", "criados": created, "ignorados_existentes": skipped_dupes, "erros": errors}

async def _route_df(df: pd.DataFrame) -> Dict[str, Any]:
    df.columns = [c.strip() for c in df.columns]
    if _is_tasks_df(df):
        return await _ingest_tasks_df(df)
    if _is_projects_df(df):
        return await _ingest_projects_df(df)
    if _is_people_df(df):
        return await _ingest_people_df(df)
    return {"type":"desconhecido","criados":0,"erros":["Layout de colunas não reconhecido."]}

# ---------------------------
# Entrada por ARQUIVO
# ---------------------------
async def ingest_file(filename: str, contents: bytes) -> Dict[str, Any]:
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
            return await _route_df(df)
        elif filename.lower().endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(contents))
            return await _route_df(df)
        elif filename.lower().endswith(".docx"):
            links = extract_links_from_docx(io.BytesIO(contents))
            return await follow_links_and_ingest(links)
        else:
            return {"type":"desconhecido","criados":0,"erros":[f"Formato não suportado: {filename}"]}
    except Exception as e:
        return {"type":"erro","criados":0,"erros":[str(e)]}

# ---------------------------
# Entrada por LINK de DOC
# ---------------------------
def fetch_text(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def extract_links_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        links.append(a["href"])
    return links

def extract_links_from_docx(filelike) -> List[str]:
    doc = Document(filelike)
    links = []
    # varredura por relationships (método mais robusto no python-docx)
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype and rel.target_ref:
            links.append(rel.target_ref)
    return list(dict.fromkeys(links))

def _guess_export_url(u: str, sheet_index: Optional[int]) -> Tuple[str, Optional[str]]:
    """
    Produz uma URL exportável quando possível.
    """
    if "docs.google.com/spreadsheets" in u:
        gid_match = re.search(r"[?&]gid=(\d+)", u)
        gid = gid_match.group(1) if gid_match else None
        base = re.sub(r"/edit.*","",u)
        if gid:
            return f"{base}/export?format=csv&gid={gid}", "csv"
        else:
            return f"{base}/export?format=csv", "csv"
    if u.lower().endswith((".xlsx",".xls")):
        return u, "xlsx"
    if u.lower().endswith(".csv"):
        return u, "csv"
    return u, None

def _read_tabular_from_url(u: str, limit_rows: Optional[int]) -> Optional[pd.DataFrame]:
    url_export, ext = _guess_export_url(u, sheet_index=None)
    r = requests.get(url_export, timeout=60)
    r.raise_for_status()
    content = r.content
    if ext == "csv":
        df = pd.read_csv(io.BytesIO(content))
    elif ext == "xlsx":
        df = pd.read_excel(io.BytesIO(content))
    else:
        # tenta extrair primeira tabela HTML
        try:
            df_list = pd.read_html(io.BytesIO(content))
        except Exception:
            try:
                df_list = pd.read_html(content.decode("utf-8", errors="ignore"))
            except Exception:
                df_list = []
        if not df_list:
            return None
        df = df_list[0]
    if limit_rows is not None:
        df = df.head(limit_rows)
    return df

async def follow_links_and_ingest(links: List[str], pick_index: Optional[int]=None, limit_rows: Optional[int]=None) -> Dict[str, Any]:
    """
    - Se pick_index for None: percorre todos os links e tenta ingerir.
    - Se pick_index >=1: pega só o N-ésimo link (ex.: 'terceira planilha' => pick_index=3).
    """
    picked = [links[pick_index-1]] if pick_index and 1 <= pick_index <= len(links) else links
    summary = []
    for u in picked:
        try:
            df = _read_tabular_from_url(u, limit_rows)
            if df is None:
                summary.append({"link": u, "resultado": {"type":"ignorado","criados":0,"erros":["Não foi possível ler tabela."]}})
                continue
            res = await _route_df(df)
            summary.append({"link": u, "resultado": res})
        except Exception as e:
            summary.append({"link": u, "resultado": {"type":"erro","criados":0,"erros":[str(e)]}})
    return {"links_processados": len(picked), "itens": summary}

async def ingest_from_doc_link(doc_url: str, pick_index: Optional[int]=None, limit_rows: Optional[int]=None) -> Dict[str, Any]:
    """
    Baixa o DOC/HTML (Google Docs ou Word publicado na web), extrai hiperlinks e segue.
    """
    html = fetch_text(doc_url)
    links = extract_links_from_html(html)
    return await follow_links_and_ingest(links, pick_index=pick_index, limit_rows=limit_rows)

# --- NOVO: ingestão de múltiplos DOCs com hyperlinks ---
async def ingest_from_doc_links(
    doc_urls: Iterable[str],
    pick_index: Optional[int] = None,
    limit_rows: Optional[int] = None
) -> Dict[str, Any]:
    """
    Processa vários documentos (Google Docs/Word publicado na web), extrai hyperlinks
    de cada um e segue para ingestão. Retorna um resumo por documento.
    """
    results = []
    count = 0
    for url in doc_urls:
        count += 1
        try:
            res = await ingest_from_doc_link(url, pick_index=pick_index, limit_rows=limit_rows)
            results.append({"doc_url": url, "ok": True, "resultado": res})
        except Exception as e:
            results.append({"doc_url": url, "ok": False, "erro": str(e)})
    return {
        "documentos_processados": count,
        "resultados": results
    }

# --- NOVO: ingestão direta de planilha/CSV por URL ---
async def ingest_from_sheet_or_csv_url(url: str, limit_rows: Optional[int] = None) -> Dict[str, Any]:
    """
    Lê uma tabela diretamente de uma URL (Google Sheets, CSV, XLSX, HTML com tabela)
    e roteia para criação de Projetos/Tarefas/Pessoas conforme o layout detectado.
    """
    try:
        df = _read_tabular_from_url(url, limit_rows)
        if df is None:
            return {"type": "ignorado", "criados": 0, "erros": ["Não foi possível ler tabela."]}
        return await _route_df(df)
    except Exception as e:
        return {"type": "erro", "criados": 0, "erros": [str(e)]}
