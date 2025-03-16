#!/usr/bin/env python
"""
Script de diagnóstico para el sistema vigIA
Verifica la configuración, base de datos, y componentes críticos
"""

import os
import sys
import sqlite3
import logging
import json
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("diagnostic")

def check_database():
    """Verificar la base de datos y sus tablas"""
    logger.info("=== Verificando base de datos ===")
    
    try:
        # Verificar si el archivo existe
        db_path = 'vigia.db'
        if not os.path.exists(db_path):
            logger.error(f"Archivo de base de datos no encontrado: {db_path}")
            return False
            
        logger.info(f"Archivo de base de datos encontrado: {db_path} ({os.path.getsize(db_path)/1024:.2f} KB)")
        
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Listar tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Tablas encontradas: {len(tables)}")
        for table in tables:
            logger.info(f"  - {table[0]}")
            
        # Verificar usuarios
        try:
            cursor.execute("SELECT id, username, email, password_hash, is_active, role_id FROM users")
            users = cursor.fetchall()
            logger.info(f"Usuarios encontrados: {len(users)}")
            for user in users:
                logger.info(f"  - ID: {user[0]}, Usuario: {user[1]}, Email: {user[2]}, Activo: {user[4]}, Rol: {user[5]}")
                logger.info(f"    Hash de contraseña: {user[3][:20]}...")
        except sqlite3.OperationalError as e:
            logger.error(f"Error al consultar usuarios: {e}")
            
        # Verificar roles
        try:
            cursor.execute("SELECT id, name FROM roles")
            roles = cursor.fetchall()
            logger.info(f"Roles encontrados: {len(roles)}")
            for role in roles:
                logger.info(f"  - ID: {role[0]}, Nombre: {role[1]}")
        except sqlite3.OperationalError as e:
            logger.error(f"Error al consultar roles: {e}")
            
        # Verificar cámaras
        try:
            cursor.execute("SELECT COUNT(*) FROM cameras")
            camera_count = cursor.fetchone()[0]
            logger.info(f"Cámaras configuradas: {camera_count}")
        except sqlite3.OperationalError as e:
            logger.error(f"Error al consultar cámaras: {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error verificando la base de datos: {e}")
        return False

def check_password_hash_compatibility():
    """Verificar la compatibilidad del hash de contraseña"""
    logger.info("=== Verificando compatibilidad de hash de contraseña ===")
    
    try:
        # Generar un hash con werkzeug
        test_password = "test123"
        password_hash = generate_password_hash(test_password)
        logger.info(f"Hash generado para 'test123': {password_hash}")
        
        # Verificar el hash
        is_valid = check_password_hash(password_hash, test_password)
        logger.info(f"Verificación del hash: {'EXITOSA' if is_valid else 'FALLIDA'}")
        
        # Intentar verificar con contraseña incorrecta
        is_invalid = check_password_hash(password_hash, "wrong_password")
        logger.info(f"Verificación con contraseña incorrecta: {'FALLIDA COMO SE ESPERABA' if not is_invalid else 'INCORRECTAMENTE EXITOSA'}")
        
        # Prueba con hash conocido
        conn = sqlite3.connect('vigia.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, password_hash FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        conn.close()
        
        if admin_user:
            username, stored_hash = admin_user
            logger.info(f"Usuario admin encontrado con hash: {stored_hash[:20]}...")
            
            # Verificar con la contraseña conocida
            is_admin_valid = check_password_hash(stored_hash, "admin123")
            logger.info(f"Verificación de contraseña de admin: {'EXITOSA' if is_admin_valid else 'FALLIDA'}")
            
            # Si falló, crear un nuevo hash y actualizar la base de datos
            if not is_admin_valid:
                logger.warning("La verificación falló. Se corregirá el hash del usuario admin.")
                new_hash = generate_password_hash("admin123")
                logger.info(f"Nuevo hash generado: {new_hash[:20]}...")
                
                # Actualizar en la base de datos
                conn = sqlite3.connect('vigia.db')
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (new_hash,))
                conn.commit()
                conn.close()
                logger.info("Hash actualizado en la base de datos.")
        else:
            logger.error("Usuario admin no encontrado en la base de datos.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verificando la compatibilidad del hash: {e}")
        return False

