# command_router.py
from datetime import date, timedelta
from typing import Optional, Dict, Any
import re
import dateparser

from beanie import PydanticObjectId
from models import Projeto, Tarefa, Funcionario, StatusTarefa, PrioridadeTarefa

# ---------------------------
# Helpers
# ---------------------------
def _parse_relative_date(txt: str):
    """
    Entende coisas como 'daqui dois dias', 'amanhã', 'em 3 semanas', '15/10/2025'.
    """
    dt = dateparser.parse(
        txt,
        languages=["pt","pt-BR"],
        settings={"PREFER_DATES_FROM":"future","RELATIVE_BASE": None}
    )
    return dt.date() if dt else None

async def _find_project_by_name(nome: str) -> Optional[Projeto]:
    return await Projeto.find_one(Projeto.nome.regex(nome, options="i"))

async def _find_task_by_name(nome: str) -> Optional[Tarefa]:
    return await Tarefa.find_one(Tarefa.nome.regex(nome, options="i"))

async def _find_user_by_name_or_email(token: str) -> Optional[Funcionario]:
    u = await Funcionario.find_one(Funcionario.email == token)
    if u: return u
    parts = token.strip().split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        cand = await Funcionario.find_one(
            Funcionario.nome.regex(first, "i"),
            Funcionario.sobrenome.regex(last, "i")
        )
        if cand: return cand
    return await Funcionario.find_one(Funcionario.nome.regex(token, "i"))

# ---------------------------
# Comandos suportados
# ---------------------------
async def handle_command(texto: str) -> Optional[Dict[str, Any]]:
    """
    Retorna um dict com {"executado": True, "mensagem": "..."} se algum comando foi reconhecido.
    Caso contrário, retorna None.
    """

    # 1) Mudar prazo de PROJETO
    # "muda o prazo do projeto X para daqui dois dias"
    m = re.search(r"muda[r]? o prazo do projeto (.+?) para (.+)$", texto, flags=re.IGNORECASE)
    if m:
        nome_proj, prazo_txt = m.group(1).strip(), m.group(2).strip()
        proj = await _find_project_by_name(nome_proj)
        if not proj:
            return {"executado": False, "mensagem": f"Projeto '{nome_proj}' não encontrado."}
        novo_prazo = _parse_relative_date(prazo_txt)
        if not novo_prazo:
            return {"executado": False, "mensagem": f"Não entendi a data '{prazo_txt}'."}
        proj.prazo = novo_prazo
        await proj.save()
        return {"executado": True, "mensagem": f"Prazo do projeto '{proj.nome}' atualizado para {novo_prazo.strftime('%d/%m/%Y')}."}

    # 2) Mudar prazo de TAREFA
    # "muda o prazo da tarefa ABC para amanhã"
    m = re.search(r"muda[r]? o prazo da tarefa (.+?) para (.+)$", texto, flags=re.IGNORECASE)
    if m:
        nome_t, prazo_txt = m.group(1).strip(), m.group(2).strip()
        t = await _find_task_by_name(nome_t)
        if not t: return {"executado": False, "mensagem": f"Tarefa '{nome_t}' não encontrada."}
        novo_prazo = _parse_relative_date(prazo_txt)
        if not novo_prazo:
            return {"executado": False, "mensagem": f"Não entendi a data '{prazo_txt}'."}
        t.prazo = novo_prazo
        await t.save()
        return {"executado": True, "mensagem": f"Prazo da tarefa '{t.nome}' atualizado para {novo_prazo.strftime('%d/%m/%Y')}."}

    # 3) Adicionar tarefa em um PROJETO e atribuir responsável
    # "adiciona a tarefa 'desenvolver frontend' no projeto Y, a ana vai ser a responsável"
    m = re.search(r"adiciona[r]? a tarefa ['\"]?(.+?)['\"]? no projeto (.+?), (.+?) vai ser a responsável", texto, flags=re.IGNORECASE)
    if m:
        nome_tarefa, nome_proj, nome_resp = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        proj = await _find_project_by_name(nome_proj)
        if not proj: return {"executado": False, "mensagem": f"Projeto '{nome_proj}' não encontrado."}
        user = await _find_user_by_name_or_email(nome_resp)
        if not user: return {"executado": False, "mensagem": f"Responsável '{nome_resp}' não encontrado."}
        novo = Tarefa(
            nome=nome_tarefa,
            projeto=proj,
            responsavel=user,
            prazo=date.today() + timedelta(days=7),
            status=StatusTarefa.NAO_INICIADA
        )
        await novo.insert()
        return {"executado": True, "mensagem": f"Tarefa '{nome_tarefa}' criada no projeto '{proj.nome}' e atribuída a {user.nome} {user.sobrenome}."}

    # 4) Alterar responsável da tarefa
    # "atribui a tarefa X para o joão" | "muda responsável da tarefa X para maria"
    m = re.search(r"(atribui|muda) (?:a )?tarefa (.+?) para (.+)$", texto, flags=re.IGNORECASE)
    if m:
        nome_t, nome_resp = m.group(2).strip(), m.group(3).strip()
        t = await _find_task_by_name(nome_t)
        if not t: return {"executado": False, "mensagem": f"Tarefa '{nome_t}' não encontrada."}
        user = await _find_user_by_name_or_email(nome_resp)
        if not user: return {"executado": False, "mensagem": f"Responsável '{nome_resp}' não encontrado."}
        t.responsavel = user
        await t.save()
        return {"executado": True, "mensagem": f"Responsável da tarefa '{t.nome}' atualizado para {user.nome} {user.sobrenome}."}

    # 5) Alterar status da tarefa
    # "marca a tarefa X como concluída/em andamento/congelada/não iniciada"
    m = re.search(r"marca[r]? a tarefa (.+?) como (concluída|concluida|em andamento|congelada|não iniciada|nao iniciada)$", texto, flags=re.IGNORECASE)
    if m:
        nome_t, status_txt = m.group(1).strip(), m.group(2).lower()
        if status_txt == "concluida": status_txt = "concluída"
        if status_txt == "nao iniciada": status_txt = "não iniciada"
        t = await _find_task_by_name(nome_t)
        if not t: return {"executado": False, "mensagem": f"Tarefa '{nome_t}' não encontrada."}
        t.status = StatusTarefa(status_txt)
        await t.save()
        return {"executado": True, "mensagem": f"Tarefa '{t.nome}' marcada como {status_txt}."}

    # Nenhum padrão encontrado
    return None
