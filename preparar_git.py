import os
import subprocess
import sys

def ejecutar_comando(comando, mensaje_error=None):
    """Ejecuta un comando y muestra el resultado"""
    print(f"\n> {comando}")
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    
    if resultado.returncode != 0 and mensaje_error:
        print(f"Error: {mensaje_error}")
        print(f"Detalles: {resultado.stderr}")
        return False
    
    print(resultado.stdout)
    return True

def preparar_git():
    """Prepara el proyecto para subirlo a Git"""
    print("=== Preparando el proyecto vigIA para Git ===")
    
    # 1. Verificar si ya existe .git
    if os.path.exists(".git"):
        print("Repositorio Git ya inicializado.")
    else:
        if not ejecutar_comando("git init", "No se pudo inicializar el repositorio Git"):
            return False
    
    # 2. Crear .gitignore si no existe
    if not os.path.exists(".gitignore"):
        print("\nCreando archivo .gitignore...")
        with open('.gitignore', 'w', encoding='utf-8') as f:
            f.write("""# Archivos y directorios a ignorar por Git

# Entornos virtuales
venv/
env/
ENV/

# Caché de Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Logs y datos temporales
logs/*.log
*.log
temp/
tmp/

# Archivos de base de datos
*.db
*.sqlite
*.sqlite3

# Archivos multimedia y binarios grandes
*.mp4
*.avi
*.mov
*.webm
*.jpg
*.jpeg
*.png
*.gif
*.bin
*.dat

# Secretos y configuraciones locales
.env
.env.local
*.key
*.pem

# Carpetas de IDE
.idea/
.vscode/
*.swp
*.swo

# Carpetas de modelos grandes
models/*.weights
models/*.pt
models/*.pth
models/*.bin

# Directorio de datos
data/recordings/
data/snapshots/

# Archivos generados
vigia_proyecto_completo.txt

# Archivos de sistema
.DS_Store
Thumbs.db
""")
        print("Archivo .gitignore creado correctamente.")
    
    # 3. Configurar usuario si es necesario
    print("\n¿Deseas configurar tu identidad de Git? (s/n)")
    respuesta = input().lower()
    if respuesta == "s":
        nombre = input("Nombre: ")
        email = input("Email: ")
        ejecutar_comando(f'git config user.name "{nombre}"')
        ejecutar_comando(f'git config user.email "{email}"')
    
    # 4. Añadir archivos
    if not ejecutar_comando("git add .", "No se pudieron añadir los archivos"):
        return False
    
    # 5. Hacer commit
    mensaje = input("\nMensaje para el commit (o Enter para usar 'Versión inicial del proyecto vigIA'): ")
    if not mensaje:
        mensaje = "Versión inicial del proyecto vigIA"
    
    if not ejecutar_comando(f'git commit -m "{mensaje}"', "No se pudo hacer commit"):
        return False
    
    # 6. Configurar repositorio remoto
    print("\n¿Deseas configurar un repositorio remoto? (s/n)")
    respuesta = input().lower()
    if respuesta == "s":
        url_repo = input("URL del repositorio (ejemplo: https://github.com/usuario/vigia.git): ")
        if not ejecutar_comando(f'git remote add origin {url_repo}', "No se pudo añadir el repositorio remoto"):
            return False
        
        # 7. Push al repositorio remoto
        print("\n¿Deseas hacer push de los cambios? (s/n)")
        respuesta = input().lower()
        if respuesta == "s":
            rama = "main"  # o "master" según la configuración
            if not ejecutar_comando(f'git push -u origin {rama}', "No se pudo hacer push"):
                return False
    
    print("\n=== Proceso completado con éxito ===")
    return True

if __name__ == "__main__":
    preparar_git() 