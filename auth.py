# auth.py
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

from models import Funcionario

load_dotenv()

# --- Configurações de Segurança ---

# Chave secreta para assinar os tokens JWT. EM PRODUÇÃO, USE UMA CHAVE COMPLEXA E MANTENHA-A SEGURA!
SECRET_KEY = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-dificil-de-adivinhar-012345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # O token expira em 30 minutos

# --- Hashing de Senha ---

# Define o contexto de criptografia, usando o algoritmo bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verificar_senha(senha_plana: str, senha_hashed: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return pwd_context.verify(senha_plana, senha_hashed)

def gerar_hash_senha(senha: str) -> str:
    """Gera o hash de uma senha."""
    return pwd_context.hash(senha)

# --- Gerenciamento de Token JWT ---

# Define o esquema de autenticação. "token" é a URL onde o cliente vai obter o token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def criar_token_acesso(data: dict):
    """Cria um novo token de acesso JWT."""
    para_codificar = data.copy()
    expira_em = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    para_codificar.update({"exp": expira_em})
    token_jwt_codificado = jwt.encode(para_codificar, SECRET_KEY, algorithm=ALGORITHM)
    return token_jwt_codificado

# --- Dependência para Obter Usuário Logado ---

async def get_usuario_logado(token: str = Depends(oauth2_scheme)) -> Funcionario:
    """
    Dependência para FastAPI: decodifica o token, valida e retorna o usuário do banco de dados.
    Esta função será usada para proteger os endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # O 'sub' (subject) do nosso token será o email do usuário
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Busca o usuário no banco de dados pelo email contido no token
    funcionario = await Funcionario.find_one(Funcionario.email == email)
    if funcionario is None:
        raise credentials_exception
        
    return funcionario