# Evidencia 3 — Integración del prototipo en un MVP beta

Sistema de Riego Inteligente · Grupo 11 · Práctica Profesionalizante I · ISPC 2026

**Link del MVP:** https://riego-inteligente-ispc.streamlit.app/

## 1. Alcance del MVP

### Qué resuelve

| Funcionalidad | Pantalla | Requerimientos | Pain point |
|---|---|---|---|
| Respuesta a "¿hay que regar?" en una frase, con la humedad del suelo, el estado del riego y los avisos | Hoy | HU-01, RF-10, RF-11 | PP-01, PP-02 |
| Agua usada, en riegos y sin orden de riego, total y por día | Agua | RF-02, RF-03, RF-04, RF-06, RF-13 | PP-01 |
| Salidas de agua con el riego cerrado ("agua fantasma") | Agua y aviso en Hoy | RF-05 | PP-01 |
| Riegos sin agua o con caudal insuficiente (dirección inversa, propuesta en la Evidencia 2) | Titular en Hoy, y Agua | RF-05 simétrico | PP-01 |
| Historial de riegos de los últimos 30 días | Riegos | HU-03 | PP-01 |
| Niveles de aviso ajustables | Ajustes | HU-01 | PP-02 |

Sobre el período completo (65 días con datos), el MVP informa:

- 77.218 L medidos; 50.125 L atribuidos a una orden y **27.094 L (35,1 %) no atribuidos**, en 121 episodios.
- 62 órdenes de riego; **13 sin caudal**, que suman 196 horas de válvula comandada abierta.
- 15 cortes de telemetría, el mayor de 63 horas; 2.056 L acumulados durante cortes, que no se pueden atribuir.

### Qué quedó fuera por ahora

| Elemento | Motivo |
|---|---|
| Módulo B: predicción de horas hasta el umbral (RF-07 a RF-09, RF-12) | Fase 2, según lo definido en la Evidencia 1 |
| Clima georreferenciado (RD-06 a RD-08) | Solo alimenta al Módulo B; se usó en el análisis, no en el producto |
| HU-02: alertas por mail o notificación | Requiere usuarios y un servicio de envío; el semáforo cubre el aviso en pantalla |
| HU-04: consumo contra requerimiento estimado | No hay un requerimiento cargado contra el cual comparar |
| HU-05: umbrales por cultivo | El caso es monocultivo; no se puede validar |
| Filtro por cultivo de la HU-03 | Mismo motivo |
| Datos en vivo y accionamiento de válvulas | No hay campo instrumentado; RNF-05 excluye el accionamiento |

## 2. Arquitectura y stack implementados

```
D_valve.csv ─────┐
D_flowmeter.csv ─┼─► etl.py ──► dataset integrado ──► app.py (Streamlit, 4 vistas)
D_moisture.csv ──┘   pandas     en memoria (caché)    Módulo C
                     Módulo A
        tests/ (pytest) verifica etl.py y app.py

GitHub (código + datos) ──► Streamlit Community Cloud ──► URL pública
```

Stack: Python, pandas, NumPy, Streamlit, Altair, pytest, GitHub, Streamlit Community Cloud.

### Qué se mantuvo de la idea original

- La arquitectura modular y la prioridad de los Módulos A y C.
- El flujo fuentes → ETL → procesamiento → tablero.
- Python, pandas, NumPy y Streamlit.
- El percentil 15 como umbral de acción.
- Que el sistema no acciona válvulas (RNF-05).
- Los faltantes sin imputar (RD-10) y el ETL reproducible desde los datos crudos (RNF-01, RNF-02).

### Qué se sacó y por qué

| Elemento | Por qué |
|---|---|
| Módulo B y Scikit-learn | Postergados a la Fase 2 para acotar el riesgo |
| API climática (Open-Meteo) | Solo la consume el Módulo B; sacarla evita depender de un servicio externo en la demo |
| Capa de almacenamiento | Los datos pesan alrededor de 1 MB y el ETL corre en segundos: se recalcula al iniciar y queda en caché. Una base de datos no aportaba nada en esta escala |
| Dataset de Kaggle | Sin clave temporal ni espacial y de otro contexto agrícola (Evidencia 1, apartado 7.9) |

### Qué se incluyó o cambió y por qué

