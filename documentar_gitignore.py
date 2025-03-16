# Script para crear un archivo .gitignore apropiado
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