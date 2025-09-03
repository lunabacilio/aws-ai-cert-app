# 🎯 AWS AI Practitioner Quiz App

Una aplicación web interactiva para practicar y prepararse para el examen AWS AI Practitioner. Desarrollada con Flask y diseñada para ofrecer una experiencia de estudio completa y eficiente.

## 🚀 Características

- **Dos modos de quiz**:
  - 📝 **Modo Inmediato**: Feedback instantáneo después de cada pregunta
  - 📊 **Modo Examen**: Todas las preguntas con resultados al final
- **Tipos de preguntas soportadas**:
  - Selección única
  - Selección múltiple  
  - Preguntas de mapeo (hotspot)
- **Funcionalidades avanzadas**:
  - Selección de rango de preguntas
  - Preguntas aleatorias
  - Progreso en tiempo real
  - Estadísticas detalladas

## 📋 Requisitos Previos

- **Python 3.11+** 
- **pip** (gestor de paquetes de Python)
- **Git** (opcional, para clonar el repositorio)

## 🔧 Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone https://github.com/lunabacilio/aws-ai-cert-app.git
cd aws-ai-cert-app
```

### 2. Crear Entorno Virtual (Recomendado)

#### En Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### En Windows (Command Prompt):
```cmd
python -m venv venv
venv\Scripts\activate
```

#### En Linux/Mac:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

## 🚀 Ejecutar la Aplicación

### Ejecución en Desarrollo

```bash
python app.py
```

