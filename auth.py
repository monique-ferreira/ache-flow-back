import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext

from models import Funcionario

load_dotenv()

# --- Configurações de Segurança ---
SECRET_KEY = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-dificil-de-adivinhar-012345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Fail-fast se não houver SECRET_KEY (evita 500 silencioso)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY não definida no ambiente. Defina SECRET_KEY nas variáveis do serviço.")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def authenticate_user(email: str, password: str) -> Optional[Funcionario]:
    usuario = await Funcionario.find_one(Funcionario.email == email)
    if not usuario:
        return None
    if not verify_password(password, usuario.senha):
        return None
    return usuario


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_usuario_logado(token: str = Depends(oauth2_scheme)) -> Funcionario:
    """Dependency para rotas protegidas. Retorna o Funcionario autenticado.
    Em caso de falha, levanta HTTP 401 (evita 500).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if not email:
            raise credentials_exception
    except Exception:
        # Captura QUALQUER erro (chave ausente, token malformado, expiração, etc.)
        raise credentials_exception

    funcionario = await Funcionario.find_one(Funcionario.email == email)
    if not funcionario:
        raise credentials_exception
    return funcionario
