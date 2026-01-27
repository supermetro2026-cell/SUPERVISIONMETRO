import streamlit as st
import pandas as pd

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(page_title="Supervisión – DATA METRO", layout="wide")

# ==================================================
# LOGIN
# ==================================================
USUARIOS = st.secrets["USUARIOS"]

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

df = cargar_datos(st.secrets["DATA"]["DATA_METRO_URL"])
# ==================================================
# NORMALIZACIÓN Y UNIFICACIÓN DE SUPERVISORES
# ==================================================

# Limpieza básica
df["SUPERVISOR"] = (
    df["SUPERVISOR"]
    .str.strip()
    .str.replace("  ", " ")
)

# Mapa CANÓNICO -> FORMATO DISPLAY (NOMBRE + APELLIDO)
SUPERVISORES_MAP = {
    # HISTÓRICO (solo apellido) -> NUEVO FORMATO
    "SIMONE": "SIMONE MAYLEN",
    "CARRANZA": "CARRANZA FERNANDO",
    "ZAVARONI": "ZAVARONI PAOLA",
    "LAZARTE": "LAZARTE NICOLAS",
    "FERNANDEZ P": "FERNANDEZ PATRICIA",
    "ALBORNOZ": "ALBORNOZ IVAN",
    "SUREDA": "SUREDA LEANDRO",
    "GRAF": "GRAF ALEJANDRO",
    "VEXENAT": "VEXENAT JORGE",
    "GEREZ": "GEREZ ANGEL",
    "RICO": "RICO MELISA",
    "PORRAS": "KARINA PORRAS",
    "ROJAS": "GASTON ROJAS",
    "DIAZ": "DIAZ CELESTE",
    "DELGADO": "DELGADO CLAUDIA",
    "GONZALEZ F": "GONZALEZ FRANCISCO",
    "GONZALEZ COMPANY": "GONZALEZ COMPANY MALENA",

    # NUEVOS FORMATOS YA OK (los dejamos igual)
    "SIMONE MAYLEN": "SIMONE MAYLEN",
    "CARRANZA FERNANDO": "CARRANZA FERNANDO",
    "ZAVARONI PAOLA": "ZAVARONI PAOLA",
    "LAZARTE NICOLAS": "LAZARTE NICOLAS",
    "FERNANDEZ PATRICIA": "FERNANDEZ PATRICIA",
    "ALBORNOZ IVAN": "ALBORNOZ IVAN",
    "SUREDA LEANDRO": "SUREDA LEANDRO",
    "GRAF ALEJANDRO": "GRAF ALEJANDRO",
    "VEXENAT JORGE": "VEXENAT JORGE",
    "GEREZ ANGEL": "GEREZ ANGEL",
    "RICO MELISA": "RICO MELISA",
    "KARINA PORRAS": "KARINA PORRAS",
    "GASTON ROJAS": "GASTON ROJAS",
    "DIAZ CELESTE": "DIAZ CELESTE",
    "DELGADO CLAUDIA": "DELGADO CLAUDIA",
    "GONZALEZ FRANCISCO": "GONZALEZ FRANCISCO",
    "GONZALEZ COMPANY MALENA": "GONZALEZ COMPANY MALENA",
}

# Aplicar reemplazo
df["SUPERVISOR"] = df["SUPERVISOR"].replace(SUPERVISORES_MAP)

# ==================================================
# EXCLUSIONES
# ==================================================

SUP_EXCL = {
    "ADICIONALES SDF","DIAZ","PORRAS","ROJAS", "ALBORNOZ", "GONZALEZ C",
    "PAROLA","PAROLA-MUSSON", "DIAZ CELESTE","KARINA PORRAS","GASTON ROJAS","ALBORNOZ IVAN","GRESPAN","LEGUIZAMON"
}

