#!/usr/bin/env python
"""
Script para documentar la estructura y contenido del proyecto vigIA
"""

import os
import datetime
import fnmatch

# Configuración
proyecto_dir = "E:/IA/motion_detector_clean"  # Ajusta esta ruta
archivo_salida = "vigia_proyecto_completo.txt"
ignorar_directorios = ["venv", "__pycache__", "node_modules", ".git", ".idea", ".vscode", "logs", "ByteTrack"]
ignorar_extensiones = [".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".dat", ".db", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".avi"]
max_tamano_archivo = 1 * 1024 * 1024  # 1MB en bytes

# Inicializar estadísticas
archivos_procesados = 0
archivos_ignorados = 0
tamano_total = 0

# Crear o sobrescribir el archivo de salida
with open(archivo_salida, 'w', encoding='utf-8') as f:
    f.write("# PROYECTO vigIA - DOCUMENTACIÓN COMPLETA\n")
    f.write(f"# Generado el {datetime.datetime.now()}\n\n")
    
    # Estructura de directorios
    f.write("## ESTRUCTURA DE DIRECTORIOS\n\n```\n")
    
    def obtener_arbol_directorios(ruta, indentacion="", ignorar=None):
        elementos = sorted(os.listdir(ruta))
        for elemento in elementos:
            ruta_completa = os.path.join(ruta, elemento)
            if os.path.isdir(ruta_completa):
                if elemento in ignorar:
                    continue
                f.write(f"{indentacion}{elemento}/\n")
                obtener_arbol_directorios(ruta_completa, indentacion + "    ", ignorar)
            else:
                f.write(f"{indentacion}{elemento}\n")
    
    obtener_arbol_directorios(proyecto_dir, "", ignorar_directorios)
    f.write("```\n\n")
    
    # Contenido de archivos
    f.write("## CONTENIDO DE ARCHIVOS\n\n")
    
    for raiz, dirs, archivos in os.walk(proyecto_dir):
        # Filtrar directorios ignorados
        dirs[:] = [d for d in dirs if d not in ignorar_directorios]
        
        for archivo in sorted(archivos):
            ruta_completa = os.path.join(raiz, archivo)
            
            # Verificar si debemos ignorar este archivo
            ignorar = False
            
            # Verificar extensión
            _, extension = os.path.splitext(archivo)
            if extension.lower() in ignorar_extensiones:
                ignorar = True
            
            # Verificar tamaño
            tamano = os.path.getsize(ruta_completa)
            if tamano > max_tamano_archivo:
                ignorar = True
                
            if ignorar:
                archivos_ignorados += 1
                continue
                
            # Obtener ruta relativa
            ruta_relativa = os.path.relpath(ruta_completa, proyecto_dir)
            
            # Escribir información del archivo
            f.write(f"### {ruta_relativa}\n")
            f.write(f"```{extension[1:]} | {tamano} bytes | Modificado: {datetime.datetime.fromtimestamp(os.path.getmtime(ruta_completa))}\n")
            f.write("```\n")
            
            # Escribir contenido del archivo
            try:
                with open(ruta_completa, 'r', encoding='utf-8', errors='replace') as archivo_contenido:
                    contenido = archivo_contenido.read()
                    f.write(contenido)
            except Exception as e:
                f.write(f"ERROR: No se pudo leer el archivo: {str(e)}")
                
            f.write("\n```\n\n")
            
            archivos_procesados += 1
            tamano_total += tamano
    
    # Resumen
    f.write("## RESUMEN DE LA DOCUMENTACIÓN\n\n")
    f.write(f"- Archivos procesados: {archivos_procesados}\n")
    f.write(f"- Archivos ignorados: {archivos_ignorados}\n")
    f.write(f"- Tamaño total de archivos incluidos: {tamano_total / 1024:.2f} KB\n\n")
    f.write("Documentación generada con el script de documentación automática de vigIA.\n")

print(f"Documentación completa guardada en: {archivo_salida}")
print(f"Archivos procesados: {archivos_procesados}")
print(f"Archivos ignorados: {archivos_ignorados}")
print(f"Tamaño total: {tamano_total / 1024:.2f} KB")