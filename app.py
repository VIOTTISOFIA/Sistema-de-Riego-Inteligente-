"""
Sistema de Riego Inteligente - MVP Modulo C (tablero)
HU-01 / RF-11: visualizacion del estado actual de humedad del suelo.

Grupo 2 - Practica Profesionalizante I - ISPC 2026
Evidencia 2: primera version funcionando.

Recorrido de punta a punta que demuestra la app:
    series IoT crudas  ->  ETL (integracion por clave temporal)
                       ->  percentil sobre la propia serie historica
                       ->  indicador con semaforo para el tecnico agricola

Ejecucion:
    streamlit run app.py
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------

st.set_page_config(page_title="Riego Inteligente | Estado del suelo",
                   page_icon="*", layout="wide",
                   initial_sidebar_state="expanded")

# Carpeta donde estan D_moisture.csv, D_valve.csv y D_flowmeter.csv
RUTA = Path("datos") if Path("datos").exists() else Path(".")

# Zona horaria del campo: Paraguay rigio en UTC-4 durante julio-septiembre 2022
OFFSET_LOCAL = pd.Timedelta(hours=4)

# Umbral de accion definido en la Evidencia 1: percentil 15 de la propia serie
UMBRAL_ACCION_DEFECTO = 15
UMBRAL_HOLGURA_DEFECTO = 40

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1150px;}
  .tarjeta {border-radius: 14px; padding: 1.1rem 1.3rem; border: 1px solid #2c3440;
            background: #161b22;}
  .etiqueta {font-size: .78rem; letter-spacing: .09em; text-transform: uppercase;
             color: #8b98a8; margin-bottom: .35rem;}
  .valor {font-size: 2.6rem; font-weight: 700; line-height: 1.1;}
  .pie {font-size: .8rem; color: #8b98a8; margin-top: .3rem;}
  .semaforo {border-radius: 14px; padding: 1.4rem 1.5rem; color: #0d1117; font-weight: 700;}
  .flujo {font-size: .82rem; color: #8b98a8; border-left: 3px solid #2c3440;
          padding-left: .8rem; margin-bottom: 1.2rem;}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# ETL - se ejecuta una sola vez y queda en cache
# ----------------------------------------------------------------------

@st.cache_data(show_spinner="Ejecutando el ETL sobre las series IoT...")
def cargar_datos() -> pd.DataFrame:
    """Reproduce el ETL documentado en la seccion 2 del notebook V2.

    Decisiones que se sostienen aca:
      - D_valve es la tabla base por ser la serie mas densa (cada 5 min).
      - La union se hace por marca temporal con merge_asof y tolerancia,
        nunca por posicion de fila.
      - litres es un acumulador: se diferencia para obtener volumen por intervalo.
      - Los faltantes son cortes reales de telemetria: se conservan como NaN.
    """

    def cargar(archivo: str, columna: str) -> pd.DataFrame:
        d = pd.read_csv(RUTA / archivo)
        d["ts_utc"] = pd.to_datetime(d["time_stamp"], format="%d-%b-%Y %H:%M:%S")
        return d[[columna, "ts_utc"]].sort_values("ts_utc").reset_index(drop=True)

    valvula = cargar("D_valve.csv", "relay")
    caudal = cargar("D_flowmeter.csv", "litres")
    humedad = cargar("D_moisture.csv", "moisture")

    df = valvula.copy()
    df = pd.merge_asof(df, caudal, on="ts_utc",
                       tolerance=pd.Timedelta("3min"), direction="nearest")
    df = pd.merge_asof(df, humedad, on="ts_utc",
                       tolerance=pd.Timedelta("20min"), direction="nearest")

    df["ts_local"] = df["ts_utc"] - OFFSET_LOCAL
    df["litros_intervalo"] = df["litres"].diff().clip(lower=0)

    # Interrupciones de telemetria (lecturas separadas por mas de 10 minutos)
    df["gap_min"] = df["ts_utc"].diff().dt.total_seconds() / 60
    df["post_gap"] = df["gap_min"] > 10

    # Percentil de cada lectura dentro de la propia serie historica del sensor.
    # Se usa el percentil y no el valor crudo porque el sensor capacitivo esta
    # sin calibrar: su rango util real es ~68,6 a 86,9 y no 0 a 100.
    df["percentil"] = df["moisture"].rank(pct=True) * 100

    return df


@st.cache_data
def tabla_percentiles(serie: pd.Series) -> pd.Series:
    """Valores de humedad cruda correspondientes a cada percentil de referencia."""
    return pd.Series({p: np.nanpercentile(serie.dropna(), p)
                      for p in (5, 15, 25, 50, 75, 95)})


def clasificar(percentil: float, umbral_accion: int, umbral_holgura: int):
    """Traduce el percentil a un estado accionable para el tecnico."""
    if pd.isna(percentil):
        return "SIN LECTURA", "#6e7681", "Telemetria interrumpida"
    if percentil < umbral_accion:
        return "RIEGO NECESARIO", "#f85149", "El suelo esta en la franja mas seca de su historico"
    if percentil < umbral_holgura:
        return "ATENCION", "#f0a848", "Descendiendo hacia el umbral de accion"
    return "OPTIMO", "#3fb950", "No hace falta regar"


# ----------------------------------------------------------------------
# Estado de la sesion: cursor que recorre la serie historica
# ----------------------------------------------------------------------

df = cargar_datos()
referencia = tabla_percentiles(df["moisture"])

if "cursor" not in st.session_state:
    st.session_state.cursor = 200
    st.session_state.reproduciendo = False

with st.sidebar:
    st.subheader("Panel de control")
    st.caption("La telemetria del campo corresponde a julio-septiembre de 2022. "
               "El tablero la reproduce como si llegara en vivo.")

    velocidad = st.select_slider("Velocidad de reproduccion",
                                 options=["Lenta", "Normal", "Rapida"], value="Normal")
    paso = {"Lenta": 3, "Normal": 12, "Rapida": 60}[velocidad]   # lecturas por tick
    intervalo = 1.5

    st.subheader("Umbrales")
    umbral_accion = st.number_input("Percentil de accion (rojo)", 1, 50,
                                    UMBRAL_ACCION_DEFECTO)
    umbral_holgura = st.number_input("Percentil de holgura (verde)", 20, 90,
                                     UMBRAL_HOLGURA_DEFECTO)

    st.divider()
    st.caption("Equivalencia en lectura cruda del sensor")
    st.dataframe(referencia.round(2).rename("humedad (%)").rename_axis("percentil"))


# ----------------------------------------------------------------------
# Controles de reproduccion, en el cuerpo principal para que queden
# visibles en las capturas junto con el indicador
# ----------------------------------------------------------------------

st.title("Estado actual del suelo")
st.markdown(
    '<div class="flujo">HU-01 &middot; RF-11 &nbsp;|&nbsp; '
    'D_moisture + D_valve + D_flowmeter &rarr; ETL por clave temporal &rarr; '
    'percentil sobre la serie propia &rarr; indicador</div>',
    unsafe_allow_html=True)

ctrl_1, ctrl_2, ctrl_3 = st.columns([6, 1.3, 1.3])

with ctrl_1:
    st.session_state.cursor = st.slider(
        "Momento de la serie", 200, len(df) - 1, st.session_state.cursor,
        help="Posicion de la lectura dentro de la telemetria historica del campo.")

with ctrl_2:
    st.write("")
    if st.button("Pausar" if st.session_state.reproduciendo else "Reproducir",
                 width="stretch", type="primary"):
        st.session_state.reproduciendo = not st.session_state.reproduciendo
        st.rerun()

with ctrl_3:
    st.write("")
    if st.button("Reiniciar", width="stretch"):
        st.session_state.cursor = 200
        st.session_state.reproduciendo = False
        st.rerun()

st.write("")

# ----------------------------------------------------------------------
# Lectura "actual"
# ----------------------------------------------------------------------

i = st.session_state.cursor
actual = df.iloc[i]
ventana = df.iloc[max(0, i - 288): i + 1]          # ultimas ~24 h (5 min por registro)

estado, color, detalle = clasificar(actual["percentil"], umbral_accion, umbral_holgura)

izq, der = st.columns([1.15, 1])

with izq:
    st.markdown(
        f'<div class="semaforo" style="background:{color}">'
        f'<div style="font-size:.85rem;letter-spacing:.1em">ESTADO</div>'
        f'<div style="font-size:2.3rem;line-height:1.2">{estado}</div>'
        f'<div style="font-weight:500;font-size:.92rem">{detalle}</div></div>',
        unsafe_allow_html=True)

with der:
    p = actual["percentil"]
    st.markdown(
        f'<div class="tarjeta"><div class="etiqueta">Humedad relativa del suelo</div>'
        f'<div class="valor" style="color:{color}">'
        f'{"P" + format(p, ".0f") if pd.notna(p) else "s/d"}</div>'
        f'<div class="pie">Lectura cruda del sensor: '
        f'{actual["moisture"]:.2f} %<br>'
        f'{actual["ts_local"]:%d/%m/%Y %H:%M} (hora local del campo)</div></div>',
        unsafe_allow_html=True)

st.write("")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Electrovalvula", "Abierta" if actual["relay"] == 1 else "Cerrada")
with c2:
    st.metric("Agua aplicada (24 h)", f'{ventana["litros_intervalo"].sum():,.0f} L')
with c3:
    minimo = ventana["percentil"].min()
    st.metric("Percentil minimo (24 h)",
              f"P{minimo:.0f}" if pd.notna(minimo) else "s/d")

st.subheader("Evolucion de las ultimas 24 horas")
serie = (ventana.set_index("ts_local")["percentil"].dropna())
if not serie.empty:
    grafico = pd.DataFrame({"Percentil de humedad": serie,
                            "Umbral de accion": umbral_accion})
    st.line_chart(grafico, color=["#f85149", "#58a6ff"], height=260)
else:
    st.info("No hay lecturas de humedad en esta ventana: telemetria interrumpida.")

if actual["post_gap"]:
    st.warning(f'Interrupcion de telemetria previa a esta lectura: '
               f'{actual["gap_min"]:.0f} minutos sin datos.')

with st.expander("Trazabilidad: del dato crudo al indicador"):
    st.markdown(
        "El tablero no lee un archivo preprocesado. Al iniciarse ejecuta el mismo ETL "
        "documentado en la seccion 2 del notebook V2 sobre los tres CSV originales de "
        "telemetria. A la izquierda, las primeras filas de `D_valve.csv` tal como vienen "
        "del repositorio de origen; a la derecha, el resultado de la integracion por "
        "marca temporal que alimenta la pantalla."
    )
    crudo, integrado = st.columns(2)
    with crudo:
        st.caption("D_valve.csv (crudo)")
        st.dataframe(pd.read_csv(RUTA / "D_valve.csv").head(6), hide_index=True)
    with integrado:
        st.caption("Dataset integrado en memoria")
        vista = df[["ts_local", "relay", "moisture", "percentil",
                    "litros_intervalo"]].iloc[i - 5: i + 1].copy()
        vista[["percentil", "litros_intervalo"]] = vista[["percentil",
                                                          "litros_intervalo"]].round(2)
        st.dataframe(vista, hide_index=True)

with st.expander("Por que se muestra un percentil y no el porcentaje crudo"):
    st.markdown(
        "El sensor capacitivo del campo no esta calibrado en unidades de humedad "
        "volumetrica: sus lecturas se mueven entre 68,6 % y 86,9 % y adoptan solo "
        "44 valores distintos. Leer *72 % de humedad* como si fuera una medicion "
        "absoluta induce a error. El percentil ubica la lectura dentro de la propia "
        "serie historica del sensor, que es una referencia valida y no depende de la "
        "calibracion. La decision esta documentada en el apartado 7 de la Evidencia 1."
    )

st.caption(f'ETL sobre {len(df):,} registros integrados por clave temporal | '
           f'periodo {df.ts_local.min():%d/%m/%Y} - {df.ts_local.max():%d/%m/%Y} | '
           f'Grupo 11 - ISPC 2026')


# ----------------------------------------------------------------------
# Actualizacion automatica: la pantalla se refresca sin recargar la pagina
# (criterio de aceptacion, escenario 1 de la HU-01)
# ----------------------------------------------------------------------

if st.session_state.reproduciendo:
    time.sleep(intervalo)
    st.session_state.cursor = min(st.session_state.cursor + paso, len(df) - 1)
    if st.session_state.cursor >= len(df) - 1:
        st.session_state.reproduciendo = False
    st.rerun()
