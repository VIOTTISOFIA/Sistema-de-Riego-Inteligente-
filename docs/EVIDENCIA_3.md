# Evidencia 3 — Integración del prototipo en un MVP beta

Sistema de Riego Inteligente · Grupo 11 · Práctica Profesionalizante I · ISPC 2026

**Link del MVP:** `PEGAR_AQUI_EL_LINK_DE_STREAMLIT`

## 1. Alcance del MVP

### Qué resuelve

| Funcionalidad | Pantalla | Requerimientos | Pain point |
|---|---|---|---|
| Respuesta a "¿hay que regar?" en una frase, con la humedad del suelo, el estado del riego y los avisos | Hoy | HU-01, RF-10, RF-11 | PP-01, PP-02 |
| Agua usada, en riegos y sin orden de riego, total y por día | Agua | RF-02, RF-03, RF-04, RF-06, RF-13 | PP-01 |
| Salidas de agua con el riego cerrado ("agua fantasma") | Agua y aviso en Hoy | RF-05 | PP-01 |
| Riegos que no entregaron agua (dirección inversa, propuesta en la Evidencia 2) | Titular en Hoy, y Agua | RF-05 simétrico | PP-01 |
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

El testing formal del proyecto se ejecuta según el plan de pruebas definido en Testeo de Software (casos CF-01 a CF-08). Esta sección registra el estado de esos casos y lo que se verificó al integrar esta versión.

### Casos funcionales del plan de pruebas

Pendientes de ejecución formal por el equipo sobre la versión publicada. La columna de observaciones anticipa qué va a encontrar quien los ejecute.

| Caso | Qué verifica | Dónde se prueba en la app | Observación previa | Resultado |
|---|---|---|---|---|
| CF-01 | Agua con válvula cerrada se cuenta como no atribuida | Situación "Agua que sale sin orden" → Hoy y Agua | El aviso "Fuga / Agua no atribuida" aparece cuando en 24 h sale tanta agua como en un riego normal (1.054 L) | |
| CF-02 | Agua con válvula abierta se cuenta como atribuida | Agua, columna "En riegos" | | |
| CF-03 | 72,65 % se muestra como P56, en verde | Hoy, fecha 13/07/2022 00:00 | El titular dice "No hace falta regar"; "ÓPTIMO" y "P56" figuran en la línea técnica | |
| CF-04 | Balance diario del 30/08/2022 | Agua, gráfico "Día por día" | Ya no se elige un día suelto: se ve dentro del período de 7 o 30 días | |
| CF-05 | Por debajo de P15 el indicador pasa a rojo | Situación "Hay que regar" | El titular dice "Hay que regar"; "RIEGO NECESARIO" figura en la línea técnica | |
| CF-06 | Orden de riego sin caudal, 29 al 31/08 | Situación "Riego abierto sin agua" | El titular dice "El riego está abierto, pero no llega agua", no la leyenda del plan | |
| CF-07 | Lecturas nulas no rompen la app | Hoy, fecha 14/07/2022 19:30 | El titular dice "No hay lectura del suelo", no "Señal de telemetría pausada" | |
| CF-08 | La pantalla se actualiza sin recargar | Hoy, botón "Avanzar el tiempo" | El control ahora es por fecha y hora, no por posición 13.212 a 13.284 | |

### Verificación automática de apoyo

Como herramienta de apoyo, el repositorio incluye 49 comprobaciones automáticas con pytest (`tests/`), que se ejecutan con el comando `pytest`. Verifican el ETL, las cifras de la auditoría y que cada vista de la app carga y responde. Sirven como pruebas de regresión: se vuelven a correr después de cada cambio. No reemplazan la ejecución de los casos funcionales.

### Recorrido de punta a punta sobre la versión publicada

Pendiente: repetirlo sobre la URL pública, desde una computadora y un celular que no sean del equipo.

| Paso | Resultado esperado | Resultado |
|---|---|---|
| Abrir el link sin iniciar sesión | Carga la pantalla Hoy con una respuesta | |
| Pulsar "Avanzar el tiempo" | La pantalla se actualiza sola | |
| Elegir la situación "Riego abierto sin agua" | Titular rojo: el riego está abierto, pero no llega agua | |
| Abrir Agua y elegir "Toda la campaña" con la fecha al final de la serie | 77.218 L usados, 27.094 L sin orden de riego | |
| Cambiar el período a 7 días | Cambian las cifras y el gráfico | |
| Descargar el detalle diario | Se descarga un CSV | |
| Abrir Riegos | Lista de riegos de los últimos 30 días | |
| Abrir desde un celular | La app se puede usar con el menú plegado | |

### Errores encontrados al integrar

| # | Error | Estado |
|---|---|---|
| 1 | El `app.py` buscaba la carpeta `datos/` y en el repositorio se llama `Datos/`. En Windows funciona; en el servidor de Streamlit, que distingue mayúsculas, la app no habría encontrado los CSV | Corregido: acepta los dos nombres |
| 2 | La posición en la serie se guardaba reasignando el valor del deslizador; el indicador podía quedar desfasado y la posición perderse al cambiar de vista | Corregido: la posición vive en el estado de la sesión |
| 3 | Si faltaba un CSV, la app mostraba un error técnico de Python | Corregido: mensaje que indica qué archivo falta |
| 4 | Se podía poner el percentil de holgura por debajo del de acción y la franja de atención desaparecía sin aviso | Corregido: aviso en pantalla |
| 5 | La tabla de trazabilidad redondeaba también la columna de fecha y generaba una advertencia de pandas | Corregido |
| 6 | Los informes anteriores hablan de 66 días y unos 410 L diarios no atribuidos. El ETL cuenta 65 días con datos, lo que da 417 L diarios | Abierto: la app muestra el valor calculado |
| 7 | Los casos CF-03 y CF-05 a CF-08 esperan leyendas y controles del prototipo anterior, que la interfaz para el operario reemplazó | Abierto: actualizar el texto esperado en el plan de pruebas |
| 9 | El menú lateral se abría desplegado en el celular y tapaba la pantalla | Corregido: en pantallas chicas arranca plegado |
| 8 | Las primeras versiones se leían como un tablero de análisis de datos, no como un producto para el operario: jerga, exceso de información y controles de simulación mezclados con el contenido | Corregido: interfaz rediseñada para el usuario final |

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
| 5–7 | Testing | Según la consigna de Testeo de Software; errores encontrados y limitaciones (secciones 3 y 4) |
| 7–12 | MVP en vivo | Desde el link: Hoy → situaciones (riego en marcha, hay que regar, riego abierto sin agua, agua sin orden) → Avanzar el tiempo → Agua → Riegos |
| 12–13 | Link | Compartirlo en el chat para que el curso entre |
| 13–15 | Consultas | |
