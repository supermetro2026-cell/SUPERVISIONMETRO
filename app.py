import streamlit as st
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(page_title="Supervisión – DATA METRO", layout="wide")

# ==================================================
# LOGIN
# ==================================================
USUARIOS = {
    "carranza": {"password": "carranza2026", "rol": "supervisor", "grupo": "CARRANZA"},
    "simone": {"password": "simone2026", "rol": "supervisor", "grupo": "SIMONE"},
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
# EXCLUSIONES
# ==================================================

SUP_EXCL = {
    "ADICIONALES SDF","ROJAS","DIAZ","PORRAS",
    "PAROLA","PAROLA-MUSSON"
}

ASIST_EXCL = {
    "Laurenzano Renzo","Carranza Fernando","Graf Alejandro",
    "Alvarez Camila","Delgado Claudia",
    "Gonzalez Company Malena","Parola Federico Javier",
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
# FILTRO MES
# ==================================================
df_mes = df[
    (df["Fecha"].dt.year == anio) &
    (df["Fecha"].dt.month == mes_num)
]

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

asistentes_validos = dominante[
    dominante["SUPERVISOR"] == sup_sel
]["Nombre de Usuario"]

df_final = df_mes[df_mes["Nombre de Usuario"].isin(asistentes_validos)]

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
mensual = (
    df_dia
    .groupby("Nombre de Usuario")
    .agg(
        Contestadas=("Contestadas","sum"),
        Dias_trabajados=("Fecha","nunique"),
        Reenvios=("Reenvios","sum"),
        Transferencias=("Transferencias","sum"),
        Prom_T_Log=("Tiempo_Logueado","mean"),
        Prom_T_ACW=("Tiempo_ACW","mean"),
        Prom_T_Listo=("Tiempo_Listo","mean"),
        Prom_T_No_Listo=("Tiempo_No_Listo","mean"),
        TMO=("Tiempo_Contestadas","mean"),
    )
    .reset_index()
)

# ============================
# PROMEDIOS CORRECTOS
# ============================
mensual["Prom. Contestadas"] = (
    mensual["Contestadas"] / mensual["Dias_trabajados"]
).round(0).astype(int)

horas_prod_asistente = (
    (df_dia["Tiempo_Logueado"] - df_dia["Tiempo_No_Listo"])
    .dt.total_seconds()
    .div(3600)
    .groupby(df_dia["Nombre de Usuario"])
    .sum()
)

mensual = mensual.set_index("Nombre de Usuario")

mensual["Prom. Contestadas x Hora"] = (
    mensual["Contestadas"]
    .div(horas_prod_asistente)
    .replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0)
    .fillna(0)
    .round(0)
    .astype(int)
)

mensual = mensual.reset_index()

for c in ["Prom_T_Log","Prom_T_ACW","Prom_T_Listo","Prom_T_No_Listo","TMO"]:
    mensual[c] = mensual[c].apply(fmt)

# ==================================================
# TOTAL DEL GRUPO
# ==================================================

# días reales trabajados por el grupo (suma de días de cada asistente)
total_dias_asistentes = mensual["Dias_trabajados"].sum()

# horas productivas reales del grupo
horas_prod_grupo = (
    (df_dia["Tiempo_Logueado"] - df_dia["Tiempo_No_Listo"])
    .dt.total_seconds()
    .div(3600)
    .sum()
)

total = pd.DataFrame([{
    "Nombre de Usuario": "TOTAL GRUPO",
    "Contestadas": mensual["Contestadas"].sum(),
    "Dias_trabajados": total_dias_asistentes,

    # promedio diario correcto
    "Prom. Contestadas": (
        round(mensual["Contestadas"].sum() / total_dias_asistentes)
        if total_dias_asistentes > 0 else 0
    ),

    # promedio por hora correcto
    "Prom. Contestadas x Hora": (
        round(mensual["Contestadas"].sum() / horas_prod_grupo)
        if horas_prod_grupo > 0 else 0
    ),

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
st.dataframe(total, hide_index=True, use_container_width=True)

st.markdown("## 🔹 Resumen mensual por asistente")
st.dataframe(
    mensual.sort_values("Contestadas", ascending=False),
    hide_index=True,
    use_container_width=True
)

# ==================================================
# DETALLE DIARIO
# ==================================================
st.markdown("## 📆 Detalle diario por asistente")

asist = st.selectbox("Asistente", sorted(df_dia["Nombre de Usuario"].unique()))
detalle = df_dia[df_dia["Nombre de Usuario"] == asist].copy()

horas_prod_dia = (
    (detalle["Tiempo_Logueado"] - detalle["Tiempo_No_Listo"])
    .dt.total_seconds()
    .div(3600)
)

detalle["Prom. Contestadas x Hora"] = (
    detalle["Contestadas"] / horas_prod_dia
).replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0).fillna(0).round(0).astype(int)

detalle["Fecha"] = detalle["Fecha"].dt.strftime("%d/%m/%Y")

for c in ["Tiempo_Contestadas","Tiempo_Logueado","Tiempo_ACW","Tiempo_Listo","Tiempo_No_Listo"]:
    detalle[c] = detalle[c].apply(fmt)

st.dataframe(
    detalle.sort_values("Fecha"),
    hide_index=True,
    use_container_width=True,
    height=450
)
