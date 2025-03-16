# Guía de Usuario - Sistema vigIA

## Índice
1. [Introducción](#introducción)
2. [Requisitos del Sistema](#requisitos-del-sistema)
3. [Instalación](#instalación)
4. [Configuración Inicial](#configuración-inicial)
5. [Acceso al Sistema](#acceso-al-sistema)
6. [Panel de Control](#panel-de-control)
7. [Gestión de Cámaras](#gestión-de-cámaras)
8. [Configuración de Zonas](#configuración-de-zonas)
9. [Alertas y Notificaciones](#alertas-y-notificaciones)
10. [Analítica de Video](#analítica-de-video)
11. [Entrenamiento de Modelos](#entrenamiento-de-modelos)
12. [Visualización en Tiempo Real](#visualización-en-tiempo-real)
13. [Grabaciones y Almacenamiento](#grabaciones-y-almacenamiento)
14. [Solución de Problemas](#solución-de-problemas)
15. [Preguntas Frecuentes](#preguntas-frecuentes)

## Introducción

vigIA es un sistema de videovigilancia inteligente que integra tecnologías de visión por computadora y aprendizaje automático para proporcionar capacidades avanzadas de detección y análisis. El sistema permite:

- Detección y seguimiento de objetos en tiempo real
- Análisis de comportamiento y patrones
- Generación automática de alertas
- Grabación inteligente basada en eventos
- Administración centralizada de múltiples cámaras
- Visualización en tiempo real y reproducción de grabaciones
- Entrenamiento de modelos personalizados

Esta guía le ayudará a instalar, configurar y utilizar todas las funcionalidades del sistema vigIA.

## Requisitos del Sistema

### Hardware Recomendado
- **CPU**: Intel Core i7 o superior (o equivalente AMD)
- **RAM**: 16GB mínimo, 32GB recomendado
- **GPU**: NVIDIA con soporte CUDA (GTX 1660 o superior)
- **Almacenamiento**: SSD de 250GB para el sistema, discos adicionales para grabaciones
- **Red**: Gigabit Ethernet

### Software Requerido
- Docker y Docker Compose
- Navegador web moderno (Chrome, Firefox, Edge)
- Cámaras compatibles con protocolos RTSP o ONVIF

## Instalación

vigIA se distribuye como un conjunto de contenedores Docker, lo que facilita su instalación en cualquier sistema compatible.

### Utilizando Docker Compose

1. Clone el repositorio de vigIA:
   ```bash
   git clone https://github.com/vigia/vigia-system.git
   cd vigia-system
   ```

2. Configure las variables de entorno (opcional):
   ```bash
   cp .env.example .env
   # Edite el archivo .env según sus necesidades
   ```

3. Inicie los servicios con Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Verifique que todos los servicios están en funcionamiento:
   ```bash
   docker-compose ps
   ```

### Instalación Manual

Para entornos sin Docker, consulte el archivo `docs/instalacion_manual.md`.

## Configuración Inicial

Después de la instalación, es necesario realizar la configuración inicial del sistema.

### Primer Acceso

1. Abra un navegador web y visite `http://localhost:80` (o la dirección IP del servidor donde instaló vigIA)
2. Inicie sesión con las credenciales predeterminadas:
   - Usuario: `admin`
   - Contraseña: `admin123`
3. Se le solicitará cambiar la contraseña inmediatamente

### Configuración Básica del Sistema

1. En el menú principal, vaya a **Configuración → Sistema**
2. Configure los parámetros generales:
   - Nombre del sistema
   - Zona horaria
   - Directorio de almacenamiento
   - Política de retención de grabaciones
3. Guarde los cambios haciendo clic en **Guardar Configuración**

## Acceso al Sistema

vigIA proporciona diferentes formas de acceso según las necesidades del usuario.

### Interfaz Web

La interfaz web es la forma principal de interactuar con el sistema:

1. Abra un navegador web y acceda a `http://[dirección-ip-del-servidor]:80`
2. Inicie sesión con sus credenciales
3. Se mostrará el panel de control principal

### API REST

Para integración con otros sistemas, vigIA proporciona una API REST completa:

1. La documentación de la API está disponible en `http://[dirección-ip-del-servidor]:8000/docs`
2. La autenticación se realiza mediante tokens JWT

### Acceso Móvil

La interfaz web es responsiva y se adapta a dispositivos móviles, pero para una mejor experiencia:

1. Descargue la aplicación móvil desde Google Play o App Store (si está disponible)
2. Configure la conexión al servidor vigIA
3. Inicie sesión con sus credenciales

## Panel de Control

El panel de control proporciona una visión general del sistema y acceso rápido a todas las funcionalidades.

### Elementos Principales

- **Vista General**: Muestra estadísticas y estado del sistema
- **Vista de Cámaras**: Visualización en vivo de todas las cámaras
- **Alertas Recientes**: Últimas alertas generadas por el sistema
- **Estado del Sistema**: Información sobre recursos y componentes

### Personalización

1. Para personalizar el panel, haga clic en **Personalizar**
2. Arrastre y suelte los widgets según sus preferencias
3. Configure cada widget según sus necesidades
4. Guarde la configuración

## Gestión de Cámaras

La gestión eficaz de cámaras es fundamental para sacar el máximo provecho de vigIA.

### Agregar una Nueva Cámara

1. Vaya a **Configuración → Cámaras**
2. Haga clic en **Agregar Cámara**
3. Complete el formulario con la información de la cámara:
   - Nombre descriptivo
   - Dirección IP
   - Modelo/fabricante
   - URL de streaming (RTSP u ONVIF)
   - Credenciales de acceso
4. Seleccione el modo de grabación:
   - Continua
   - Basada en movimiento
   - Programada
5. Haga clic en **Guardar**

### Configuración Avanzada de Cámaras

Para cada cámara, puede configurar parámetros avanzados:

1. Seleccione la cámara y haga clic en **Configuración Avanzada**
2. Configure:
   - Resolución y FPS
   - Filtros de calidad
   - Rotación y transformación
   - Parámetros de compresión

### Prueba de Conectividad

1. Seleccione la cámara y haga clic en **Probar Conexión**
2. El sistema verificará:
   - Accesibilidad
   - Autenticación
   - Calidad del streaming

## Configuración de Zonas

Las zonas permiten definir áreas de interés específicas dentro del campo visual de las cámaras.

### Crear una Nueva Zona

1. Vaya a **Configuración → Cámaras**
2. Seleccione la cámara deseada
3. Haga clic en **Zonas**
4. Seleccione **Nueva Zona**
5. Dibuje el polígono que define la zona sobre la imagen de la cámara
6. Configure las propiedades de la zona:
   - Nombre descriptivo
   - Tipo (intrusión, línea de cruce, área de conteo)
   - Color de visualización
   - Comportamientos a detectar
7. Guarde la configuración

### Tipos de Zonas

- **Zona de Intrusión**: Detecta objetos que ingresan al área definida
- **Línea de Cruce**: Detecta objetos que cruzan una línea virtual
- **Área de Conteo**: Cuenta objetos dentro de un área definida
- **Zona de Permanencia**: Detecta objetos que permanecen por tiempo prolongado

## Alertas y Notificaciones

vigIA ofrece un sistema flexible de alertas basado en los eventos detectados.

### Configuración de Alertas

1. Vaya a **Configuración → Alertas**
2. Haga clic en **Nueva Regla de Alerta**
3. Configure los criterios de activación:
   - Tipo de evento (intrusión, cruce de línea, etc.)
   - Cámara y zona específica
   - Clase de objeto (persona, vehículo, etc.)
   - Horario de activación
4. Configure las acciones a realizar:
   - Notificación en el sistema
   - Correo electrónico
   - Webhook
   - SMS (si está configurado)
5. Guarde la configuración

### Gestión de Alertas

1. Vaya a **Alertas** en el menú principal
2. Visualice todas las alertas generadas
3. Filtre por fecha, cámara o tipo
4. Marque las alertas como revisadas
5. Agregue comentarios a cada alerta

## Analítica de Video

La analítica de video es el núcleo de vigIA, proporcionando detección y análisis inteligente.

### Configuración de Analíticas

1. Vaya a **Configuración → Analíticas**
2. Configure los agentes de analítica:
   - Detector de objetos (seleccione modelo)
   - Seguimiento de objetos (seleccione algoritmo)
   - Análisis de comportamiento

### Analíticas Disponibles

- **Detección de Objetos**: Identifica y clasifica objetos (personas, vehículos, etc.)
- **Seguimiento**: Mantiene la identidad de los objetos a través de múltiples frames
- **Análisis de Comportamiento**:
  - Detección de merodeo
  - Análisis de multitudes
  - Abandono/retiro de objetos
  - Velocidad de movimiento

## Entrenamiento de Modelos

vigIA permite entrenar modelos personalizados para mejorar la precisión en su entorno específico.

### Creación de Datasets

1. Vaya a **Modelos → Datasets**
2. Haga clic en **Nuevo Dataset**
3. Seleccione el método de creación:
   - Desde grabaciones existentes
   - Subida manual de imágenes
   - Captura desde cámaras en vivo
4. Etiquete las imágenes:
   - Manualmente
   - Con asistencia de IA

### Entrenamiento de Modelo

1. Vaya a **Modelos → Entrenamiento**
2. Seleccione **Nuevo Entrenamiento**
3. Configure los parámetros:
   - Dataset a utilizar
   - Modelo base
   - Clases a detectar
   - Hiperparámetros
4. Inicie el entrenamiento
5. Monitorice el progreso y métricas

### Despliegue de Modelo

1. Una vez finalizado el entrenamiento, vaya a **Modelos → Despliegue**
2. Seleccione el modelo entrenado
3. Asigne el modelo a cámaras específicas
4. Active el nuevo modelo

## Visualización en Tiempo Real

vigIA ofrece potentes herramientas de visualización en tiempo real.

### Vista de Múltiples Cámaras

1. Vaya a **Monitoreo → Vista en Vivo**
2. Seleccione la disposición de visualización (2x2, 3x3, etc.)
3. Arrastre las cámaras deseadas a cada panel
4. Utilice los controles para:
   - Zoom digital
   - Control PTZ (si la cámara lo soporta)
   - Captura de instantáneas

### Visualización Avanzada

- **Overlays**: Muestra información en tiempo real sobre los objetos detectados
- **Trayectorias**: Visualiza el movimiento de objetos
- **Mapa de Calor**: Muestra áreas de mayor actividad
- **Contadores**: Visualiza conteos en tiempo real

## Grabaciones y Almacenamiento

vigIA gestiona eficientemente el almacenamiento de grabaciones.

### Búsqueda de Grabaciones

1. Vaya a **Grabaciones → Búsqueda**
2. Filtre por:
   - Cámara
   - Fecha y hora
   - Eventos detectados
   - Objetos específicos
3. Visualice los resultados en la línea de tiempo

### Reproducción

1. Seleccione la grabación deseada
2. Utilice los controles de reproducción:
   - Reproducir/Pausar
   - Avance rápido/lento
   - Salto a evento
3. Exporte segmentos específicos

### Gestión de Almacenamiento

1. Vaya a **Configuración → Almacenamiento**
2. Configure:
   - Política de retención
   - Límites de espacio
   - Limpieza automática
   - Ubicaciones de almacenamiento

## Solución de Problemas

### Diagnóstico del Sistema

1. Vaya a **Sistema → Diagnóstico**
2. Verifique:
   - Estado de componentes
   - Uso de recursos
   - Conectividad de cámaras
   - Logs del sistema

### Problemas Comunes

#### Cámara no conecta
- Verifique la URL de streaming
- Confirme credenciales
- Verifique conectividad de red

#### Rendimiento lento
- Revise uso de CPU/GPU
- Ajuste resolución de cámaras
- Verifique carga de red

#### Alertas no se generan
- Revise configuración de zonas
- Verifique modelo de detección
- Compruebe reglas de alertas

## Preguntas Frecuentes

### ¿Cuántas cámaras puede gestionar el sistema?
El número depende del hardware. Una configuración recomendada puede manejar entre 16-32 cámaras a 1080p.

### ¿Es compatible con mis cámaras existentes?
vigIA es compatible con cualquier cámara que soporte RTSP, ONVIF o HTTP.

### ¿Necesito una GPU para ejecutar el sistema?
Para un rendimiento óptimo, se recomienda una GPU NVIDIA con soporte CUDA, pero el sistema puede funcionar con CPU para cargas ligeras.

### ¿Cómo puedo ampliar el almacenamiento?
Puede añadir discos adicionales y configurarlos en la sección de Almacenamiento.

### ¿Puedo acceder al sistema desde Internet?
Sí, aunque se recomienda hacerlo mediante una VPN por seguridad. 