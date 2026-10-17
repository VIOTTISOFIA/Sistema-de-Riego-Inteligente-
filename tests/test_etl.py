"""Pruebas de la logica de datos (Modulo A y ETL). Ejecutar con: pytest"""

from pathlib import Path

import pandas as pd
import pytest

import etl

RAIZ = Path(__file__).parent.parent
RUTA = next((RAIZ / c for c in ("Datos", "datos") if (RAIZ / c).exists()), RAIZ)


@pytest.fixture(scope="module")
def df():
    return etl.ejecutar_etl(RUTA)


def serie(columna, filas):
    """Arma una serie sintetica: filas = [(valor, 'HH:MM'), ...] del 01/08/2022."""
    return pd.DataFrame({columna: [v for v, _ in filas],
                         "ts_utc": pd.to_datetime([f"2022-08-01 {h}" for _, h in filas])})


# ---------- ETL sobre los datos reales ----------

def test_la_tabla_base_es_la_valvula(df):
    crudo = pd.read_csv(RUTA / "D_valve.csv")
    assert len(df) == len(crudo) == 17427
    assert not df["ts_utc"].duplicated().any()


def test_hora_local_es_utc_menos_4(df):
    assert ((df["ts_utc"] - df["ts_local"]) == pd.Timedelta(hours=4)).all()


def test_el_volumen_por_intervalo_nunca_es_negativo(df):
    assert (df["litros_intervalo"].dropna() >= 0).all()


def test_los_faltantes_no_se_imputan(df):
    assert df["moisture"].isna().sum() > 0
    assert df["litres"].isna().sum() > 0


def test_percentil_entre_0_y_100(df):
    p = df["percentil"].dropna()
    assert p.min() > 0 and p.max() <= 100


def test_se_detectan_las_15_interrupciones(df):
    assert df["post_gap"].sum() == 15


# ---------- Auditoria: cifras comprometidas en las Evidencias 1 y 2 ----------

def test_cifras_de_la_auditoria(df):
    r = etl.resumen_auditoria(df)
    assert round(r["medido"]) == 77218
    assert round(r["no_atribuido"]) == 27094
    assert r["pct_no_atribuido"] == pytest.approx(35.1, abs=0.1)
    assert r["atribuido"] + r["no_atribuido"] == pytest.approx(r["medido"])


def test_el_balance_diario_suma_lo_mismo_que_el_resumen(df):
    r, b = etl.resumen_auditoria(df), etl.balance_diario(df)
    assert b["atribuido"].sum() == pytest.approx(r["atribuido"])
    assert b["no_atribuido"].sum() == pytest.approx(r["no_atribuido"])
    assert b["min_comandados"].sum() == r["min_comandados"]


def test_los_episodios_suman_el_agua_no_atribuida(df):
    ep = etl.episodios_no_comandados(df)
    assert ep["litros"].sum() == pytest.approx(etl.resumen_auditoria(df)["no_atribuido"])
    assert (ep["litros"] > 0).all()


def test_eventos_de_riego(df):
    ev = etl.eventos_riego(df)
    assert len(ev) == 62
    assert ev["dur_min"].median() == 60
    assert (ev["fin"] >= ev["inicio"]).all()


def test_orden_sin_caudal_del_29_de_agosto(df):
    """El caso de la Figura 4 de la Evidencia 2: valvula abierta dias, ~61 L."""
    sin = etl.ordenes_sin_caudal(etl.eventos_riego(df))
    caso = sin[sin["inicio"].dt.strftime("%Y-%m-%d") == "2022-08-29"]
    assert caso["dur_min"].max() > 24 * 60
    assert caso["litros"].max() < 100


def test_filtrar_periodo_incluye_los_extremos(df):
    dia = df["fecha"].iloc[5000]
    sub = etl.filtrar_periodo(df, dia, dia)
    assert set(sub["fecha"]) == {dia}
    assert etl.filtrar_periodo(df).equals(df)


# ---------- Logica con datos sinteticos ----------

def test_integracion_sintetica_atribuye_bien():
    horas = ["00:00", "00:05", "00:10", "00:15", "00:20", "00:25"]
    valvula = serie("relay", list(zip([0, 1, 1, 0, 0, 0], horas)))
    caudal = serie("litres", list(zip([0, 10, 30, 30, 80, 80], horas)))
    humedad = serie("moisture", [(70.0, "00:00"), (72.0, "00:20")])
    d = etl.integrar(valvula, caudal, humedad)

    r = etl.resumen_auditoria(d)
    assert (r["atribuido"], r["no_atribuido"]) == (30, 50)
    assert r["pct_no_atribuido"] == pytest.approx(62.5)

    ev = etl.eventos_riego(d)
    assert len(ev) == 1 and ev.loc[0, "dur_min"] == 10 and not ev.loc[0, "sin_caudal"]

    ep = etl.episodios_no_comandados(d)
    assert len(ep) == 1 and ep.loc[0, "litros"] == 50


def test_el_agua_acumulada_en_un_corte_no_se_atribuye():
    valvula = serie("relay", [(0, "00:00"), (0, "00:05"), (0, "03:00")])
    caudal = serie("litres", [(0, "00:00"), (0, "00:05"), (500, "03:00")])
    d = etl.integrar(valvula, caudal, serie("moisture", [(70.0, "00:00")]))
    r = etl.resumen_auditoria(d)
    assert r["no_clasificable"] == 500 and r["medido"] == 0
    assert r["interrupciones"] == 1
    assert pd.isna(r["pct_no_atribuido"])


