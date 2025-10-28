# command_router.py
from datetime import date, timedelta, datetime
from typing import Optional, Dict, Any
import re
import dateparser

from beanie import PydanticObjectId
from models import Projeto, Tarefa, Funcionario, StatusTarefa, PrioridadeTarefa


# =========================
# Helpers
# =========================
def _parse_relative_date(txt: str) -> Optional[date]:
    """
    Entende 'amanhã', 'daqui 2 dias', '15/11/2025', etc.
    """
    dt = dateparser.parse(
        txt,
        settings={"PREFER_DATES_FROM": "future", "DATE_ORDER": "DMY", "TIMEZONE": "America/Sao_Paulo"},
        languages=["pt", "pt-BR", "en"],
    )
    if not dt:
        return None
    return dt.date()


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


# =========================
# Comandos suportados
# =========================
async def handle_command(texto: str) -> Optional[Dict[str, Any]]:
    """
    Retorna {"executado": True, "mensagem": "..."} se algum comando foi reconhecido; senão None.
    """

    # 1) Mudar prazo/data_fim do PROJETO
    m = re.search(r"muda[r]? o prazo do projeto (.+?) para (.+)$", texto, flags=re.IGNORECASE)
    if m:
        nome_proj, prazo_txt = m.group(1).strip(), m.group(2).strip()
        proj = await Projeto.find_one(Projeto.nome == nome_proj)
        if not proj:
            return {"executado": False, "mensagem": f"Projeto '{nome_proj}' não encontrado."}
        nova_data = _parse_relative_date(prazo_txt)
        if not nova_data:
            return {"executado": False, "mensagem": f"Não entendi a data '{prazo_txt}'."}
        proj.prazo = nova_data
        await proj.save()
        return {"executado": True, "mensagem": f"Prazo do projeto '{proj.nome}' atualizado para {proj.prazo}."}

    # 2) Mudar prazo/data_fim da TAREFA
    m = re.search(r"muda[r]? o prazo (?:da|de) tarefa (.+?) para (.+)$", texto, flags=re.IGNORECASE)
    if m:
        nome_tarefa, prazo_txt = m.group(1).strip(), m.group(2).strip()
        tarefa = await Tarefa.find_one(Tarefa.nome == nome_tarefa, fetch_links=True)
        if not tarefa:
            return {"executado": False, "mensagem": f"Tarefa '{nome_tarefa}' não encontrada."}
        nova_data = _parse_relative_date(prazo_txt)
        if not nova_data:
            return {"executado": False, "mensagem": f"Não entendi a data '{prazo_txt}'."}
        tarefa.data_fim = nova_data
        await tarefa.save()
        await _recalcular_situacao_projeto(tarefa.projeto.id)
        return {"executado": True, "mensagem": f"Prazo da tarefa '{tarefa.nome}' atualizado para {tarefa.data_fim}."}

    # 3) Ajustar porcentagem da TAREFA (ex: "marque a tarefa X como 80%")
    m = re.search(r"(?:marc[ae]|atualiza[re]?) a tarefa (.+?) como (\d{1,3})\s?%", texto, flags=re.IGNORECASE)
    if m:
        nome_tarefa, pct = m.group(1).strip(), int(m.group(2))
        pct = max(0, min(100, pct))
        tarefa = await Tarefa.find_one(Tarefa.nome == nome_tarefa, fetch_links=True)
        if not tarefa:
            return {"executado": False, "mensagem": f"Tarefa '{nome_tarefa}' não encontrada."}
        tarefa.porcentagem = pct
        tarefa.status = (
            StatusTarefa.CONCLUIDA if pct == 100
            else (StatusTarefa.NAO_INICIADA if pct == 0 else StatusTarefa.EM_ANDAMENTO)
        )
        tarefa.dataConclusao = datetime.utcnow() if tarefa.status == StatusTarefa.CONCLUIDA else None
        await tarefa.save()
        await _recalcular_situacao_projeto(tarefa.projeto.id)
        return {"executado": True, "mensagem": f"Porcentagem da tarefa '{tarefa.nome}' atualizada para {pct}%."}

    # 4) Alterar prioridade da TAREFA
    m = re.search(r"(?:prioridade|define a prioridade) da tarefa (.+?) para (baixa|m[eé]dia|alta)", texto, flags=re.IGNORECASE)
    if m:
        nome_tarefa, prio = m.group(1).strip(), m.group(2).lower()
        if prio == "media":
            prio = "média"
        tarefa = await Tarefa.find_one(Tarefa.nome == nome_tarefa, fetch_links=True)
        if not tarefa:
            return {"executado": False, "mensagem": f"Tarefa '{nome_tarefa}' não encontrada."}
        tarefa.prioridade = PrioridadeTarefa(prio)
        await tarefa.save()
        return {"executado": True, "mensagem": f"Prioridade da tarefa '{tarefa.nome}' definida como {prio}."}

    return None