ASIST_EXCL = {
    "Laurenzano Renzo","Carranza Fernando","Graf Alejandro",
    "Alvarez Camila","Delgado Claudia",
    "Gonzalez Company Malena","Parola Federico Javier","Simone Maylen",
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
        lista_sup = sorted(df["SUPERVISOR"].unique())
        lista_sup.insert(0, "TODOS (CALL)")
        sup_sel = st.selectbox("Supervisor", lista_sup)

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

#DETECTAR SI ESTAMOS EN MODO TODOS
modo_call = (sup_sel == "TODOS (CALL)")

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

if sup_sel == "TODOS (CALL)":
    df_final = df_mes.copy()
else:
    asistentes_validos = dominante[
        dominante["SUPERVISOR"] == sup_sel
    ]["Nombre de Usuario"]
    df_final = df_mes[df_mes["Nombre de Usuario"].isin(asistentes_validos)]

# ==================================================
# VALIDACIÓN: SIN DATOS
# ==================================================

if df_final.empty:
    st.warning("⚠️ No hay datos para este período.")
    st.stop()

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

# ============================
# TMO DIARIO
# ============================
df_dia["TMO"] = (
    df_dia["Tiempo_Contestadas"]
    .div(df_dia["Contestadas"])
    .replace([pd.NA, pd.NaT, float("inf"), -float("inf")], pd.Timedelta(0))
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

COLUMNAS_MENSUAL = [
    "Nombre de Usuario",
    "Contestadas",
    "Dias_trabajados",
    "Prom. Contestadas",
    "Prom. Contestadas x Hora",
    "TMO",
    "Prom_T_Log",
    "Prom_T_ACW",
    "Prom_T_Listo",
    "Prom_T_No_Listo",
    "Reenvios",
    "Transferencias",
]

COLUMNAS_MENSUAL_OK = [
    c for c in COLUMNAS_MENSUAL if c in mensual.columns
]

mensual_mostrar = mensual[COLUMNAS_MENSUAL_OK]

import altair as alt

# ==================================================
#agregado para jefatura TABLA RESUMEN MENS POR SUP
if sup_sel == "TODOS (CALL)":

    st.markdown("## 👔 Resumen mensual por supervisor")

    resumen_sup = (
        df_mes
        .groupby("SUPERVISOR")
        .agg(
            Contestadas=("Llamadas Contestadas","sum"),
            Dias_trabajados=("Fecha","nunique"),
            TMO=("Tiempo en Llamadas Contestadas","mean"),
            Tiempo_No_Listo=("Tiempo Estado No Listo","mean"),
        )
        .reset_index()
    )

    # Prom contestadas x día
    resumen_sup["Prom. Contestadas"] = (
        resumen_sup["Contestadas"] / resumen_sup["Dias_trabajados"]
    ).round(0).astype(int)

    # Formato tiempos
    resumen_sup["TMO"] = resumen_sup["TMO"].apply(fmt)
    resumen_sup["Tiempo_No_Listo"] = resumen_sup["Tiempo_No_Listo"].apply(fmt)

    COLUMNAS_SUP = [
        "SUPERVISOR",
        "Contestadas",
        "Dias_trabajados",
        "Prom. Contestadas",
        "TMO",
        "Tiempo_No_Listo",
    ]

    st.dataframe(
        resumen_sup.sort_values("Contestadas", ascending=False)[COLUMNAS_SUP],
        hide_index=True,
        use_container_width=True
    )
# ==================================================
# ==================================================
# SALIDA
# ==================================================
st.markdown("## 🔹 Total del grupo")
st.dataframe(total, hide_index=True, use_container_width=True)

# ==================================================
# 📊 ACUMULADO ANUAL DE CONTESTADAS
# ==================================================
st.markdown("## 📊 Acumulado anual de contestadas")

# Base anual
if sup_sel == "TODOS (CALL)":
    df_anual = df[df["Fecha"].dt.year == anio]
else:
    df_anual = df[
        (df["Fecha"].dt.year == anio) &
        (df["Nombre de Usuario"].isin(asistentes_validos))
    ]

# Agrupar por mes
acumulado_mes = (
    df_anual
    .groupby(df_anual["Fecha"].dt.month)["Llamadas Contestadas"]
    .sum()
    .reset_index(name="Contestadas")
    .rename(columns={"Fecha": "Mes"})
)

# Completar meses faltantes
acumulado_mes = (
    acumulado_mes
    .set_index("Mes")
    .reindex(range(1, 13), fill_value=0)
    .reset_index()
)

# Nombre de mes
acumulado_mes["Mes_nombre"] = [
    "Ene","Feb","Mar","Abr","May","Jun",
    "Jul","Ago","Sep","Oct","Nov","Dic"
]

# Orden cronológico
orden_meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

# Gráfico
chart = (
    alt.Chart(acumulado_mes)
    .mark_bar()
    .encode(
        x=alt.X("Mes_nombre:N", sort=orden_meses, title="Mes"),
        y=alt.Y("Contestadas:Q", title="Llamadas contestadas"),
        tooltip=["Mes_nombre", "Contestadas"]
    )
    .properties(height=400)
)

st.altair_chart(chart, use_container_width=True)

# ==================================================

if not modo_call:
    st.markdown("## 🔹 Resumen mensual por asistente")
    st.dataframe(
        mensual_mostrar.sort_values("Contestadas", ascending=False),
        hide_index=True,
        use_container_width=True
    )


# ==================================================
# DETALLE DIARIO POR ASISTENTE (solo modo supervisor)
# ==================================================
if not modo_call:

    st.markdown("## 📆 Detalle diario por asistente")

    asist = st.selectbox("Asistente", sorted(df_dia["Nombre de Usuario"].unique()))
    detalle = df_dia[df_dia["Nombre de Usuario"] == asist].copy()

    # ============================
    # PRODUCTIVIDAD DIARIA
    # ============================
    horas_prod_dia = (
        (detalle["Tiempo_Logueado"] - detalle["Tiempo_No_Listo"])
        .dt.total_seconds()
        .div(3600)
    )

    detalle["Prom. Contestadas x Hora"] = (
        detalle["Contestadas"] / horas_prod_dia
    ).replace([pd.NA, pd.NaT, float("inf"), -float("inf")], 0).fillna(0).round(0).astype(int)

    # ============================
    # FORMATO FECHA Y TIEMPOS
    # ============================
    detalle["Fecha"] = detalle["Fecha"].dt.strftime("%d/%m/%Y")

    for c in ["Tiempo_Contestadas","TMO","Tiempo_Logueado","Tiempo_ACW","Tiempo_Listo","Tiempo_No_Listo"]:
        detalle[c] = detalle[c].apply(fmt)

    # ============================
    # ORDEN COLUMNAS
    # ============================
    COLUMNAS_DIARIO = [
        "Nombre de Usuario",
        "Fecha",
        "Contestadas",
        "Prom. Contestadas x Hora",
        "TMO",
        "Tiempo_Contestadas",
        "Tiempo_Logueado",
        "Tiempo_ACW",
        "Tiempo_Listo",
        "Tiempo_No_Listo",
        "Reenvios",
        "Transferencias",
    ]

    COLUMNAS_DIARIO_OK = [c for c in COLUMNAS_DIARIO if c in detalle.columns]
    detalle = detalle[COLUMNAS_DIARIO_OK]

    # ============================
    # OUTPUT
    # ============================
    st.dataframe(
        detalle.sort_values("Fecha"),
        hide_index=True,
        use_container_width=True,
        height=450
    )


