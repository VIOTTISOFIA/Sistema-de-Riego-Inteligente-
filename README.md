# Sistema de Riego Inteligente — MVP beta

Capa de software para la **auditoría hídrica** y la **visualización del estado del suelo** de un sistema de riego ya instalado. Práctica Profesionalizante I (ISPC, 2026) — Evidencia 3.

**Aplicación publicada:** `PEGAR_AQUI_EL_LINK_DE_STREAMLIT`

El tablero procesa telemetría real de un cultivo de frutilla en Paraguay (julio a septiembre de 2022). No está conectado a un campo en vivo y no acciona válvulas.

## Qué hace

| Pantalla | Qué muestra | Requerimientos |
|---|---|---|
| Hoy | La respuesta a "¿hay que regar?" en una frase, la humedad del suelo, si el riego está entregando agua y si sale agua sin orden | HU-01, RF-10, RF-11 |
| Agua | Agua usada, en riegos y sin orden de riego, día por día; salidas de agua sin orden; riegos que no entregaron agua | RF-02 a RF-06, RF-13 |
| Riegos | Riegos de los últimos 30 días con duración, litros y humedad al empezar | HU-03 |
| Ajustes | Niveles a partir de los cuales se avisa | — |
| Acerca de esta versión | Alcance, limitaciones, arquitectura y trazabilidad | — |

## Estructura

```
├── app.py               # Interfaz (Módulo C): Streamlit, 4 vistas
├── etl.py               # ETL y auditoría hídrica (Módulo A): pandas, sin interfaz
├── tests/
│   ├── test_etl.py      # Pruebas de la lógica de datos
│   └── test_app.py      # Pruebas de punta a punta de la app
├── Datos/               # Telemetría cruda (Mendeley Data, DOI 10.17632/cjb4vy4mzj.3)
│   ├── D_valve.csv      # Estado comandado a la electroválvula (0/1)
│   ├── D_flowmeter.csv  # Volumen acumulado (L)
│   └── D_moisture.csv   # Humedad del suelo (%)
├── docs/EVIDENCIA_3.md  # Arquitectura, pruebas, errores y limitaciones
├── .streamlit/config.toml
├── requirements.txt
└── requirements-dev.txt
```

Si los CSV están en la raíz, junto a `app.py`, la aplicación también los encuentra.

## Ejecutar en local

```
pip install -r requirements.txt
streamlit run app.py
```

## Ejecutar las pruebas

```
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Publicar (Streamlit Community Cloud)

1. Subir a GitHub, en un repositorio público, todo el contenido de esta carpeta, incluida `Datos/`.
2. Entrar a <https://share.streamlit.io> con la cuenta de GitHub y elegir **Create app**.
3. Indicar el repositorio, la rama `main` y `app.py` como archivo principal.
4. **Deploy**. Al terminar, copiar la URL pública y pegarla arriba en este README.

Cada `git push` a la rama vuelve a desplegar la aplicación. En el plan gratuito la aplicación se suspende si pasa un tiempo sin visitas: conviene abrirla antes de la presentación.

## Cómo se procesan los datos

Cada vez que la aplicación se inicia, `etl.py` ejecuta el ETL sobre los tres CSV originales:

- **Integración por clave temporal** con `merge_asof` (tolerancia de 3 min para el caudalímetro y 20 min para la humedad), con `D_valve` como tabla base.
- **Zona horaria**: de UTC a hora local del campo (UTC-4).
- **Caudalímetro**: es un acumulador; se diferencia para obtener litros por intervalo.
- **Faltantes**: los cortes de telemetría se conservan como nulos, sin imputar.
- **Percentiles**: el estado del suelo se expresa como percentil de la propia serie del sensor.
- **Auditoría**: el agua registrada con la válvula abierta se atribuye a una orden; la registrada con la válvula cerrada queda como no atribuida. Una orden con menos de 0,5 L por minuto comandado se marca como *sin caudal*.

## Equipo (Grupo 11 — ISPC 2026)

- Gonella, Lucas
- Nadales, Katya María
- Villalón, Favio
- Viotti, Sofía Anahí
- Zunino, Luca
