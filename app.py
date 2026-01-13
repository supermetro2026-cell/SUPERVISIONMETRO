import streamlit as st
import pandas as pd
from datetime import time

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(
    page_title="Supervisión – DATA METRO",
    layout="wide"
)

# ==================================================
# USUARIOS (luego podés pasarlos a st.secrets)
# ==================================================
USUARIOS = {
    "simone": {"password": "simonem2026", "rol": "supervisor", "grupo": "SIMONE"},
    "gonzalezf": {"password": "gonzalezf123", "rol": "supervisor", "grupo": "GONZALEZ F"},
    "carranza": {"password": "carranza2026", "rol": "supervisor", "grupo": "CARRANZA"},
    "lazarte": {"password": "lazarten2026", "rol": "supervisor", "grupo": "LAZARTE"},
    "delgado": {"password": "delgado123", "rol": "supervisor", "grupo": "DELGADO"},
    "gonzalezcompany": {"password": "gonzalezc1", "rol": "supervisor", "grupo": "GONZALEZ COMPANY"},
    "fernandez": {"password": "fernandezp2026", "rol": "supervisor", "grupo": "FERNANDEZ P"},
    "gerez": {"password": "gerez123", "rol": "supervisor", "grupo": "GEREZ"},
    "graf": {"password": "agraf2026", "rol": "supervisor", "grupo": "GRAF"},
    "vexenat": {"password": "vexenat123", "rol": "supervisor", "grupo": "VEXENAT"},
    "zavaroni": {"password": "zavaroni2026", "rol": "supervisor", "grupo": "ZAVARONI"},
    "jefatura": {"password": "admin123", "rol": "jefe"},
}

# ==================================================
# LOGIN
# ==================================================
if "login_ok" not in st.session_state:
    st.session_state.login_ok = False

if not st.session_state.login_ok:
    st.title("🔐 Ingreso – Supervisión DATA METRO")

    usuario = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if usuario in USUARIOS and USUARIOS[usuario]["password"] == password:
            st.session_state.login_ok = True
            st.session_state.usuario = usuario
            st.session_state.rol = USUARIOS[usuario]["rol"]
            st.session_state.grupo = USUARIOS[usuario].get("grupo")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.stop()

# ==================================================
# HEADER + LOGOUT
# ==================================================
st.title("Supervisión – DATA METRO")

colA, colB = st.columns([4, 1])
with colB:
    if st.button("Salir"):
        st.session_state.clear()
        st.rerun()

# ==================================================
# FUNCIONES AUXILIARES
# ==================================================
def excel_time_to_timedelta(x):
    if pd.isna(x):
        return pd.Timedelta(0)
    if isinstance(x, time):
        return pd.Timedelta(hours=x.hour, minutes=x.minute, seconds=x.second)
    if isinstance(x, pd.Timedelta):
        return x
    try:
        return pd.to_timedelta(x)
    except:
        return pd.Timedelta(0)

def fmt(td):
    if pd.isna(td):
        return ""
    if isinstance(td, time):
        return f"{td.hour:02}:{td.minute:02}:{td.second:02}"
    if isinstance(td, pd.Timedelta):
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02}:{m:02}:{s:02}"
    return ""

# ==================================================
# CARGA DE DATOS DESDE GOOGLE DRIVE
# ==================================================
HOJA = "A.I. POR DIA"

@st.cache_data(show_spinner="Cargando datos...")
def cargar_datos(url):
    df = pd.read_excel(url, sheet_name=HOJA)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df

df = cargar_datos(st.secrets["DATA_METRO_URL"])

# ==================================================
# CONVERSIÓN DE TIEMPOS
# ==================================================
COLUMNAS_TIEMPO = [
    "Tiempo en Llamadas Contestadas",
    "Tiempo Logueado",
    "Tiempo ACW",
    "Tiempo Estado Listo",
    "Tiempo Estado No Listo",
]

@st.cache_data
def convertir_tiempos(df):
    df = df.copy()
    for c in COLUMNAS_TIEMPO:
        df[c] = df[c].apply(excel_time_to_timedelta)
    return df

df = convertir_tiempos(df)

# ==================================================
# FILTROS
# ==================================================
st.markdown("## Filtros")

SUPERVISORES_EXCLUIDOS = {
    "ADICIONALES SDF", "DIAZ", "PORRAS", "ROJAS",
    "PAROLA", "PAROLA-MUSSON", "GONZALEZ C"
}

supervisores_validos = sorted(
    s for s in df["SUPERVISOR"].dropna().unique()
    if s not in SUPERVISORES_EXCLUIDOS
)

col1, col2, col3 = st.columns(3)

with col1:
    if st.session_state.rol == "supervisor":
        supervisor_sel = st.session_state.grupo
        st.info(f"Grupo asignado: {supervisor_sel}")
    else:
        supervisor_sel = st.selectbox("Supervisor", supervisores_validos)

with col2:
    anio = st.selectbox("Año", sorted(df["Fecha"].dt.year.dropna().unique()))

with col3:
    mes_nombre = st.selectbox(
        "Mes",
        ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    )

mes_num = {
    "Enero":1,"Febrero":2,"Marzo":3,"Abril":4,"Mayo":5,"Junio":6,
    "Julio":7,"Agosto":8,"Septiembre":9,"Octubre":10,"Noviembre":11,"Diciembre":12
}[mes_nombre]

# ==================================================
# FILTRADO BASE
# ==================================================
df_mes = df[
    (df["Fecha"].dt.year == anio) &
    (df["Fecha"].dt.month == mes_num)
]

if df_mes.empty:
    st.warning("⚠️ No hay datos para este período.")
    st.stop()

# ==================================================
# SUPERVISOR DOMINANTE
# ==================================================
dominante = (
    df_mes
    .groupby(["Nombre de Usuario", "SUPERVISOR"])["Fecha"]
    .nunique()
    .reset_index(name="dias")
    .sort_values("dias", ascending=False)
    .drop_duplicates("Nombre de Usuario")
)

dominante = dominante[dominante["SUPERVISOR"] == supervisor_sel]
df_final = df_mes[df_mes["Nombre de Usuario"].isin(dominante["Nombre de Usuario"])]

if df_final.empty:
    st.warning("⚠️ No hay datos para este período.")
    st.stop()


# ==================================================
# RESUMEN MENSUAL
# ==================================================
@st.cache_data
def resumen_mensual(df_final):
    g = df_final.groupby("Nombre de Usuario")

    resumen = g.agg(
        Contestadas=("Llamadas Contestadas", "sum"),
        Dias_trabajados=("Fecha", "nunique"),
        Tiempo_Logueado=("Tiempo Logueado", "sum"),
        Tiempo_ACW=("Tiempo ACW", "sum"),
        Tiempo_Listo=("Tiempo Estado Listo", "sum"),
        Tiempo_No_Listo=("Tiempo Estado No Listo", "sum"),
        Reenvios_cola=("Re envios a la cola", "sum"),
        Transferencias=("Transferencias Realizadas", "sum"),
        Tiempo_Contestadas=("Tiempo en Llamadas Contestadas", "sum"),
    ).reset_index()

    resumen["Prom. Contestadas"] = (
        resumen["Contestadas"] / resumen["Dias_trabajados"]
    ).round(0).fillna(0).astype(int)

    horas_prod = (
        resumen["Tiempo_Logueado"] - resumen["Tiempo_No_Listo"]
    ).dt.total_seconds() / 3600

    resumen["Prom. Contestadas x Hora"] = (
        resumen["Contestadas"] / horas_prod
    ).round(0).fillna(0).astype(int)

    resumen["Prom. Tiempo Logueado"] = resumen["Tiempo_Logueado"] / resumen["Dias_trabajados"]
    resumen["Prom. Tiempo ACW"] = resumen["Tiempo_ACW"] / resumen["Dias_trabajados"]
    resumen["Prom. Tiempo Listo"] = resumen["Tiempo_Listo"] / resumen["Dias_trabajados"]
    resumen["Prom. Tiempo No Listo"] = resumen["Tiempo_No_Listo"] / resumen["Dias_trabajados"]
    resumen["TMO"] = resumen["Tiempo_Contestadas"] / resumen["Contestadas"]

    return resumen

resumen = resumen_mensual(df_final)

