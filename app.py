from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(
    page_title="GRUPO PINZON - CRM", page_icon="🛡️", layout="wide"
)

# --- CONFIGURACIÓN DE CONEXIÓN INTELIGENTE (LOCAL vs SUPABASE) ---
try:
  if "postgres" in st.secrets and "connection_string" in st.secrets["postgres"]:
    db_url = st.secrets["postgres"]["connection_string"]
    if db_url.startswith("postgres://"):
      db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
      db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
  else:
    db_url = "sqlite:///crm_local_test.db"
    engine = create_engine(db_url)
    st.sidebar.info(
        "💻 Modo Pruebas Local (SQLite)\nTus datos aquí no afectan la oficina."
    )
except Exception as e:
  try:
    db_url = "sqlite:///crm_local_test.db"
    engine = create_engine(db_url)
    st.sidebar.info("💻 Modo Pruebas Local (SQLite por excepción)")
  except Exception as inner_e:
    st.error(
        f"⚠️ Error crítico de conexión a la base de datos: {e} / {inner_e}"
    )
    st.stop()

# Detectar el motor para ajustar la sintaxis SQL dinámicamente
ES_SQLITE = engine.name == "sqlite"
PH = "?" if ES_SQLITE else "%s"
ID_SERIAL = (
    "INTEGER PRIMARY KEY AUTOINCREMENT" if ES_SQLITE else "SERIAL PRIMARY KEY"
)


# --- ESTILOS CSS GENERALES ---
st.markdown(
    """
<style>
    /* OCULTAR BARRA SUPERIOR DE STREAMLIT (Share, estrella, github, etc.) */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    footer {
        visibility: hidden;
    }
    [data-testid="stStatusWidget"] {
        visibility: hidden;
    }
    .stAppDeployButton {
        display: none !important;
    }

    h2, h3 {
        color: #002B49 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background-color: #0072CE;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #005bb5;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(0, 114, 206, 0.3);
    }
    button[kind="secondary"] {
        background-color: #78BE20 !important;
        color: white !important;
        border: none !important;
    }
    div[data-testid="stPopoverBody"] {
        width: 220px !important;
        max-width: 220px !important;
        padding: 8px !important;
    }
    div[data-testid="stPopoverBody"] button {
        font-size: 11px !important;
        padding: 4px 8px !important;
        min-height: 28px !important;
    }
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-family: sans-serif;
        font-size: 14px;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-top: 10px;
    }
    .custom-table th {
        background-color: #78BE20 !important;
        color: #ffffff !important;
        text-align: left;
        padding: 12px 16px;
        font-weight: 700;
    }
    .custom-table td {
        padding: 10px 16px;
        color: #334155;
        border-bottom: 1px solid #e2e8f0;
    }
    .custom-table tr:hover {
        background-color: #f1f5f9;
    }
    .fila-excedida {
        background-color: #f8d7da !important;
        color: #721c24 !important;
        font-weight: bold;
    }
    [data-testid="stDataFrame"] th, div[data-testid="stTable"] th {
        background-color: #78BE20 !important;
        color: white !important;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #78BE20;
    }
</style>
""",
    unsafe_allow_html=True,
)


def obtener_ahora_mexico():
  return datetime.now(timezone(timedelta(hours=-6)))


def calcular_edad_desde_rfc(rfc):
  if not rfc or len(rfc.strip()) < 10 or str(rfc).startswith("TEMP_"):
    return "S/D"
  try:
    limpio = rfc.strip().upper()
    yy, mm, dd = int(limpio[4:6]), int(limpio[6:8]), int(limpio[8:10])
    anio_actual = obtener_ahora_mexico().year
    siglo = 2000 if yy <= (anio_actual % 100) else 1900
    anio = siglo + yy
    f_nac = datetime(anio, mm, dd)
    hoy = obtener_ahora_mexico()
    edad = (
        hoy.year
        - f_nac.year
        - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
    )
    return str(edad) if 0 <= edad < 120 else "S/D"
  except Exception:
    return "S/D"


def limpiar_fecha_str(val):
  if pd.isna(val) or val is None:
    return ""
  s = str(val).strip()
  if not s or s.lower() == "nan" or s == "0":
    return ""
  return s.split(" ")[0] if " " in s else s


def parsear_a_date(val):
  s = limpiar_fecha_str(val)
  if not s:
    return obtener_ahora_mexico().date()
  for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
    try:
      return datetime.strptime(s, fmt).date()
    except ValueError:
      continue
  return obtener_ahora_mexico().date()


# --- INICIALIZACIÓN DE TABLAS ---
with engine.begin() as conn_sql:
  conn_sql.exec_driver_sql(f"""
    CREATE TABLE IF NOT EXISTS usuarios (
        id {ID_SERIAL},
        usuario TEXT UNIQUE, password TEXT, rol TEXT,
        nombre_completo TEXT, apellido TEXT, telefono TEXT, direccion TEXT
    )
    """)

  conn_sql.exec_driver_sql(f"""
    CREATE TABLE IF NOT EXISTS clientes (
        rfc TEXT PRIMARY KEY, nombre TEXT, apellido TEXT,
        tel1 TEXT, tel2 TEXT, tel3 TEXT, telefono TEXT,
        sector TEXT, poliza TEXT, dividendos TEXT,
        ult_fecha_asignacion TEXT, edad TEXT, fecha_ult_mov TEXT,
        observaciones_tel TEXT, observaciones_asesor TEXT,
        telefonista_asignada TEXT DEFAULT 'Sin Asignar',
        estatus TEXT DEFAULT 'Disponible',
        estado_tel1 TEXT DEFAULT 'Sin marcar',
        estado_tel2 TEXT DEFAULT 'Sin marcar',
        estado_tel3 TEXT DEFAULT 'Sin marcar',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

  conn_sql.exec_driver_sql(f"""
    CREATE TABLE IF NOT EXISTS historial_llamadas (
        id {ID_SERIAL},
        rfc_cliente TEXT, usuario TEXT, accion TEXT, detalle TEXT, fecha_registro TEXT
    )
    """)

  conn_sql.exec_driver_sql(f"""
    CREATE TABLE IF NOT EXISTS citas (
        id {ID_SERIAL},
        rfc_cliente TEXT, cliente TEXT NOT NULL, telefono TEXT,
        agente TEXT, asesor TEXT DEFAULT 'Sin Asignar',
        fecha TEXT NOT NULL, hora TEXT NOT NULL, estado TEXT NOT NULL, notas TEXT
    )
    """)

  conn_sql.exec_driver_sql(f"""
    CREATE TABLE IF NOT EXISTS asistencia_telefonistas (
        id {ID_SERIAL},
        usuario TEXT NOT NULL,
        tipo_registro TEXT NOT NULL,
        fecha TEXT NOT NULL,
        hora_inicio TEXT NOT NULL,
        hora_fin TEXT,
        duracion_minutos INTEGER,
        estado TEXT NOT NULL
    )
    """)

hoy_str_mex = obtener_ahora_mexico().strftime("%Y-%m-%d")
with engine.begin() as conn_sql:
  conn_sql.exec_driver_sql(
      f"""
        UPDATE citas SET estado = 'No Asistió (Automático)' 
        WHERE estado = 'Pendiente' AND date(fecha) < {PH}
    """,
      (hoy_str_mex,),
  )

with engine.connect() as conn_sql:
  res_u = conn_sql.exec_driver_sql("SELECT COUNT(*) FROM usuarios").fetchone()[0]

if res_u == 0:
  with engine.begin() as conn_sql:
    conn_sql.exec_driver_sql(
        f"""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
        (
            "admin",
            "1234",
            "Administrador",
            "Administrador",
            "Principal",
            "5550000000",
            "Oficina Central",
        ),
    )
    conn_sql.exec_driver_sql(
        f"""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
        (
            "tele1",
            "1234",
            "Telefonista",
            "Telefonista",
            "Uno",
            "5551111111",
            "Call Center",
        ),
    )
    conn_sql.exec_driver_sql(
        f"""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
        (
            "tele2",
            "1234",
            "Telefonista",
            "Telefonista",
            "Dos",
            "5552222222",
            "Call Center",
        ),
    )
    conn_sql.exec_driver_sql(
        f"""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
        ("asesor1", "1234", "Asesor", "Asesor", "Uno", "5553333333", "Campo"),
    )
    conn_sql.exec_driver_sql(
        f"""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
        ("asesor2", "1234", "Asesor", "Asesor", "Dos", "5554444444", "Campo"),
    )


def autenticar(usuario, password):
  with engine.connect() as conn_sql:
    res = conn_sql.exec_driver_sql(
        f"SELECT usuario, rol FROM usuarios WHERE usuario = {PH} AND password = {PH}",
        (usuario, password),
    ).fetchone()
  return res


def guardar_cita(
    rfc_cliente, cliente, telefono, agente, fecha, hora, estado, notas
):
  with engine.begin() as conn_sql:
    conn_sql.exec_driver_sql(
        f"""
        INSERT INTO citas (rfc_cliente, cliente, telefono, agente, asesor, fecha, hora, estado, notas)
        VALUES ({PH}, {PH}, {PH}, {PH}, 'Sin Asignar', {PH}, {PH}, {PH}, {PH})
        """,
        (
            rfc_cliente,
            cliente,
            telefono,
            agente,
            str(fecha),
            str(hora),
            estado,
            notas,
        ),
    )


def obtener_usuarios_por_rol(rol):
  with engine.connect() as conn_sql:
    res = conn_sql.exec_driver_sql(
        f"SELECT usuario FROM usuarios WHERE rol = {PH} ORDER BY usuario",
        (rol,),
    ).fetchall()
  return [row[0] for row in res]


def limpiar_val(val):
  if pd.isna(val) or val is None:
    return ""
  val_str = str(val).strip()
  if val_str.endswith(".0"):
    val_str = val_str[:-2]
  return "" if val_str == "nan" else val_str


def cargar_base_general(df_cargado):
  registros = []
  df_cargado.columns = [str(col).strip().upper() for col in df_cargado.columns]
  contador_sin_rfc = 1
  for _, fila in df_cargado.iterrows():
    nom = limpiar_val(fila.get("NOMBRE", "")) or "Sin Nombre"
    ape = limpiar_val(fila.get("APELLIDOS", "")) or "Sin Apellido"
    t1, t2, t3 = (
        limpiar_val(fila.get("TEL1", "")),
        limpiar_val(fila.get("TEL2", "")),
        limpiar_val(fila.get("TEL3", "")),
    )
    tels = [t for t in [t1, t2, t3] if t and t != "0"]
    telefono_principal = " / ".join(tels) if tels else "Sin Teléfono"

    rfc = limpiar_val(fila.get("RFC", ""))
    if not rfc or rfc.upper() == "NONE":
      rfc = f"TEMP_{obtener_ahora_mexico().strftime('%y%m%d')}_{contador_sin_rfc}"
      contador_sin_rfc += 1

    sector = limpiar_val(fila.get("DEPENDENCIA", ""))
    poliza = limpiar_val(fila.get("POLIZA", ""))
    dividendos = limpiar_fecha_str(fila.get("DIVIDENDOS", ""))
    ult_fecha_asig = limpiar_fecha_str(fila.get("ULT FECHA ASIGNACION", ""))
    edad_excel = limpiar_val(fila.get("EDAD", ""))
    edad_calc = (
        edad_excel
        if edad_excel and edad_excel != "S/D"
        else calcular_edad_desde_rfc(rfc)
    )
    fecha_ult_mov = limpiar_fecha_str(fila.get("FECHA ULT MOV", ""))
    obs_tel = limpiar_val(fila.get("OBSERVACIONES TEL", ""))
    obs_asesor = limpiar_val(fila.get("OBSERVACIONES ASESOR", ""))

    registros.append((
        rfc.upper(),
        nom,
        ape,
        t1,
        t2,
        t3,
        telefono_principal,
        sector,
        poliza,
        dividendos,
        ult_fecha_asig,
        edad_calc,
        fecha_ult_mov,
        obs_tel,
        obs_asesor,
    ))

  with engine.begin() as conn_sql:
    for reg in registros:
      try:
        if ES_SQLITE:
          conn_sql.exec_driver_sql(
              f"""
                INSERT OR REPLACE INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin Asignar', 'Disponible', 'Sin marcar', 'Sin marcar', 'Sin marcar')
            """,
              reg,
          )
        else:
          conn_sql.exec_driver_sql(
              f"""
                INSERT INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin Asignar', 'Disponible', 'Sin marcar', 'Sin marcar', 'Sin marcar')
                ON CONFLICT (rfc) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido,
                    tel1 = EXCLUDED.tel1,
                    tel2 = EXCLUDED.tel2,
                    tel3 = EXCLUDED.tel3,
                    telefono = EXCLUDED.telefono,
                    sector = EXCLUDED.sector,
                    poliza = EXCLUDED.poliza
            """,
              reg,
          )
      except Exception:
        pass
  return len(registros)


@st.dialog("➕ Registrar Nuevo Prospecto")
def modal_crear_prospecto(usuario_actual, rol_actual):
  with st.form("form_modal_nuevo_prospecto"):
    col1, col2 = st.columns(2)
    with col1:
      rfc = st.text_input("RFC (Identificador Principal) *")
      nombre = st.text_input("Nombre(s) *")
      apellido = st.text_input("Apellidos *")
      tel1, tel2, tel3 = (
          st.text_input("TEL 1"),
          st.text_input("TEL 2"),
          st.text_input("TEL 3"),
      )
    with col2:
      sector = st.text_input("Dependencia")
      poliza = st.text_input("Póliza")
      dividendos_dt = st.date_input(
          "Dividendos", value=obtener_ahora_mexico().date()
      )
      ult_fecha_asig_dt = st.date_input(
          "Ult Fecha Asignación", value=obtener_ahora_mexico().date()
      )
      fecha_ult_mov_dt = st.date_input(
          "Fecha Ult Mov", value=obtener_ahora_mexico().date()
      )

    if rol_actual == "Administrador":
      telefonista_asignada = st.selectbox(
          "Asignar a:",
          ["Sin Asignar"]
          + obtener_usuarios_por_rol("Telefonista")
          + obtener_usuarios_por_rol("Asesor"),
      )
    elif rol_actual in ["Telefonista", "Asesor"]:
      telefonista_asignada = usuario_actual
      st.info(f"📌 Asignado a: **{usuario_actual}**")
    else:
      telefonista_asignada = "admin"

    estatus = st.selectbox(
        "Estatus Inicial", ["Disponible", "Asignado", "En Seguimiento"]
    )
    obs_tel, obs_asesor = (
        st.text_area("Observaciones Tel"),
        st.text_area("Observaciones Asesor"),
    )

    if st.form_submit_button("💾 Guardar Prospecto", use_container_width=True):
      if not rfc.strip() or not nombre.strip() or not apellido.strip():
        st.error("⚠️ Los campos RFC, Nombre(s) y Apellidos son obligatorios.")
      else:
        tels_disp = [t for t in [tel1, tel2, tel3] if t]
        telefono_final = " / ".join(tels_disp) if tels_disp else "Sin Teléfono"
        edad_calc = calcular_edad_desde_rfc(rfc)
        f_hoy = obtener_ahora_mexico().strftime("%Y/%m/%d")
        obs_tel_f = (
            f"({f_hoy} - {usuario_actual}) {obs_tel}" if obs_tel else ""
        )
        obs_asesor_f = (
            f"({f_hoy} - {usuario_actual}) {obs_asesor}" if obs_asesor else ""
        )

        with engine.begin() as conn_sql:
          if ES_SQLITE:
            conn_sql.exec_driver_sql(
                f"""
                INSERT OR REPLACE INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin marcar', 'Sin marcar', 'Sin marcar')
            """,
                (
                    rfc.strip().upper(),
                    nombre,
                    apellido,
                    tel1,
                    tel2,
                    tel3,
                    telefono_final,
                    sector,
                    poliza,
                    dividendos_dt.strftime("%Y-%m-%d"),
                    ult_fecha_asig_dt.strftime("%Y-%m-%d"),
                    edad_calc,
                    fecha_ult_mov_dt.strftime("%Y-%m-%d"),
                    obs_tel_f,
                    obs_asesor_f,
                    telefonista_asignada,
                    estatus,
                ),
            )
          else:
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin marcar', 'Sin marcar', 'Sin marcar')
                ON CONFLICT (rfc) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido,
                    tel1 = EXCLUDED.tel1,
                    tel2 = EXCLUDED.tel2,
                    tel3 = EXCLUDED.tel3
            """,
                (
                    rfc.strip().upper(),
                    nombre,
                    apellido,
                    tel1,
                    tel2,
                    tel3,
                    telefono_final,
                    sector,
                    poliza,
                    dividendos_dt.strftime("%Y-%m-%d"),
                    ult_fecha_asig_dt.strftime("%Y-%m-%d"),
                    edad_calc,
                    fecha_ult_mov_dt.strftime("%Y-%m-%d"),
                    obs_tel_f,
                    obs_asesor_f,
                    telefonista_asignada,
                    estatus,
                ),
            )
        st.success(
            f"✅ ¡Prospecto '{nombre} {apellido}' registrado con éxito!"
        )
        st.rerun()


def renderizar_bloque_con_tabla(df_entrada, key_suffix, ocultar_tels=False):
  df = df_entrada.copy()
  if ocultar_tels:
    for col_tel in ["tel1", "tel2", "tel3", "telefono"]:
      if col_tel in df.columns:
        df[col_tel] = "🔒 ***-ocultos***"

  cant_por_pagina = 100
  total_filas = len(df)

  with st.popover("⚙️ Opciones de Tabla y Multi-Filtros Avanzados"):
    sel_prev = st.session_state.get(f"sel_rfcs_{key_suffix}", [])
    col_pop1, col_pop2 = st.columns([1.6, 1.4])
    with col_pop1:
      if st.button(
          "✅ Seleccionar 100 de esta página",
          key=f"btn_sel_pag_{key_suffix}",
          use_container_width=True,
      ):
        p_act = st.session_state.get(f"pag_num_{key_suffix}", 1)
        ini_p = (p_act - 1) * cant_por_pagina
        fin_p = min(ini_p + cant_por_pagina, total_filas)
        rfcs_pag = df.iloc[ini_p:fin_p]["rfc"].tolist()
        st.session_state[f"sel_rfcs_{key_suffix}"] = list(
            set(sel_prev + rfcs_pag)
        )
        st.rerun()
    with col_pop2:
      st.markdown(f"📌 **Seleccionados:** `{len(sel_prev)}`")

    if st.button("❌ Desmarcar Todos", key=f"btn_desel_all_{key_suffix}"):
      st.session_state[f"sel_rfcs_{key_suffix}"] = []
      st.rerun()

    st.markdown("---")
    st.markdown("##### 🗂️ Panel de Multi-Filtros Acumulativos")

    if st.button(
        "🔄 Restablecer / Borrar Filtros",
        key=f"btn_reset_filtros_{key_suffix}",
        use_container_width=True,
    ):
      for k in [
          "tel_est",
          "mercado",
          "est_gral",
          "usuario",
          "chk_edad",
          "chk_div",
          "chk_asig",
          "chk_mov",
      ]:
        if f"filtro_{k}_{key_suffix}" in st.session_state:
          st.session_state[f"filtro_{k}_{key_suffix}"] = (
              "Todos" if "chk" not in k else False
          )
      st.rerun()

    st.selectbox(
        "📞 Estatus de Teléfonos:",
        [
            "Todos",
            "Sin marcar",
            "Válido / Contesta",
            "Número Erróneo / Malo",
            "No Contesta / Buzón",
        ],
        key=f"filtro_tel_est_{key_suffix}",
    )
    if "sector" in df.columns:
      st.selectbox(
          "🏢 Mercado / Dependencia:",
          ["Todos"]
          + sorted(
              [str(x) for x in df["sector"].dropna().unique() if str(x).strip()]
          ),
          key=f"filtro_mercado_{key_suffix}",
      )
    if "estatus" in df.columns:
      st.selectbox(
          "📌 Estatus del Prospecto:",
          ["Todos"]
          + sorted(
              [
                  str(x)
                  for x in df["estatus"].dropna().unique()
                  if str(x).strip()
              ]
          ),
          key=f"filtro_est_gral_{key_suffix}",
      )
    if "telefonista_asignada" in df.columns:
      st.selectbox(
          "👤 Usuario Asignado:",
          ["Todos"]
          + sorted(
              [
                  str(x)
                  for x in df["telefonista_asignada"].dropna().unique()
                  if str(x).strip()
              ]
          ),
          key=f"filtro_usuario_{key_suffix}",
      )

  if (
      st.session_state.get(f"filtro_tel_est_{key_suffix}", "Todos") != "Todos"
      and "estado_tel1" in df.columns
  ):
    v = st.session_state[f"filtro_tel_est_{key_suffix}"]
    df = df[
        (df["estado_tel1"] == v)
        | (df["estado_tel2"] == v)
        | (df["estado_tel3"] == v)
    ]
  if (
      st.session_state.get(f"filtro_mercado_{key_suffix}", "Todos") != "Todos"
      and "sector" in df.columns
  ):
    df = df[df["sector"] == st.session_state[f"filtro_mercado_{key_suffix}"]]
  if (
      st.session_state.get(f"filtro_est_gral_{key_suffix}", "Todos") != "Todos"
      and "estatus" in df.columns
  ):
    df = df[df["estatus"] == st.session_state[f"filtro_est_gral_{key_suffix}"]]
  if (
      st.session_state.get(f"filtro_usuario_{key_suffix}", "Todos") != "Todos"
      and "telefonista_asignada" in df.columns
  ):
    df = df[
        df["telefonista_asignada"]
        == st.session_state[f"filtro_usuario_{key_suffix}"]
    ]

  if "Seleccionar" not in df.columns:
    df.insert(0, "Seleccionar", False)

  st.session_state["lista_rfcs_navegacion"] = df["rfc"].tolist()
  tot_filt = len(df)
  tot_pags = (
      max(1, (tot_filt - 1) // cant_por_pagina + 1) if tot_filt > 0 else 1
  )

  if tot_filt > cant_por_pagina:
    p_act = st.selectbox(
        f"📄 Páginas (Bloques de 100 de {tot_filt} coincidentes):",
        range(1, tot_pags + 1),
        key=f"pag_num_{key_suffix}",
    )
    df_a_mostrar = df.iloc[
        (p_act - 1) * cant_por_pagina : p_act * cant_por_pagina
    ].copy()
  else:
    df_a_mostrar = df.copy()

  sel_prev = st.session_state.get(f"sel_rfcs_{key_suffix}", [])
  df_a_mostrar["Seleccionar"] = df_a_mostrar["rfc"].isin(sel_prev)

  column_config = {
      "Seleccionar": st.column_config.CheckboxColumn(
          "Seleccionar", default=False, width="small"
      ),
      "rfc": st.column_config.TextColumn("RFC / ID", width="medium"),
  }
  cols_dis = [c for c in df.columns if c not in ["Seleccionar"]]

  if sel_prev:
    if st.button(
        "🚀 Abrir / Ver Ficha",
        key=f"btn_sup_{key_suffix}",
        use_container_width=True,
    ):
      st.session_state["prospecto_editar_rfc"] = str(sel_prev[0])
      st.rerun()

  editor_res = st.data_editor(
      df_a_mostrar,
      key=f"tabla_editor_{key_suffix}",
      use_container_width=True,
      hide_index=True,
      column_config=column_config,
      disabled=cols_dis,
  )

  sel_actual = editor_res[editor_res["Seleccionar"] == True]["rfc"].tolist()
  otros = [r for r in sel_prev if r not in df_a_mostrar["rfc"].tolist()]
  final_sel = list(set(otros + sel_actual))

  if final_sel != sel_prev:
    st.session_state[f"sel_rfcs_{key_suffix}"] = final_sel
    st.rerun()

  return editor_res


for k, v in [
    ("usuario_logueado", None),
    ("rol", None),
    ("prospecto_editar_rfc", None),
    ("lista_rfcs_navegacion", []),
    ("seccion_activa", None),
    ("menu_abierto", False),
]:
  if k not in st.session_state:
    st.session_state[k] = v

# --- OCULTAR BARRA DE HERRAMIENTAS Y DESCARGA CSV A NO-ADMINISTRADORES ---
rol_actual_sesion = st.session_state.get("rol", None)

if rol_actual_sesion != "Administrador":
  st.markdown(
      """
    <style>
        /* Oculta la barra flotante de herramientas y descarga CSV de las tablas para no administradores */
        [data-testid="stElementToolbar"] {
            display: none !important;
        }
    </style>
    """,
      unsafe_allow_html=True,
  )

if st.session_state["usuario_logueado"] is None:
  st.markdown(
      """
      <style>
          .stApp {
              background-color: #005a9c !important;
          }
          .block-container {
              padding-top: 4rem !important;
              padding-bottom: 0rem !important;
              max-width: 92% !important;
          }
          .stTextInput label, .stTextInput div {
              color: #ffffff !important;
          }
          .stButton>button {
              background-color: #78BE20 !important;
              color: #ffffff !important;
              font-size: 1.1rem !important;
              font-weight: bold !important;
              padding: 0.6rem 1rem !important;
              border-radius: 6px !important;
              border: none !important;
          }
          .stButton>button:hover {
              background-color: #619e18 !important;
          }
      </style>
  """,
      unsafe_allow_html=True,
  )

  col_logo, col_login = st.columns([1.8, 1], gap="large")

  with col_logo:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 30px; padding-top: 2rem;">
            <div style="font-family: 'Segoe UI', sans-serif; font-weight: 900; line-height: 1; background: #ffffff; color: #002B49; padding: 28px 38px; border-radius: 22px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); flex-shrink: 0;">
                <span style="font-size: 6rem; color: #0072CE;">G</span><span style="font-size: 4.5rem; color: #78BE20;">P</span>
            </div>
            <div style="display: flex; flex-direction: column; justify-content: center;">
                <h1 style="color: #ffffff !important; margin: 0; font-size: 3.8rem; font-weight: 900; letter-spacing: 2px; line-height: 1.1; text-shadow: 0 3px 10px rgba(0,0,0,0.3);">GRUPO</h1>
                <h1 style="color: #ffffff !important; margin: 0; font-size: 3.8rem; font-weight: 900; letter-spacing: 2px; line-height: 1.1; text-shadow: 0 3px 10px rgba(0,0,0,0.3);">PINZÓN</h1>
                <p style="margin: 12px 0 0 0; font-size: 1.4rem; color: #ffffff !important; font-weight: 500; opacity: 0.95; text-shadow: 0 2px 6px rgba(0,0,0,0.3);">Sistema de Control de Prospectos y CRM</p>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

  with col_login:
    st.markdown(
        "<h2 style='color: #ffffff !important; margin-top: 2rem;"
        " font-size: 2.2rem; font-weight: 800; text-shadow: 0 2px 6px"
        " rgba(0,0,0,0.3);'>🔑 Iniciar Sesión</h2>",
        unsafe_allow_html=True,
    )
    usr = st.text_input("Usuario", key="login_usr")
    pwd = st.text_input("Contraseña", type="password", key="login_pwd")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Entrar al Sistema", use_container_width=True):
      datos = autenticar(usr, pwd)
      if datos:
        st.session_state["usuario_logueado"], st.session_state["rol"] = (
            datos[0],
            datos[1],
        )
        st.session_state["seccion_activa"] = None
        st.rerun()
      else:
        st.error("⚠️ Usuario o contraseña incorrectos")

else:
  st.markdown(
      """
      <style>
          .stApp {
              background-color: #f4f7f6 !important;
          }
          .block-container {
              padding-top: 3.5rem !important;
              padding-bottom: 2rem !important;
          }
      </style>
  """,
      unsafe_allow_html=True,
  )

  rol, usuario = st.session_state["rol"], st.session_state["usuario_logueado"]

  opciones = (
      [
          "1. Cargar Base General",
          "2. Ver Banco de Prospectos",
          "3. Gestión y Asignación de Prospectos",
          "4. Reporte de Citas y Actividad",
          "5. Gestión de Usuarios y Roles",
      ]
      if rol == "Administrador"
      else (
          [
              "Mis Prospectos y Gestión",
              "Mis Citas Agendadas",
              "Control de Tiempo (Comida/Baño)",
          ]
          if rol == "Telefonista"
          else [
              "Mis Prospectos Asignados",
              "Bolsa de Citas del Día (Asesores)",
              "Mis Registros de Hoy",
              "📊 Reportes de Citas y Asistencias",
          ]
      )
  )

  if (
      st.session_state["seccion_activa"] is None
      or st.session_state["seccion_activa"] not in opciones
  ):
    st.session_state["seccion_activa"] = opciones[0]

  col_nav1, col_nav2, col_nav3 = st.columns([1.2, 3.8, 1.5])
  with col_nav1:
    menu_container_key = f"menu_cont_{st.session_state['seccion_activa']}"
    with st.container(key=menu_container_key):
      with st.popover("☰ Menú"):
        st.caption("Sección:")
        for op in opciones:
          es_activa = op == st.session_state["seccion_activa"]
          if st.button(
              op,
              key=f"btn_menu_{op}",
              use_container_width=True,
              type="primary" if es_activa else "secondary",
          ):
            st.session_state["seccion_activa"] = op
            st.session_state["prospecto_editar_rfc"] = None
            st.rerun()

  opcion = st.session_state["seccion_activa"]

  with col_nav2:
    st.markdown(
        f"<div style='text-align: center; padding-top: 8px;'>👤 <b>Usuario:</b>"
        f" <code>{usuario}</code> &nbsp;|&nbsp; 🛡️ <b>Rol:</b>"
        f" <code>{rol}</code></div>",
        unsafe_allow_html=True,
    )
  with col_nav3:
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
      for k in [
          "usuario_logueado",
          "rol",
          "prospecto_editar_rfc",
          "lista_rfcs_navegacion",
          "seccion_activa",
      ]:
        st.session_state[k] = None if k != "lista_rfcs_navegacion" else []
      st.rerun()

  st.markdown("---")

  st.markdown(
      """
      <div style="background: linear-gradient(135deg, #002B49 0%, #0072CE 100%); padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(0,43,73,0.15); border-bottom: 4px solid #78BE20; display: flex; align-items: center; gap: 20px;">
          <div style="font-family: 'Segoe UI', sans-serif; font-weight: 900; line-height: 1; background: #ffffff; color: #002B49; padding: 10px 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
              <span style="font-size: 2.4rem; color: #0072CE;">G</span><span style="font-size: 1.5rem; color: #78BE20;">P</span>
          </div>
          <div>
              <h1 style="color: #78BE20 !important; margin: 0; font-size: 2.5rem; font-weight: 800; letter-spacing: 1px;">GRUPO PINZÓN</h1>
              <p style="margin: 4px 0 0 0; font-size: 1rem; opacity: 0.9; color: #ffffff !important;">Sistema de Control de Prospectos y CRM</p>
          </div>
      </div>
  """,
      unsafe_allow_html=True,
  )

  if st.session_state["prospecto_editar_rfc"] is not None:
    rfc_actual = st.session_state["prospecto_editar_rfc"]
    lista_rfcs = st.session_state["lista_rfcs_navegacion"]
    pos_actual = lista_rfcs.index(rfc_actual) if rfc_actual in lista_rfcs else 0
    total_prospectos = len(lista_rfcs) if lista_rfcs else 1

    with engine.connect() as conn_sql:
      row = conn_sql.exec_driver_sql(
          f"""
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, 
                   dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                   observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                   estado_tel1, estado_tel2, estado_tel3
            FROM clientes WHERE rfc = {PH}
        """,
          (rfc_actual,),
      ).fetchone()

    if not row:
      st.error("No se encontró la información del prospecto.")
      st.session_state["prospecto_editar_rfc"] = None
    else:

      def ejecutar_guardado_y_salto(destino):
        rfc_limpio = str(
            st.session_state.get(f"frfc_{rfc_actual}", row[0])
        ).strip().upper()
        n_nombre = st.session_state.get(f"fn_{rfc_actual}", row[1])
        n_apellido = st.session_state.get(f"fa_{rfc_actual}", row[2])
        n_t1 = st.session_state.get(f"ftel1_{rfc_actual}", row[3])
        n_t2 = st.session_state.get(f"ftel2_{rfc_actual}", row[4])
        n_t3 = st.session_state.get(f"ftel3_{rfc_actual}", row[5])
        n_sector = st.session_state.get(f"fs_{rfc_actual}", row[6])
        n_poliza = st.session_state.get(f"fp_{rfc_actual}", row[7])
        n_div = st.session_state.get(f"fdiv_{rfc_actual}", parsear_a_date(row[8]))
        n_asig_f = st.session_state.get(
            f"fulfasig_{rfc_actual}", parsear_a_date(row[9])
        )
        n_mov = st.session_state.get(f"ffum_{rfc_actual}", parsear_a_date(row[11]))
        n_obs_tel = st.session_state.get(f"fobs_tel_{rfc_actual}", row[12] or "")
        n_obs_asesor = st.session_state.get(
            f"fobs_asesor_{rfc_actual}", row[13] or ""
        )
        est_t1 = st.session_state.get(f"est_t1_{rfc_actual}", row[16])
        est_t2 = st.session_state.get(f"est_t2_{rfc_actual}", row[17])
        est_t3 = st.session_state.get(f"est_t3_{rfc_actual}", row[18])

        edad_nueva = calcular_edad_desde_rfc(rfc_limpio)
        tels_disp = [t for t in [n_t1, n_t2, n_t3] if t]
        telefono_general = (
            " / ".join(tels_disp) if tels_disp else "Sin Teléfono"
        )

        with engine.begin() as conn_sql:
          if rfc_limpio != rfc_actual:
            conn_sql.exec_driver_sql(
                f"DELETE FROM clientes WHERE rfc = {PH}", (rfc_actual,)
            )

          if ES_SQLITE:
            conn_sql.exec_driver_sql(
                f"""
                INSERT OR REPLACE INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                    estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
                (
                    rfc_limpio,
                    n_nombre,
                    n_apellido,
                    n_t1,
                    n_t2,
                    n_t3,
                    telefono_general,
                    n_sector,
                    n_poliza,
                    str(n_div),
                    str(n_asig_f),
                    edad_nueva,
                    str(n_mov),
                    n_obs_tel,
                    n_obs_asesor,
                    row[14],
                    row[15],
                    est_t1,
                    est_t2,
                    est_t3,
                ),
            )
          else:
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                    estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
                ON CONFLICT (rfc) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido,
                    tel1 = EXCLUDED.tel1,
                    tel2 = EXCLUDED.tel2,
                    tel3 = EXCLUDED.tel3,
                    telefono = EXCLUDED.telefono,
                    sector = EXCLUDED.sector,
                    poliza = EXCLUDED.poliza,
                    observaciones_tel = EXCLUDED.observaciones_tel,
                    observaciones_asesor = EXCLUDED.observaciones_asesor,
                    estado_tel1 = EXCLUDED.estado_tel1,
                    estado_tel2 = EXCLUDED.estado_tel2,
                    estado_tel3 = EXCLUDED.estado_tel3
            """,
                (
                    rfc_limpio,
                    n_nombre,
                    n_apellido,
                    n_t1,
                    n_t2,
                    n_t3,
                    telefono_general,
                    n_sector,
                    n_poliza,
                    str(n_div),
                    str(n_asig_f),
                    edad_nueva,
                    str(n_mov),
                    n_obs_tel,
                    n_obs_asesor,
                    row[14],
                    row[15],
                    est_t1,
                    est_t2,
                    est_t3,
                ),
            )

        if destino == "siguiente":
          if pos_actual < total_prospectos - 1:
            st.session_state["prospecto_editar_rfc"] = lista_rfcs[
                pos_actual + 1
            ]
          else:
            st.warning("✅ Has llegado al final de la lista.")
            st.session_state["prospecto_editar_rfc"] = None
        elif destino == "anterior":
          if pos_actual > 0:
            st.session_state["prospecto_editar_rfc"] = lista_rfcs[
                pos_actual - 1
            ]
          else:
            st.warning("⚠️ Estás en el primer registro.")
        else:
          st.session_state["prospecto_editar_rfc"] = None
        st.rerun()

      col_top1, col_nav_ant, col_nav_sig, col_top2 = st.columns(
          [2.2, 0.6, 0.6, 1.5]
      )
      with col_top1:
        st.caption(
            f"📍 Viendo Registro **{pos_actual + 1} de {total_prospectos}**"
        )
      with col_nav_ant:
        if st.button("⬅️", use_container_width=True, key="f_ant"):
          ejecutar_guardado_y_salto("anterior")
      with col_nav_sig:
        if st.button("➡️", use_container_width=True, key="f_sig"):
          ejecutar_guardado_y_salto("siguiente")
      with col_top2:
        if st.button("❌ Cerrar", use_container_width=True, key="c_ficha"):
          ejecutar_guardado_y_salto("cerrar")

      nombre_completo_id = f"{str(row[1]).strip().upper()} {str(row[2]).strip().upper()}"
      st.markdown(
          f"## 📋 Ficha Prospecto [RFC: {row[0]}] - {nombre_completo_id}"
      )
      st.info(
          f"👤 **Asignado a:** `{row[14]}` | 📌 **Estatus Actual:** `{row[15]}`"
      )

      if rol in ["Telefonista", "Asesor"] and row[14] in [
          "Sin Asignar",
          "",
      ]:
        if st.button("🙋‍♂ ¡Tomar este prospecto para mí!"):
          with engine.begin() as conn_sql:
            conn_sql.exec_driver_sql(
                f"UPDATE clientes SET telefonista_asignada = {PH}, estatus ="
                f" 'Asignado' WHERE rfc = {PH}",
                (usuario, rfc_actual),
            )
          st.success("¡Te has asignado el prospecto exitosamente!")
          st.rerun()

      col1, col2 = st.columns(2, gap="large")

      with col1:
        st.markdown("#### 👤 Datos Principales")
        st.text_input("RFC", value=str(row[0] or ""), key=f"frfc_{rfc_actual}")
        st.text_input(
            "Nombre(s)", value=str(row[1] or ""), key=f"fn_{rfc_actual}"
        )
        st.text_input(
            "Apellidos", value=str(row[2] or ""), key=f"fa_{rfc_actual}"
        )
        st.text_input(
            "Dependencia", value=str(row[6] or ""), key=f"fs_{rfc_actual}"
        )
        st.text_input("Póliza", value=str(row[7] or ""), key=f"fp_{rfc_actual}")

        st.markdown("---")
        st.markdown("#### 📞 Control de Números Telefónicos y Estatus")
        opciones_estados = [
            "Sin marcar",
            "Válido / Contesta",
            "Número Erróneo / Malo",
            "No Contesta / Buzón",
        ]
        for i, (t_col, est_col) in enumerate(
            [(3, 16), (4, 17), (5, 18)], start=1
        ):
          t_val = str(row[t_col] or "")
          est_val = row[est_col] if row[est_col] else "Sin marcar"
          idx = (
              opciones_estados.index(est_val)
              if est_val in opciones_estados
              else 0
          )
          c_t, c_e = st.columns([1.2, 1.8])
          with c_t:
            st.text_input(
                f"TEL {i}", value=t_val, key=f"ftel{i}_{rfc_actual}"
            )
          with c_e:
            st.selectbox(
                f"Estatus Tel {i}",
                opciones_estados,
                index=idx,
                key=f"est_t{i}_{rfc_actual}",
            )

      with col2:
        st.markdown("#### 📅 Cita Generada Activa")
        with st.container(key=f"cont_cita_{rfc_actual}"):
          with engine.connect() as conn_sql:
            cita_reciente = conn_sql.exec_driver_sql(
                f"""
                SELECT id, fecha, hora, estado, agente, notas FROM citas 
                WHERE rfc_cliente = {PH} ORDER BY id DESC LIMIT 1
            """,
                (rfc_actual,),
            ).fetchone()

          if cita_reciente:
            c_id, c_fecha, c_hora, c_estado, c_agente, c_notas = cita_reciente
            st.markdown(
                f"📌 **Fecha:** `{c_fecha}` | **Hora:** `{c_hora}` | **Agente:**"
                f" `{c_agente}`"
            )
            st.markdown(f"**Estado Cita:** `{c_estado}`")
            if c_notas:
              st.caption(f"📝 Notas: {c_notas}")

            bc1, bc2 = st.columns(2)
            with bc1:
              if st.button(
                  "✅ Marcar Asistida", key=f"btn_asis_{c_id}_{rfc_actual}"
              ):
                with engine.begin() as conn_sql:
                  conn_sql.exec_driver_sql(
                      f"UPDATE citas SET estado = 'Asistida / Atendida' WHERE id"
                      f" = {PH}",
                      (c_id,),
                  )
                  conn_sql.exec_driver_sql(
                      f"UPDATE clientes SET estatus = 'Cita Asistida' WHERE rfc"
                      f" = {PH}",
                      (rfc_actual,),
                  )
                st.success("¡Cita marcada como Asistida!")
                st.rerun()
            with bc2:
              if st.button(
                  "❌ Marcar No Asistió", key=f"btn_noasis_{c_id}_{rfc_actual}"
              ):
                with engine.begin() as conn_sql:
                  conn_sql.exec_driver_sql(
                      f"UPDATE citas SET estado = 'No Asistió' WHERE id = {PH}",
                      (c_id,),
                  )
                  conn_sql.exec_driver_sql(
                      f"UPDATE clientes SET estatus = 'No Asistió' WHERE rfc ="
                      f" {PH}",
                      (rfc_actual,),
                  )
                st.warning("Cita marcada como No Asistió.")
                st.rerun()
          else:
            st.write("No hay citas generadas recientemente para este prospecto.")

        st.markdown("---")
        st.markdown("#### 📋 Fechas y Seguimiento")
        st.date_input(
            "Dividendos",
            value=parsear_a_date(row[8]),
            key=f"fdiv_{rfc_actual}",
        )
        st.date_input(
            "Ult Fecha Asignación",
            value=parsear_a_date(row[9]),
            key=f"fulfasig_{rfc_actual}",
        )
        st.text_input(
            "Edad (Calculada/Registrada)",
            value=str(row[10] or calcular_edad_desde_rfc(row[0])),
            disabled=True,
            key=f"fedad_{rfc_actual}",
        )
        st.date_input(
            "Fecha Ult Mov",
            value=parsear_a_date(row[11]),
            key=f"ffum_{rfc_actual}",
        )

      st.markdown("---")
      st.markdown("#### 📝 Observaciones Generales")
      es_telefonista = rol == "Telefonista"

      col_obs1, col_obs2 = st.columns(2)
      with col_obs1:
        st.text_area(
            "Observaciones Telefonista (Solo Lectura)",
            value=str(row[12] or ""),
            disabled=es_telefonista,
            key=f"fobs_tel_{rfc_actual}",
            help=(
                "Historial acumulado de llamadas registradas."
                if es_telefonista
                else ""
            ),
        )
      with col_obs2:
        st.text_area(
            "Observaciones Asesor (Solo Lectura)",
            value=str(row[13] or ""),
            disabled=es_telefonista,
            key=f"fobs_asesor_{rfc_actual}",
            help="Notas registradas por el asesor." if es_telefonista else "",
        )

      st.markdown("---")
      st.subheader("📞 Registro de Llamada / Tareas")
      accion_llamada = st.selectbox(
          "Selecciona opción de llamada:",
          [
              "Cita",
              "Posible Asistencia",
              "Recado",
              "Mensaje de texto",
              "No existe",
              "No le interesa",
              "No contesta",
          ],
          key=f"sel_accion_{rfc_actual}",
      )

      with st.form(f"form_llamada_{rfc_actual}"):
        detalle_accion = st.text_area(
            "Detalle / Observaciones de la llamada o recado:",
            key=f"txt_det_{rfc_actual}",
        )
        usa_agenda = accion_llamada in ["Cita", "Posible Asistencia"]

        if usa_agenda:
          f_cita = st.date_input(
              "Fecha de Cita",
              value=obtener_ahora_mexico().date(),
              key=f"f_cita_{rfc_actual}",
          )
          bloques_horas = []
          for h in range(9, 17):
            for m in [0, 30]:
              if h == 16 and m > 0:
                break
              bloques_horas.append(f"{h:02d}:{m:02d}")
          h_cita = st.selectbox(
              "Hora de Cita (9:00 AM a 4:00 PM)",
              bloques_horas,
              key=f"h_cita_{rfc_actual}",
          )
        else:
          st.info(
              f"📌 Campos de fecha y hora bloqueados para **{accion_llamada}**."
              " Se registrará automáticamente."
          )
          f_cita, h_cita = (
              obtener_ahora_mexico().date(),
              obtener_ahora_mexico().strftime("%H:%M"),
          )

        if st.form_submit_button(
            "💾 Registrar Acción", use_container_width=True
        ):
          f_hoy_formato = obtener_ahora_mexico().strftime("%Y/%m/%d")
          ahora_local = obtener_ahora_mexico().strftime("%Y-%m-%d %H:%M:%S")

          nueva_obs_formateada = (
              f"({f_hoy_formato} - {usuario}) [{accion_llamada}]"
              f" {detalle_accion.strip()}"
              if detalle_accion.strip()
              else f"({f_hoy_formato} - {usuario}) [{accion_llamada}]"
          )
          obs_actuales = row[12] if row[12] else ""
          obs_acumuladas = (
              f"{obs_actuales}\n{nueva_obs_formateada}"
              if obs_actuales.strip()
              else nueva_obs_formateada
          )

          with engine.begin() as conn_sql:
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO historial_llamadas (rfc_cliente, usuario, accion, detalle, fecha_registro)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH})
            """,
                (
                    rfc_actual,
                    usuario,
                    accion_llamada,
                    detalle_accion,
                    ahora_local,
                ),
            )

            if usa_agenda:
              guardar_cita(
                  rfc_actual,
                  nombre_completo_id,
                  row[3] if row[3] else "Sin Teléfono",
                  usuario,
                  f_cita,
                  h_cita,
                  "Pendiente",
                  detalle_accion,
              )
              est_nuevo = (
                  "Cita Agendada"
                  if accion_llamada == "Cita"
                  else "Posible Asistencia"
              )
              conn_sql.exec_driver_sql(
                  f"""
                    UPDATE clientes 
                    SET estatus = {PH}, observaciones_tel = {PH} 
                    WHERE rfc = {PH}
                """,
                  (est_nuevo, obs_acumuladas, rfc_actual),
              )
              st.success(f"✅ ¡{accion_llamada} registrada exitosamente!")
            else:
              conn_sql.exec_driver_sql(
                  f"""
                    UPDATE clientes 
                    SET estatus = {PH}, observaciones_tel = {PH} 
                    WHERE rfc = {PH}
                """,
                  (
                      f"En Seguimiento ({accion_llamada})",
                      obs_acumuladas,
                      rfc_actual,
                  ),
              )
              st.success(f"✅ ¡{accion_llamada} registrado en el historial!")
          st.rerun()

      st.markdown("---")
      st.subheader("📜 HISTORIAL DE LLAMADAS")
      df_hist = pd.read_sql(
          f"""
            SELECT fecha_registro as "Fecha/Hora", usuario as "Usuario", accion as "Acción", detalle as "Detalle"
            FROM historial_llamadas WHERE rfc_cliente = {PH} ORDER BY id DESC
        """,
          con=engine,
          params=(rfc_actual,),
      )
      if df_hist.empty:
        st.info("No hay registros previos en el historial de llamadas.")
      else:
        st.markdown(
            df_hist.to_html(classes="custom-table", index=False, escape=False),
            unsafe_allow_html=True,
        )

      st.markdown("---")
      cb1, cb2, cb3 = st.columns(3)
      with cb1:
        if st.button("⬅️ Guardar y Anterior", key=f"b_ant_{rfc_actual}"):
          ejecutar_guardado_y_salto("anterior")
      with cb2:
        if st.button("💾 Guardar y Cerrar", key=f"b_cer_{rfc_actual}"):
          ejecutar_guardado_y_salto("cerrar")
      with cb3:
        if st.button("💾 Guardar y Siguiente ➡", key=f"b_sig_{rfc_actual}"):
          ejecutar_guardado_y_salto("siguiente")

  else:
    if rol == "Administrador":
      if opcion == "1. Cargar Base General":
        st.header("📥 Cargar Base General")
        archivo = st.file_uploader(
            "Sube tu archivo (.xlsx o .csv)", type=["xlsx", "xls", "csv"]
        )
        if archivo is not None:
          try:
            df_cargado = (
                pd.read_csv(archivo, encoding="utf-8")
                if archivo.name.lower().endswith(".csv")
                else pd.read_excel(archivo, engine="openpyxl")
            )
            st.dataframe(df_cargado.head(10), use_container_width=True)
            if st.button("Guardar en Banco General"):
              total = cargar_base_general(df_cargado)
              st.success(
                  f"✅ ¡Se cargaron {total} prospectos exitosamente!"
              )
          except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

      elif opcion == "2. Ver Banco de Prospectos":
        st.header("📊 Banco General de Prospectos")
        df_banco = pd.read_sql(
            "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza,"
            " dividendos, ult_fecha_asignacion, edad, telefonista_asignada,"
            " estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes",
            con=engine,
        )
        if df_banco.empty:
          st.warning("No hay clientes registrados.")
        else:
          renderizar_bloque_con_tabla(
              df_banco, key_suffix="banco", ocultar_tels=False
          )

      elif opcion == "3. Gestión y Asignación de Prospectos":
        st.header("🔄 Gestión y Asignación de Prospectos")
        col_busq, col_filt, col_crear = st.columns([2, 2, 1])
        with col_busq:
          busqueda = st.text_input(
              "🔎 Buscar por RFC, Nombre, Apellido o Teléfono:"
          )
        with col_filt:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          activar_filtros = st.toggle("🔍 Mostrar Filtros Avanzados")
        with col_crear:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          if st.button("➕ Crear Nuevo", use_container_width=True):
            modal_crear_prospecto(usuario, rol)

        condiciones = []
        params_query = []
        if busqueda:
          if ES_SQLITE:
            condiciones.append(
                "(rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR tel1 LIKE"
                " ?)"
            )
            patron = f"%{busqueda}%"
            params_query.extend([patron, patron, patron, patron])
          else:
            condiciones.append(
                "(rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR tel1"
                " ILIKE %s)"
            )
            patron = f"%{busqueda}%"
            params_query.extend([patron, patron, patron, patron])

        query = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, fecha_ult_mov, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes"
        if condiciones:
          query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY fecha_creacion DESC LIMIT 1000"

        df_resultados = pd.read_sql(
            query, con=engine, params=params_query if params_query else None
        )
        if df_resultados.empty:
          st.warning(
              "No se encontraron prospectos con los filtros seleccionados."
          )
        else:
          renderizar_bloque_con_tabla(
              df_resultados, key_suffix="gestion_admin", ocultar_tels=False
          )
          rfcs_sel_global = st.session_state.get("sel_rfcs_gestion_admin", [])
          cant_sel = len(rfcs_sel_global)

          st.markdown("---")
          st.subheader("⚡ Actualización y Asignación Masiva")
          c1, c2, c3 = st.columns([2, 2, 1])
          with c1:
            tele_destino = st.selectbox(
                "Asignar a:",
                obtener_usuarios_por_rol("Telefonista")
                + obtener_usuarios_por_rol("Asesor"),
            )
          with c2:
            estatus_masivo = st.selectbox(
                "Cambiar Estatus A:",
                [
                    "Asignado",
                    "Disponible",
                    "En Seguimiento",
                    "No Interesado",
                ],
            )
          with c3:
            st.metric("Seleccionados", cant_sel)

          if st.button("🚀 Aplicar Cambios Masivos"):
            if cant_sel == 0:
              st.warning("⚠️ Marca la casilla 'Seleccionar' en la tabla.")
            else:
              with engine.begin() as conn_sql:
                for rfc_item in rfcs_sel_global:
                  conn_sql.exec_driver_sql(
                      f"UPDATE clientes SET telefonista_asignada = {PH},"
                      f" estatus = {PH} WHERE rfc = {PH}",
                      (tele_destino, estatus_masivo, rfc_item),
                  )
              st.session_state["sel_rfcs_gestion_admin"] = []
              st.success(
                  f"✅ ¡Se actualizaron {cant_sel} prospectos correctamente!"
              )
              st.rerun()

      elif opcion == "4. Reporte de Citas y Actividad":
        st.header("📊 Reporte General de Citas y Actividad")
        f_rep = st.date_input(
            "Fecha Base:", value=obtener_ahora_mexico().date()
        )
        f_rep_str = str(f_rep)

        tab_rep1, tab_rep2, tab_rep3, tab_rep4 = st.tabs([
            "📈 Citas y Eficiencia",
            "📞 Llamadas Telefonistas",
            "⏱️ Auditoría de Tiempos (Llamadas)",
            "🍽️ / 🚽 Comida y Baño",
        ])

        with tab_rep1:
          df_rep = pd.read_sql(
              f"SELECT * FROM citas WHERE fecha = {PH}",
              con=engine,
              params=(f_rep_str,),
          )
          m1, m2, m3, m4 = st.columns(4)
          tot_c = len(df_rep)
          asis = (
              len(
                  df_rep[
                      df_rep["estado"].str.contains(
                          "Asistida", case=False, na=False
                      )
                  ]
              )
              if not df_rep.empty
              else 0
          )
          pend = (
              len(df_rep[df_rep["estado"] == "Pendiente"])
              if not df_rep.empty
              else 0
          )
          efec = f"{(asis / tot_c * 100):.1f}%" if tot_c > 0 else "0%"

          m1.metric("Total Citas", tot_c)
          m2.metric("Asistidas", asis)
          m3.metric("Pendientes", pend)
          m4.metric("Tasa de Asistencia", efec)

          st.markdown("---")
          if not df_rep.empty:
            st.markdown(
                df_rep.to_html(
                    classes="custom-table", index=False, escape=False
                ),
                unsafe_allow_html=True,
            )
          else:
            st.info("No hay citas registradas para esta fecha.")

        with tab_rep2:
          like_op = "LIKE" if ES_SQLITE else "LIKE"
          df_tot = pd.read_sql(
              f"""
                SELECT usuario as "Telefonista", COUNT(*) as "Total General" 
                FROM historial_llamadas WHERE fecha_registro {like_op} {PH} GROUP BY usuario
            """,
              con=engine,
              params=(f"{f_rep_str}%",),
          )
          if df_tot.empty:
            st.info(f"No hay registros de llamadas para la fecha ({f_rep_str}).")
          else:
            st.dataframe(df_tot, use_container_width=True, hide_index=True)

        with tab_rep3:
          st.markdown(
              "##### ⏱️ Auditoría de Tiempos y Tasa de Actividad por Usuario"
          )
          usuarios_lista = obtener_usuarios_por_rol(
              "Telefonista"
          ) + obtener_usuarios_por_rol("Asesor")
          usr_auditar = st.selectbox(
              "Selecciona el usuario a auditar:", ["Todos"] + usuarios_lista
          )

          like_op = "LIKE" if ES_SQLITE else "LIKE"
          if usr_auditar == "Todos":
            query_aud = f"""
                SELECT h.fecha_registro as "Fecha/Hora", h.usuario as "Usuario", h.rfc_cliente as "RFC", c.nombre || ' ' || c.apellido as "Prospecto", h.accion as "Acción", h.detalle as "Detalle"
                FROM historial_llamadas h LEFT JOIN clientes c ON h.rfc_cliente = c.rfc
                WHERE h.fecha_registro {like_op} {PH} ORDER BY h.fecha_registro ASC
            """
            df_aud = pd.read_sql(
                query_aud, con=engine, params=(f"{f_rep_str}%",)
            )
          else:
            query_aud = f"""
                SELECT h.fecha_registro as "Fecha/Hora", h.usuario as "Usuario", h.rfc_cliente as "RFC", c.nombre || ' ' || c.apellido as "Prospecto", h.accion as "Acción", h.detalle as "Detalle"
                FROM historial_llamadas h LEFT JOIN clientes c ON h.rfc_cliente = c.rfc
                WHERE h.usuario = {PH} AND h.fecha_registro {like_op} {PH} ORDER BY h.fecha_registro ASC
            """
            df_aud = pd.read_sql(
                query_aud,
                con=engine,
                params=(usr_auditar, f"{f_rep_str}%"),
            )

          if df_aud.empty:
            st.info(
                f"No hay registros de llamadas para el usuario y fecha"
                " seleccionados."
            )
          else:
            df_aud["Dt"] = pd.to_datetime(df_aud["Fecha/Hora"])
            df_aud["Tiempo con Próximo Prospecto"] = (
                df_aud["Dt"].diff().fillna(pd.Timedelta(seconds=0))
            )
            df_aud["Minutos Transcurridos"] = df_aud[
                "Tiempo con Próximo Prospecto"
            ].dt.total_seconds() / 60
            df_aud["Minutos Transcurridos"] = df_aud[
                "Minutos Transcurridos"
            ].round(1)

            df_mostrar_aud = df_aud[
                [
                    "Fecha/Hora",
                    "Usuario",
                    "RFC",
                    "Prospecto",
                    "Acción",
                    "Minutos Transcurridos",
                    "Detalle",
                ]
            ].copy()
            df_mostrar_aud.iloc[0, df_mostrar_aud.columns.get_loc(
                "Minutos Transcurridos"
            )] = 0.0

            st.markdown(
                df_mostrar_aud.to_html(
                    classes="custom-table", index=False, escape=False
                ),
                unsafe_allow_html=True,
            )

        with tab_rep4:
          df_asistencia_rep = pd.read_sql(
              f"""
                SELECT usuario as "Telefonista", tipo_registro as "Tipo", hora_inicio as "Inicio", hora_fin as "Fin", duracion_minutos as "Minutos", estado as "Estado"
                FROM asistencia_telefonistas WHERE fecha = {PH} ORDER BY id DESC
            """,
              con=engine,
              params=(f_rep_str,),
          )
          if df_asistencia_rep.empty:
            st.info(
                "No hay registros de comida/baño registrados en esta fecha."
            )
          else:
            html_tabla = "<table class='custom-table'><thead><tr>"
            for col in df_asistencia_rep.columns:
              html_tabla += f"<th>{col}</th>"
            html_tabla += "</tr></thead><tbody>"

            for _, r in df_asistencia_rep.iterrows():
              clase = (
                  "class='fila-excedida'"
                  if "EXCEDIDO" in str(r["Estado"])
                  else ""
              )
              html_tabla += f"<tr {clase}>"
              for val in r:
                html_tabla += f"<td>{val if pd.notna(val) else ''}</td>"
              html_tabla += "</tr>"
            html_tabla += "</tbody></table>"

            st.markdown(html_tabla, unsafe_allow_html=True)

      elif opcion == "5. Gestión de Usuarios y Roles":
        st.header("👥 Panel de Administración de Usuarios")
        tab_c, tab_e = st.tabs(
            ["➕ Crear Nuevo Usuario", "✏️ Editar Usuarios"]
        )
        with tab_c:
          with st.form("form_crear_usuario", clear_on_submit=True):
            cu1, cu2 = st.columns(2)
            with cu1:
              n_usr = st.text_input("Usuario *")
              n_pwd = st.text_input("Contraseña *", type="password")
              n_rol = st.selectbox(
                  "Rol", ["Administrador", "Telefonista", "Asesor"]
              )
            with cu2:
              n_nom, n_ape = st.text_input("Nombre(s)"), st.text_input(
                  "Apellidos"
              )
              n_tel, n_dir = st.text_input("Teléfono"), st.text_input(
                  "Dirección"
              )
            if st.form_submit_button(
                "💾 Crear Usuario", use_container_width=True
            ):
              if not n_usr.strip() or not n_pwd.strip():
                st.error("⚠️ Usuario y contraseña obligatorios.")
              else:
                try:
                  with engine.begin() as conn_sql:
                    conn_sql.exec_driver_sql(
                        f"""
                            INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
                            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
                        """,
                        (
                            n_usr.strip(),
                            n_pwd.strip(),
                            n_rol,
                            n_nom,
                            n_ape,
                            n_tel,
                            n_dir,
                        ),
                    )
                  st.success(f"✅ ¡Usuario '{n_usr}' creado con éxito!")
                except Exception:
                  st.error("⚠️ El usuario ya existe.")
        with tab_e:
          st.markdown("##### ✏️ Modificar Datos o Contraseña de Usuarios")
          df_u = pd.read_sql(
              "SELECT id, usuario, rol, nombre_completo, apellido, telefono,"
              " direccion FROM usuarios",
              con=engine,
          )
          for _, ur in df_u.iterrows():
            with st.expander(
                f"👤 {ur['usuario']} ({ur['rol']}) - {ur['nombre_completo']}"
            ):
              with st.form(f"form_edit_u_{ur['usuario']}"):
                e_pwd = st.text_input(
                    "Nueva Contraseña (dejar en blanco para no cambiar)",
                    type="password",
                    key=f"epwd_{ur['usuario']}",
                )
                roles_disponibles = ["Administrador", "Telefonista", "Asesor"]
                idx_rol = (
                    roles_disponibles.index(ur["rol"])
                    if ur["rol"] in roles_disponibles
                    else 0
                )
                e_rol = st.selectbox(
                    "Rol",
                    roles_disponibles,
                    index=idx_rol,
                    key=f"erol_{ur['usuario']}",
                )
                e_nom = st.text_input(
                    "Nombre(s)",
                    value=str(ur["nombre_completo"] or ""),
                    key=f"enom_{ur['usuario']}",
                )
                e_ape = st.text_input(
                    "Apellidos",
                    value=str(ur["apellido"] or ""),
                    key=f"eape_{ur['usuario']}",
                )
                e_tel = st.text_input(
                    "Teléfono",
                    value=str(ur["telefono"] or ""),
                    key=f"etel_{ur['usuario']}",
                )
                e_dir = st.text_input(
                    "Dirección",
                    value=str(ur["direccion"] or ""),
                    key=f"edir_{ur['usuario']}",
                )

                col_sub1, col_sub2 = st.columns(2)
                actualizar = col_sub1.form_submit_button(
                    "💾 Guardar Cambios", use_container_width=True
                )

                eliminar = False
                if ur["usuario"] != "admin":
                  eliminar = col_sub2.form_submit_button(
                      "🗑️ Eliminar Usuario", use_container_width=True
                  )

                if actualizar:
                  with engine.begin() as conn_sql:
                    if e_pwd.strip():
                      conn_sql.exec_driver_sql(
                          f"UPDATE usuarios SET password = {PH}, rol = {PH},"
                          f" nombre_completo = {PH}, apellido = {PH}, telefono ="
                          f" {PH}, direccion = {PH} WHERE usuario = {PH}",
                          (
                              e_pwd.strip(),
                              e_rol,
                              e_nom,
                              e_ape,
                              e_tel,
                              e_dir,
                              ur["usuario"],
                          ),
                      )
                    else:
                      conn_sql.exec_driver_sql(
                          f"UPDATE usuarios SET rol = {PH}, nombre_completo ="
                          f" {PH}, apellido = {PH}, telefono = {PH}, direccion ="
                          f" {PH} WHERE usuario = {PH}",
                          (
                              e_rol,
                              e_nom,
                              e_ape,
                              e_tel,
                              e_dir,
                              ur["usuario"],
                          ),
                      )
                  st.success(
                      f"✅ ¡Usuario '{ur['usuario']}' actualizado correctamente!"
                  )
                  st.rerun()

                if eliminar:
                  with engine.begin() as conn_sql:
                    conn_sql.exec_driver_sql(
                        f"DELETE FROM usuarios WHERE usuario = {PH}",
                        (ur["usuario"],),
                    )
                  st.success(f"🗑️ Usuario '{ur['usuario']}' eliminado.")
                  st.rerun()

    elif rol == "Telefonista":
      if opcion == "Mis Prospectos y Gestión":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")
        busqueda_tele = st.text_input("🔎 Buscar:")
        q_t = f"""
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1, estado_tel2, estado_tel3 
            FROM clientes WHERE telefonista_asignada = {PH}
        """
        params_t = (usuario,)
        if busqueda_tele:
          if ES_SQLITE:
            q_t += (
                " AND (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR poliza"
                " LIKE ?)"
            )
          else:
            q_t += (
                " AND (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR"
                " poliza ILIKE %s)"
            )
          pt = f"%{busqueda_tele}%"
          params_t = (usuario, pt, pt, pt, pt)

        df_p = pd.read_sql(q_t, con=engine, params=params_t)
        if df_p.empty:
          st.info("No se encontraron prospectos.")
        else:
          renderizar_bloque_con_tabla(
              df_p, key_suffix="gestion_tele", ocultar_tels=True
          )

      elif opcion == "Mis Citas Agendadas":
        st.header(f"📅 Agenda Diaria ({usuario})")
        f_sel = st.date_input(
            "Fecha:", value=obtener_ahora_mexico().date()
        ).strftime("%Y-%m-%d")
        df_ag = pd.read_sql(
            f"""
            SELECT fecha as "Fecha", hora as "Hora", cliente as "Cliente", estado as "Estado", notas as "Notas" 
            FROM citas WHERE agente = {PH} AND fecha = {PH} ORDER BY hora ASC
        """,
            con=engine,
            params=(usuario, f_sel),
        )
        if df_ag.empty:
          st.info("No hay citas para esta fecha.")
        else:
          st.markdown(
              df_ag.to_html(
                  classes="custom-table", index=False, escape=False
              ),
              unsafe_allow_html=True,
          )

      elif opcion == "Control de Tiempo (Comida/Baño)":
        st.header("⏱️ Control de Tiempos y Salidas")
        f_hoy_str = obtener_ahora_mexico().strftime("%Y-%m-%d")
        LIMITE_MINUTOS_COMIDA = 30

        with engine.connect() as conn_sql:
          reg_comida_activo = conn_sql.exec_driver_sql(
              f"""
                SELECT id, hora_inicio FROM asistencia_telefonistas 
                WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Comida' AND estado = 'En Curso'
            """,
              (usuario, f_hoy_str),
          ).fetchone()

          reg_bano_activo = conn_sql.exec_driver_sql(
              f"""
                SELECT id, hora_inicio FROM asistencia_telefonistas 
                WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Baño' AND estado = 'En Curso'
            """,
              (usuario, f_hoy_str),
          ).fetchone()

          conteo_bano = conn_sql.exec_driver_sql(
              f"""
                SELECT COUNT(*) FROM asistencia_telefonistas 
                WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Baño'
            """,
              (usuario, f_hoy_str),
          ).fetchone()[0]

        col_c1, col_c2 = st.columns(2)

        with col_c1:
          st.subheader("🍽️ Tiempo de Comida (30 Minutos)")
          if reg_comida_activo:
            st.warning(
                f"⏳ Comida iniciada a las: **{reg_comida_activo[1]}**"
            )
            if st.button(
                "🔴 REGRESÉ DE COMER",
                key="btn_fin_comida",
                use_container_width=True,
            ):
              h_inicio = datetime.strptime(
                  f"{f_hoy_str} {reg_comida_activo[1]}", "%Y-%m-%d %H:%M:%S"
              )
              h_fin = obtener_ahora_mexico()
              duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)

              if duracion <= LIMITE_MINUTOS_COMIDA:
                est_final = "A Tiempo"
              else:
                exceso = duracion - LIMITE_MINUTOS_COMIDA
                est_final = f"EXCEDIDO (+{exceso} min)"

              with engine.begin() as conn_sql:
                conn_sql.exec_driver_sql(
                    f"""
                        UPDATE asistencia_telefonistas 
                        SET hora_fin = {PH}, duracion_minutos = {PH}, estado = {PH} 
                        WHERE id = {PH}
                    """,
                    (
                        h_fin.strftime("%H:%M:%S"),
                        duracion,
                        est_final,
                        reg_comida_activo[0],
                    ),
                )
              st.success(
                  f"✅ Regreso registrado. Tiempo total: {duracion} min."
              )
              st.rerun()
          else:
            if st.button(
                "🟢 INICIAR COMIDA",
                key="btn_ini_comida",
                use_container_width=True,
            ):
              h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
              with engine.begin() as conn_sql:
                conn_sql.exec_driver_sql(
                    f"""
                        INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado)
                        VALUES ({PH}, 'Comida', {PH}, {PH}, 'En Curso')
                    """,
                    (usuario, f_hoy_str, h_ini_str),
                )
              st.success("¡Disfruta tu tiempo de comida!")
              st.rerun()

        with col_c2:
          st.subheader("🚽 Salida al Baño")
          st.info(f"📌 Total de salidas al baño hoy: **{conteo_bano}**")

          if reg_bano_activo:
            st.warning(
                f"⏳ Salida al baño iniciada a las: **{reg_bano_activo[1]}**"
            )
            if st.button(
                "🔴 REGRESÉ DEL BAÑO",
                key="btn_fin_bano",
                use_container_width=True,
            ):
              h_inicio = datetime.strptime(
                  f"{f_hoy_str} {reg_bano_activo[1]}", "%Y-%m-%d %H:%M:%S"
              )
              h_fin = obtener_ahora_mexico()
              duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)

              with engine.begin() as conn_sql:
                conn_sql.exec_driver_sql(
                    f"""
                        UPDATE asistencia_telefonistas 
                        SET hora_fin = {PH}, duracion_minutos = {PH}, estado = 'Completado' 
                        WHERE id = {PH}
                    """,
                    (
                        h_fin.strftime("%H:%M:%S"),
                        duracion,
                        reg_bano_activo[0],
                    ),
                )
              st.success("✅ Regreso del baño registrado.")
              st.rerun()
          else:
            if st.button(
                "🟢 IR AL BAÑO", key="btn_ini_bano", use_container_width=True
            ):
              h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
              with engine.begin() as conn_sql:
                conn_sql.exec_driver_sql(
                    f"""
                        INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado)
                        VALUES ({PH}, 'Baño', {PH}, {PH}, 'En Curso')
                    """,
                    (usuario, f_hoy_str, h_ini_str),
                )
              st.success("Salida al baño registrada.")
              st.rerun()

        st.markdown("---")
        st.subheader("📜 Mi Historial de Salidas Hoy")
        df_mi_asistencia = pd.read_sql(
            f"""
            SELECT tipo_registro as "Tipo", hora_inicio as "Inicio", hora_fin as "Fin", duracion_minutos as "Minutos", estado as "Estado"
            FROM asistencia_telefonistas WHERE usuario = {PH} AND fecha = {PH} ORDER BY id DESC
        """,
            con=engine,
            params=(usuario, f_hoy_str),
        )
        if df_mi_asistencia.empty:
          st.caption("No registras salidas el día de hoy.")
        else:
          html_tabla = "<table class='custom-table'><thead><tr>"
          for col in df_mi_asistencia.columns:
            html_tabla += f"<th>{col}</th>"
          html_tabla += "</tr></thead><tbody>"

          for _, r in df_mi_asistencia.iterrows():
            clase = (
                "class='fila-excedida'"
                if "EXCEDIDO" in str(r["Estado"])
                else ""
            )
            html_tabla += f"<tr {clase}>"
            for val in r:
              html_tabla += f"<td>{val if pd.notna(val) else ''}</td>"
            html_tabla += "</tr>"
          html_tabla += "</tbody></table>"

          st.markdown(html_tabla, unsafe_allow_html=True)

    else:
      if opcion == "Mis Prospectos Asignados":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")
        busq_a = st.text_input("🔎 Buscar:")
        q_a = f"""
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1, estado_tel2, estado_tel3 
            FROM clientes WHERE telefonista_asignada = {PH}
        """
        params_a = (usuario,)
        if busq_a:
          if ES_SQLITE:
            q_a += " AND (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ?)"
          else:
            q_a += " AND (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s)"
          pa = f"%{busq_a}%"
          params_a = (usuario, pa, pa, pa)

        df_pa = pd.read_sql(q_a, con=engine, params=params_a)
        if df_pa.empty:
          st.info("No se encontraron prospectos.")
        else:
          renderizar_bloque_con_tabla(
              df_pa, key_suffix="gestion_asesor", ocultar_tels=True
          )
      elif opcion == "Bolsa de Citas del Día (Asesores)":
        st.header(f"💼 Bolsa de Citas del Día ({usuario})")
        f_hoy = obtener_ahora_mexico().strftime("%Y-%m-%d")
        df_b = pd.read_sql(
            f"""
            SELECT id, fecha as "Fecha", hora as "Hora", cliente as "Cliente", telefono as "Teléfono", estado as "Estado", notas as "Notas" 
            FROM citas WHERE fecha = {PH} AND (asesor = {PH} OR asesor = 'Sin Asignar') ORDER BY hora ASC
        """,
            con=engine,
            params=(f_hoy, usuario),
        )
        if df_b.empty:
          st.info("No hay citas en la bolsa para hoy.")
        else:
          st.markdown(
              df_b.to_html(
                  classes="custom-table", index=False, escape=False
              ),
              unsafe_allow_html=True,
          )
      elif opcion == "Mis Registros de Hoy":
        st.header(f"📝 Mis Registros de Hoy ({usuario})")
        f_hoy = obtener_ahora_mexico().strftime("%Y-%m-%d")
        like_op = "LIKE" if ES_SQLITE else "LIKE"
        df_rh = pd.read_sql(
            f"""
            SELECT h.fecha_registro as "Fecha/Hora", c.nombre || ' ' || c.apellido as "Cliente", h.accion as "Acción", h.detalle as "Detalle" 
            FROM historial_llamadas h JOIN clientes c ON h.rfc_cliente = c.rfc 
            WHERE h.usuario = {PH} AND h.fecha_registro {like_op} {PH} ORDER BY h.id DESC
        """,
            con=engine,
            params=(usuario, f"{f_hoy}%"),
        )
        if df_rh.empty:
          st.info("No tienes registros hoy.")
        else:
          st.markdown(
              df_rh.to_html(
                  classes="custom-table", index=False, escape=False
              ),
              unsafe_allow_html=True,
          )
      elif opcion == "📊 Reportes de Citas y Asistencias":
        st.header("📊 Reportes de Asesor")
        f_rep_a = st.date_input(
            "Fecha Base:", value=obtener_ahora_mexico().date()
        ).strftime("%Y-%m-%d")
        df_ra = pd.read_sql(
            f"SELECT * FROM citas WHERE agente = {PH} AND fecha = {PH}",
            con=engine,
            params=(usuario, f_rep_a),
        )
        m1, m2 = st.columns(2)
        m1.metric("Mis Citas del Día", len(df_ra))
        asis_a = (
            len(
                df_ra[
                    df_ra["estado"].str.contains(
                        "Asistida", case=False, na=False
                    )
                ]
            )
            if not df_ra.empty
            else 0
        )
        m2.metric("Citas Asistidas", asis_a)
        if not df_ra.empty:
          st.markdown(
              df_ra.to_html(
                  classes="custom-table", index=False, escape=False
              ),
              unsafe_allow_html=True,
          )
