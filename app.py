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
        "Tiempo Hold",
    ]
    for c in columnas_tiempo:
        df[c] = df[c].apply(to_td)

    return df

df = cargar_datos(st.secrets["DATA"]["DATA_METRO_URL"])

# ==================================================
# CARGA Y NORMALIZACIÓN DE CASOS CRM
# ==================================================
import re
import unicodedata


def _tokens_nombre(valor):
    """Limpia y separa los componentes de un nombre."""
    if pd.isna(valor):
        return []
    texto = str(valor).strip().upper()
    texto = texto.replace("?", "N")  # algunos caracteres ñ llegan dañados en la exportación CRM
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.findall(r"[A-Z0-9]+", texto)


def normalizar_nombre_crm(valor):
    """Normaliza nombres CRM, contemplando el formato duplicado nombre-apellido-nombre."""
    tokens = _tokens_nombre(valor)
    if len(tokens) < 2:
        return ""

    # Algunos registros vienen como: NOMBRE APELLIDO NOMBRE SEGUNDO_NOMBRE.
    # Ej.: CANDELA LUDUEÑA CANDELA ORIANA.
    if len(tokens) >= 3 and tokens[0] == tokens[2]:
        partes = [tokens[0], tokens[1]]
    else:
        # Formato habitual: nombres y luego apellido(s).
        partes = [tokens[0], tokens[-1]]

    return "|".join(sorted(partes))


def normalizar_nombre_metro(valor):
    """DATA METRO: apellido + nombre(s). Usa primer apellido y primer nombre."""
    tokens = _tokens_nombre(valor)
    if len(tokens) < 2:
        return ""
    return "|".join(sorted([tokens[0], tokens[1]]))


@st.cache_data(ttl=300)
def cargar_casos_crm(url):
    crm = pd.read_csv(url, sep=";", encoding="latin1", low_memory=False)
    crm["fecha_inicio"] = pd.to_datetime(crm["fecha_inicio"], errors="coerce", dayfirst=True)
    crm["fecha_inicio"] = crm["fecha_inicio"].dt.normalize()
    crm["nro_caso"] = crm["nro_caso"].fillna("").astype(str).str.strip()
    crm["motivo"] = crm["motivo"].astype(str).str.strip().str.upper()
    crm["categoria"] = crm["categoria"].fillna("RELLAMADO").astype(str).str.strip()
    crm["categoria"] = crm["categoria"].replace(
        to_replace=r"(?i)^SIN CATEGOR[IÍ]A$",
        value="RELLAMADO",
        regex=True,
    )
    crm["agente_crm"] = (
        crm["agente_iniciador_na"].fillna("").astype(str)
        .str.split("-", n=1).str[-1].str.strip()
    )
    crm["clave_agente"] = crm["agente_crm"].apply(normalizar_nombre_crm)
    return crm


crm = cargar_casos_crm(st.secrets["DATA"]["DATA_CRM_URL"])

# Mapa de nombre normalizado de DATA METRO -> nombre de usuario original.
# Solo se acepta una coincidencia única; agentes ambiguos/no encontrados se ignoran.
metro_nombres = (
    df["Nombre de Usuario"].dropna().astype(str).str.strip().drop_duplicates().tolist()
)
claves_metro = {}
for nombre_metro in metro_nombres:
    clave = normalizar_nombre_metro(nombre_metro)
    if clave:
        claves_metro.setdefault(clave, []).append(nombre_metro)

claves_metro_unicas = {
    clave: nombres[0] for clave, nombres in claves_metro.items() if len(nombres) == 1
}
crm["Nombre de Usuario"] = crm["clave_agente"].map(claves_metro_unicas)
crm = crm[
    crm["Nombre de Usuario"].notna()
    & crm["fecha_inicio"].notna()
    & crm["nro_caso"].ne("")
    & crm["nro_caso"].str.lower().ne("nan")
].copy()

# Se conservan todas las filas de CRM, incluso cuando coinciden todos sus campos.
# El tablero cuenta registros/gestiones cargadas, no números de caso únicos.

MOTIVOS_CRM = {
    "CONSULTA": "Consultas",
    "RECLAMO": "Reclamos",
    "QUEJA": "Quejas",
    "SOLICITUD": "Solicitudes",
    "SOLICITUDES": "Solicitudes",
    "AGRADECIMIENTO": "Agradecimientos",
    "SUGERENCIA": "Sugerencias",
    "RELLAMADO": "Rellamados",
    "RELLAMADOS": "Rellamados",
}
crm["Tipo de caso"] = crm["motivo"].map(MOTIVOS_CRM).fillna("Otros")

# Resumen diario de casos por asistente.
casos_diarios = (
    crm.groupby(["Nombre de Usuario", "fecha_inicio"])
    .agg(Casos_Cargados=("nro_caso", "size"))
    .reset_index()
    .rename(columns={"fecha_inicio": "Fecha"})
)

