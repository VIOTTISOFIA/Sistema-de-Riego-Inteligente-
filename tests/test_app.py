"""Pruebas de punta a punta: levantan la app completa sin navegador (AppTest)."""

import datetime as dt
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


def abrir(vista=None, situacion=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if situacion:
        at.sidebar.selectbox[0].set_value(situacion).run()
    if vista:
        at.sidebar.radio[0].set_value(vista).run()
    assert not at.exception, at.exception
    return at


def textos(at):
    return (" ".join(m.value for m in at.markdown)
            + " ".join(str(m.value) for m in at.metric))


def metricas(at):
    return {m.label: m.value for m in at.metric}


def test_la_app_abre_en_hoy_con_una_respuesta():
    at = abrir()
    assert "Todavía no hace falta regar" in textos(at)
    assert "Martes 16/08/2022, 07:00 h" in textos(at)


@pytest.mark.parametrize("situacion, titular", [
    ("Una mañana normal", "Todavía no hace falta regar"),
    ("Riego en marcha", "Regando"),
    ("Hay que regar", "Hay que regar"),
    ("Riego abierto sin agua", "El riego está abierto, pero no llega agua"),
    ("Agua que sale sin orden", "Fuga / Agua no atribuida")])
def test_cada_situacion_muestra_su_mensaje(situacion, titular):
    assert titular in textos(abrir(situacion=situacion))


def test_el_estado_tecnico_acompana_al_titular():
    t = textos(abrir(situacion="Hay que regar"))
    assert "RIEGO NECESARIO" in t and "regar por debajo de P15" in t


def test_mover_la_fecha_cambia_la_pantalla():
    at = abrir()
    at.sidebar.slider[0].set_value(dt.datetime(2022, 9, 1, 21, 30)).run()
    assert not at.exception
    assert "Jueves 01/09/2022" in textos(at)
    assert "no llega agua" in textos(at)


def test_avanzar_el_tiempo_actualiza_solo_y_se_detiene_al_final():
    at = abrir()
    at.sidebar.slider[0].set_value(dt.datetime(2022, 9, 16, 19, 30)).run()
    at.sidebar.button[0].click().run(timeout=60)
    assert not at.exception
    assert at.session_state["reproduciendo"] is False
    assert "Viernes 16/09/2022, 20:00 h" in textos(at)


def test_sin_lectura_de_humedad_no_rompe():
    at = abrir()
    at.sidebar.slider[0].set_value(dt.datetime(2022, 7, 14, 19, 30)).run()
    assert not at.exception
    assert "No hay lectura del suelo" in textos(at)


def test_agua_muestra_solo_lo_ocurrido_hasta_ahora():
    at = abrir("Agua")
    usada_30 = metricas(at)["Agua usada"]
    at.sidebar.slider[0].set_value(dt.datetime(2022, 9, 16, 19, 30)).run()
    at.segmented_control[0].set_value("Toda la campaña").run()
    assert not at.exception
    m = metricas(at)
    assert m["Agua usada"] == "77.218 L" and m["Sin orden de riego"] == "27.094 L"
    assert usada_30 != "77.218 L"
    assert "De cada 100 litros, 35 salieron sin una orden de riego" in textos(at)


def test_riegos_ultimos_30_dias_y_filtro():
    at = abrir("Riegos", situacion="Riego abierto sin agua")
    total = int(metricas(at)["Riegos"])
    at.toggle[0].set_value(True).run()
    assert not at.exception
    assert 0 < int(metricas(at)["Riegos"]) < total


def test_ajustes_cambian_el_nivel_de_aviso():
    at = abrir("Ajustes")
    at.number_input[0].set_value(39).run()
    at.sidebar.radio[0].set_value("Hoy").run()
    assert "Hay que regar" in textos(at)        # P37 queda por debajo de 39


def test_ajustes_invalidos_no_se_guardan():
    at = abrir("Ajustes")
    at.number_input[0].set_value(50).run()
    at.number_input[1].set_value(20).run()
    assert not at.exception
    assert len(at.warning) == 1
    assert at.session_state["umbral_accion"] < at.session_state["umbral_holgura"]


def test_acerca_lista_las_limitaciones():
    at = abrir("Acerca de esta versión")
    assert "Limitaciones conocidas" in [s.value for s in at.subheader]
