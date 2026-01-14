import streamlit as st
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(page_title="Supervisión – DATA METRO", layout="wide")

# ==================================================
# LOGIN SIMPLE
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
def to_td(x):
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
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)

    columnas_tiempo = [
        "Tiempo en Llamadas Contestadas",
        "Tiempo Logueado",
        "Tiempo ACW",
        "Tiempo Estado Listo",
        "Tiempo Estado No Listo",
    ]
    for c in columnas_tiempo:
        df[c] = df[c].apply(to_td)

    return df

df = cargar_datos(st.secrets["DATA_METRO_URL"])

# ==================================================
# Asistentes excluidos del análisis (supervisores / pruebas)
# ==================================================
SUP_EXCL = {
    "ADICIONALES SDF","ROJAS","DIAZ","PORRAS",
    "PAROLA","PAROLA-MUSSON"
}

ASIST_EXCL = {
    "Laurenzano Renzo",
    "Carranza Fernando",
    "Graf Alejandro",
    "Alvarez Camila",
    "Delgado Claudia",
    "Gonzalez Company Malena",
    "Parola Federico Javier",
}

df = df[~df["SUPERVISOR"].isin(SUP_EXCL)]
df = df[~df["Nombre de Usuario"].isin(ASIST_EXCL)]


# ==================================================
# FILTROS
# ==================================================
col1, col2, col3 = st.columns(3)

with col1:
    if st.session_state.rol == "supervisor":
        sup_sel = st.session_state.grupo
        st.info(f"Supervisor: {sup_sel}")
    else:
        sup_sel = st.selectbox("Supervisor", sorted(df["SUPERVISOR"].unique()))

with col2:
    anio = st.selectbox("Año", sorted(df["Fecha"].dt.year.unique()))

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
# FILTRO BASE MES / AÑO (SIN SUPERVISOR)
# ==================================================
df_mes = df[
    (df["Fecha"].dt.year == anio) &
    (df["Fecha"].dt.month == mes_num)
]

# ==================================================
# SUPERVISOR DOMINANTE POR ASISTENTE
# ==================================================
dominante = (
    df_mes
    .groupby(["Nombre de Usuario", "SUPERVISOR"])["Fecha"]
    .nunique()
    .reset_index(name="dias")
    .sort_values("dias", ascending=False)
    .drop_duplicates("Nombre de Usuario")
)

asistentes_validos = dominante[
    dominante["SUPERVISOR"] == sup_sel
]["Nombre de Usuario"]

df_final = df_mes[
    df_mes["Nombre de Usuario"].isin(asistentes_validos)
]

# ==================================================
# AGRUPACIÓN DIARIA
# ==================================================
df_dia = (
    df_final
    .groupby(["Nombre de Usuario", "Fecha"])
    .agg(
        Contestadas=("Llamadas Contestadas", "sum"),
        Tiempo_Contestadas=("Tiempo en Llamadas Contestadas", "sum"),
        Tiempo_Logueado=("Tiempo Logueado", "sum"),
        Tiempo_ACW=("Tiempo ACW", "sum"),
        Tiempo_Listo=("Tiempo Estado Listo", "sum"),
        Tiempo_No_Listo=("Tiempo Estado No Listo", "sum"),
        Reenvios=("Re envios a la cola", "sum"),
        Transferencias=("Transferencias Realizadas", "sum"),
    )
    .reset_index()
)

# ==================================================
# RESUMEN MENSUAL
# ==================================================
g = df_dia.groupby("Nombre de Usuario")

mensual = g.agg(
    Contestadas=("Contestadas","sum"),
    Dias_trabajados=("Fecha","nunique"),
    Reenvios=("Reenvios","sum"),
    Transferencias=("Transferencias","sum"),
    Prom_T_Log=("Tiempo_Logueado","mean"),
    Prom_T_ACW=("Tiempo_ACW","mean"),
    Prom_T_Listo=("Tiempo_Listo","mean"),
    Prom_T_No_Listo=("Tiempo_No_Listo","mean"),
    TMO=("Tiempo_Contestadas","mean"),
).reset_index()

horas_prod = (
    (mensual["Prom_T_Log"] - mensual["Prom_T_No_Listo"])
    .dt.total_seconds()
    .div(3600)
)

mensual["Prom. Contestadas"] = (
    mensual["Contestadas"]
    .div(mensual["Dias_trabajados"])
    .round(0)
    .astype(int)
)

mensual["Prom. Contestadas x Hora"] = (
    mensual["Contestadas"]
    .div(horas_prod)
    .replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0)
    .fillna(0)
    .round(0)
    .astype(int)
)

for c in ["Prom_T_Log","Prom_T_ACW","Prom_T_Listo","Prom_T_No_Listo","TMO"]:
    mensual[c] = mensual[c].apply(fmt)

# ==================================================
# TOTAL DEL GRUPO
# ==================================================
total_dias = mensual["Dias_trabajados"].sum()

total = pd.DataFrame([{
    "Nombre de Usuario": "TOTAL GRUPO",
    "Contestadas": mensual["Contestadas"].sum(),
    "Dias_trabajados": total_dias,
    "Prom. Contestadas": round(mensual["Contestadas"].sum()/total_dias) if total_dias else 0,
    "Prom. Contestadas x Hora": round(mensual["Prom. Contestadas x Hora"].mean()),
    "Prom. Tiempo Logueado": fmt(df_dia["Tiempo_Logueado"].mean()),
    "Prom. Tiempo ACW": fmt(df_dia["Tiempo_ACW"].mean()),
    "Prom. Tiempo Listo": fmt(df_dia["Tiempo_Listo"].mean()),
    "Prom. Tiempo No Listo": fmt(df_dia["Tiempo_No_Listo"].mean()),
    "Reenvios": mensual["Reenvios"].sum(),
    "Transferencias": mensual["Transferencias"].sum(),
    "TMO": fmt(df_dia["Tiempo_Contestadas"].mean()),
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

asist = st.selectbox("Asistente", sorted(df_dia["Nombre de Usuario"].unique()))
detalle = df_dia[df_dia["Nombre de Usuario"] == asist].copy()
detalle["Fecha"] = detalle["Fecha"].dt.strftime("%d/%m/%Y")

for c in ["Tiempo_Contestadas","Tiempo_Logueado","Tiempo_ACW","Tiempo_Listo","Tiempo_No_Listo"]:
    detalle[c] = detalle[c].apply(fmt)

st.dataframe(detalle.sort_values("Fecha"), hide_index=True)
