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
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- Hashing de Senha ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verificar_senha(senha_plana: str, senha_hashed: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return pwd_context.verify(senha_plana, senha_hashed)

def gerar_hash_senha(senha: str) -> str:
    """Gera o hash de uma senha."""
    return pwd_context.hash(senha)

# --- Gerenciamento de Token JWT ---
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
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    funcionario = await Funcionario.find_one(Funcionario.email == email)
    if funcionario is None:
        raise credentials_exception
        
    return funcionario