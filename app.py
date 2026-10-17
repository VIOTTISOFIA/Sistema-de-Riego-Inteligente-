"""
Riego Inteligente - MVP beta
Modulo A (auditoria hidrica) + Modulo C (tablero para el operario)

Practica Profesionalizante I - ISPC 2026 - Evidencia 3

Pantallas, pensadas para el tecnico u operario de riego:
    Hoy       ¿Hay que regar? ¿Esta llegando el agua? ¿Se esta perdiendo agua?
    Agua      Cuanta agua se uso y cuanta salio sin una orden de riego
    Riegos    Historial de riegos
    Ajustes   Niveles de aviso
    Acerca    Alcance, limitaciones y trazabilidad de esta version

La telemetria es historica (2022). El panel "Demostracion" de la barra
lateral fija el momento que el producto trata como "ahora"; todas las
pantallas muestran solo lo ocurrido hasta ese momento.

Ejecucion local:
    streamlit run app.py
"""

import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import etl

st.set_page_config(page_title="Riego Inteligente", page_icon="💧", layout="centered",
                   initial_sidebar_state="auto")

BASE = Path(__file__).parent
# En Linux (el servidor) "Datos" y "datos" son carpetas distintas: se aceptan ambas
RUTA = next((BASE / c for c in ("Datos", "datos") if (BASE / c).exists()), BASE)

# Umbral de accion definido en la Evidencia 1: percentil 15 de la propia serie
UMBRAL_ACCION_DEFECTO = 15
UMBRAL_HOLGURA_DEFECTO = 40
AHORA_INICIAL = pd.Timestamp("2022-08-16 07:00")   # una manana cualquiera de la campana

TINTA, AGUA, HOJA, ROJO, AMBAR, GRIS = (
    "#14261F", "#1F6FB2", "#2E7D4F", "#C2382B", "#B97A0E", "#6B7A74")
COLOR_NIVEL = {"critico": ROJO, "atencion": AMBAR, "regando": AGUA, "bien": HOJA,
               "sin_dato": GRIS}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

VISTAS = ["Hoy", "Agua", "Riegos", "Ajustes", "Acerca de esta versión"]

