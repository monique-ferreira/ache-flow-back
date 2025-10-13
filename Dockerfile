# Dockerfile

# 1. Usar uma imagem base oficial do Python
FROM python:3.11-slim-bullseye

# Atualizar pacotes do sistema para corrigir vulnerabilidades e remover cache
RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Definir a pasta de trabalho dentro do contêiner
WORKDIR /app

# 3. Copiar o arquivo de dependências e instalá-las
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar o resto do código do seu projeto para dentro do contêiner
COPY . .

# 5. Expor a porta 8000
# (O Render irá mapear isso para a porta 443 (HTTPS) automaticamente)
EXPOSE 8000

# 6. Comando para iniciar a aplicação quando o contêiner for executado
# Usamos o Gunicorn para gerenciar 4 workers Uvicorn em produção.
# O host 0.0.0.0 é necessário para que a aplicação seja acessível de fora do contêiner.
CMD gunicorn -w 2 --timeout 120 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT