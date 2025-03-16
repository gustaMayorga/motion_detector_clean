import os
import subprocess
from pathlib import Path

def ejecutar_comando(comando):
    """Ejecuta un comando y devuelve la salida"""
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    return resultado.stdout.strip(), resultado.stderr.strip(), resultado.returncode

def buscar_repos_embebidos():
    """Busca directorios que contengan .git dentro del proyecto"""
    repos_embebidos = []
    directorio_raiz = "."
    raiz_git = os.path.join(directorio_raiz, ".git")
    
    # Asegurar que estamos en un repositorio Git
    if not os.path.exists(raiz_git):
        return repos_embebidos
    
    # Buscar directorios .git
    for ruta, directorios, archivos in os.walk(directorio_raiz):
        if ".git" in directorios and ruta != directorio_raiz:
            # Excluir el .git principal
            if not os.path.samefile(os.path.join(ruta, ".git"), raiz_git):
                repos_embebidos.append(ruta)
    
    return repos_embebidos

def manejar_repo_embebido(ruta):
    """Maneja un repositorio embebido"""
    print(f"\nRepositorio embebido encontrado: {ruta}")
    print("Opciones:")
    print("1. Convertir en submódulo (necesitas la URL del repositorio)")
    print("2. Eliminar el directorio .git (mantener archivos)")
    print("3. Ignorar completamente (añadir a .gitignore)")
    print("4. Omitir este repositorio")
    
    opcion = input("Selecciona una opción (1-4): ")
    
    if opcion == "1":
        url = input("URL del repositorio (ej: https://github.com/usuario/repo.git): ")
        stdout, stderr, code = ejecutar_comando(f"git rm --cached {ruta}")
        if code != 0:
            print(f"Error al eliminar del índice: {stderr}")
            return False
        
        stdout, stderr, code = ejecutar_comando(f"git submodule add {url} {ruta}")
        if code != 0:
            print(f"Error al añadir submódulo: {stderr}")
            return False
        print(f"Submódulo añadido correctamente: {ruta}")
        
    elif opcion == "2":
        git_dir = os.path.join(ruta, ".git")
        try:
            import shutil
            shutil.rmtree(git_dir)
            print(f"Directorio .git eliminado de {ruta}")
            stdout, stderr, code = ejecutar_comando(f"git add {ruta}")
            if code != 0:
                print(f"Error al añadir archivos: {stderr}")
                return False
            print(f"Archivos añadidos correctamente desde {ruta}")
        except Exception as e:
            print(f"Error al eliminar .git: {e}")
            return False
            
    elif opcion == "3":
        with open(".gitignore", "a") as f:
            f.write(f"\n{ruta}/\n")
        stdout, stderr, code = ejecutar_comando(f"git rm --cached -r {ruta}")
        if code != 0:
            print(f"Error al eliminar del índice: {stderr}")
            return False
        print(f"{ruta} añadido a .gitignore y eliminado del índice")
        
    elif opcion == "4":
        print(f"Omitiendo {ruta}")
        
    else:
        print("Opción no válida")
        return False
        
    return True

def main():
    print("=== Gestor de Repositorios Git Embebidos ===")
    
    repos_embebidos = buscar_repos_embebidos()
    
    if not repos_embebidos:
        print("No se encontraron repositorios Git embebidos.")
        return
    
    print(f"Se encontraron {len(repos_embebidos)} repositorios embebidos:")
    for i, repo in enumerate(repos_embebidos, 1):
        print(f"{i}. {repo}")
    
    print("\nManejando cada repositorio embebido...")
    for repo in repos_embebidos:
        manejar_repo_embebido(repo)
    
    print("\nProceso completado. Verifica los cambios con 'git status'.")

if __name__ == "__main__":
    main() 