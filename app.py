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
# USUARIOS
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
# HEADER
# ==================================================
st.title("Supervisión – DATA METRO")

colA, colB = st.columns([4, 1])
with colB:
    if st.button("Salir"):
        st.session_state.clear()
        st.rerun()

# ==================================================
# FUNCIONES
# ==================================================
def excel_time_to_timedelta(x):
    if pd.isna(x):
        return pd.Timedelta(0)
    if isinstance(x, time):
        return pd.Timedelta(hours=x.hour, minutes=x.minute, seconds=x.second)
    try:
        return pd.to_timedelta(x)
    except:
        return pd.Timedelta(0)

def fmt(td):
    if pd.isna(td):
        return ""
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02}:{m:02}:{s:02}"

# ==================================================
# CARGA CSV GOOGLE DRIVE
# ==================================================
@st.cache_data(show_spinner="Cargando datos...")
def cargar_datos(url):
    df = pd.read_csv(
        url,
        sep=";",
        encoding="latin1"
    )

    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")

    for c in [
        "Tiempo en Llamadas Contestadas",
        "Tiempo Logueado",
        "Tiempo ACW",
        "Tiempo Estado Listo",
        "Tiempo Estado No Listo",
    ]:
        df[c] = df[c].apply(excel_time_to_timedelta)

    return df

df = cargar_datos(st.secrets["DATA_METRO_URL"])

# ==================================================
# FILTROS
# ==================================================
st.markdown("## Filtros")

col1, col2, col3 = st.columns(3)

with col1:
    if st.session_state.rol == "supervisor":
        supervisor_sel = st.session_state.grupo
        st.info(f"Grupo: {supervisor_sel}")
    else:
        supervisor_sel = st.selectbox(
            "Supervisor",
            sorted(df["SUPERVISOR"].dropna().unique())
        )

with col2:
    anio = st.selectbox("Año", sorted(df["Fecha"].dt.year.dropna().unique()))

with col3:
    mes = st.selectbox(
        "Mes",
        ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    )

mes_num = {
    "Enero":1,"Febrero":2,"Marzo":3,"Abril":4,"Mayo":5,"Junio":6,
    "Julio":7,"Agosto":8,"Septiembre":9,"Octubre":10,"Noviembre":11,"Diciembre":12
}[mes]

df_mes = df[
    (df["SUPERVISOR"] == supervisor_sel) &
    (df["Fecha"].dt.year == anio) &
    (df["Fecha"].dt.month == mes_num)
]

# ==================================================
# RESUMEN MENSUAL
# ==================================================
g = df_mes.groupby("Nombre de Usuario")

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



horas_prod = (resumen["Tiempo_Logueado"] - resumen["Tiempo_No_Listo"]).dt.total_seconds() / 3600
resumen["Prom. Contestadas x Hora"] = (resumen["Contestadas"] / horas_prod).round(0).astype(int)

resumen["Prom. Contestadas x Hora"] = (
    resumen["Contestadas"] / horas_prod
).replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0
).fillna(0
).round(0
).astype(int)

resumen["Prom. Tiempo Logueado"] = resumen["Tiempo_Logueado"] / resumen["Dias_trabajados"]
resumen["Prom. Tiempo ACW"] = resumen["Tiempo_ACW"] / resumen["Dias_trabajados"]
resumen["Prom. Tiempo Listo"] = resumen["Tiempo_Listo"] / resumen["Dias_trabajados"]
resumen["Prom. Tiempo No Listo"] = resumen["Tiempo_No_Listo"] / resumen["Dias_trabajados"]
resumen["TMO"] = resumen["Tiempo_Contestadas"] / resumen["Contestadas"]

for c in [
    "Prom. Tiempo Logueado",
    "Prom. Tiempo ACW",
    "Prom. Tiempo Listo",
    "Prom. Tiempo No Listo",
    "TMO",
]:
    resumen[c] = resumen[c].apply(fmt)

# ==================================================
# TOTAL GRUPO
# ==================================================
st.markdown("### Total del grupo")
st.dataframe(resumen, hide_index=True)

# ==================================================
# DETALLE DIARIO
# ==================================================
st.markdown("## 📆 Detalle diario por asistente")

asistente = st.selectbox(
    "Asistente",
    sorted(resumen["Nombre de Usuario"].unique())
)

df_dia = df_mes[df_mes["Nombre de Usuario"] == asistente]

df_dia = df_dia.groupby("Fecha").agg(
    Llamadas_Contestadas=("Llamadas Contestadas", "sum"),
    Tiempo_Logueado=("Tiempo Logueado", "sum"),
    Tiempo_ACW=("Tiempo ACW", "sum"),
    Tiempo_Listo=("Tiempo Estado Listo", "sum"),
    Tiempo_No_Listo=("Tiempo Estado No Listo", "sum"),
).reset_index()

horas = (df_dia["Tiempo_Logueado"] - df_dia["Tiempo_No_Listo"]).dt.total_seconds() / 3600
df_dia["Prom. Contestadas x Hora"] = (
    df_dia["Llamadas_Contestadas"] / horas
).replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0
).fillna(0
).round(0
).astype(int)


df_dia["Fecha"] = df_dia["Fecha"].dt.strftime("%d/%m/%Y")

for c in ["Tiempo_Logueado","Tiempo_ACW","Tiempo_Listo","Tiempo_No_Listo"]:
    df_dia[c] = df_dia[c].apply(fmt)

st.dataframe(df_dia, hide_index=True)