| Cambio | Por qué |
|---|---|
| Despliegue en Streamlit Community Cloud | La consigna exige que cualquiera pueda entrar con un link; es gratuito y despliega desde GitHub sin configurar servidores |
| Lógica separada en `etl.py`, sin dependencia de Streamlit | Permite probar la auditoría sin levantar la interfaz (RNF-06) |
| Comprobaciones automáticas con pytest | Herramienta de apoyo para detectar regresiones después de cada cambio |
| Auditoría en las dos direcciones | La Evidencia 2 mostró órdenes de riego sin caudal, que el RF-05 original no contemplaba |
| Los datos viajan en el repositorio | La app publicada no depende de ningún archivo local |
| Interfaz pensada para el operario | El pain point es un operario que a las 7 de la mañana tiene que decidir si riega. La pantalla principal responde eso en una frase y en lenguaje llano; los códigos, percentiles y la trazabilidad pasaron a una línea técnica y a la pantalla "Acerca de esta versión" |
| El producto solo muestra lo ocurrido hasta "ahora" | Un panel de demostración separado fija qué momento de la telemetría de 2022 se trata como ahora; así las pantallas se comportan como lo harían con datos en vivo |
| Tema claro y una sola columna | Se usa en el campo, a la luz del día y desde el celular |
| Altair para el gráfico integrado | Permite superponer humedad, órdenes de riego y caudal en un mismo eje de tiempo; viene incluido con Streamlit |
| Validación de archivos de entrada | Un archivo faltante o mal formado ahora produce un mensaje claro |

## 3. Pruebas

El testing formal se documenta en la Evidencia 3 de Testeo de Software (parte A): 32 casos de prueba (CF-01 a CF-20, integración INT-01 a INT-06 y usabilidad US-01 a US-06), su resultado, la evidencia visual y el reporte de defectos DEF-01 a DEF-18. Esta sección resume lo que ese trabajo encontró y qué se corrigió en el MVP.

### Defectos corregidos en esta versión

| Defecto | Qué pasaba | Corrección | Casos a reverificar |
|---|---|---|---|
| DEF-10 | Una sola lectura de humedad faltante mostraba "No hay lectura del suelo", aunque la anterior era de 5 minutos antes | Se usa la última lectura válida hasta 60 minutos; recién después se avisa que el sensor no envía datos. La línea técnica indica "última lectura hace X min" | CF-07 |
| DEF-11 | Riegos que sí entregaron algo de agua (98 L, 92 L y 63 L) se rotulaban "Sin agua" | Cada riego tiene un resultado: "Correcto", "Sin agua" (menos de 1 L) o "Caudal insuficiente" (menos de 0,5 L por minuto). El titular distingue "no llega agua" de "llega muy poca agua" | CF-06, CF-12 |
| DEF-13 | El mensaje de error mostraba la ruta interna del servidor | El mensaje nombra solo el archivo y la carpeta | CF-19 |
| DEF-16 | Riegos y Agua mostraban datos posteriores al "ahora" en un riego en curso (95 h y 62,8 L, contra 35 h y 61 L en Hoy) | Los riegos se calculan solo con lo ocurrido hasta el momento elegido; las tres pantallas coinciden | CF-06, INT-02 |
| DEF-18 | Dependencias sin tope de versión y Altair sin declarar | `requirements.txt` con rangos acotados y Altair declarado | INT-06 |

Cada corrección suma una comprobación automática de regresión. El repositorio incluye 56 comprobaciones con pytest (`tests/`), que se ejecutan con `pytest`. Sirven para detectar regresiones después de cada cambio y no reemplazan la ejecución de los casos.

### Defectos que siguen abiertos

| Defecto | Por qué queda abierto |
|---|---|
| DEF-06 | Las Evidencias 1 y 2 hablan de 66 días y unos 410 L diarios; el ETL cuenta 65 días y 417 L. Es una corrección de los informes anteriores, no del MVP |
| DEF-12 | Una lectura igual al valor del P15 cae en el percentil 14 por los empates del sensor y dispara "Hay que regar". Es una decisión de criterio pendiente con el analista |
| DEF-14 | La app falla con archivos CSV muy cortos o de otro período, por valores fijos de la demostración. Se resuelve al pasar a datos en vivo (Fase 2) |
| DEF-15 | "Avanzar el tiempo" recorre la serie completa en unos 19 minutos y no tiene control de velocidad. Es una mejora de la demostración |
| DEF-17 | Inconsistencia en la identificación del grupo entre documentos |

### Errores encontrados al integrar (antes del testing formal)

