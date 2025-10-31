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
SECRET_KEY = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-dificil-de-adivinhar-012345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# --- Criptografia de senha ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- OAuth2 (o frontend envia para /token) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- JWT ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- Autenticação ---
async def authenticate_user(email: str, password: str) -> Optional[Funcionario]:
    user = await Funcionario.find_one(Funcionario.email == email)
    if not user:
        return None
    # espera que o modelo tenha atributo senha_hash
    senha_hash = getattr(user, "senha_hash", None)
    if not verify_password(password, senha_hash or ""):
        return None
    return user

# --- Dependência para Obter Usuário Logado ---
async def get_usuario_logado(token: str = Depends(oauth2_scheme)) -> Funcionario:
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