# ==================================================
# TOTAL DEL GRUPO
# ==================================================
total_grupo = pd.DataFrame([{
    "Nombre de Usuario": "TOTAL GRUPO",
    "Contestadas": resumen["Contestadas"].sum(),
    "Dias_trabajados": resumen["Dias_trabajados"].sum(),
    "Prom. Contestadas": int(resumen["Contestadas"].sum() / resumen["Dias_trabajados"].sum()),
    "Prom. Contestadas x Hora": int(
        resumen["Contestadas"].sum() /
        ((df_final["Tiempo Logueado"].sum() -
          df_final["Tiempo Estado No Listo"].sum()).total_seconds() / 3600)
    ),
    "Prom. Tiempo Logueado": df_final["Tiempo Logueado"].sum() / resumen["Dias_trabajados"].sum(),
    "Prom. Tiempo ACW": df_final["Tiempo ACW"].sum() / resumen["Dias_trabajados"].sum(),
    "Prom. Tiempo Listo": df_final["Tiempo Estado Listo"].sum() / resumen["Dias_trabajados"].sum(),
    "Prom. Tiempo No Listo": df_final["Tiempo Estado No Listo"].sum() / resumen["Dias_trabajados"].sum(),
    "Reenvios_cola": resumen["Reenvios_cola"].sum(),
    "Transferencias": resumen["Transferencias"].sum(),
    "TMO": df_final["Tiempo en Llamadas Contestadas"].sum() / resumen["Contestadas"].sum(),
}])

# ==================================================
# FORMATO DE TIEMPOS (MENSUAL)
# ==================================================
for c in [
    "Prom. Tiempo Logueado",
    "Prom. Tiempo ACW",
    "Prom. Tiempo Listo",
    "Prom. Tiempo No Listo",
    "TMO",
]:
    resumen[c] = resumen[c].apply(fmt)
    total_grupo[c] = total_grupo[c].apply(fmt)

COLUMNAS_MOSTRAR = [
    "Nombre de Usuario",
    "Contestadas",
    "Dias_trabajados",
    "Prom. Contestadas",
    "Prom. Contestadas x Hora",
    "Prom. Tiempo Logueado",
    "Prom. Tiempo ACW",
    "Prom. Tiempo Listo",
    "Prom. Tiempo No Listo",
    "Reenvios_cola",
    "Transferencias",
    "TMO",
]

# ==================================================
# SALIDA MENSUAL
# ==================================================
st.markdown("### Total del grupo")
st.dataframe(
    total_grupo[COLUMNAS_MOSTRAR],
    width="stretch",
    hide_index=True
)

st.markdown("## Resumen mensual por asistente")
st.dataframe(
    resumen.sort_values("Contestadas", ascending=False)[COLUMNAS_MOSTRAR],
    width="stretch",
    hide_index=True
)

# ==================================================
# DETALLE DIARIO
# ==================================================
st.markdown("## 📆 Detalle diario por asistente")

asistente_sel = st.selectbox(
    "Seleccionar asistente",
    sorted(resumen["Nombre de Usuario"].unique())
)

df_diario = df_final[df_final["Nombre de Usuario"] == asistente_sel].copy()

g_dia = df_diario.groupby("Fecha")

df_diario = g_dia.agg(
    Llamadas_Contestadas=("Llamadas Contestadas", "sum"),
    Tiempo_en_Llamadas_Contestadas=("Tiempo en Llamadas Contestadas", "sum"),
    Tiempo_Logueado=("Tiempo Logueado", "sum"),
    Tiempo_ACW=("Tiempo ACW", "sum"),
    Tiempo_Estado_Listo=("Tiempo Estado Listo", "sum"),
    Tiempo_Estado_No_Listo=("Tiempo Estado No Listo", "sum"),
    Reenvios_cola=("Re envios a la cola", "sum"),
    Transferencias=("Transferencias Realizadas", "sum"),
).reset_index()

horas_prod_dia = (
    df_diario["Tiempo_Logueado"] - df_diario["Tiempo_Estado_No_Listo"]
).dt.total_seconds() / 3600

df_diario["Prom. Contestadas x Hora"] = (
    df_diario["Llamadas_Contestadas"] / horas_prod_dia
).round(0).fillna(0).astype(int)

df_diario["Fecha"] = df_diario["Fecha"].dt.strftime("%d/%m/%Y")

for c in [
    "Tiempo_en_Llamadas_Contestadas",
    "Tiempo_Logueado",
    "Tiempo_ACW",
    "Tiempo_Estado_Listo",
    "Tiempo_Estado_No_Listo",
]:
    df_diario[c] = df_diario[c].apply(fmt)

st.dataframe(
    df_diario,
    width="stretch",
    hide_index=True
)