| # | Error | Estado |
|---|---|---|
| 1 | El `app.py` buscaba la carpeta `datos/` y en el repositorio se llama `Datos/`. En Windows funciona; en el servidor de Streamlit, que distingue mayúsculas, la app no habría encontrado los CSV | Corregido: acepta los dos nombres |
| 2 | La posición en la serie se guardaba reasignando el valor del deslizador; el indicador podía quedar desfasado y la posición perderse al cambiar de vista | Corregido: la posición vive en el estado de la sesión |
| 3 | Si faltaba un CSV, la app mostraba un error técnico de Python | Corregido: mensaje que indica qué archivo falta |
| 4 | Se podía poner el nivel de holgura por debajo del de acción y la franja de atención desaparecía sin aviso | Corregido: aviso en pantalla |
| 5 | La tabla de trazabilidad redondeaba también la columna de fecha y generaba una advertencia de pandas | Corregido |
| 6 | Los casos CF-03 y CF-05 a CF-08 esperaban leyendas y controles del prototipo anterior | Corregido: casos reescritos en la Evidencia 3 de Testeo de Software |
| 7 | Las primeras versiones se leían como un tablero de análisis de datos, no como un producto para el operario | Corregido: interfaz rediseñada para el usuario final |
| 8 | El menú lateral se abría desplegado en el celular y tapaba la pantalla | Corregido: en pantallas chicas arranca plegado |

### Situaciones de la demostración

| Situación | Momento | Qué muestra |
|---|---|---|
| Una mañana normal | 16/08/2022 07:00 | "Todavía no hace falta regar" |
| Riego en marcha | 14/08/2022 18:00 | "Regando" |
| Hay que regar | 16/09/2022 12:40 | "Hay que regar" |
| Riego abierto sin agua | 04/09/2022 08:00 | "El riego está abierto, pero no llega agua" (0 L) |
| Riego con muy poca agua | 01/09/2022 21:50 | "El riego está abierto, pero llega muy poca agua" (63 L en 4 días) |
| Agua que sale sin orden | 03/08/2022 07:00 | Aviso "Fuga / Agua no atribuida" |

## 4. Limitaciones conocidas

1. **Datos históricos, no en vivo.** La vista de estado reproduce la serie de 2022.
2. **Un solo campo, un solo cultivo, 65 días de invierno.** Los resultados no se pueden extrapolar.
3. **Sensor sin calibrar.** El percentil indica qué tan seco está el suelo respecto de su propio historial, no cuánta agua contiene.
4. **El percentil usa toda la serie**, incluidas lecturas posteriores al momento mostrado. Con un sensor en vivo se calcularía sobre el historial acumulado y los primeros días serían poco confiables.
5. **La auditoría detecta, no diagnostica.** El agua sin orden es compatible con una fuga, con riego manual o con un segundo sector que comparte el caudalímetro.
6. **El agua comandada se mide en tiempo, no en litros.** No se conoce el caudal nominal de la instalación.
7. **Los niveles de aviso son criterios del equipo**: se avisa de agua sin orden cuando en 24 h sale tanta como en un riego normal del lote (1.054 L, la mediana de los riegos con agua), y de riego sin agua por debajo de 0,5 L/min. No están validados con el productor.
8. **Cortes de telemetría.** Lo que el caudalímetro acumula durante un corte (2.056 L) queda fuera del total auditado.
9. **Sin usuarios ni persistencia.** Los umbrales modificados valen para esa sesión.
10. **Hosting gratuito.** La app se suspende tras un tiempo sin visitas y hay que reactivarla.
11. **Las fechas de los gráficos aparecen en inglés** (formato del componente de Streamlit).

## 5. Guion para la presentación (15 minutos)

| Min | Bloque | Qué mostrar |
|---|---|---|
| 0–2 | Alcance | Los dos pain points; qué resuelve y qué quedó fuera (sección 1) |
| 2–5 | Arquitectura | Diagrama; qué se mantuvo, qué se sacó, qué se agregó (sección 2) |
| 5–7 | Testing | Casos, defectos encontrados y corregidos (sección 3 y Evidencia 3 de Testeo de Software) y limitaciones (sección 4) |
| 7–12 | MVP en vivo | Desde el link: Hoy → situaciones (riego en marcha, hay que regar, riego abierto sin agua, riego con muy poca agua, agua sin orden) → Avanzar el tiempo → Agua → Riegos |
| 12–13 | Link | Compartirlo en el chat para que el curso entre |
| 13–15 | Consultas | |
