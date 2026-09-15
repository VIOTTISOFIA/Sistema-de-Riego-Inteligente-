# **Sistema de Riego Inteligente**

Capa de software complementaria para la auditoría hídrica y la visualización de telemetría de riego, desarrollada como Producto Mínimo Viable (MVP) para la Práctica Profesionalizante I (ISPC, 2026).

## **Descripción General del Proyecto**

Este repositorio contiene el código y la estructura de datos correspondientes al **Módulo C (Tablero de Visualización)** y al **Módulo A (Auditoría Hídrica)** del proyecto Sistema de Riego Inteligente.  
El sistema procesa y audita telemetría histórica real de un campo de cultivo (monitoreado entre julio y septiembre de 2022), integrando múltiples fuentes de datos para resolver dos problemáticas críticas identificadas en la gestión del recurso hídrico:

> * **PP-01 (Falta de trazabilidad del consumo de agua):** Detectar y cuantificar discrepancias entre el volumen de agua comandado por el sistema y el volumen efectivamente registrado por el caudalímetro (identificando volúmenes no atribuidos o "agua fantasma").  
> * **PP-02 (Estado actual del suelo):** Mostrar el estado operativo de la humedad del suelo de forma confiable, utilizando percentiles relativos de su propia serie histórica para mitigar las limitaciones de calibración de los sensores capacitivos de campo.

## **Estructura del Repositorio**

`sistema-de-riego-inteligente/`  
`├── app.py              # Tablero interactivo principal en Streamlit`  
`├── requirements.txt    # Dependencias y librerías del proyecto`  
`└── datos/              # Series temporales de telemetría cruda`  
    `├── D_moisture.csv  # Registros del sensor de humedad del suelo (%)`  
    `├── D_valve.csv     # Estados comandados a la electroválvula (0/1)`  
    `└── D_flowmeter.csv # Mediciones del volumen acumulado de agua (L)`

*(Nota: Si los archivos CSV se ubican directamente en la raíz junto a app.py, la aplicación también los detectará automáticamente).*

## **Requisitos e Instalación**

Para ejecutar este proyecto de manera local, asegúrate de tener instalado Python y sigue estos pasos:

> 1. Clona este repositorio o descarga los archivos en tu equipo.  
> 2. Instala las dependencias necesarias ejecutando:

`pip install -r requirements.txt`

## **Ejecución del Tablero**

Para poner en marcha la interfaz interactiva de Streamlit, ejecuta el siguiente comando desde la raíz del proyecto:

`streamlit run app.py`

Automáticamente se abrirá una pestaña en tu navegador predeterminado apuntando a http://localhost:8501.

## **Funcionamiento del Pipeline y ETL**

El tablero no lee archivos preprocesados estáticos: cada vez que se inicia la aplicación, el sistema ejecuta de manera automatizada el mismo proceso ETL (Extraer, Transformar y Cargar) sobre los archivos CSV originales:

> * **Integración temporal:** Se sincronizan las tres fuentes de telemetría (válvula, caudalímetro y humedad) mediante una clave temporal común utilizando merge\_asof (con tolerancias controladas para cada frecuencia de muestreo).  
> * **Corrección de zona horaria:** Las marcas temporales en UTC se ajustan a la hora local del campo (UTC-4).  
> * **Tratamiento del caudalímetro:** Se diferencia el acumulador de caudal para obtener el volumen exacto aplicado por intervalo.  
> * **Gestión de valores faltantes:** Las interrupciones reales de la telemetría se conservan explícitamente como NaN para evitar sesgos o mediciones inventadas por imputación artificial.  
> * **Cálculo de percentiles:** A partir de la serie integrada, el sistema calcula de forma dinámica el estado del suelo expresado en percentiles históricos.

## **Equipo de Trabajo (Grupo 2 — ISPC 2026\)**

> * Gonella, Lucas  
> * Nadales, Katya María  
> * Villalón, Favio  
> * Viotti, Sofía Anahí  
> * Zunino, Luca