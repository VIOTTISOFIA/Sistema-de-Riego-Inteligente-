# HU-01 — Estado actual del suelo (RF-11)

Primera versión funcionando del Módulo C del MVP. Grupo 2 — ISPC 2026.

## Estructura

```
evidencia2/
├── app.py
├── requirements.txt
└── datos/
    ├── D_moisture.csv
    ├── D_valve.csv
    └── D_flowmeter.csv
```

Si los CSV quedan junto a `app.py` en lugar de en `datos/`, la app también los encuentra.

## Ejecución

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre en `http://localhost:8501`.

## Qué demuestra el recorrido

El dato crudo nunca se toca a mano: la app ejecuta el mismo ETL del notebook V2 al
arrancar (integración por clave temporal con `merge_asof`, conversión a hora local
UTC-4, diferenciación del acumulador de caudal, faltantes conservados como `NaN`) y
recién después calcula el percentil y pinta el indicador.

Como la telemetría es histórica (11/07 a 16/09 de 2022), el tablero la reproduce como
si llegara en vivo: el botón **Reproducir** avanza el cursor sobre la serie y la
pantalla se actualiza sola, sin recargar la página.

## Guía de capturas

Mover el slider **Momento de la serie** a estas posiciones:

| Captura | Posición | Qué se ve | Criterio que cubre |
|---|---|---|---|
| 1 | 200 | Estado **ÓPTIMO** en verde, válvula cerrada | Escenario 2 (contraste) |
| 2 | 252 | Estado **ATENCIÓN** en ámbar | Transición del indicador |
| 3 | 8168 | Estado **RIEGO NECESARIO** en rojo, P14, válvula abierta, 1.398 L en 24 h | Escenario 2 |
| 4 | — | Video de 15–20 s con **Reproducir** activo | Escenario 1 |
| 5 | — | Panel lateral con la tabla percentil ↔ lectura cruda | Justificación del percentil |

Para el video alcanza con una grabación de pantalla corta mostrando cómo el valor y el
color cambian solos mientras nadie toca el navegador.

## Nota sobre el percentil

El sensor capacitivo del campo no está calibrado: sus lecturas se mueven entre 68,6 %
y 86,9 % y toman solo 44 valores distintos. Mostrar «72 % de humedad» como medición
absoluta induce a error, así que el estado se expresa en percentiles de la propia
serie histórica del sensor, según la decisión documentada en la Evidencia 1.