def check_config_files():
    """Verificar archivos de configuración"""
    logger.info("=== Verificando archivos de configuración ===")
    
    try:
        # Verificar archivo principal de configuración
        config_file = 'configs/config.yaml'
        if not os.path.exists(config_file):
            logger.error(f"Archivo de configuración no encontrado: {config_file}")
            return False
            
        logger.info(f"Archivo de configuración encontrado: {config_file}")
        
        # Verificar directorios importantes
        important_dirs = ['data', 'logs', 'models', 'configs']
        for dir_name in important_dirs:
            if os.path.exists(dir_name) and os.path.isdir(dir_name):
                logger.info(f"Directorio encontrado: {dir_name}")
            else:
                logger.warning(f"Directorio no encontrado: {dir_name}")
                os.makedirs(dir_name, exist_ok=True)
                logger.info(f"Directorio creado: {dir_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verificando archivos de configuración: {e}")
        return False

def check_logs():
    """Verificar archivos de log"""
    logger.info("=== Verificando archivos de log ===")
    
    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            logger.error(f"Directorio de logs no encontrado: {log_dir}")
            return False
            
        log_files = list(Path(log_dir).glob('*.log'))
        logger.info(f"Archivos de log encontrados: {len(log_files)}")
        
        if log_files:
            # Verificar el archivo más reciente
            latest_log = max(log_files, key=os.path.getmtime)
            logger.info(f"Log más reciente: {latest_log.name} ({os.path.getsize(latest_log)/1024:.2f} KB)")
            
            # Mostrar las últimas líneas
            with open(latest_log, 'r') as f:
                last_lines = f.readlines()[-10:]
                logger.info("Últimas 10 líneas del log:")
                for line in last_lines:
                    logger.info(f"  {line.strip()}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verificando archivos de log: {e}")
        return False

def repair_database():
    """Reparar problemas comunes en la base de datos"""
    logger.info("=== Reparando la base de datos ===")
    
    try:
        conn = sqlite3.connect('vigia.db')
        cursor = conn.cursor()
        
        # 1. Comprobar si existe el rol de administrador
        cursor.execute("SELECT id FROM roles WHERE name = 'admin'")
        admin_role = cursor.fetchone()
        
        if not admin_role:
            logger.warning("Rol de administrador no encontrado. Creando...")
            cursor.execute("INSERT INTO roles (name, description, created_at, updated_at) VALUES ('admin', 'Administrador del sistema', datetime('now'), datetime('now'))")
            admin_role_id = cursor.lastrowid
            logger.info(f"Rol de administrador creado con ID: {admin_role_id}")
        else:
            admin_role_id = admin_role[0]
            logger.info(f"Rol de administrador encontrado con ID: {admin_role_id}")
        
        # 2. Comprobar si existe el usuario administrador
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        
        if not admin_user:
            logger.warning("Usuario administrador no encontrado. Creando...")
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash("admin123")
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name, role_id, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, ("admin", "admin@vigia.local", password_hash, "Administrador", "del Sistema", admin_role_id, 1))
            
            admin_user_id = cursor.lastrowid
            logger.info(f"Usuario administrador creado con ID: {admin_user_id}")
        else:
            admin_user_id = admin_user[0]
            logger.info(f"Usuario administrador encontrado con ID: {admin_user_id}")
            
            # Actualizar hash de contraseña
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash("admin123")
            
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, admin_user_id))
            logger.info("Hash de contraseña actualizado para el usuario administrador")
        
        conn.commit()
        conn.close()
        logger.info("Reparación de la base de datos completada")
        
        return True
        
    except Exception as e:
        logger.error(f"Error reparando la base de datos: {e}")
        return False

def main():
    """Función principal del diagnóstico"""
    logger.info("=== Iniciando diagnóstico del sistema vigIA ===")
    
    # Ejecutar todas las verificaciones
    db_ok = check_database()
    hash_ok = check_password_hash_compatibility()
    config_ok = check_config_files()
    logs_ok = check_logs()
    
    # Resumen
    logger.info("=== Resumen del diagnóstico ===")
    logger.info(f"Base de datos: {'OK' if db_ok else 'ERROR'}")
    logger.info(f"Hash de contraseña: {'OK' if hash_ok else 'ERROR'}")
    logger.info(f"Archivos de configuración: {'OK' if config_ok else 'ERROR'}")
    logger.info(f"Archivos de log: {'OK' if logs_ok else 'ERROR'}")
    
    # Reparar si es necesario
    if not db_ok or not hash_ok:
        logger.info("Se detectaron problemas. Iniciando reparación...")
        repair_database()
    
    logger.info("=== Diagnóstico completado ===")

if __name__ == "__main__":
    main() 