# Situaciones reales de la serie para recorrer el producto en una demostracion
SITUACIONES = {
    "Una mañana normal": pd.Timestamp("2022-08-16 07:00"),
    "Riego en marcha": pd.Timestamp("2022-08-14 18:00"),
    "Hay que regar": pd.Timestamp("2022-09-16 12:40"),
    "Riego abierto sin agua": pd.Timestamp("2022-09-04 08:00"),
    "Riego con muy poca agua": pd.Timestamp("2022-09-01 21:50"),
    "Agua que sale sin orden": pd.Timestamp("2022-08-03 07:00"),
}

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@600;700&display=swap');
  html, body, .stApp, .stApp p, .stApp label, .stApp button, .stApp input,
  [data-testid="stMetricValue"], [data-testid="stMarkdownContainer"] {
      font-family: 'Barlow', system-ui, sans-serif;}
  .stApp h1, .stApp h2, .stApp h3 {font-family: 'Barlow Condensed', 'Barlow', sans-serif;
      font-weight: 700; letter-spacing: .005em;}
  .block-container {padding-top: 2.6rem; max-width: 760px;}
  .momento {color: #6B7A74; font-size: .95rem; margin-bottom: .5rem;}
  .titular {border-radius: 6px; padding: 1.5rem 1.6rem 1.4rem; color: #fff;}
  .titular .grande {font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
      font-size: clamp(2.2rem, 7vw, 3.3rem); line-height: 1.02;}
  .titular .apoyo {font-size: 1.08rem; margin-top: .55rem; max-width: 34em;}
  .fila {display: flex; gap: .9rem; padding: .85rem 0; border-bottom: 1px solid #DCE3DE;}
  .fila:last-child {border-bottom: none;}
  .punto {flex: none; width: .7rem; height: .7rem; border-radius: 50%; margin-top: .42rem;}
  .fila .que {font-weight: 600;}
  .fila .como {color: #3D4F47;}
  .aviso {border-left: 5px solid; padding: .75rem 1rem; background: #fff;
      margin: .6rem 0; border-radius: 0 6px 6px 0;}
  .aviso .hacer {margin-top: .3rem; color: #3D4F47;}
  .barra {position: relative; height: 16px; border-radius: 8px; margin: 1.5rem 0 .3rem;}
  .barra .marca {position: absolute; top: -7px; width: 4px; height: 30px;
      background: #14261F; border-radius: 2px; transform: translateX(-2px);}
  .extremos {display: flex; justify-content: space-between; color: #6B7A74;
      font-size: .85rem;}
  .tecnico {color: #6B7A74; font-size: .85rem; margin-top: .5rem;}
  .demo {font-size: .82rem; color: #6B7A74;}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Formato
# ----------------------------------------------------------------------

def litros(x: float) -> str:
    """12345.6 -> '12.346 L'"""
    return f"{x:,.0f}".replace(",", ".") + " L"


def duracion(minutos: float) -> str:
    h, m = divmod(int(minutos), 60)
    if h >= 48:
        return f"{h // 24} días"
    if h >= 3:
        return f"{h + (m >= 30)} h"
    return (f"{h} h {m:02d} min" if m else f"{h} h") if h else f"{m} min"


def hace(minutos: float) -> str:
    return "hace " + duracion(minutos)


def fecha_larga(ts) -> str:
    ts = ts.round("5min")
    return f"{DIAS[ts.weekday()].capitalize()} {ts:%d/%m/%Y}, {ts:%H:%M} h"


# ----------------------------------------------------------------------
# Datos: el ETL corre una vez por despliegue y queda en cache
# ----------------------------------------------------------------------

@st.cache_data(show_spinner="Cargando los datos del campo...")
def cargar_datos() -> pd.DataFrame:
    return etl.ejecutar_etl(RUTA)


@st.cache_data
def cargar_eventos() -> pd.DataFrame:
    return etl.eventos_riego(cargar_datos())


try:
    df = cargar_datos()
except etl.DatosInvalidos as e:
    st.error(f"No se pudo iniciar la aplicación. {e}")
    st.info("Hacen falta D_valve.csv, D_flowmeter.csv y D_moisture.csv en la carpeta "
            "`Datos/` o junto a `app.py`.")
    st.stop()

eventos = cargar_eventos()


@st.cache_data(max_entries=64)
def eventos_hasta(i: int) -> pd.DataFrame:
    return etl.eventos_riego(cargar_datos().iloc[: i + 1])
RIEGO_TIPICO = etl.riego_tipico(eventos)
T_MIN, T_MAX = df["ts_local"].iloc[300].ceil("h"), df["ts_local"].iloc[-1]


def posicion(ts) -> int:
    """Indice de la ultima lectura disponible en el momento ts."""
    return max(int(df["ts_local"].searchsorted(pd.Timestamp(ts), side="right")) - 1, 300)


ss = st.session_state
if "ahora" not in ss:
    ss.ahora = AHORA_INICIAL
    ss.reproduciendo = False
    ss.umbral_accion = UMBRAL_ACCION_DEFECTO
    ss.umbral_holgura = UMBRAL_HOLGURA_DEFECTO


# ----------------------------------------------------------------------
# Barra lateral: navegacion del producto + panel de demostracion
# ----------------------------------------------------------------------

def mover_ahora():
    ss.ahora = pd.Timestamp(ss.ahora_slider)


def alternar_reproduccion():
    ss.reproduciendo = not ss.reproduciendo


def ir_a_situacion():
    if ss.situacion in SITUACIONES:
        ss.ahora = SITUACIONES[ss.situacion]
        ss.reproduciendo = False
    ss.situacion = None


with st.sidebar:
    st.markdown("## 💧 Riego Inteligente")
    st.caption("Lote de frutilla · La Colmena, Paraguay")
    vista = st.radio("Ir a", VISTAS, key="vista", label_visibility="collapsed")

    st.divider()
    st.markdown("**Demostración**")
    st.markdown('<div class="demo">Los datos son telemetría real de julio a septiembre '
                'de 2022. Acá elegís qué momento se muestra como «ahora».</div>',
                unsafe_allow_html=True)
    ss.ahora_slider = ss.ahora.to_pydatetime()
    st.slider("Fecha y hora", T_MIN.to_pydatetime(), T_MAX.to_pydatetime(),
              key="ahora_slider", step=pd.Timedelta(minutes=30).to_pytimedelta(),
              format="DD/MM HH:mm", on_change=mover_ahora)
    st.button("Pausar" if ss.reproduciendo else "Avanzar el tiempo",
              width="stretch", on_click=alternar_reproduccion)
    st.selectbox("Ir a una situación", list(SITUACIONES), index=None, key="situacion",
                 placeholder="Elegir…", on_change=ir_a_situacion)

if vista != VISTAS[0]:
    ss.reproduciendo = False

# "Ahora": todo el producto ve solo lo ocurrido hasta este momento
I = posicion(ss.ahora)
hist = df.iloc[: I + 1]
# DEF-16: los riegos se arman sobre el historico recortado, asi una orden en curso
# muestra solo lo ocurrido hasta "ahora" en todas las pantallas
ev_hist = eventos_hasta(I)
S = etl.situacion_actual(df, I, ss.umbral_accion)
AHORA = S["ts"]


def encabezado(titulo: str):
    st.markdown(f'<div class="momento">{fecha_larga(AHORA)}</div>',
                unsafe_allow_html=True)
    st.title(titulo)


# ======================================================================
# Hoy
# ======================================================================

def barra_humedad(p: float, accion: float, holgura: float) -> str:
    fondo = (f"linear-gradient(90deg, #E3A39B 0 {accion}%, #EBCF94 {accion}% {holgura}%, "
             f"#A9D3B6 {holgura}% 100%)")
    return (f'<div class="barra" style="background:{fondo}">'
            f'<div class="marca" style="left:{p:.0f}%"></div></div>'
            f'<div class="extremos"><span>Seco</span><span>Húmedo</span></div>')


def grafico_humedad(ventana: pd.DataFrame, ev: pd.DataFrame, umbral: float):
    t0, t1 = ventana["ts_local"].min(), ventana["ts_local"].max()
    dominio = alt.Scale(domain=[t0, t1])
    ordenes = ev[(ev["fin"] >= t0) & (ev["inicio"] <= t1)].copy()
    ordenes["desde"] = ordenes["inicio"].clip(lower=t0)
    ordenes["hasta"] = (ordenes["fin"] + pd.Timedelta(minutes=5)).clip(upper=t1)
    ordenes["Riego"] = ordenes["sin_caudal"].map({True: "Con problemas", False: "Con agua"})
    franjas = alt.Chart(ordenes).mark_rect(opacity=0.3).encode(
        x=alt.X("desde:T", scale=dominio), x2="hasta:T",
        color=alt.Color("Riego:N",
                        scale=alt.Scale(domain=["Con agua", "Con problemas"],
                                        range=[AGUA, ROJO]),
                        legend=alt.Legend(orient="bottom", title="Riegos")),
        tooltip=[alt.Tooltip("inicio:T", format="%d/%m %H:%M", title="Inicio"),
                 alt.Tooltip("dur_min:Q", title="Duración (min)"),
                 alt.Tooltip("litros:Q", format=".0f", title="Litros")])
    linea = alt.Chart(ventana.dropna(subset=["percentil"])).mark_line(
        color=TINTA, strokeWidth=2, interpolate="step-after").encode(
        x=alt.X("ts_local:T", title=None, scale=dominio,
                axis=alt.Axis(format="%d/%m %Hh", labelAngle=0, tickCount=6)),
        y=alt.Y("percentil:Q", title="Humedad (0 seco · 100 húmedo)",
                scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip("ts_local:T", format="%d/%m %H:%M", title="Hora"),
                 alt.Tooltip("percentil:Q", format=".0f", title="Humedad")])
    limite = alt.Chart(pd.DataFrame({"y": [umbral]})).mark_rule(
        color=ROJO, strokeDash=[5, 4]).encode(y="y:Q")
    return alt.layer(franjas, linea, limite)


def fila(color: str, que: str, como: str) -> str:
    return (f'<div class="fila"><div class="punto" style="background:{color}"></div>'
            f'<div><div class="que">{que}</div><div class="como">{como}</div></div></div>')


def vista_hoy():
    nivel, titulo, apoyo = etl.titular(S, ss.umbral_holgura)
    # El titular ya dice lo mas urgente: los avisos muestran solo lo que agrega algo
    cubiertos = {"Orden de riego emitida sin caudal detectado", "Riego necesario"}
    if nivel == "sin_dato":
        cubiertos.add("Señal de telemetría pausada")
    avisos = [a for a in etl.alertas(S, RIEGO_TIPICO) if a[1] not in cubiertos]

    st.markdown(f'<div class="momento">{fecha_larga(AHORA)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="titular" style="background:{COLOR_NIVEL[nivel]}">'
                f'<div class="grande">{titulo}</div>'
                f'<div class="apoyo">{apoyo}</div></div>', unsafe_allow_html=True)

    # ---- Suelo ----
    st.subheader("Humedad del suelo")
    p = S["percentil"]
    if pd.isna(p):
        st.markdown("Sin lectura del sensor en este momento.")
    else:
        estado = etl.clasificar(p, ss.umbral_accion, ss.umbral_holgura)[0]
        st.markdown(barra_humedad(p, ss.umbral_accion, ss.umbral_holgura),
                    unsafe_allow_html=True)
        previa = (f' · última lectura {hace(S["min_sin_humedad"])}'
                  if S["min_sin_humedad"] > 0 else "")
        st.markdown(f'<div class="tecnico">Estado: {estado} · P{p:.0f} de la serie del '
                    f'sensor · lectura {S["humedad"]:.2f} %'.replace(".", ",")
                    + ' · regar por debajo de P' + f'{ss.umbral_accion}{previa}</div>',
                    unsafe_allow_html=True)

    # ---- Riego y agua: dos comprobaciones en lenguaje llano ----
    ec = S["en_curso"]
    if ec:
        mal = ec["sin_caudal"] and ec["min"] >= etl.AVISO_SIN_CAUDAL_MIN
        riego = fila(ROJO if mal else AGUA, "Riego abierto",
                     f"Empezó {hace(ec['min'])}. Agua entregada: {litros(ec['litros'])}.")
    elif ev_hist.empty:
        riego = fila(GRIS, "Riego cerrado", "Todavía no hay riegos registrados.")
    else:
        u = ev_hist.iloc[-1]
        minutos = (AHORA - u["fin"]).total_seconds() / 60
        if u["sin_caudal"]:
            riego = fila(ROJO, "Riego cerrado",
                         f"El último riego fue {hace(minutos)} y "
                         + ("no entregó agua " if u["resultado"] == "Sin agua"
                            else "entregó muy poca agua ")
                         + f"({duracion(u['dur_min'])} abierto, {litros(u['litros'])}).")
        else:
            riego = fila(HOJA, "Riego cerrado",
                         f"Último riego {hace(minutos)}: {duracion(u['dur_min'])}, "
                         f"{litros(u['litros'])}.")
    na = S["no_atribuida_24h"]
    if na >= RIEGO_TIPICO:
        agua = fila(AMBAR, "Sale agua sin que el riego esté abierto",
                    f"{litros(na)} en las últimas 24 horas, tanto como un riego completo.")
    elif na >= 1:
        agua = fila(HOJA, "Sin pérdidas importantes",
                    f"{litros(na)} salieron sin orden de riego en las últimas 24 horas.")
    else:
        agua = fila(HOJA, "Sin pérdidas", "No salió agua con el riego cerrado en las "
                                          "últimas 24 horas.")
    st.subheader("Riego y agua")
    st.markdown(riego + agua, unsafe_allow_html=True)

    # ---- Avisos ----
    if avisos:
        st.subheader("Avisos")
        for niv, tit, texto, accion in avisos:
            color = ROJO if niv == "critico" else AMBAR
            st.markdown(f'<div class="aviso" style="border-color:{color}">'
                        f'<b>{tit}</b><br>{texto}'
                        f'<div class="hacer">Qué hacer: {accion}</div></div>',
                        unsafe_allow_html=True)

    # ---- Evolucion ----
    st.subheader("Últimos 3 días")
    st.altair_chart(grafico_humedad(hist.iloc[-3 * etl.REGISTROS_24H:], ev_hist,
                                    ss.umbral_accion),
                    width="stretch", height=280)
    st.caption("La línea es la humedad del suelo. Las franjas marcan cuándo estuvo "
               "abierto el riego. La línea punteada es el nivel por debajo del cual "
               "hay que regar.")

    # Avance automatico del tiempo (HU-01: la pantalla se actualiza sola)
    if ss.reproduciendo:
        time.sleep(1.5)
        ss.ahora = min(ss.ahora + pd.Timedelta(hours=1), T_MAX)
        if ss.ahora >= T_MAX:
            ss.reproduciendo = False
        st.rerun()


# ======================================================================
# Agua (Modulo A: RF-02 a RF-06, RF-13)
# ======================================================================

def vista_agua():
    encabezado("Agua")
    PERIODOS = {"7 días": 7, "30 días": 30, "Toda la campaña": None}
    elegido = st.segmented_control("Período", list(PERIODOS), default="30 días",
                                   label_visibility="collapsed") or "30 días"
    dias = PERIODOS[elegido]
    desde = AHORA - pd.Timedelta(days=dias) if dias else hist["ts_local"].iloc[0]
    sub = hist[hist["ts_local"] >= desde]
    ev = ev_hist[ev_hist["inicio"] >= desde]
    r = etl.resumen_auditoria(sub)

    if not r["medido"]:
        st.info("No se registró agua en este período.")
        return

    de_cada_100 = round(r["pct_no_atribuido"])
    st.markdown(f"### De cada 100 litros, {de_cada_100} salieron sin una orden de riego")
    c1, c2, c3 = st.columns(3)
    c1.metric("Agua usada", litros(r["medido"]))
    c2.metric("En riegos", litros(r["atribuido"]))
    c3.metric("Sin orden de riego", litros(r["no_atribuido"]))

    st.subheader("Día por día")
    diario = etl.balance_diario(sub)
    largo = (diario[["atribuido", "no_atribuido"]]
             .rename(columns={"atribuido": "En riegos", "no_atribuido": "Sin orden de riego"})
             .rename_axis("fecha").reset_index()
             .melt("fecha", var_name="Agua", value_name="litros"))
    largo["fecha"] = pd.to_datetime(largo["fecha"])
    st.altair_chart(
        alt.Chart(largo).mark_bar().encode(
            x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%d/%m", labelAngle=0)),
            y=alt.Y("litros:Q", title="Litros"),
            color=alt.Color("Agua:N",
                            scale=alt.Scale(domain=["En riegos", "Sin orden de riego"],
                                            range=[AGUA, AMBAR]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("fecha:T", format="%d/%m/%Y", title="Día"), "Agua:N",
                     alt.Tooltip("litros:Q", format=".0f", title="Litros")]),
        width="stretch", height=280)

    columnas = {
        "inicio": st.column_config.DatetimeColumn("Inicio", format="DD/MM HH:mm"),
        "dur_min": st.column_config.NumberColumn("Minutos"),
        "litros": st.column_config.NumberColumn("Litros", format="%.0f")}

    st.subheader("Agua que salió sin orden de riego")
    episodios = etl.episodios_no_comandados(sub)
    episodios = episodios[episodios["litros"] >= 10]
    if episodios.empty:
        st.markdown("No hubo salidas de agua con el riego cerrado.")
    else:
        st.caption(f"{len(episodios)} veces en el período. Puede ser un riego manual, "
                   "otro sector que comparte el medidor o una pérdida: conviene "
                   "confirmarlo en el campo.")
        st.dataframe(episodios.sort_values("litros", ascending=False)
                     [["inicio", "dur_min", "litros"]].head(10),
                     hide_index=True, column_config=columnas)

    st.subheader("Riegos sin agua o con caudal insuficiente")
    sin = etl.ordenes_sin_caudal(ev)
    if sin.empty:
        st.markdown("Todos los riegos del período entregaron agua.")
    else:
        nada = int((sin["resultado"] == "Sin agua").sum())
        st.caption(f"{len(sin)} de {len(ev)} riegos: {nada} sin agua y {len(sin) - nada} "
                   f"con caudal insuficiente (menos de "
                   f"{str(etl.CAUDAL_MINIMO_L_MIN).replace('.', ',')} L por minuto; "
                   f"un riego normal ronda los 16). En total, "
                   f"{duracion(sin['dur_min'].sum())} de riego abierto.")
        st.dataframe(sin.sort_values("dur_min", ascending=False)
                     [["inicio", "dur_min", "litros", "resultado"]],
                     hide_index=True,
                     column_config={**columnas, "resultado": "Resultado"})

    st.download_button("Descargar el detalle diario", diario.round(1).to_csv().encode("utf-8"),
                       file_name="agua_por_dia.csv", mime="text/csv")


# ======================================================================
# Riegos (HU-03)
# ======================================================================

def vista_riegos():
    encabezado("Riegos")
    desde = AHORA - pd.Timedelta(days=30)
    ev = ev_hist[ev_hist["inicio"] >= desde]
    st.caption("Últimos 30 días.")
    solo = st.toggle("Ver solo los riegos con problemas de caudal")
    if solo:
        ev = ev[ev["sin_caudal"]]
    if ev.empty:
        st.markdown("No hay riegos para mostrar.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Riegos", len(ev))
    c2.metric("Agua entregada", litros(ev["litros"].sum()))
    c3.metric("Duración habitual", duracion(ev["dur_min"].median()))

    tabla = ev.sort_values("inicio", ascending=False).assign(
        resultado=lambda d: d["resultado"])
    st.dataframe(
        tabla[["inicio", "dur_min", "litros", "percentil_inicial", "resultado"]],
        hide_index=True, height=480,
        column_config={
            "inicio": st.column_config.DatetimeColumn("Inicio", format="DD/MM/YYYY HH:mm"),
            "dur_min": st.column_config.NumberColumn("Minutos"),
            "litros": st.column_config.NumberColumn("Litros", format="%.0f"),
            "percentil_inicial": st.column_config.ProgressColumn(
                "Humedad al empezar", min_value=0, max_value=100, format="%.0f",
                help="0 es lo más seco que estuvo el suelo; 100, lo más húmedo."),
            "resultado": "Resultado"})


# ======================================================================
# Ajustes
# ======================================================================

def vista_ajustes():
    encabezado("Ajustes")
    st.markdown("La humedad se muestra de 0 a 100 comparando la lectura de ahora con "
                "todo lo que midió el sensor en este lote: 0 es lo más seco que "
                "estuvo y 100, lo más húmedo.")
    accion = st.number_input("Avisar que hay que regar por debajo de", 1, 50,
                             ss.umbral_accion)
    holgura = st.number_input("Considerar que el suelo está bien por encima de", 20, 90,
                              ss.umbral_holgura)
    if holgura <= accion:
        st.warning("El segundo nivel tiene que ser mayor que el primero. "
                   "No se guardó el cambio.")
    else:
        ss.umbral_accion, ss.umbral_holgura = int(accion), int(holgura)

    st.subheader("Aviso de agua sin orden de riego")
    st.markdown(f"Se avisa cuando en 24 horas sale, con el riego cerrado, tanta agua "
                f"como en un riego normal de este lote: **{litros(RIEGO_TIPICO)}**.")
    st.subheader("Aviso de riego sin agua")
    st.markdown(f"Se avisa cuando el riego lleva {etl.AVISO_SIN_CAUDAL_MIN} minutos "
                f"abierto y pasan menos de "
                f"{str(etl.CAUDAL_MINIMO_L_MIN).replace('.', ',')} litros por minuto.")


# ======================================================================
# Acerca de esta version (para la presentacion; no es parte del uso diario)
# ======================================================================

def vista_acerca():
    st.title("Acerca de esta versión")
    r = etl.resumen_auditoria(df)
    st.markdown(
        "Versión beta del MVP. Es una capa de software que **lee** lo que ya mide un "
        "sistema de riego instalado y lo traduce en avisos para el operario. No "
        "reemplaza al sistema ni abre o cierra válvulas.")

    a, b = st.columns(2)
    with a:
        st.subheader("Qué resuelve")
        st.markdown("""
- Dice si hay que regar, según la humedad del suelo.
- Avisa si el riego está abierto y no llega agua.
- Avisa si sale agua sin una orden de riego.
- Muestra cuánta agua se usó y el historial de riegos.
""")
    with b:
        st.subheader("Qué quedó fuera")
        st.markdown("""
- Anticipar cuándo va a hacer falta regar (Módulo B, con clima).
- Avisos por mensaje o notificación.
- Varios lotes, cultivos y usuarios.
- Conexión en vivo a los sensores.
""")

    st.subheader("Limitaciones conocidas")
    st.markdown(f"""
1. **Datos históricos.** La aplicación muestra telemetría de 2022; el panel
   «Demostración» elige qué momento se trata como ahora.
2. **Un solo lote, un cultivo, {r["dias"]} días de invierno.** No se puede extrapolar.
3. **Sensor sin calibrar.** La humedad es relativa al historial del propio sensor
   (percentil), no una medida de cuánta agua tiene el suelo.
4. **La escala de humedad usa toda la serie**, incluidas lecturas posteriores al
   momento mostrado. Con un sensor en vivo se calcularía sobre lo acumulado.
5. **Detecta, no diagnostica.** El agua sin orden puede ser una pérdida, un riego
   manual u otro sector que comparte el medidor.
6. **Cortes de señal**: {r["interrupciones"]} en el período, el mayor de
   {df["gap_min"].max() / 60:.0f} horas. Se muestran como faltantes, sin inventar datos.
7. **Sin usuarios ni memoria.** Los ajustes valen para la sesión.
8. **Alojamiento gratuito.** La aplicación se suspende si pasa un tiempo sin visitas
   y hay que reactivarla desde la propia página.
""")

    st.subheader("Cómo está hecha")
    st.code("""D_valve.csv ─────┐
D_flowmeter.csv ─┼─► etl.py ──► datos integrados ──► app.py (Streamlit)
D_moisture.csv ──┘   Módulo A    en memoria           Módulo C
GitHub (código + datos) ──► Streamlit Community Cloud ──► link público""",
            language=None)
    st.caption("Python · pandas · NumPy · Streamlit · Altair · pytest")

    with st.expander("Trazabilidad: del dato crudo a la pantalla"):
        st.markdown("La aplicación no lee un archivo ya procesado: al iniciar integra "
                    "los tres archivos originales por marca de tiempo.")
        st.caption("D_valve.csv, tal como viene del repositorio de origen")
        st.dataframe(pd.read_csv(RUTA / "D_valve.csv", nrows=5), hide_index=True)
        st.caption("Datos integrados en el momento mostrado")
        st.dataframe(df[["ts_local", "relay", "moisture", "percentil", "litros_intervalo"]]
                     .iloc[I - 4: I + 1].round({"percentil": 1, "litros_intervalo": 1}),
                     hide_index=True)
        st.caption(f"{len(df):,} registros integrados".replace(",", "."))


{VISTAS[0]: vista_hoy, VISTAS[1]: vista_agua, VISTAS[2]: vista_riegos,
 VISTAS[3]: vista_ajustes, VISTAS[4]: vista_acerca}[vista]()
