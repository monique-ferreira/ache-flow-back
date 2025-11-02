# Ache Flow Back

API FastAPI para gestão de projetos/tarefas com autenticação, IA (Vertex AI) e ingestão de dados.

## Requisitos
- Python 3.11+
- MongoDB em execução (local ou remoto)
- (Opcional) Conta GCP para usar Vertex AI

## Configuração
1. Crie um arquivo `.env` na raiz (use o `.env.example` como base):
```
MONGO_URI=mongodb://localhost:27017/ache_flow
SECRET_KEY=troque-esta-chave
# IA (opcional)
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=us-central1
# Se for usar credenciais locais (opcional)
# GOOGLE_APPLICATION_CREDENTIALS=C:\\caminho\\para\\service-account.json
```

2. Instale as dependências:
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3. Execute a API (desenvolvimento):
```powershell
uvicorn main:app --reload
```

4. Crie um usuário e faça login:
- Criar usuário (POST /funcionarios):
```json
{
  "nome": "Ana",
  "sobrenome": "Luiza",
  "email": "ana@example.com",
  "senha": "minha_senha",
  "cargo": "Gestora",
  "departamento": "PMO"
}
```
- Login (POST /token) como form-urlencoded:
```powershell
$body = @{ username = "ana@example.com"; password = "minha_senha" }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/token -Body $body -ContentType 'application/x-www-form-urlencoded'
```
Resposta esperada:
```json
{"access_token":"...","token_type":"bearer","id":"..."}
```

## Variáveis de ambiente
- `MONGO_URI` (obrigatório): inclua o nome do database na URI, ex: `mongodb://localhost:27017/ache_flow`.
- `SECRET_KEY` (obrigatório): chave para assinar JWT.
- `GOOGLE_CLOUD_PROJECT` (opcional): ativa IA Gemini no Vertex AI se definido.
- `GOOGLE_CLOUD_LOCATION` (opcional, default `us-central1`).
- `GOOGLE_APPLICATION_CREDENTIALS` (opcional): caminho do JSON de service account.

Sem `GOOGLE_CLOUD_PROJECT`, a IA fica desativada e retorna uma mensagem padrão, mas a API funciona normalmente.

## Docker (opcional)
Para usar Docker, certifique-se que `requirements.txt` está atualizado e exporte as variáveis de ambiente necessárias.
```powershell
# build
docker build -t ache-flow-back .
# run (expondo porta 8000)
docker run --rm -p 8000:8000 --env-file .env ache-flow-back
```

## Endpoints principais
- `POST /funcionarios` — cria usuário (senha é armazenada com hash)
- `POST /token` — login OAuth2 (retorna access_token e id)
- CRUD de Projetos/Tarefas/Calendário
- `POST /ai/chat` — IA (requer token Bearer)
- `POST /ingest/arquivo` — ingestão CSV/XLSX/DOCX
- `POST /ingest/link` e `/ingest/links` — ingestão por documentos com links

## Dicas
- Use o Swagger: http://127.0.0.1:8000/docs
- Se receber 422 no `/token`, verifique se está enviando `application/x-www-form-urlencoded` (não JSON).
- Se receber erro de DB na inicialização, revise `MONGO_URI` e se o MongoDB está rodando.