def test_orden_sin_caudal_sintetica():
    horas = ["00:00", "00:05", "00:10", "00:15"]
    d = etl.integrar(serie("relay", list(zip([1, 1, 1, 1], horas))),
                     serie("litres", list(zip([0, 0, 0, 0], horas))),
                     serie("moisture", [(70.0, "00:00")]))
    assert etl.eventos_riego(d)["sin_caudal"].all()


def test_sin_riegos_devuelve_tablas_vacias():
    horas = ["00:00", "00:05"]
    d = etl.integrar(serie("relay", list(zip([0, 0], horas))),
                     serie("litres", list(zip([5, 5], horas))),
                     serie("moisture", [(70.0, "00:00")]))
    assert etl.eventos_riego(d).empty
    assert etl.episodios_no_comandados(d).empty


@pytest.mark.parametrize("percentil, esperado", [
    (3, "RIEGO NECESARIO"), (14.9, "RIEGO NECESARIO"), (15, "ATENCIÓN"),
    (39.9, "ATENCIÓN"), (40, "ÓPTIMO"), (99, "ÓPTIMO"), (float("nan"), "SIN LECTURA")])
def test_semaforo(percentil, esperado):
    assert etl.clasificar(percentil, 15, 40)[0] == esperado


# ---------- Entradas invalidas ----------

def test_archivo_faltante(tmp_path):
    with pytest.raises(etl.DatosInvalidos, match="No se encontró") as e:
        etl.ejecutar_etl(tmp_path)
    assert str(tmp_path) not in str(e.value)        # DEF-13: sin ruta del servidor


def test_columnas_incorrectas(tmp_path):
    (tmp_path / "D_valve.csv").write_text("estado,fecha\n1,hoy\n")
    with pytest.raises(etl.DatosInvalidos, match="columnas"):
        etl.cargar_serie(tmp_path, "D_valve.csv", "relay")


def test_fecha_con_formato_inesperado(tmp_path):
    (tmp_path / "D_valve.csv").write_text("relay,time_stamp\n1,2022-07-12 00:00\n")
    with pytest.raises(etl.DatosInvalidos, match="formato"):
        etl.cargar_serie(tmp_path, "D_valve.csv", "relay")


# ---------- Situacion actual, titular y avisos (integracion A + C) ----------

@pytest.mark.parametrize("posicion, titulo, avisos", [
    (200, "No hace falta regar", []),
    (9176, "Todavía no hace falta regar", []),
    (5471, "No hace falta regar", ["Fuga / Agua no atribuida"]),
    (13920, "El riego está abierto, pero llega muy poca agua",
     ["Orden de riego emitida sin caudal detectado"]),
    (14609, "El riego está abierto, pero no llega agua",
     ["Orden de riego emitida sin caudal detectado"]),
    (17340, "Hay que regar", ["Riego necesario"])])
def test_titular_y_avisos_en_momentos_conocidos(df, posicion, titulo, avisos):
    s = etl.situacion_actual(df, posicion, 15)
    assert etl.titular(s, 40)[1] == titulo
    umbral = etl.riego_tipico(etl.eventos_riego(df))
    assert [a[1] for a in etl.alertas(s, umbral)] == avisos


def test_riego_tipico_es_la_mediana_de_los_riegos_con_agua(df):
    assert etl.riego_tipico(etl.eventos_riego(df)) == pytest.approx(1054, abs=1)


def test_la_orden_en_curso_acumula_desde_su_inicio(df):
    s = etl.situacion_actual(df, 13920, 15)
    assert s["en_curso"]["min"] > 24 * 60 and s["en_curso"]["sin_caudal"]
    assert etl.situacion_actual(df, 200, 15)["en_curso"] is None


def test_la_serie_horaria_conserva_el_total(df):
    h = etl.serie_horaria(df)
    assert h["litros"].sum() == pytest.approx(etl.resumen_auditoria(df)["medido"])


# ---------- Correcciones de la Evidencia 3 de Testing ----------

def test_resultado_distingue_sin_agua_de_caudal_insuficiente(df):
    """DEF-11"""
    ev = etl.eventos_riego(df)
    assert ev["resultado"].value_counts().to_dict() == {
        "Correcto": 49, "Sin agua": 10, "Caudal insuficiente": 3}
    insuf = ev[ev["resultado"] == "Caudal insuficiente"]
    assert (insuf["litros"] >= 1).all() and insuf["sin_caudal"].all()


def test_eventos_sobre_historico_recortado(df):
    """DEF-16: armados hasta el 30/08 12:00, la orden en curso no ve el futuro."""
    i = int(df["ts_local"].searchsorted(pd.Timestamp("2022-08-30 12:00"), side="right")) - 1
    ultima = etl.eventos_riego(df.iloc[: i + 1]).iloc[-1]
    assert ultima["dur_min"] == etl.situacion_actual(df, i, 15)["en_curso"]["min"]


def test_falta_puntual_de_humedad_usa_la_ultima_lectura(df):
    """DEF-10"""
    s = etl.situacion_actual(df, 852, 15)
    assert pd.isna(df["moisture"].iloc[852]) and pd.notna(s["percentil"])
    assert etl.titular(s, 40)[0] != "sin_dato"


def test_sin_humedad_mas_de_una_hora_es_sin_dato():
    horas = [f"{h:02d}:{m:02d}" for h in (0, 1) for m in range(0, 60, 5)]
    d = etl.integrar(serie("relay", [(0, h) for h in horas]),
                     serie("litres", [(0, h) for h in horas]),
                     serie("moisture", [(70.0, "00:00")]))
    s = etl.situacion_actual(d, len(d) - 1, 15)
    assert etl.titular(s, 40)[1] == "No hay lectura del suelo"
