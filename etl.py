"""
Sistema de Riego Inteligente - logica de datos (sin interfaz)

Modulo A (auditoria hidrica) y ETL compartido con el Modulo C (tablero).
Este archivo no importa Streamlit: asi la logica se puede probar de forma
independiente de la interfaz (RNF-06) con `pytest`.

Recorrido:
    3 CSV crudos -> integrar() -> dataset por clave temporal
                 -> eventos_riego() / balance_diario() / resumen_auditoria()
                 -> episodios_no_comandados() / ordenes_sin_caudal()
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Zona horaria del campo: Paraguay rigio en UTC-4 durante julio-septiembre 2022
OFFSET_LOCAL = pd.Timedelta(hours=4)

TOLERANCIA_CAUDAL = pd.Timedelta("3min")
TOLERANCIA_HUMEDAD = pd.Timedelta("20min")

# Una separacion mayor a 10 minutos entre lecturas de la valvula (que reporta
# cada 5) se considera una interrupcion de telemetria.
GAP_MIN = 10
MIN_POR_REGISTRO = 5

# Una orden de riego se considera "sin caudal" cuando el caudalimetro registra
# menos de 0,5 L por minuto comandado. Un riego tipico ronda los 16 L/min.
CAUDAL_MINIMO_L_MIN = 0.5
# Por debajo de este volumen se considera que una orden no entrego agua en absoluto;
# por encima, pero con menos de CAUDAL_MINIMO_L_MIN, entrego "caudal insuficiente".
LITROS_SIN_AGUA = 1.0

ARCHIVOS = {"relay": "D_valve.csv", "litres": "D_flowmeter.csv",
            "moisture": "D_moisture.csv"}
FORMATO_FECHA = "%d-%b-%Y %H:%M:%S"


class DatosInvalidos(Exception):
    """Los archivos de telemetria faltan o no tienen el formato esperado."""


# ----------------------------------------------------------------------
# Extraccion
# ----------------------------------------------------------------------

def cargar_serie(ruta: Path, archivo: str, columna: str) -> pd.DataFrame:
    camino = Path(ruta) / archivo
    if not camino.exists():
        # Solo el nombre de la carpeta: la ruta absoluta del servidor no se muestra
        raise DatosInvalidos(f"No se encontró el archivo {archivo} en la carpeta "
                             f"«{Path(ruta).name}».")
    d = pd.read_csv(camino)
    faltan = {columna, "time_stamp"} - set(d.columns)
    if faltan:
        raise DatosInvalidos(
            f"{archivo} no tiene las columnas esperadas: falta {sorted(faltan)}.")
    try:
        d["ts_utc"] = pd.to_datetime(d["time_stamp"], format=FORMATO_FECHA)
    except (ValueError, TypeError) as e:
        raise DatosInvalidos(
            f"{archivo} tiene marcas temporales con un formato inesperado.") from e
    d[columna] = pd.to_numeric(d[columna], errors="coerce")
    return d[[columna, "ts_utc"]].sort_values("ts_utc").reset_index(drop=True)


def cargar_series(ruta: Path) -> dict:
    return {col: cargar_serie(ruta, arch, col) for col, arch in ARCHIVOS.items()}


# ----------------------------------------------------------------------
# Transformacion
# ----------------------------------------------------------------------

def integrar(valvula: pd.DataFrame, caudal: pd.DataFrame,
             humedad: pd.DataFrame) -> pd.DataFrame:
    """Reproduce el ETL documentado en la seccion 2 del notebook V2.

    - D_valve es la tabla base por ser la serie mas densa (cada 5 min).
    - La union se hace por marca temporal con merge_asof y tolerancia,
      nunca por posicion de fila.
    - litres es un acumulador: se diferencia para obtener volumen por intervalo.
    - Los faltantes son cortes reales de telemetria: se conservan como NaN.
    """
    if valvula.empty:
        raise DatosInvalidos("La serie de la electrovalvula esta vacia.")

    df = pd.merge_asof(valvula, caudal, on="ts_utc",
                       tolerance=TOLERANCIA_CAUDAL, direction="nearest")
    df = pd.merge_asof(df, humedad, on="ts_utc",
                       tolerance=TOLERANCIA_HUMEDAD, direction="nearest")

    df["ts_local"] = df["ts_utc"] - OFFSET_LOCAL
    df["fecha"] = df["ts_local"].dt.date
    df["litros_intervalo"] = df["litres"].diff().clip(lower=0)

    df["gap_min"] = df["ts_utc"].diff().dt.total_seconds() / 60
    df["post_gap"] = df["gap_min"] > GAP_MIN

    # Percentil de cada lectura dentro de la propia serie historica del sensor.
    # Se usa el percentil y no el valor crudo porque el sensor capacitivo esta
    # sin calibrar: su rango util real es ~68,6 a 86,9 y no 0 a 100.
    df["percentil"] = df["moisture"].rank(pct=True) * 100

    # Bloques contiguos de valvula abierta, cortados tambien por interrupciones
    df["bloque"] = ((df["relay"].diff() != 0) | df["post_gap"]).cumsum()
    return df


def ejecutar_etl(ruta: Path) -> pd.DataFrame:
    s = cargar_series(ruta)
    return integrar(s["relay"], s["litres"], s["moisture"])


def tabla_percentiles(serie: pd.Series) -> pd.Series:
    """Lectura cruda del sensor que corresponde a cada percentil de referencia."""
    limpia = serie.dropna()
    return pd.Series({p: np.percentile(limpia, p) for p in (5, 15, 25, 50, 75, 95)})


def clasificar(percentil: float, umbral_accion: float, umbral_holgura: float):
    """Traduce el percentil a un estado accionable para el tecnico."""
    if pd.isna(percentil):
        return "SIN LECTURA", "#6e7681", "Señal de telemetría pausada"
    if percentil < umbral_accion:
        return ("RIEGO NECESARIO", "#f85149",
                "El suelo está en la franja más seca de su histórico")
    if percentil < umbral_holgura:
        return "ATENCIÓN", "#f0a848", "Descendiendo hacia el umbral de accion"
    return "ÓPTIMO", "#3fb950", "No hace falta regar"


# ----------------------------------------------------------------------
# Modulo A - auditoria hidrica
# ----------------------------------------------------------------------

def filtrar_periodo(df: pd.DataFrame, desde=None, hasta=None) -> pd.DataFrame:
    """Recorta por fecha local (ambos extremos incluidos)."""
    m = pd.Series(True, index=df.index)
    if desde is not None:
        m &= df["fecha"] >= desde
    if hasta is not None:
        m &= df["fecha"] <= hasta
    return df[m]


def resumen_auditoria(df: pd.DataFrame) -> dict:
    """RF-02 a RF-06: volumen medido, atribuido a una orden y no atribuido.

    El volumen que el acumulador suma durante una interrupcion de telemetria
    no se puede asignar a ningun estado de la valvula: se informa aparte y
    queda fuera del total auditado.
    """
    normal = df[~df["post_gap"]]
    atribuido = normal.loc[normal["relay"] == 1, "litros_intervalo"].sum()
    no_atribuido = normal.loc[normal["relay"] == 0, "litros_intervalo"].sum()
    medido = atribuido + no_atribuido
    dias = df["fecha"].nunique()
    return {
        "medido": float(medido),
        "atribuido": float(atribuido),
        "no_atribuido": float(no_atribuido),
        "pct_no_atribuido": float(100 * no_atribuido / medido) if medido else float("nan"),
        "no_clasificable": float(df.loc[df["post_gap"], "litros_intervalo"].sum()),
        "min_comandados": int((df["relay"] == 1).sum() * MIN_POR_REGISTRO),
        "dias": int(dias),
        "no_atribuido_dia": float(no_atribuido / dias) if dias else float("nan"),
        "interrupciones": int(df["post_gap"].sum()),
    }


def balance_diario(df: pd.DataFrame) -> pd.DataFrame:
    """RF-06 / RF-13: litros por dia, atribuidos y no atribuidos."""
    normal = df[~df["post_gap"]]
    litros = (normal.assign(estado=np.where(normal["relay"] == 1,
                                             "atribuido", "no_atribuido"))
              .pivot_table(index="fecha", columns="estado",
                           values="litros_intervalo", aggfunc="sum")
              .reindex(columns=["atribuido", "no_atribuido"]))
    minutos = (df.groupby("fecha")["relay"].sum() * MIN_POR_REGISTRO)
    out = litros.join(minutos.rename("min_comandados"), how="outer").fillna(0)
    out["min_comandados"] = out["min_comandados"].astype(int)
    return out


def eventos_riego(df: pd.DataFrame) -> pd.DataFrame:
    """Ordenes de riego: bloques contiguos con la valvula comandada abierta.

    `sin_caudal` marca la direccion inversa del RF-05: hubo orden de riego
    pero el caudalimetro practicamente no registro agua.
    """
    columnas = ["inicio", "fin", "dur_min", "litros", "caudal_l_min",
                "humedad_inicial", "percentil_inicial", "sin_caudal", "resultado"]
    on = df[df["relay"] == 1]
    if on.empty:
        return pd.DataFrame(columns=columnas)
    ev = (on.groupby("bloque")
          .agg(inicio=("ts_local", "min"), fin=("ts_local", "max"),
               n=("relay", "size"), litros=("litros_intervalo", "sum"),
               humedad_inicial=("moisture", "first"),
               percentil_inicial=("percentil", "first"))
          .reset_index(drop=True))
    ev["dur_min"] = ev["n"] * MIN_POR_REGISTRO
    ev["caudal_l_min"] = ev["litros"] / ev["dur_min"]
    ev["sin_caudal"] = ev["caudal_l_min"] < CAUDAL_MINIMO_L_MIN
    ev["resultado"] = [resultado_riego(l, s) for l, s in zip(ev["litros"], ev["sin_caudal"])]
    return ev[columnas]


def resultado_riego(litros: float, sin_caudal: bool) -> str:
    """Rotulo de una orden de riego para el operario (DEF-11)."""
    if not sin_caudal:
        return "Correcto"
    return "Sin agua" if litros < LITROS_SIN_AGUA else "Caudal insuficiente"


def ordenes_sin_caudal(eventos: pd.DataFrame) -> pd.DataFrame:
    return eventos[eventos["sin_caudal"]].reset_index(drop=True)


def episodios_no_comandados(df: pd.DataFrame) -> pd.DataFrame:
    """RF-05: caudal registrado con la valvula comandada cerrada ("agua fantasma").

    Agrupa los registros consecutivos con caudal en un mismo episodio.
    """
    columnas = ["inicio", "fin", "dur_min", "litros"]
    m = (df["relay"] == 0) & (df["litros_intervalo"] > 0) & (~df["post_gap"])
    if not m.any():
        return pd.DataFrame(columns=columnas)
    grupo = (m != m.shift()).cumsum()[m]
    ep = (df[m].groupby(grupo)
          .agg(inicio=("ts_local", "min"), fin=("ts_local", "max"),
               n=("relay", "size"), litros=("litros_intervalo", "sum"))
          .reset_index(drop=True))
    ep["dur_min"] = ep["n"] * MIN_POR_REGISTRO
    return ep[columnas]


# ----------------------------------------------------------------------
# Integracion A + C: lo que el tecnico necesita saber "ahora"
# ----------------------------------------------------------------------

# Minutos sin lectura de humedad a partir de los cuales se considera que el
# sensor dejo de enviar datos
MAX_MIN_SIN_HUMEDAD = 60

# Minutos de orden abierta sin caudal a partir de los cuales se avisa
AVISO_SIN_CAUDAL_MIN = 30

REGISTROS_24H = 24 * 60 // MIN_POR_REGISTRO


def situacion_actual(df: pd.DataFrame, i: int, umbral_accion: float) -> dict:
    """Resume el estado del campo en la lectura i usando las tres series."""
    actual = df.iloc[i]
    v24 = df.iloc[max(0, i - REGISTROS_24H): i + 1]
    normal = v24[~v24["post_gap"]]

    # Orden de riego en curso: bloque de valvula abierta que llega hasta i
    en_curso = None
    if actual["relay"] == 1:
        bloque = df.iloc[: i + 1]
        bloque = bloque[bloque["bloque"] == actual["bloque"]]
        minutos = len(bloque) * MIN_POR_REGISTRO
        agua = float(bloque["litros_intervalo"].sum())
        en_curso = {"inicio": bloque["ts_local"].iloc[0], "min": minutos, "litros": agua,
                    "sin_caudal": agua < minutos * CAUDAL_MINIMO_L_MIN}

    # Ultima lectura valida de humedad (para saber hace cuanto no hay dato)
    validas = df["moisture"].iloc[: i + 1].dropna()
    min_sin_humedad = (float((actual["ts_local"] - df["ts_local"].loc[validas.index[-1]])
                             .total_seconds() / 60) if len(validas) else float("nan"))

    # DEF-10: el sensor reporta cada ~20 min, asi que una falta puntual no es un
    # corte. Hasta MAX_MIN_SIN_HUMEDAD se usa la ultima lectura valida.
    percentil, humedad = actual["percentil"], actual["moisture"]
    if pd.isna(percentil) and len(validas) and min_sin_humedad <= MAX_MIN_SIN_HUMEDAD:
        percentil = df["percentil"].loc[validas.index[-1]]
        humedad = validas.iloc[-1]

    return {
        "ts": actual["ts_local"],
        "percentil": percentil,
        "humedad": humedad,
        "valvula_abierta": bool(actual["relay"] == 1),
        "en_curso": en_curso,
        "litros_24h": float(normal["litros_intervalo"].sum()),
        "no_atribuida_24h": float(normal.loc[normal["relay"] == 0, "litros_intervalo"].sum()),
        "bajo_umbral": bool(pd.notna(percentil) and percentil < umbral_accion),
        "corte_previo_min": float(actual["gap_min"]) if actual["post_gap"] else 0.0,
        "min_sin_humedad": min_sin_humedad,
    }


def riego_tipico(eventos: pd.DataFrame) -> float:
    """Litros de un riego normal en este campo: mediana de las ordenes con caudal.

    Se usa como vara para el aviso de agua sin orden: se avisa cuando en 24 h
    salio, con la valvula cerrada, tanta agua como en un riego completo.
    """
    con_caudal = eventos.loc[~eventos["sin_caudal"], "litros"]
    return float(con_caudal.median()) if len(con_caudal) else float("inf")


def titular(s: dict, umbral_holgura: float) -> tuple:
    """La respuesta a "que hago ahora", en lenguaje del operario.

    Devuelve (nivel, titulo, detalle). nivel: critico | atencion | regando | bien | sin_dato
    """
    ec = s["en_curso"]
    if ec and ec["sin_caudal"] and ec["min"] >= AVISO_SIN_CAUDAL_MIN:
        poca = ec["litros"] >= LITROS_SIN_AGUA          # DEF-11: no es lo mismo que nada
        return ("critico",
                "El riego está abierto, pero " + ("llega muy poca agua" if poca
                                                  else "no llega agua"),
                "Revisá la bomba, la llave de paso, el filtro y la electroválvula.")
    if pd.isna(s["percentil"]) or s["min_sin_humedad"] > MAX_MIN_SIN_HUMEDAD:
        return ("sin_dato", "No hay lectura del suelo",
                "El sensor de humedad no está enviando datos. Revisá su alimentación "
                "y la señal.")
    if ec:
        return ("regando", "Regando",
                "El riego está en marcha y el agua está llegando.")
    if s["bajo_umbral"]:
        return ("critico", "Hay que regar",
                "El suelo está más seco de lo habitual y no hay un riego en marcha.")
    if s["percentil"] < umbral_holgura:
        return ("atencion", "Todavía no hace falta regar",
                "El suelo se está secando. Conviene volver a mirar en unas horas.")
    return ("bien", "No hace falta regar", "El suelo tiene buena humedad.")


def alertas(s: dict, umbral_fuga: float = 1000.0) -> list:
    """Traduce la situacion a avisos con una accion sugerida, de mayor a menor urgencia.

    Cada aviso: (nivel, titulo, detalle, accion). nivel: 'critico' | 'atencion'.
    """
    out = []
    ec = s["en_curso"]
    if ec and ec["sin_caudal"] and ec["min"] >= AVISO_SIN_CAUDAL_MIN:
        out.append(("critico", "Orden de riego emitida sin caudal detectado",
                    f"La válvula está comandada abierta hace {ec['min'] // 60} h "
                    f"{ec['min'] % 60:02d} min y el caudalímetro registró "
                    f"{ec['litros']:.0f} L. El cultivo puede no estar recibiendo agua.",
                    "Revisar en el campo: bomba, llave de paso, filtro y electroválvula."))
    if s["bajo_umbral"] and not s["valvula_abierta"]:
        out.append(("critico", "Riego necesario",
                    f"El suelo está en P{s['percentil']:.0f}, por debajo del umbral de "
                    "acción, y no hay una orden de riego en curso.",
                    "Activar el riego."))
    if s["no_atribuida_24h"] >= umbral_fuga:
        out.append(("atencion", "Fuga / Agua no atribuida",
                    f"En las últimas 24 h pasaron {s['no_atribuida_24h']:,.0f} L".replace(",", ".")
                    + " por el caudalímetro con la válvula cerrada.",
                    "Confirmar si hubo riego manual u otro sector abierto; si no, "
                    "buscar pérdidas aguas abajo del caudalímetro."))
    if pd.isna(s["percentil"]) or s["min_sin_humedad"] > MAX_MIN_SIN_HUMEDAD:
        out.append(("atencion", "Señal de telemetría pausada",
                    "No hay lectura de humedad reciente: el estado del suelo no se "
                    "puede evaluar.",
                    "Verificar alimentación y conectividad del sensor."))
    elif s["corte_previo_min"]:
        out.append(("atencion", "Señal de telemetría pausada",
                    f"Esta lectura llega después de {s['corte_previo_min'] / 60:.1f} h "
                    "sin datos.".replace(".", ",", 1),
                    "Tomar con cautela los acumulados de las últimas 24 h."))
    return out


def serie_horaria(df: pd.DataFrame) -> pd.DataFrame:
    """Litros por hora, separados en atribuidos y no atribuidos (para graficar)."""
    normal = df[~df["post_gap"]]
    h = (normal.assign(hora=normal["ts_local"].dt.floor("h"),
                       tipo=np.where(normal["relay"] == 1, "Atribuida a una orden",
                                     "No atribuida"))
         .groupby(["hora", "tipo"], as_index=False)["litros_intervalo"].sum()
         .rename(columns={"litros_intervalo": "litros"}))
    return h[h["litros"] > 0]
