import streamlit as st
import pandas as pd
from datetime import time

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(page_title="Supervisión – DATA METRO", layout="wide")

# ==================================================
# LOGIN (sin cambios)
# ==================================================
USUARIOS = {
    "carranza": {"password": "carranza2026", "rol": "supervisor", "grupo": "CARRANZA"},
    "jefatura": {"password": "admin123", "rol": "jefe"},
}

if "login_ok" not in st.session_state:
    st.session_state.login_ok = False

if not st.session_state.login_ok:
    st.title("🔐 Ingreso – Supervisión DATA METRO")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u in USUARIOS and USUARIOS[u]["password"] == p:
            st.session_state.login_ok = True
            st.session_state.rol = USUARIOS[u]["rol"]
            st.session_state.grupo = USUARIOS[u].get("grupo")
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# ==================================================
# FUNCIONES
# ==================================================
def excel_time_to_timedelta(x):
    if pd.isna(x):
        return pd.Timedelta(0)
    try:
        return pd.to_timedelta(x)
    except:
        return pd.Timedelta(0)

def fmt(td):
    if pd.isna(td):
        return ""
    s = int(td.total_seconds())
    return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"

# ==================================================
# CARGA CSV
# ==================================================
@st.cache_data
def cargar_datos(url):
    df = pd.read_csv(url, sep=";", encoding="latin1")
    df.columns = df.columns.str.strip().str.lower()

    df = df.rename(columns={
        "nombre de usuario": "Nombre de Usuario",
        "supervisor": "SUPERVISOR",
        "fecha": "Fecha",
        "contestadas": "Contestadas",
        "tiempo en contestadas": "Tiempo en Contestadas",
        "tiempo logueado": "Tiempo Logueado",
        "tiempo acw": "Tiempo ACW",
        "tiempo listo": "Tiempo Listo",
        "tiempo no listo": "Tiempo No Listo",
        "reenvios a cola": "Reenvios",
        "transferencias realizadas": "Transferencias",
    })

    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)

    for c in [
        "Tiempo en Contestadas","Tiempo Logueado","Tiempo ACW",
        "Tiempo Listo","Tiempo No Listo"
    ]:
        df[c] = df[c].apply(excel_time_to_timedelta)

    return df

df = cargar_datos(st.secrets["DATA_METRO_URL"])

# ==================================================
# FILTROS
# ==================================================
SUP_EXCL = {"ADICIONALES SDF","ROJAS","DIAZ","PORRAS","PAROLA","PAROLA-MUSSON"}

df = df[~df["SUPERVISOR"].isin(SUP_EXCL)]

col1, col2, col3 = st.columns(3)

with col1:
    if st.session_state.rol == "supervisor":
        sup = st.session_state.grupo
        st.info(f"Supervisor: {sup}")
    else:
        sup = st.selectbox("Supervisor", sorted(df["SUPERVISOR"].unique()))

with col2:
    anio = st.selectbox("Año", sorted(df["Fecha"].dt.year.unique()))

with col3:
    mes = st.selectbox("Mes", range(1,13))

df = df[
    (df["SUPERVISOR"] == sup) &
    (df["Fecha"].dt.year == anio) &
    (df["Fecha"].dt.month == mes)
]

# ==================================================
# RESUMEN MENSUAL
# ==================================================
g = df.groupby("Nombre de Usuario")

mensual = g.agg(
    Contestadas=("Contestadas","sum"),
    Dias_trabajados=("Fecha","nunique"),
    Reenvios=("Reenvios","sum"),
    Transferencias=("Transferencias","sum"),
    Prom_T_Log=("Tiempo Logueado","mean"),
    Prom_T_ACW=("Tiempo ACW","mean"),
    Prom_T_Listo=("Tiempo Listo","mean"),
    Prom_T_No_Listo=("Tiempo No Listo","mean"),
    TMO=("Tiempo en Contestadas","mean"),
).reset_index()

horas_prod = (mensual["Prom_T_Log"] - mensual["Prom_T_No_Listo"]).dt.total_seconds()/3600
mensual["Prom. Contestadas x Hora"] = (mensual["Contestadas"]/horas_prod).round(0)

mensual["Prom. Contestadas"] = (mensual["Contestadas"]/mensual["Dias_trabajados"]).round(0)

# formato
for c in ["Prom_T_Log","Prom_T_ACW","Prom_T_Listo","Prom_T_No_Listo","TMO"]:
    mensual[c] = mensual[c].apply(fmt)

# ==================================================
# TOTAL GRUPO
# ==================================================
total = pd.DataFrame([{
    "Nombre de Usuario": "TOTAL GRUPO",
    "Contestadas": mensual["Contestadas"].sum(),
    "Dias_trabajados": mensual["Dias_trabajados"].sum(),
    "Prom. Contestadas": round(mensual["Contestadas"].sum()/mensual["Dias_trabajados"].sum()),
    "Prom. Contestadas x Hora": round(mensual["Prom. Contestadas x Hora"].mean()),
    "Prom. Tiempo Logueado": fmt(pd.to_timedelta(mensual["Prom_T_Log"]).mean()),
    "Prom. Tiempo ACW": fmt(pd.to_timedelta(mensual["Prom_T_ACW"]).mean()),
    "Prom. Tiempo Listo": fmt(pd.to_timedelta(mensual["Prom_T_Listo"]).mean()),
    "Prom. Tiempo No Listo": fmt(pd.to_timedelta(mensual["Prom_T_No_Listo"]).mean()),
    "Reenvios": mensual["Reenvios"].sum(),
    "Transferencias": mensual["Transferencias"].sum(),
    "TMO": fmt(pd.to_timedelta(mensual["TMO"]).mean()),
}])

# ==================================================
# SALIDA
# ==================================================
st.markdown("## 🔹 Total del grupo")
st.dataframe(total, hide_index=True)

st.markdown("## 🔹 Resumen mensual por asistente")
st.dataframe(
    mensual.sort_values("Contestadas", ascending=False),
    hide_index=True
)

# ==================================================
# DETALLE DIARIO
# ==================================================
st.markdown("## 📆 Detalle diario por asistente")

asist = st.selectbox("Asistente", sorted(df["Nombre de Usuario"].unique()))
df_d = df[df["Nombre de Usuario"] == asist].copy()
df_d["Fecha"] = df_d["Fecha"].dt.strftime("%d/%m/%Y")

for c in ["Tiempo en Contestadas","Tiempo Logueado","Tiempo ACW","Tiempo Listo","Tiempo No Listo"]:
    df_d[c] = df_d[c].apply(fmt)

st.dataframe(df_d.sort_values("Fecha"), hide_index=True)
