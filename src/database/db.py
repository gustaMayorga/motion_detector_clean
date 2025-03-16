import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

# Cargar configuración desde variables de entorno o valores por defecto
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///vigia.db")

# Configurar logger
logger = logging.getLogger("Database")

# Crear engine con pool de conexiones
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Reciclar conexiones cada hora
    pool_pre_ping=True,  # Verificar conexión antes de usar
    poolclass=QueuePool
)

# Crear fábrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Crear sesión con scope para entornos multihilo
db_session = scoped_session(SessionLocal)

@contextmanager
def get_db():
    """Proporciona una sesión de base de datos con manejo de contexto"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en la transacción: {e}")
        raise
    finally:
        session.close()

def init_db():
    """Inicializa la base de datos creando todas las tablas"""
    from src.database.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Base de datos inicializada")

def drop_db():
    """Elimina todas las tablas de la base de datos"""
    from src.database.models import Base
    Base.metadata.drop_all(bind=engine)
    logger.info("Base de datos eliminada") 