# Desglose diario por tipo de gestión.
casos_tipos_diarios = (
    crm.pivot_table(
        index=["Nombre de Usuario", "fecha_inicio"],
        columns="Tipo de caso",
        values="nro_caso",
        aggfunc="count",
        fill_value=0,
    )
    .reset_index()
    .rename(columns={"fecha_inicio": "Fecha"})
)
casos_tipos_diarios.columns.name = None

# Ranking diario de temas (categoria).
top_temas_diarios = (
    crm.groupby(["Nombre de Usuario", "fecha_inicio", "categoria"])
    .size()
    .reset_index(name="Cantidad")
    .sort_values(["Nombre de Usuario", "fecha_inicio", "Cantidad", "categoria"],
                 ascending=[True, True, False, True])
)

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
    "CARRIZO GABRIEL": "CARRIZO GABRIEL",

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
    "CARRIZO GABRIEL":"CARRIZO GABRIEL",
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
    "Gonzalez Company Malena","Parola Federico Javier","Simone Maylen","Ibarra Yamila"
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

# Se conserva el criterio original de supervisor dominante por cantidad de
# días registrados en DATA METRO, sin filtrar por llamadas contestadas.
dominante = (
    df_mes
    .groupby(["Nombre de Usuario", "SUPERVISOR"])["Fecha"]
    .nunique()
    .reset_index(name="dias")
    .sort_values(["Nombre de Usuario", "dias", "SUPERVISOR"], ascending=[True, False, True])
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
# CRM DEL GRUPO / SUPERVISOR EN EL MES SELECCIONADO
# ==================================================
# Se asignan los casos al supervisor dominante de cada asistente en el mes,
# usando la misma lógica de pertenencia que DATA METRO.
crm_mes_grupo = crm[
    (crm["fecha_inicio"].dt.year == anio)
    & (crm["fecha_inicio"].dt.month == mes_num)
].merge(
    dominante[["Nombre de Usuario", "SUPERVISOR"]],
    on="Nombre de Usuario",
    how="inner"
)

if not modo_call:
    crm_mes_grupo = crm_mes_grupo[crm_mes_grupo["SUPERVISOR"] == sup_sel].copy()

cantidad_casos_crm_grupo = len(crm_mes_grupo)

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
        Tiempo_hold=("Tiempo Hold", "sum"),
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
# Excluir el 29/10/2026 únicamente de los cálculos del resumen mensual por asistente.
# df_dia permanece intacto para el detalle diario y el total del grupo.
df_dia_mensual = df_dia[
    df_dia["Fecha"].dt.normalize() != pd.Timestamp("2026-10-29")
].copy()

mensual = (
    df_dia_mensual
    .groupby("Nombre de Usuario")
    .agg(
        Contestadas=("Contestadas","sum"),
        Tiempo_Contestadas_Total=("Tiempo_Contestadas","sum"),
        Dias_trabajados=("Fecha","nunique"),
        Reenvios=("Reenvios","sum"),
        Transferencias=("Transferencias","sum"),
        Prom_T_Log=("Tiempo_Logueado","mean"),
        Prom_T_ACW=("Tiempo_ACW","mean"),
        Prom_T_Listo=("Tiempo_Listo","mean"),
        Prom_T_No_Listo=("Tiempo_No_Listo","mean"),
    )
    .reset_index()
)

mensual["TMO"] = (
    mensual["Tiempo_Contestadas_Total"]
    .div(mensual["Contestadas"])
    .replace([pd.NA, pd.NaT, float("inf"), -float("inf")], pd.Timedelta(0))
)

mensual.drop(columns=["Tiempo_Contestadas_Total"], inplace=True)

# ============================
# PROMEDIOS CORRECTOS
# ============================
mensual["Prom. Contestadas"] = (
    mensual["Contestadas"] / mensual["Dias_trabajados"]
).round(0).astype(int)

horas_prod_asistente = (
    (df_dia_mensual["Tiempo_Logueado"] - df_dia_mensual["Tiempo_No_Listo"])
    .dt.total_seconds()
    .div(3600)
    .groupby(df_dia_mensual["Nombre de Usuario"])
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

# Casos CRM del mes por asistente, asignados según el supervisor dominante
# del período (la misma lógica utilizada para el total CRM del grupo).
casos_crm_por_asistente = (
    crm_mes_grupo.groupby("Nombre de Usuario")
    .size()
    .rename("Casos CRM")
    .reset_index()
)
mensual = mensual.merge(casos_crm_por_asistente, on="Nombre de Usuario", how="left")
mensual["Casos CRM"] = mensual["Casos CRM"].fillna(0).astype(int)

for c in ["Prom_T_Log","Prom_T_ACW","Prom_T_Listo","Prom_T_No_Listo","TMO"]:
    mensual[c] = mensual[c].apply(fmt)

# ==================================================
# TOTAL DEL GRUPO
# ==================================================

total_dias_asistentes = (
    df_dia.groupby("Nombre de Usuario")["Fecha"]
    .nunique()
    .sum()
)

horas_prod_grupo = (
    (df_dia["Tiempo_Logueado"] - df_dia["Tiempo_No_Listo"])
    .dt.total_seconds()
    .div(3600)
    .sum()
)

total = pd.DataFrame([{
    "Nombre de Usuario": "TOTAL CALL" if modo_call else "TOTAL GRUPO",

    "Contestadas": df_dia["Contestadas"].sum(),
    "Dias_trabajados": total_dias_asistentes,

    "Prom. Contestadas": (
        round(df_dia["Contestadas"].sum() / total_dias_asistentes)
        if total_dias_asistentes > 0 else 0
    ),

    "Prom. Contestadas x Hora": (
        round(df_dia["Contestadas"].sum() / horas_prod_grupo)
        if horas_prod_grupo > 0 else 0
    ),

    "Prom. Tiempo Logueado": fmt(df_dia["Tiempo_Logueado"].mean()),
    "Prom. Tiempo ACW": fmt(df_dia["Tiempo_ACW"].mean()),
    "Prom. Tiempo Listo": fmt(df_dia["Tiempo_Listo"].mean()),
    "Prom. Tiempo No Listo": fmt(df_dia["Tiempo_No_Listo"].mean()),

    "Reenvios": df_dia["Reenvios"].sum(),
    "Transferencias": df_dia["Transferencias"].sum(),
    "Casos CRM": cantidad_casos_crm_grupo,
   "TMO": fmt(
    df_dia["Tiempo_Contestadas"].sum() /
    df_dia["Contestadas"].sum()
) if df_dia["Contestadas"].sum() > 0 else fmt(pd.Timedelta(0)),
}])

COLUMNAS_MENSUAL = [
    "Nombre de Usuario",
    "Contestadas",
    "Casos CRM",
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
# SALIDA
# ==================================================
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

st.markdown("## 🔹 Total del grupo")
st.dataframe(total, hide_index=True, use_container_width=True)




# Top 5 de temas CRM del grupo/supervisor en el mes seleccionado.
st.markdown("### 🏆 Top 5 temas CRM del grupo")
st.caption(f"{mes_nombre} {anio} · {sup_sel if not modo_call else 'Todos los grupos'}")
if crm_mes_grupo.empty:
    st.info("No hay casos CRM atribuidos a este grupo durante el período seleccionado.")
else:
    top5_temas_grupo = (
        crm_mes_grupo["categoria"].value_counts()
        .head(5)
        .rename_axis("Tema")
        .reset_index(name="Casos")
    )
    st.dataframe(top5_temas_grupo, hide_index=True, use_container_width=True)



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

    for c in ["Tiempo_Contestadas","TMO","Tiempo_Logueado","Tiempo_ACW","Tiempo_Listo","Tiempo_No_Listo","Tiempo_hold"]:
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
        "Tiempo_hold",
        "Tiempo_Listo",
        "Tiempo_No_Listo",
        "Reenvios",
        "Transferencias",
    ]

    COLUMNAS_DIARIO_OK = [c for c in COLUMNAS_DIARIO if c in detalle.columns]
    detalle = detalle[COLUMNAS_DIARIO_OK]

    detalle = detalle.rename(columns={
    "Tiempo_hold": "Tiempo Hold"
    })


    # ============================
    # OUTPUT
    # ============================
    st.dataframe(
        detalle.sort_values("Fecha"),
        hide_index=True,
        use_container_width=True,
        height=450
    )

# ==================================================

    # ==================================================
    # ACUMULADO CRM DEL MES PARA EL ASISTENTE SELECCIONADO
    # ==================================================
    crm_asistente_mes = crm[
        (crm["Nombre de Usuario"] == asist)
        & (crm["fecha_inicio"].dt.year == anio)
        & (crm["fecha_inicio"].dt.month == mes_num)
    ].copy()

    st.markdown("### 📊 Acumulado CRM del período")
    st.caption(f"{mes_nombre} {anio} · {asist}")

    total_casos_crm = len(crm_asistente_mes)
    st.metric("Total de casos cargados", f"{total_casos_crm:,}".replace(",", "."))

    if crm_asistente_mes.empty:
        st.info("No hay casos CRM atribuidos a este asistente durante el período seleccionado.")
    else:
        col_crm_tipos, col_crm_temas = st.columns(2)
        with col_crm_tipos:
            st.markdown("**Casos por tipo**")
            acumulado_tipos = (
                crm_asistente_mes.groupby("Tipo de caso").size()
                .reindex(["Consultas", "Reclamos", "Quejas", "Solicitudes",
                          "Rellamados", "Agradecimientos", "Sugerencias", "Otros"], fill_value=0)
                .rename_axis("Tipo").reset_index(name="Casos")
            )
            st.dataframe(acumulado_tipos, hide_index=True, use_container_width=True)

        with col_crm_temas:
            st.markdown("**Top 5 temas del período**")
            acumulado_temas = (
                crm_asistente_mes["categoria"].value_counts()
                .head(5).rename_axis("Tema").reset_index(name="Casos")
            )
            st.dataframe(acumulado_temas, hide_index=True, use_container_width=True)
