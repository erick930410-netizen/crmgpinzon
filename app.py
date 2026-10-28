from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

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
    engine = create_engine(
        db_url,
        connect_args={"timeout": 30},
        poolclass=NullPool
    )
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA journal_mode=WAL")
      cursor.execute("PRAGMA synchronous=NORMAL")
      cursor.close()

    st.sidebar.info(
        "💻 Modo Pruebas Local (SQLite sin concurrencia bloqueante)\nTus datos aquí no afectan la oficina."
    )
except Exception as e:
  try:
    db_url = "sqlite:///crm_local_test.db"
    engine = create_engine(db_url, connect_args={"timeout": 30}, poolclass=NullPool)
    st.sidebar.info("💻 Modo Pruebas Local (SQLite por excepción)")
  except Exception as inner_e:
    st.error(
        f"⚠️ Error crítico de conexión a la base de datos: {e} / {inner_e}"
    )
    st.stop()

ES_SQLITE = engine.name == "sqlite"
PH = "?" if ES_SQLITE else "%s"
ID_SERIAL = (
    "INTEGER PRIMARY KEY AUTOINCREMENT" if ES_SQLITE else "SERIAL PRIMARY KEY"
)


# --- ESTILOS CSS GENERALES ---
st.markdown(
    """
<style>
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

    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 1rem !important;
    }

    h1, h2, h3 {
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

    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
    }

    div[data-testid="stExpander"] {
        background-color: #0072CE !important;
        border: none !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        background-color: #0072CE !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] summary svg {
        fill: #ffffff !important;
    }
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
        background-color: #0072CE !important;
        border-radius: 0 0 8px 8px !important;
        padding: 20px !important;
        color: #ffffff !important;
    }
    div[data-testid="stExpander"] label, div[data-testid="stExpander"] .stMarkdown {
        color: #ffffff !important;
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

    .banner-alerta-seguimiento {
        background: linear-gradient(135deg, #ff4b4b 0%, #d92b2b 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(217, 43, 43, 0.4);
        margin-bottom: 20px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
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


def calcular_rango_fechas(f_base, tipo_periodo):
  if tipo_periodo == "📅 Diario":
    f_ini = f_base
    f_fin = f_base
  elif tipo_periodo == "🗓️ Semanal":
    f_ini = f_base - timedelta(days=f_base.weekday())
    f_fin = f_ini + timedelta(days=6)
  else:
    f_ini = f_base.replace(day=1)
    if f_base.month == 12:
      f_fin = f_base.replace(year=f_base.year + 1, month=1, day=1) - timedelta(days=1)
    else:
      f_fin = f_base.replace(month=f_base.month + 1, day=1) - timedelta(days=1)
  return f_ini.strftime("%Y-%m-%d"), f_fin.strftime("%Y-%m-%d")


def inicializar_base_de_datos():
  queries_init = [
      f"""
      CREATE TABLE IF NOT EXISTS usuarios (
          id {ID_SERIAL},
          usuario TEXT UNIQUE, password TEXT, rol TEXT,
          nombre_completo TEXT, apellido TEXT, telefono TEXT, direccion TEXT
      )
      """,
      f"""
      CREATE TABLE IF NOT EXISTS clientes (
          rfc TEXT PRIMARY KEY, nombre TEXT, apellido TEXT,
          tel1 TEXT, tel2 TEXT, tel3 TEXT, telefono TEXT, tel_opcional TEXT,
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
      """,
      "ALTER TABLE clientes ADD COLUMN tel_opcional TEXT",
      f"""
      CREATE TABLE IF NOT EXISTS historial_llamadas (
          id {ID_SERIAL},
          rfc_cliente TEXT, usuario TEXT, accion TEXT, detalle TEXT, fecha_registro TEXT
      )
      """,
      f"""
      CREATE TABLE IF NOT EXISTS citas (
          id {ID_SERIAL},
          rfc_cliente TEXT, cliente TEXT NOT NULL, telefono TEXT,
          agente TEXT, asesor TEXT DEFAULT 'Sin Asignar',
          fecha TEXT NOT NULL, hora TEXT NOT NULL, estado TEXT NOT NULL, notas TEXT
      )
      """,
      f"""
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
      """
  ]

  for q in queries_init:
    try:
      with engine.begin() as conn_sql:
        conn_sql.exec_driver_sql(q)
    except Exception:
      pass

inicializar_base_de_datos()

hoy_str_mex = obtener_ahora_mexico().strftime("%Y-%m-%d")
try:
  with engine.begin() as conn_sql:
    conn_sql.exec_driver_sql(
        f"""
          UPDATE citas SET estado = 'No Asistió (Automático)' 
          WHERE estado = 'Pendiente' AND date(fecha) < {PH}
      """,
        (hoy_str_mex,),
    )
except Exception:
  pass

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


def obtener_usuarios_por_rol(rol):
  with engine.connect() as conn_sql:
    res = conn_sql.exec_driver_sql(
        f"SELECT usuario FROM usuarios WHERE rol = {PH} ORDER BY usuario",
        (rol,),
    ).fetchall()
  return [row[0] for row in res]


def obtener_todos_los_usuarios_asignables():
  roles = ["Telefonista", "Asesor", "Base de Datos"]
  usuarios = []
  for r in roles:
    usuarios.extend(obtener_usuarios_por_rol(r))
  return sorted(list(set(usuarios)))


def limpiar_val(val):
  if pd.isna(val) or val is None:
    return ""
  val_str = str(val).strip()
  if val_str.endswith(".0"):
    val_str = val_str[:-2]
  return "" if val_str == "nan" else val_str


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
          ["Sin Asignar"] + obtener_todos_los_usuarios_asignables(),
      )
    elif rol_actual in ["Telefonista", "Asesor", "Base de Datos"]:
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
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin marcar', 'Sin marcar', 'Sin marcar')
            """,
                (
                    rfc.strip().upper(),
                    nombre,
                    apellido,
                    tel1,
                    tel2,
                    tel3,
                    telefono_final,
                    "",
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
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
                ON CONFLICT (rfc) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido
            """,
                (
                    rfc.strip().upper(),
                    nombre,
                    apellido,
                    tel1,
                    tel2,
                    tel3,
                    telefono_final,
                    "",
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
                    "Sin marcar",
                    "Sin marcar",
                    "Sin marcar",
                ),
            )
        st.success(
            f"✅ ¡Prospecto '{nombre} {apellido}' registrado con éxito!"
        )
        st.rerun()


# --- TABLA CON SELECCIÓN RÁPIDA MASIVA Y MEMORIA DE POSICIÓN ---
def renderizar_bloque_con_tabla(df_entrada, key_suffix, ocultar_tels=False):
  df = df_entrada.copy()
  if ocultar_tels:
    for col_tel in ["tel1", "tel2", "tel3", "telefono", "Teléfono", "tel_opcional"]:
      if col_tel in df.columns:
        df[col_tel] = "🔒 ***-ocultos***"

  cant_por_pagina = 100
  sel_prev = st.session_state.get(f"sel_rfcs_{key_suffix}", [])

  if "Seleccionar" not in df.columns:
    df.insert(0, "Seleccionar", False)

  st.session_state["lista_rfcs_navegacion"] = df["rfc"].tolist()
  tot_filt = len(df)
  tot_pags = (
      max(1, (tot_filt - 1) // cant_por_pagina + 1) if tot_filt > 0 else 1
  )

  key_pag_state = f"pag_idx_guardada_{key_suffix}"
  if key_pag_state not in st.session_state:
    st.session_state[key_pag_state] = 1

  if tot_filt > cant_por_pagina:
    if st.session_state[key_pag_state] > tot_pags:
      st.session_state[key_pag_state] = tot_pags

    p_act = st.selectbox(
        f"📄 Páginas (Bloques de 100 de {tot_filt} coincidentes):",
        range(1, tot_pags + 1),
        index=st.session_state[key_pag_state] - 1,
        key=f"pag_num_{key_suffix}",
    )
    st.session_state[key_pag_state] = p_act
    df_a_mostrar = df.iloc[
        (p_act - 1) * cant_por_pagina : p_act * cant_por_pagina
    ].copy()
    offset_num = (p_act - 1) * cant_por_pagina
  else:
    df_a_mostrar = df.copy()
    offset_num = 0

  col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1.8, 1.5, 1.2])
  with col_b1:
    if st.button("☑️ Marcar Página Actual", key=f"btn_sel_pag_{key_suffix}", use_container_width=True):
      rfcs_pag = df_a_mostrar["rfc"].tolist()
      st.session_state[f"sel_rfcs_{key_suffix}"] = list(set(sel_prev + rfcs_pag))
      st.rerun()
  with col_b2:
    if st.button(f"☑️ Marcar TODOS ({tot_filt})", key=f"btn_sel_todos_{key_suffix}", use_container_width=True):
      st.session_state[f"sel_rfcs_{key_suffix}"] = df["rfc"].tolist()
      st.rerun()
  with col_b3:
    if st.button("🧹 Desmarcar Todo", key=f"btn_desmarcar_{key_suffix}", use_container_width=True):
      st.session_state[f"sel_rfcs_{key_suffix}"] = []
      st.rerun()
  with col_b4:
    cant_actuales_sel = len(st.session_state.get(f"sel_rfcs_{key_suffix}", []))
    st.markdown(f"<div style='padding-top:8px; font-weight:bold; color:#0072CE;'>Selected: {cant_actuales_sel}</div>", unsafe_allow_html=True)

  df_a_mostrar.insert(0, "#", range(offset_num + 1, offset_num + len(df_a_mostrar) + 1))
  df_a_mostrar["Seleccionar"] = df_a_mostrar["rfc"].isin(st.session_state.get(f"sel_rfcs_{key_suffix}", []))

  column_config = {
      "#": st.column_config.NumberColumn("#", width="small", disabled=True),
      "Seleccionar": st.column_config.CheckboxColumn(
          "Seleccionar", default=False, width="small"
      ),
      "rfc": st.column_config.TextColumn("RFC / ID", width="medium"),
  }
  cols_dis = [c for c in df.columns if c not in ["Seleccionar"]] + ["#"]

  if st.session_state.get(f"sel_rfcs_{key_suffix}", []):
    if st.button(
        "🚀 Abrir / Ver Ficha",
        key=f"btn_sup_{key_suffix}",
        use_container_width=True,
    ):
      st.session_state["prospecto_editar_rfc"] = str(st.session_state[f"sel_rfcs_{key_suffix}"][0])
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
  otros = [r for r in st.session_state.get(f"sel_rfcs_{key_suffix}", []) if r not in df_a_mostrar["rfc"].tolist()]
  final_sel = list(set(otros + sel_actual))

  if final_sel != st.session_state.get(f"sel_rfcs_{key_suffix}", []):
    st.session_state[f"sel_rfcs_{key_suffix}"] = final_sel
    st.rerun()

  return editor_res


def renderizar_control_tiempos_modal(usuario_act):
  f_hoy_str = obtener_ahora_mexico().strftime("%Y-%m-%d")
  LIMITE_MINUTOS_COMIDA = 30
  LIMITE_MINUTOS_RECESO = 10

  with engine.connect() as conn_sql:
    reg_comida_activo = conn_sql.exec_driver_sql(
        f"""
          SELECT id, hora_inicio FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Comida' AND estado = 'En Curso'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()

    comida_registrada_hoy = conn_sql.exec_driver_sql(
        f"""
          SELECT COUNT(*) FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Comida' AND estado != 'En Curso'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()[0] > 0

    reg_receso_activo = conn_sql.exec_driver_sql(
        f"""
          SELECT id, hora_inicio FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Receso' AND estado = 'En Curso'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()

    receso_registrado_hoy = conn_sql.exec_driver_sql(
        f"""
          SELECT COUNT(*) FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Receso' AND estado != 'En Curso'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()[0] > 0

    reg_bano_activo = conn_sql.exec_driver_sql(
        f"""
          SELECT id, hora_inicio FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Baño' AND estado = 'En Curso'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()

    conteo_bano = conn_sql.exec_driver_sql(
        f"""
          SELECT COUNT(*) FROM asistencia_telefonistas 
          WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Baño'
      """,
        (usuario_act, f_hoy_str),
    ).fetchone()[0]

  st.markdown("### ⏱️ Registro de Tiempos")
  
  st.caption("🍽️ Tiempo de Comida (30 Min - Única vez al día)")
  if comida_registrada_hoy:
    st.info("✅ Ya realizaste tu comida del día.")
  else:
    if reg_comida_activo:
      st.warning(f"⏳ Comida iniciada a las: **{reg_comida_activo[1]}**")
      if st.button("🔴 REGRESÉ DE COMER", key="btn_fin_comida_pop", use_container_width=True):
        h_inicio = datetime.strptime(f"{f_hoy_str} {reg_comida_activo[1]}", "%Y-%m-%d %H:%M:%S")
        h_fin = obtener_ahora_mexico()
        duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)
        est_final = "A Tiempo" if duracion <= LIMITE_MINUTOS_COMIDA else f"EXCEDIDO (+{duracion - LIMITE_MINUTOS_COMIDA} min)"
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(
              f"UPDATE asistencia_telefonistas SET hora_fin = {PH}, duracion_minutos = {PH}, estado = {PH} WHERE id = {PH}",
              (h_fin.strftime("%H:%M:%S"), duracion, est_final, reg_comida_activo[0]),
          )
        st.success(f"Regreso guardado ({duracion} min)")
        st.rerun()
    else:
      if st.button("🟢 IR A COMER", key="btn_ini_comida_pop", use_container_width=True):
        h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(
              f"INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado) VALUES ({PH}, 'Comida', {PH}, {PH}, 'En Curso')",
              (usuario_act, f_hoy_str, h_ini_str),
          )
        st.success("¡Buen provecho!")
        st.rerun()

  st.markdown("---")
  col_rec, col_ban = st.columns(2)

  with col_rec:
    st.caption("☕ Receso (10 Min - Única vez al día)")
    if receso_registrado_hoy:
      st.info("✅ Ya realizaste tu receso del día.")
    else:
      if reg_receso_activo:
        st.warning(f"⏳ Receso iniciado: **{reg_receso_activo[1]}**")
        if st.button("🔴 REGRESÉ RECESO", key="btn_fin_receso_pop", use_container_width=True):
          h_inicio = datetime.strptime(f"{f_hoy_str} {reg_receso_activo[1]}", "%Y-%m-%d %H:%M:%S")
          h_fin = obtener_ahora_mexico()
          duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)
          est_final = "A Tiempo" if duracion <= LIMITE_MINUTOS_RECESO else f"EXCEDIDO (+{duracion - LIMITE_MINUTOS_RECESO} min)"
          with engine.begin() as conn_sql:
            conn_sql.exec_driver_sql(
                f"UPDATE asistencia_telefonistas SET hora_fin = {PH}, duracion_minutos = {PH}, estado = {PH} WHERE id = {PH}",
                (h_fin.strftime("%H:%M:%S"), duracion, est_final, reg_receso_activo[0]),
            )
          st.success("Regreso de receso guardado")
          st.rerun()
      else:
        if st.button("🟢 TOMAR RECESO", key="btn_ini_receso_pop", use_container_width=True):
          h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
          with engine.begin() as conn_sql:
            conn_sql.exec_driver_sql(
                f"INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado) VALUES ({PH}, 'Receso', {PH}, {PH}, 'En Curso')",
                (usuario_act, f_hoy_str, h_ini_str),
            )
          st.success("Receso iniciado")
          st.rerun()

  with col_ban:
    st.caption(f"🚽 Baño (Hoy: {conteo_bano})")
    if reg_bano_activo:
      st.warning(f"⏳ Baño iniciado: **{reg_bano_activo[1]}**")
      if st.button("🔴 REGRESÉ BAÑO", key="btn_fin_bano_pop", use_container_width=True):
        h_inicio = datetime.strptime(f"{f_hoy_str} {reg_bano_activo[1]}", "%Y-%m-%d %H:%M:%S")
        h_fin = obtener_ahora_mexico()
        duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(
              f"UPDATE asistencia_telefonistas SET hora_fin = {PH}, duracion_minutos = {PH}, estado = 'Completado' WHERE id = {PH}",
              (h_fin.strftime("%H:%M:%S"), duracion, reg_bano_activo[0]),
          )
        st.success("Regreso guardado")
        st.rerun()
    else:
      if st.button("🟢 IR AL BAÑO", key="btn_ini_bano_pop", use_container_width=True):
        h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(
              f"INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado) VALUES ({PH}, 'Baño', {PH}, {PH}, 'En Curso')",
              (usuario_act, f_hoy_str, h_ini_str),
          )
        st.success("Salida guardada")
        st.rerun()


def comprobar_recordatorios_asesor(usuario_act):
  f_hoy_str = obtener_ahora_mexico().strftime("%Y-%m-%d")
  df_pendientes = pd.read_sql(
      f"""
      SELECT cliente, rfc_cliente, fecha, notas 
      FROM citas 
      WHERE asesor = {PH} AND estado = 'Seguimiento 3 Semanas (Pendiente)' AND fecha <= {PH}
      ORDER BY fecha ASC
      """,
      con=engine,
      params=(usuario_act, f_hoy_str),
  )
  return df_pendientes


for k, v in [
    ("usuario_logueado", None),
    ("rol", None),
    ("prospecto_editar_rfc", None),
    ("lista_rfcs_navegacion", []),
    ("seccion_activa", None),
    ("reset_filtros_trigger", 0),
]:
  if k not in st.session_state:
    st.session_state[k] = v

rol_actual_sesion = st.session_state.get("rol", None)

if rol_actual_sesion != "Administrador":
  st.markdown(
      """
    <style>
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
              padding-top: 0rem !important;
              padding-bottom: 0rem !important;
              max-width: 95% !important;
          }
          .stTextInput label, .stTextInput div {
              color: #ffffff !important;
          }
          .stButton>button {
              background-color: #78BE20 !important;
              color: #ffffff !important;
              font-size: 1.05rem !important;
              font-weight: bold !important;
              padding: 0.5rem 1rem !important;
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

  st.markdown(
      """
      <h1 style="color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; font-size: 5.4rem; font-weight: 950; letter-spacing: 2px; margin-bottom: 0.5rem; text-shadow: 0 4px 10px rgba(0,0,0,0.3); width: 100%; white-space: nowrap;">GRUPO PINZON T</h1>
  """,
      unsafe_allow_html=True,
  )

  col_logo_izq, col_espacio_medio, col_login_der = st.columns([1.6, 0.3, 1.1], gap="large")

  with col_logo_izq:
    st.markdown(
        """
        <div style="background: #ffffff; color: #002B49; padding: 45px 70px; border-radius: 24px; box-shadow: 0 12px 30px rgba(0,0,0,0.3); display: inline-block; text-align: center;">
            <span style="font-size: 16rem; font-weight: 900; color: #0072CE; line-height: 0.8;">G</span><span style="font-size: 12rem; font-weight: 900; color: #78BE20; line-height: 0.8;">p</span>
        </div>
        <div style="text-align: center; width: 100%; display: flex; justify-content: center;">
            <p style="margin: 20px 0 0 0; font-size: 2.25rem; color: #ffffff !important; font-weight: 800; text-shadow: 0 3px 8px rgba(0,0,0,0.4); line-height: 1.2; max-width: 550px;">Sistema de Control de Prospectos y CRM</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

  with col_login_der:
    st.markdown(
        """
        <div style="background: rgba(0, 43, 73, 0.5); padding: 25px 25px; border-radius: 14px; box-shadow: 0 6px 20px rgba(0,0,0,0.3); backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,0.15);">
            <h3 style='color: #ffffff !important; margin-top: 0; margin-bottom: 12px; font-size: 1.8rem; font-weight: 800; text-shadow: 0 2px 5px rgba(0,0,0,0.3); text-align: center;'>🔑 Iniciar Sesión</h3>
    """,
        unsafe_allow_html=True,
    )
    
    usr = st.text_input("Usuario", key="login_usr")
    pwd = st.text_input("Contraseña", type="password", key="login_pwd")
    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
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
        
    st.markdown("</div>", unsafe_allow_html=True)

else:
  st.markdown(
      """
      <style>
          .stApp {
              background-color: #f4f7f6 !important;
          }
          .block-container {
              padding-top: 1.2rem !important;
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
          "6. Dashboard y Estadísticas de Asesores",
      ]
      if rol == "Administrador"
      else (
          [
              "Mis Prospectos y Gestión",
              "Mis Citas Agendadas",
          ]
          if rol == "Telefonista"
          else (
              ["Mis Prospectos Asignados (Depuración BD)"]
              if rol == "Base de Datos"
              else [
                  "Prospectos",
                  "Bolsa de Citas del Día (Asesores)",
                  "Mis Registros de Hoy",
                  "📊 Reportes de Citas y Asistencias",
              ]
          )
      )
  )

  if (
      st.session_state["seccion_activa"] is None
      or st.session_state["seccion_activa"] not in opciones
  ):
    st.session_state["seccion_activa"] = opciones[0]

  col_nav1, col_nav2, col_nav_tiempos, col_nav3 = st.columns([2.2, 2.5, 1.2, 1.2])
  
  with col_nav1:
    st.markdown(
        """
        <div style="background-color: #78BE20; padding: 6px 12px; border-radius: 8px 8px 0 0; margin-bottom: -6px; text-align: center; box-shadow: 0 2px 6px rgba(120,190,32,0.3);">
            <span style="color: white; font-weight: 900; font-size: 1.1rem; letter-spacing: 1px;">📌 MENÚ</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    idx_actual = opciones.index(st.session_state["seccion_activa"]) if st.session_state["seccion_activa"] in opciones else 0
    seccion_elegida = st.selectbox(
        "",
        opciones,
        index=idx_actual,
        key="selector_navegacion_directa",
        label_visibility="collapsed"
    )
    if seccion_elegida != st.session_state["seccion_activa"]:
      st.session_state["seccion_activa"] = seccion_elegida
      st.session_state["prospecto_editar_rfc"] = None
      st.rerun()

  opcion = st.session_state["seccion_activa"]

  with col_nav2:
    st.markdown(
        f"<div style='text-align: center; padding-top: 28px;'>👤 <b>Usuario:</b>"
        f" <code>{usuario}</code> &nbsp;|&nbsp; 🛡️ <b>Rol:</b>"
        f" <code>{rol}</code></div>",
        unsafe_allow_html=True,
    )

  with col_nav_tiempos:
    if rol == "Telefonista":
      st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
      with st.popover("🍽️/Toilet/☕ Tiempos"):
        renderizar_control_tiempos_modal(usuario)

  with col_nav3:
    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
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

  if rol == "Asesor":
    df_alertas_asesor = comprobar_recordatorios_asesor(usuario)
    if not df_alertas_asesor.empty:
      cant_pend = len(df_alertas_asesor)
      st.markdown(
          f"""
          <div class="banner-alerta-seguimiento">
              <div style="font-size: 1.25rem; font-weight: bold; margin-bottom: 6px;">
                  🔔 RECORDATORIO DE SEGUIMIENTO Y ENTREGA DE DOCUMENTOS ({cant_pend} PENDIENTES)
              </div>
              <div style="font-size: 1rem;">
                  Han transcurrido 3 semanas desde el cierre/servicio de los siguientes clientes. Recuerda dar seguimiento y entregar documentación:
              </div>
          </div>
          """,
          unsafe_allow_html=True,
      )
      for _, row_alt in df_alertas_asesor.iterrows():
        col_a1, col_a2 = st.columns([3, 1])
        with col_a1:
          st.warning(f"👤 **Cliente:** {row_alt['cliente']} (RFC: `{row_alt['rfc_cliente']}`) | 📅 **Fecha Programada:** {row_alt['fecha']} | 📝 **Detalle:** {row_alt['notas']}")
        with col_a2:
          if st.button("✅ Marcar Entregado", key=f"btn_firm_entregado_{row_alt['rfc_cliente']}"):
            with engine.begin() as conn_sql:
              conn_sql.exec_driver_sql(
                  f"UPDATE citas SET estado = 'Documentos Entregados' WHERE rfc_cliente = {PH} AND estado = 'Seguimiento 3 Semanas (Pendiente)'",
                  (row_alt['rfc_cliente'],),
              )
            st.success("¡Seguimiento marcado como entregado!")
            st.rerun()

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
                   estado_tel1, estado_tel2, estado_tel3, tel_opcional
            FROM clientes WHERE rfc = {PH}
        """,
          (rfc_actual,),
      ).fetchone()

    if not row:
      st.error("No se encontró la información del prospecto.")
      st.session_state["prospecto_editar_rfc"] = None
    else:

      def ejecutar_guardado_y_salto(destino):
        if rol == "Asesor":
          accion_sel_val = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
          if accion_sel_val == "Cierre / Actualización":
            monto_val = st.session_state.get(f"monto_act_{rfc_actual}", "").strip()
            if not monto_val or monto_val == "0":
              st.error("⚠️ ¡OBLIGATORIO! Debes ingresar el Monto de la Actualización para registrar un Cierre.")
              return False

        rfc_limpio = str(
            st.session_state.get(f"frfc_{rfc_actual}", row[0])
        ).strip().upper()
        n_nombre = st.session_state.get(f"fn_{rfc_actual}", row[1])
        n_apellido = st.session_state.get(f"fa_{rfc_actual}", row[2])

        if rol in ["Base de Datos", "Asesor"]:
          n_t1, n_t2, n_t3 = row[3], row[4], row[5]
        else:
          n_t1 = st.session_state.get(f"ftel1_{rfc_actual}", row[3])
          n_t2 = st.session_state.get(f"ftel2_{rfc_actual}", row[4])
          n_t3 = st.session_state.get(f"ftel3_{rfc_actual}", row[5])

        n_tel_opcional_input = st.session_state.get(f"ftel_opcional_{rfc_actual}", "").strip() if rol == "Asesor" else ""
        n_tel_opcional = n_tel_opcional_input if n_tel_opcional_input else (row[19] or "")

        n_sector = st.session_state.get(f"fs_{rfc_actual}", row[6])
        n_poliza = st.session_state.get(f"fp_{rfc_actual}", row[7])
        n_div = st.session_state.get(f"fdiv_{rfc_actual}", parsear_a_date(row[8]))
        n_asig_f = st.session_state.get(
            f"fulfasig_{rfc_actual}", parsear_a_date(row[9])
        )
        n_mov = st.session_state.get(f"ffum_{rfc_actual}", parsear_a_date(row[11]))
        
        obs_asesor_previas = row[13] or ""
        input_nueva_obs_asesor = st.session_state.get(f"fobs_asesor_{rfc_actual}", "")
        
        n_obs_asesor = obs_asesor_previas
        detalle_formateado_historial = ""
        estatus_general = row[15]
        usuario_asignado_final = row[14]

        if rol == "Asesor":
          f_hoy_dt = obtener_ahora_mexico()
          f_hoy_formato = f_hoy_dt.strftime("%Y/%m/%d")
          accion_sel = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
          
          if accion_sel != "-- Seleccionar Acción --":
            usuario_asignado_final = usuario
            
            extra_detalle = []
            programar_seguimiento = False

            if accion_sel == "Cierre / Actualización":
              programar_seguimiento = True
              monto_act = st.session_state.get(f"monto_act_{rfc_actual}", "").strip()
              hizo_serv = st.session_state.get(f"chk_servicio_{rfc_actual}", False)
              if monto_act:
                extra_detalle.append(f"Monto Act: ${monto_act}")
              if hizo_serv:
                tipo_s = st.session_state.get(f"tipo_serv_{rfc_actual}", "Dividendos")
                if tipo_s == "Otros":
                  det_otro = st.session_state.get(f"det_otro_serv_{rfc_actual}", "").strip()
                  extra_detalle.append(f"Servicio: Otros ({det_otro})")
                else:
                  extra_detalle.append(f"Servicio: {tipo_s}")

            elif accion_sel == "Solo Servicio":
              programar_seguimiento = True
              tipo_s = st.session_state.get(f"tipo_serv_solo_{rfc_actual}", "Dividendos")
              if tipo_s == "Otros":
                det_otro = st.session_state.get(f"det_otro_serv_solo_{rfc_actual}", "").strip()
                extra_detalle.append(f"Servicio: Otros ({det_otro})")
              else:
                extra_detalle.append(f"Servicio: {tipo_s}")

            str_extra = " | ".join(extra_detalle)
            str_tel = f" [Tel Opc: {n_tel_opcional}]" if n_tel_opcional else ""
            str_completo_detalle = f"{str_extra} - {input_nueva_obs_asesor.strip()}" if str_extra and input_nueva_obs_asesor.strip() else (str_extra or input_nueva_obs_asesor.strip())

            if str_completo_detalle:
              obs_formateada = f"({f_hoy_formato} - {usuario}) [{accion_sel}]{str_tel} {str_completo_detalle}"
              n_obs_asesor = f"{obs_asesor_previas}\n{obs_formateada}".strip() if obs_asesor_previas else obs_formateada
              detalle_formateado_historial = str_completo_detalle

            estatus_general = f"Atendido ({accion_sel})"

            if programar_seguimiento:
              fecha_recordatorio = (f_hoy_dt + timedelta(days=21)).strftime("%Y-%m-%d")
              nombre_cliente_completo = f"{n_nombre} {n_apellido}"
              with engine.begin() as conn_sql_rec:
                conn_sql_rec.exec_driver_sql(
                    f"""
                    INSERT INTO citas (rfc_cliente, cliente, telefono, agente, asesor, fecha, hora, estado, notas)
                    VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, '09:00', 'Seguimiento 3 Semanas (Pendiente)', {PH})
                    """,
                    (
                        rfc_limpio,
                        nombre_cliente_completo,
                        n_tel_opcional or n_t1 or "Sin Tel",
                        row[14],
                        usuario,
                        fecha_recordatorio,
                        f"Entrega de documentos y seguimiento de {accion_sel}: {str_extra}",
                    ),
                )

        else:
          if input_nueva_obs_asesor and input_nueva_obs_asesor != obs_asesor_previas:
            n_obs_asesor = input_nueva_obs_asesor

        n_obs_tel = st.session_state.get(f"fobs_tel_{rfc_actual}", row[12] or "")
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
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                    estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """,
                (
                    rfc_limpio,
                    n_nombre,
                    n_apellido,
                    n_t1,
                    n_t2,
                    n_t3,
                    telefono_general,
                    n_tel_opcional,
                    n_sector,
                    n_poliza,
                    str(n_div),
                    str(n_asig_f),
                    edad_nueva,
                    str(n_mov),
                    n_obs_tel,
                    n_obs_asesor,
                    usuario_asignado_final,
                    estatus_general,
                    est_t1,
                    est_t2,
                    est_t3,
                ),
            )
          else:
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                    estado_tel1, estado_tel2, estado_tel3
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
                ON CONFLICT (rfc) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido,
                    tel1 = EXCLUDED.tel1,
                    tel2 = EXCLUDED.tel2,
                    tel3 = EXCLUDED.tel3,
                    telefono = EXCLUDED.telefono,
                    tel_opcional = EXCLUDED.tel_opcional,
                    sector = EXCLUDED.sector,
                    poliza = EXCLUDED.poliza,
                    dividendos = EXCLUDED.dividendos,
                    ult_fecha_asignacion = EXCLUDED.ult_fecha_asignacion,
                    fecha_ult_mov = EXCLUDED.fecha_ult_mov,
                    observaciones_tel = EXCLUDED.observaciones_tel,
                    observaciones_asesor = EXCLUDED.observaciones_asesor,
                    telefonista_asignada = EXCLUDED.telefonista_asignada,
                    estatus = EXCLUDED.estatus,
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
                    n_tel_opcional,
                    n_sector,
                    n_poliza,
                    str(n_div),
                    str(n_asig_f),
                    edad_nueva,
                    str(n_mov),
                    n_obs_tel,
                    n_obs_asesor,
                    usuario_asignado_final,
                    estatus_general,
                    est_t1,
                    est_t2,
                    est_t3,
                ),
            )

          if rol == "Asesor" and detalle_formateado_historial:
            accion_sel = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
            ahora_local = obtener_ahora_mexico().strftime("%Y-%m-%d %H:%M:%S")
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO historial_llamadas (rfc_cliente, usuario, accion, detalle, fecha_registro)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH})
            """,
                (
                    rfc_actual,
                    usuario,
                    accion_sel,
                    detalle_formateado_historial,
                    ahora_local,
                ),
            )

        if destino == "siguiente":
          st.success("💾 ¡Cambios guardados con éxito!")
          if pos_actual < total_prospectos - 1:
            st.session_state["prospecto_editar_rfc"] = lista_rfcs[
                pos_actual + 1
            ]
          else:
            st.warning("✅ Has llegado al final de la lista.")
            st.session_state["prospecto_editar_rfc"] = None
        elif destino == "anterior":
          st.success("💾 ¡Cambios guardados con éxito!")
          if pos_actual > 0:
            st.session_state["prospecto_editar_rfc"] = lista_rfcs[
                pos_actual - 1
            ]
          else:
            st.warning("⚠️ Estás en el primer registro.")
        else:
          st.success("💾 ¡Cambios guardados con éxito!")
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

      st.markdown(
          f"""
          <div style="background-color: #e8f4f8; border-left: 6px solid #0072CE; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
              👤 <b>Asignado a:</b> <code>{row[14]}</code> &nbsp;|&nbsp; 📌 <b>Estatus Actual:</b> <code>{row[15]}</code>
          </div>
          """,
          unsafe_allow_html=True,
      )

      with engine.connect() as conn_citas:
        cita_activa = conn_citas.exec_driver_sql(
            f"SELECT id, fecha, hora, notas FROM citas WHERE rfc_cliente = {PH} AND estado = 'Pendiente' ORDER BY id DESC",
            (rfc_actual,),
        ).fetchone()

      col_f1, col_f2 = st.columns(2, gap="large")

      with col_f1:
        st.markdown("### 👤 Datos Principales")
        st.text_input("RFC", value=str(row[0] or ""), key=f"frfc_{rfc_actual}")
        st.text_input("Nombre(s)", value=str(row[1] or ""), key=f"fn_{rfc_actual}")
        st.text_input("Apellidos", value=str(row[2] or ""), key=f"fa_{rfc_actual}")
        st.text_input("Dependencia", value=str(row[6] or ""), key=f"fs_{rfc_actual}")
        st.text_input("Póliza", value=str(row[7] or ""), key=f"fp_{rfc_actual}")

        st.markdown("---")
        st.markdown("### 📞 Control de Números Telefónicos y Estatus")
        
        if rol in ["Base de Datos", "Asesor"]:
          st.text_input("TEL 1", value="🔒 ***-ocultos***", disabled=True, key=f"ftel1_dis_{rfc_actual}")
          st.text_input("TEL 2", value="🔒 ***-ocultos***", disabled=True, key=f"ftel2_dis_{rfc_actual}")
          st.text_input("TEL 3", value="🔒 ***-ocultos***", disabled=True, key=f"ftel3_dis_{rfc_actual}")
          
          tel_opc_existente = str(row[19] or "").strip()
          if tel_opc_existente:
            st.text_input(
                "📱 TEL OPCIONAL / ACTUALIZADO",
                value="🔒 ***-ocultos***",
                disabled=True,
                key=f"ftel_opcional_dis_{rfc_actual}",
            )
          else:
            st.text_input(
                "📱 TEL OPCIONAL / ACTUALIZADO (Asesor)",
                value="",
                key=f"ftel_opcional_{rfc_actual}",
                placeholder="Ingresa número telefónico si lo obtuviste en cita",
            )
        else:
          opciones_estados = ["Sin marcar", "Válido / Contesta", "Número Erróneo / Malo", "No Contesta / Buzón"]
          for i, (t_col, est_col) in enumerate([(3, 16), (4, 17), (5, 18)], start=1):
            t_val = str(row[t_col] or "")
            est_val = row[est_col] if row[est_col] else "Sin marcar"
            idx = opciones_estados.index(est_val) if est_val in opciones_estados else 0
            c_t, c_e = st.columns([1.2, 1.8])
            with c_t:
              st.text_input(f"TEL {i}", value=t_val, key=f"ftel{i}_{rfc_actual}")
            with c_e:
              st.selectbox(f"Estatus Tel {i}", opciones_estados, index=idx, key=f"est_t{i}_{rfc_actual}")

      with col_f2:
        st.markdown("### 📅 Cita Generada Activa")
        if cita_activa:
          id_cita, f_cita, h_cita, n_cita = cita_activa
          st.success(f"📌 **Cita Agendada:** {f_cita} a las {h_cita} | **Notas:** {n_cita}")
          
          est_asist_sel = st.selectbox(
              "¿Asistió a la cita?:",
              ["-- Confirmar Asistencia --", "✅ Sí Asistió", "❌ No Asistió"],
              key=f"sel_asistencia_{id_cita}"
          )
          if est_asist_sel != "-- Confirmar Asistencia --":
            nuevo_est_cita = "Asistida" if est_asist_sel == "✅ Sí Asistió" else "No Asistió"
            with engine.begin() as conn_sql_asis:
              conn_sql_asis.exec_driver_sql(
                  f"UPDATE citas SET estado = {PH} WHERE id = {PH}",
                  (nuevo_est_cita, id_cita)
              )
            st.success(f"Cita marcada como '{nuevo_est_cita}'. ¡Registro actualizado!")
            st.rerun()
        else:
          st.caption("No hay citas generadas recientemente para este prospecto.")

        st.markdown("---")
        st.markdown("### 📋 Fechas y Seguimiento")
        st.date_input("Dividendos", value=parsear_a_date(row[8]), key=f"fdiv_{rfc_actual}")
        st.date_input("Ult Fecha Asignación", value=parsear_a_date(row[9]), key=f"fulfasig_{rfc_actual}")
        st.text_input("Edad (Calculada/Registrada)", value=str(row[10] or calcular_edad_desde_rfc(row[0])), disabled=True, key=f"fedad_{rfc_actual}")
        st.date_input("Fecha Ult Mov", value=parsear_a_date(row[11]), key=f"ffum_{rfc_actual}")

        if rol == "Asesor":
          st.markdown("---")
          st.markdown("### 🎯 Acción / Resultado de Cita")
          accion_asesor = st.selectbox(
              "Selecciona el resultado *:",
              [
                  "-- Seleccionar Acción --",
                  "Cierre / Actualización",
                  "Solo Servicio",
                  "No Quiso Nada",
                  "Lo Va a Pensar",
                  "Regresa Después",
              ],
              key=f"accion_asesor_{rfc_actual}",
          )

          if accion_asesor == "Cierre / Actualización":
            st.text_input("💰 Monto de la Actualización (OBLIGATORIO) *:", key=f"monto_act_{rfc_actual}", placeholder="Ej. 15000")
            hizo_servicio_cierre = st.checkbox("¿También se le hizo servicio?", key=f"chk_servicio_{rfc_actual}")
            if hizo_servicio_cierre:
              tipo_serv = st.selectbox(
                  "Selecciona el tipo de servicio:",
                  ["Dividendos", "Cambio RFC", "Cambio Beneficiarios", "Otros"],
                  key=f"tipo_serv_{rfc_actual}"
              )
              if tipo_serv == "Otros":
                st.text_input("Especifica el servicio realizado:", key=f"det_otro_serv_{rfc_actual}")

          elif accion_asesor == "Solo Servicio":
            tipo_serv_solo = st.selectbox(
                "Selecciona el tipo de servicio:",
                ["Dividendos", "Cambio RFC", "Cambio Beneficiarios", "Otros"],
                key=f"tipo_serv_solo_{rfc_actual}"
            )
            if tipo_serv_solo == "Otros":
              st.text_input("Especifica el servicio realizado:", key=f"det_otro_serv_solo_{rfc_actual}")

      st.markdown("---")
      st.markdown("### 📝 Observaciones Generales")
      
      col_obs1, col_obs2 = st.columns(2)
      with col_obs1:
        st.text_area(
            "Observaciones Telefonista (Solo Lectura)",
            value=str(row[12] or ""),
            disabled=True,
            key=f"fobs_tel_{rfc_actual}",
        )
      with col_obs2:
        st.text_area(
            "Observaciones Asesor (Solo Lectura)" if rol != "Asesor" else "Observaciones Asesor",
            value=str(row[13] or ""),
            disabled=(rol != "Asesor" and rol != "Administrador"),
            key=f"fobs_asesor_{rfc_actual}",
        )

      if rol in ["Telefonista", "Administrador"]:
        st.markdown("---")
        st.markdown("### 📞 Registro de Llamada / Tareas")
        
        opc_llamada = st.selectbox(
            "Selecciona opción de llamada:",
            ["Cita", "No Contesta / Buzón", "Número Erróneo", "No Interesado", "Llamar Después"],
            key=f"opc_llamada_{rfc_actual}"
        )
        
        with st.container():
          det_llamada = st.text_area("Detalle / Observaciones de la llamada o recado:", key=f"det_llamada_{rfc_actual}")
          
          if opc_llamada == "Cita":
            c_f_cita, c_h_cita = st.columns(2)
            with c_f_cita:
              f_cita_sel = st.date_input("Fecha de Cita", value=obtener_ahora_mexico().date(), key=f"fcita_{rfc_actual}")
            with c_h_cita:
              horas_disponibles = [f"{h:02d}:00" for h in range(9, 17)]
              h_cita_sel = st.selectbox("Hora de Cita (9:00 AM a 4:00 PM)", horas_disponibles, key=f"hcita_{rfc_actual}")
          
          if st.button("💾 Registrar Acción", key=f"btn_reg_accion_{rfc_actual}"):
            f_hoy_f = obtener_ahora_mexico().strftime("%Y-%m-%d %H:%M:%S")
            f_hoy_fecha_sola = obtener_ahora_mexico().strftime("%Y-%m-%d")
            obs_prev = str(row[12] or "")
            
            det_final_historial = det_llamada.strip() if det_llamada.strip() else "Sin observaciones adicionales"
            nueva_obs = f"({f_hoy_f} - {usuario}) [{opc_llamada}] {det_final_historial}"
            obs_tel_actualizada = f"{obs_prev}\n{nueva_obs}".strip() if obs_prev else nueva_obs

            estatus_nuevo = "Cita Agendada" if opc_llamada == "Cita" else row[15]

            est_t1_val = st.session_state.get(f"est_t1_{rfc_actual}", row[16])
            est_t2_val = st.session_state.get(f"est_t2_{rfc_actual}", row[17])
            est_t3_val = st.session_state.get(f"est_t3_{rfc_actual}", row[18])

            if opc_llamada == "No Contesta / Buzón" and est_t1_val == "Sin marcar":
              est_t1_val = "No Contesta / Buzón"

            with engine.begin() as conn_sql_tele:
              conn_sql_tele.exec_driver_sql(
                  f"""
                  UPDATE clientes 
                  SET observaciones_tel = {PH}, 
                      estatus = {PH}, 
                      estado_tel1 = {PH}, 
                      estado_tel2 = {PH}, 
                      estado_tel3 = {PH},
                      fecha_ult_mov = {PH} 
                  WHERE rfc = {PH}
                  """,
                  (obs_tel_actualizada, estatus_nuevo, est_t1_val, est_t2_val, est_t3_val, f_hoy_fecha_sola, rfc_actual),
              )
              
              conn_sql_tele.exec_driver_sql(
                  f"INSERT INTO historial_llamadas (rfc_cliente, usuario, accion, detalle, fecha_registro) VALUES ({PH}, {PH}, {PH}, {PH}, {PH})",
                  (rfc_actual, usuario, opc_llamada, det_final_historial, f_hoy_f),
              )

              if opc_llamada == "Cita":
                cliente_nom = f"{row[1]} {row[2]}"
                conn_sql_tele.exec_driver_sql(
                    f"""
                    INSERT INTO citas (rfc_cliente, cliente, telefono, agente, asesor, fecha, hora, estado, notas)
                    VALUES ({PH}, {PH}, {PH}, {PH}, 'Sin Asignar', {PH}, {PH}, 'Pendiente', {PH})
                    """,
                    (rfc_actual, cliente_nom, row[3] or "Sin Tel", usuario, str(f_cita_sel), str(h_cita_sel), det_final_historial),
                )

            st.success("✅ Acción, estatus de teléfonos y llamada registrados con éxito.")
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
        st.info("No hay registros previos en el historial.")
      else:
        st.markdown(
            df_hist.to_html(
                classes="custom-table", index=False, escape=False
            ),
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
                    "",
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
                                rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                                poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                                observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                            )
                            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin Asignar', 'Disponible', 'Sin marcar', 'Sin marcar', 'Sin marcar')
                        """,
                          reg,
                      )
                    else:
                      conn_sql.exec_driver_sql(
                          f"""
                            INSERT INTO clientes (
                                rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, 
                                poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                                observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                            )
                            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin Asignar', 'Disponible', 'Sin marcar', 'Sin marcar', 'Sin marcar')
                            ON CONFLICT (rfc) DO UPDATE SET
                                nombre = EXCLUDED.nombre,
                                apellido = EXCLUDED.apellido
                        """,
                          reg,
                      )
                  except Exception:
                    pass
              st.success(
                  f"✅ ¡Se cargaron {len(registros)} prospectos exitosamente!"
              )
          except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

      elif opcion == "2. Ver Banco de Prospectos":
        st.header("📊 Banco General de Prospectos")
        df_banco = pd.read_sql(
            "SELECT rfc, nombre, apellido, tel1, tel2, tel3, tel_opcional, sector, poliza,"
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
        col_busq, col_crear = st.columns([3, 1])
        with col_busq:
          busqueda = st.text_input(
              "🔎 Buscar por RFC, Nombre, Apellido o Teléfono:"
          )
        with col_crear:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          if st.button("➕ Crear Nuevo", use_container_width=True):
            modal_crear_prospecto(usuario, rol)

        trig = st.session_state["reset_filtros_trigger"]

        with st.expander("Filtros Avanzados", expanded=False):
          col_fa1, col_fa2, col_fa3 = st.columns(3)

          lista_meses = [
              ("01", "01 - Enero"),
              ("02", "02 - Febrero"),
              ("03", "03 - Marzo"),
              ("04", "04 - Abril"),
              ("05", "05 - Mayo"),
              ("06", "06 - Junio"),
              ("07", "07 - Julio"),
              ("08", "08 - Agosto"),
              ("09", "09 - Septiembre"),
              ("10", "10 - Octubre"),
              ("11", "11 - Noviembre"),
              ("12", "12 - Diciembre"),
          ]
          lista_anios = ["2026", "2025", "2024", "2023"]

          with col_fa1:
            st.markdown("##### 👤 Usuario Asignado")
            with engine.connect() as conn_u:
              res_usr_db = conn_u.exec_driver_sql("SELECT DISTINCT telefonista_asignada FROM clientes WHERE telefonista_asignada IS NOT NULL AND telefonista_asignada != ''").fetchall()
            usuarios_bd = sorted(list(set([r[0] for r in res_usr_db if r[0]])))
            opciones_agentes_admin = ["Todos", "Sin Asignar"] + usuarios_bd
            f_usuario_admin = st.selectbox("Filtrar por Usuario Asignado:", opciones_agentes_admin, key=f"f_usuario_admin_sel_{trig}")

            st.markdown("##### 📌 Estatus General")
            f_est_g = st.selectbox("Estatus Específico:", ["Todos", "Disponible", "Asignado", "En Seguimiento", "Cita Agendada", "No Interesado"], key=f"f_estatus_gestion_{trig}")

          with col_fa2:
            st.markdown("##### 📅 Fecha de Asignación")
            filtrar_fa = st.checkbox("Activar Filtro Fecha Asignación", key=f"f_asig_hab_{trig}")
            modo_fa = st.selectbox("Modo de Vista:", ["Fecha Específica", "Rango de Fechas", "Por Mes / Año", "Por Año"], key=f"modo_fa_{trig}")

            if modo_fa == "Fecha Específica":
              fa_especifica = st.date_input("Fecha:", value=obtener_ahora_mexico().date(), key=f"fa_esp_{trig}")
            elif modo_fa == "Rango de Fechas":
              fa_rango = st.date_input("Rango (Inicio - Fin):", value=(obtener_ahora_mexico().date() - timedelta(days=7), obtener_ahora_mexico().date()), key=f"fa_ran_{trig}")
            elif modo_fa == "Por Mes / Año":
              c_m, c_a = st.columns(2)
              with c_m:
                fa_mes_num = st.selectbox("Mes:", [m[1] for m in lista_meses], key=f"fa_mes_{trig}")
              with c_a:
                fa_mes_anio = st.selectbox("Año:", lista_anios, key=f"fa_mes_anio_{trig}")
            else:
              fa_anio = st.selectbox("Selecciona Año:", lista_anios, key=f"fa_anio_{trig}")

            st.markdown("##### 🏢 Mercado / Dependencia")
            with engine.connect() as conn_s:
              res_sec_g = conn_s.exec_driver_sql("SELECT DISTINCT sector FROM clientes WHERE sector IS NOT NULL AND sector != ''").fetchall()
            sectores_g = ["Todos"] + [r[0] for r in res_sec_g if r[0]]
            f_sec_g = st.selectbox("Seleccionar Dependencia:", sectores_g, key=f"f_sector_gestion_{trig}")

          with col_fa3:
            st.markdown("##### 🔄 Fecha Último Movimiento")
            filtrar_fm = st.checkbox("Activar Filtro Último Movimiento", key=f"f_mov_hab_{trig}")
            modo_fm = st.selectbox("Modo de Vista:", ["Fecha Específica", "Rango de Fechas", "Por Mes / Año", "Por Año"], key=f"modo_fm_{trig}")

            if modo_fm == "Fecha Específica":
              fm_especifica = st.date_input("Fecha:", value=obtener_ahora_mexico().date(), key=f"fm_esp_{trig}")
            elif modo_fm == "Rango de Fechas":
              fm_rango = st.date_input("Rango (Inicio - Fin):", value=(obtener_ahora_mexico().date() - timedelta(days=7), obtener_ahora_mexico().date()), key=f"fm_ran_{trig}")
            elif modo_fm == "Por Mes / Año":
              cm_m, cm_a = st.columns(2)
              with cm_m:
                fm_mes_num = st.selectbox("Mes:", [m[1] for m in lista_meses], key=f"fm_mes_{trig}")
              with cm_a:
                fm_mes_anio = st.selectbox("Año:", lista_anios, key=f"fm_mes_anio_{trig}")
            else:
              fm_anio = st.selectbox("Selecciona Año:", lista_anios, key=f"fm_anio_{trig}")

            st.markdown("##### 📞 Estatus de Teléfono")
            f_tel_est_g = st.selectbox("Estado de Llamada:", ["Todos", "Sin marcar", "Válido / Contesta", "Número Erróneo / Malo", "No Contesta / Buzón"], key=f"f_tel_estado_gestion_{trig}")

          st.markdown("---")
          
          col_b_esp, col_b_res = st.columns([3, 1])
          with col_b_res:
            if st.button("🔄 Borrar", key="btn_reset_admin_filtros", use_container_width=True):
              st.session_state["reset_filtros_trigger"] += 1
              st.rerun()

        condiciones = []
        params_query = []
        
        if busqueda:
          if ES_SQLITE:
            condiciones.append(
                "(rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR tel1 LIKE ?)"
            )
            patron = f"%{busqueda}%"
            params_query.extend([patron, patron, patron, patron])
          else:
            condiciones.append(
                "(rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR tel1 ILIKE %s)"
            )
            patron = f"%{busqueda}%"
            params_query.extend([patron, patron, patron, patron])

        val_usr = st.session_state.get(f"f_usuario_admin_sel_{trig}", "Todos")
        if val_usr != "Todos":
          condiciones.append("telefonista_asignada = ?" if ES_SQLITE else "telefonista_asignada = %s")
          params_query.append(val_usr)

        if st.session_state.get(f"f_asig_hab_{trig}", False):
          m_fa = st.session_state.get(f"modo_fa_{trig}", "Fecha Específica")
          if m_fa == "Fecha Específica":
            condiciones.append("ult_fecha_asignacion = ?" if ES_SQLITE else "ult_fecha_asignacion = %s")
            params_query.append(str(st.session_state.get(f"fa_esp_{trig}", obtener_ahora_mexico().date())))
          elif m_fa == "Rango de Fechas":
            rango_val = st.session_state.get(f"fa_ran_{trig}")
            if isinstance(rango_val, tuple) and len(rango_val) == 2:
              f_ini, f_fin = rango_val
              condiciones.append("ult_fecha_asignacion >= ? AND ult_fecha_asignacion <= ?" if ES_SQLITE else "ult_fecha_asignacion >= %s AND ult_fecha_asignacion <= %s")
              params_query.extend([str(f_ini), str(f_fin)])
          elif m_fa == "Por Mes / Año":
            m_sel = st.session_state.get(f"fa_mes_{trig}", "01 - Enero")[:2]
            a_sel = st.session_state.get(f"fa_mes_anio_{trig}", "2026")
            patron_mes_anio = f"{a_sel}-{m_sel}-%"
            condiciones.append("ult_fecha_asignacion LIKE ?" if ES_SQLITE else "ult_fecha_asignacion LIKE %s")
            params_query.append(patron_mes_anio)
          elif m_fa == "Por Año":
            anio_sel = st.session_state.get(f"fa_anio_{trig}", "2026")
            patron_anio = f"{anio_sel}-%"
            condiciones.append("ult_fecha_asignacion LIKE ?" if ES_SQLITE else "ult_fecha_asignacion LIKE %s")
            params_query.append(patron_anio)

        if st.session_state.get(f"f_mov_hab_{trig}", False):
          m_fm = st.session_state.get(f"modo_fm_{trig}", "Fecha Específica")
          if m_fm == "Fecha Específica":
            condiciones.append("fecha_ult_mov = ?" if ES_SQLITE else "fecha_ult_mov = %s")
            params_query.append(str(st.session_state.get(f"fm_esp_{trig}", obtener_ahora_mexico().date())))
          elif m_fm == "Rango de Fechas":
            rango_val_m = st.session_state.get(f"fm_ran_{trig}")
            if isinstance(rango_val_m, tuple) and len(rango_val_m) == 2:
              f_ini_m, f_fin_m = rango_val_m
              condiciones.append("fecha_ult_mov >= ? AND fecha_ult_mov <= ?" if ES_SQLITE else "fecha_ult_mov >= %s AND fecha_ult_mov <= %s")
              params_query.extend([str(f_ini_m), str(f_fin_m)])
          elif m_fm == "Por Mes / Año":
            m_sel_m = st.session_state.get(f"fm_mes_{trig}", "01 - Enero")[:2]
            a_sel_m = st.session_state.get(f"fm_mes_anio_{trig}", "2026")
            patron_mes_anio_m = f"{a_sel_m}-{m_sel_m}-%"
            condiciones.append("fecha_ult_mov LIKE ?" if ES_SQLITE else "fecha_ult_mov LIKE %s")
            params_query.append(patron_mes_anio_m)
          elif m_fm == "Por Año":
            anio_sel_m = st.session_state.get(f"fm_anio_{trig}", "2026")
            patron_anio_m = f"{anio_sel_m}-%"
            condiciones.append("fecha_ult_mov LIKE ?" if ES_SQLITE else "fecha_ult_mov LIKE %s")
            params_query.append(patron_anio_m)

        val_sec = st.session_state.get(f"f_sector_gestion_{trig}", "Todos")
        if val_sec != "Todos":
          condiciones.append("sector = ?" if ES_SQLITE else "sector = %s")
          params_query.append(val_sec)

        val_est = st.session_state.get(f"f_estatus_gestion_{trig}", "Todos")
        if val_est != "Todos":
          condiciones.append("estatus = ?" if ES_SQLITE else "estatus = %s")
          params_query.append(val_est)

        val_tel_est = st.session_state.get(f"f_tel_estado_gestion_{trig}", "Todos")
        if val_tel_est != "Todos":
          condiciones.append("(estado_tel1 = ? OR estado_tel2 = ? OR estado_tel3 = ?)" if ES_SQLITE else "(estado_tel1 = %s OR estado_tel2 = %s OR estado_tel3 = %s)")
          params_query.extend([val_tel_est]*3)

        query = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, tel_opcional, sector, poliza, dividendos, ult_fecha_asignacion, fecha_ult_mov, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes"
        if condiciones:
          query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY fecha_creacion DESC LIMIT 1000"

        df_resultados = pd.read_sql(
            query, con=engine, params=tuple(params_query) if params_query else None
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
          c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
          with c1:
            tele_destino = st.selectbox(
                "Asignar a:",
                obtener_todos_los_usuarios_asignables(),
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
            nueva_fecha_asig = st.date_input("Fecha Asignación Masiva:", value=obtener_ahora_mexico().date())
          with c4:
            st.metric("Seleccionados", cant_sel)

          if st.button("🚀 Aplicar Cambios Masivos"):
            if cant_sel == 0:
              st.warning("⚠️ Marca la casilla 'Seleccionar' en la tabla.")
            else:
              f_asig_str = nueva_fecha_asig.strftime("%Y-%m-%d")
              with engine.begin() as conn_sql:
                for rfc_item in rfcs_sel_global:
                  conn_sql.exec_driver_sql(
                      f"UPDATE clientes SET telefonista_asignada = {PH},"
                      f" estatus = {PH}, ult_fecha_asignacion = {PH} WHERE rfc = {PH}",
                      (tele_destino, estatus_masivo, f_asig_str, rfc_item),
                  )
              st.session_state["sel_rfcs_gestion_admin"] = []
              st.success(
                  f"✅ ¡Se actualizaron {cant_sel} prospectos correctamente con fecha {f_asig_str}!"
              )
              st.rerun()

      elif opcion == "4. Reporte de Citas y Actividad":
        st.header("📊 Reporte General de Citas y Actividad")
        
        c_f1, c_f2 = st.columns([2, 2])
        with c_f1:
          f_rep = st.date_input("Fecha Base:", value=obtener_ahora_mexico().date())
        with c_f2:
          tipo_periodo_rep = st.selectbox("Visualizar Período:", ["📅 Diario", "🗓️ Semanal", "📆 Mensual"])

        f_ini_rep, f_fin_rep = calcular_rango_fechas(f_rep, tipo_periodo_rep)
        st.caption(f"🗓️ Consultando registros desde **{f_ini_rep}** hasta **{f_fin_rep}**")

        tab_rep1, tab_rep2, tab_rep3, tab_rep4 = st.tabs([
            "📈 Citas y Eficiencia",
            "📞 Llamadas Telefonistas",
            "⏱️ Auditoría de Tiempos (Llamadas)",
            "🍽️ / 🚽 Comida y Baño",
        ])

        with tab_rep1:
          df_rep = pd.read_sql(
              f"SELECT * FROM citas WHERE fecha >= {PH} AND fecha <= {PH}",
              con=engine,
              params=(f_ini_rep, f_fin_rep),
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
            st.info("No hay citas registradas para este período.")

        with tab_rep2:
          df_tot = pd.read_sql(
              f"""
                SELECT usuario as "Telefonista", COUNT(*) as "Total General" 
                FROM historial_llamadas 
                WHERE date(fecha_registro) >= {PH} AND date(fecha_registro) <= {PH}
                GROUP BY usuario
            """,
              con=engine,
              params=(f_ini_rep, f_fin_rep),
          )
          if df_tot.empty:
            st.info("No hay registros de llamadas para el período seleccionado.")
          else:
            df_tot.columns = [str(c) for c in df_tot.columns]
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

          if usr_auditar == "Todos":
            query_aud = f"""
                SELECT h.fecha_registro as "Fecha/Hora", h.usuario as "Usuario", h.rfc_cliente as "RFC", c.nombre || ' ' || c.apellido as "Prospecto", h.accion as "Acción", h.detalle as "Detalle"
                FROM historial_llamadas h LEFT JOIN clientes c ON h.rfc_cliente = c.rfc
                WHERE date(h.fecha_registro) >= {PH} AND date(h.fecha_registro) <= {PH} 
                ORDER BY h.fecha_registro ASC
            """
            df_aud = pd.read_sql(query_aud, con=engine, params=(f_ini_rep, f_fin_rep))
          else:
            query_aud = f"""
                SELECT h.fecha_registro as "Fecha/Hora", h.usuario as "Usuario", h.rfc_cliente as "RFC", c.nombre || ' ' || c.apellido as "Prospecto", h.accion as "Acción", h.detalle as "Detalle"
                FROM historial_llamadas h LEFT JOIN clientes c ON h.rfc_cliente = c.rfc
                WHERE h.usuario = {PH} AND date(h.fecha_registro) >= {PH} AND date(h.fecha_registro) <= {PH} 
                ORDER BY h.fecha_registro ASC
            """
            df_aud = pd.read_sql(query_aud, con=engine, params=(usr_auditar, f_ini_rep, f_fin_rep))

          if df_aud.empty:
            st.info("No hay registros de llamadas para el usuario y período seleccionados.")
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
                SELECT fecha as "Fecha", usuario as "Telefonista", tipo_registro as "Tipo", hora_inicio as "Inicio", hora_fin as "Fin", duracion_minutos as "Minutos", estado as "Estado"
                FROM asistencia_telefonistas 
                WHERE fecha >= {PH} AND fecha <= {PH} 
                ORDER BY id DESC
            """,
              con=engine,
              params=(f_ini_rep, f_fin_rep),
          )
          if df_asistencia_rep.empty:
            st.info("No hay registros de comida/baño en el período seleccionado.")
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
                  "Rol",
                  ["Administrador", "Telefonista", "Asesor", "Base de Datos"],
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
                roles_disponibles = [
                    "Administrador",
                    "Telefonista",
                    "Asesor",
                    "Base de Datos",
                ]
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

      elif opcion == "6. Dashboard y Estadísticas de Asesores":
        st.header("📈 Dashboard y Métricas de Asesores Comercial")
        
        c_a1, c_a2 = st.columns([2, 2])
        with c_a1:
          f_base_a = st.date_input("Fecha Base:", value=obtener_ahora_mexico().date(), key="f_base_dashboard_asesor")
        with c_a2:
          tipo_per_a = st.selectbox("Período de Análisis:", ["📅 Diario", "🗓️ Semanal", "📆 Mensual"], key="tipo_per_dashboard_asesor")

        f_ini_a, f_fin_a = calcular_rango_fechas(f_base_a, tipo_per_a)
        st.info(f"📊 Analizando rendimiento comercial desde **{f_ini_a}** hasta **{f_fin_a}**")

        df_hist_asesores = pd.read_sql(
            f"""
            SELECT h.usuario as "Asesor", h.accion as "Accion", h.detalle as "Detalle", h.fecha_registro as "Fecha"
            FROM historial_llamadas h
            JOIN usuarios u ON h.usuario = u.usuario
            WHERE u.rol = 'Asesor' AND date(h.fecha_registro) >= {PH} AND date(h.fecha_registro) <= {PH}
            """,
            con=engine,
            params=(f_ini_a, f_fin_a),
        )

        df_citas_asesores = pd.read_sql(
            f"""
            SELECT asesor as "Asesor", estado as "Estado"
            FROM citas
            WHERE fecha >= {PH} AND fecha <= {PH} AND asesor != 'Sin Asignar'
            """,
            con=engine,
            params=(f_ini_a, f_fin_a),
        )

        lista_asesores_db = obtener_usuarios_por_rol("Asesor")
        
        datos_resumen = []
        for asr in lista_asesores_db:
          sub_citas = df_citas_asesores[df_citas_asesores["Asesor"] == asr] if not df_citas_asesores.empty else pd.DataFrame()
          tot_citas = len(sub_citas)
          asistidas = len(sub_citas[sub_citas["Estado"].str.contains("Asistida", case=False, na=False)]) if not sub_citas.empty else 0

          sub_hist = df_hist_asesores[df_hist_asesores["Asesor"] == asr] if not df_hist_asesores.empty else pd.DataFrame()
          cierres = len(sub_hist[sub_hist["Accion"] == "Cierre / Actualización"]) if not sub_hist.empty else 0
          servicios = len(sub_hist[sub_hist["Accion"] == "Solo Servicio"]) if not sub_hist.empty else 0
          
          monto_total = 0.0
          if not sub_hist.empty:
            for det in sub_hist["Detalle"].fillna(""):
              if "Monto Act: $" in det:
                try:
                  monto_str = det.split("Monto Act: $")[1].split(" ")[0].replace(",", "")
                  monto_total += float(monto_str)
                except Exception:
                  pass

          efectividad = f"{(cierres / asistidas * 100):.1f}%" if asistidas > 0 else "0.0%"

          datos_resumen.append({
              "Asesor": asr,
              "Citas Agendadas": tot_citas,
              "Citas Asistidas": asistidas,
              "Cierres / Actualizaciones": cierres,
              "Solo Servicio": servicios,
              "Monto Actualizaciones": f"${monto_total:,.2f}",
              "% Efectividad Cierre": efectividad
          })

        df_resumen_asesores = pd.DataFrame(datos_resumen)

        m_tot_citas = df_resumen_asesores["Citas Agendadas"].sum() if not df_resumen_asesores.empty else 0
        m_tot_asist = df_resumen_asesores["Citas Asistidas"].sum() if not df_resumen_asesores.empty else 0
        m_tot_cierres = df_resumen_asesores["Cierres / Actualizaciones"].sum() if not df_resumen_asesores.empty else 0
        m_tot_serv = df_resumen_asesores["Solo Servicio"].sum() if not df_resumen_asesores.empty else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Citas Agendadas", m_tot_citas)
        kpi2.metric("Citas Asistidas", m_tot_asist)
        kpi3.metric("💼 Cierres Totales", m_tot_cierres)
        kpi4.metric("🛠️ Servicios Realizados", m_tot_serv)

        st.markdown("---")
        st.subheader("🏆 Tabla Comparativa por Asesor")
        
        if df_resumen_asesores.empty:
          st.info("No hay asesores o actividad registrada en el período.")
        else:
          st.markdown(
              df_resumen_asesores.to_html(classes="custom-table", index=False, escape=False),
              unsafe_allow_html=True,
          )

        st.markdown("---")
        st.subheader("📜 Detalle de Transacciones Comercial")
        if df_hist_asesores.empty:
          st.caption("No hay actividades comerciales registradas en este rango de fechas.")
        else:
          st.dataframe(df_hist_asesores, use_container_width=True, hide_index=True)

    elif rol == "Base de Datos":
      if opcion == "Mis Prospectos Asignados (Depuración BD)":
        st.header(f"🗃️ Prospectos Asignados para Depuración ({usuario})")
        busqueda_bd = st.text_input("🔎 Buscar por RFC, Nombre o Apellido:")
        q_bd = f"""
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, estatus 
            FROM clientes WHERE telefonista_asignada = {PH}
        """
        params_bd = (usuario,)
        if busqueda_bd:
          if ES_SQLITE:
            q_bd += " AND (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ?)"
          else:
            q_bd += " AND (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s)"
          pbd = f"%{busqueda_bd}%"
          params_bd = (usuario, pbd, pbd, pbd)

        df_bd = pd.read_sql(q_bd, con=engine, params=params_bd)
        if df_bd.empty:
          st.info(
              "No tienes prospectos asignados para depuración en este momento."
          )
        else:
          renderizar_bloque_con_tabla(
              df_bd, key_suffix="gestion_bd", ocultar_tels=True
          )

    elif rol == "Telefonista":
      if opcion == "Mis Prospectos y Gestión":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")
        col_busq_tele, col_pop_tele = st.columns([2.5, 1.5])
        with col_busq_tele:
          busqueda_tele = st.text_input("🔎 Buscar por Nombre, RFC o Póliza:")
        with col_pop_tele:
          st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
          with st.popover("⚙️ Filtros Avanzados"):
            st.markdown("##### 📞 Estatus de Llamada")
            filtro_estatus_tel_tele = st.selectbox(
                "Filtrar por estatus de llamada:",
                ["Todos los estatus", "🔁 No Contesta / Buzón", "Sin marcar", "Válido / Contesta", "Número Erróneo / Malo"],
                key="filtro_estatus_tel_tele_sel"
            )
            st.markdown("---")
            st.markdown("##### 📅 Fecha Específica de Asignación")
            filtrar_fa_tele = st.checkbox("Filtrar por esta fecha", key="f_asig_hab_tele")
            fa_tele_esp = st.date_input("Fecha Asignación:", value=obtener_ahora_mexico().date(), key="fa_tele_esp")

        q_t = f"""
            SELECT DISTINCT c.rfc, c.nombre, c.apellido, c.tel1, c.tel2, c.tel3, c.sector, c.poliza, c.dividendos, c.ult_fecha_asignacion, c.edad, c.estatus, c.estado_tel1, c.estado_tel2, c.estado_tel3 
            FROM clientes c
        """
        if filtro_estatus_tel_tele == "🔁 No Contesta / Buzón":
          q_t += " LEFT JOIN historial_llamadas h ON c.rfc = h.rfc_cliente"

        q_t += f" WHERE c.telefonista_asignada = {PH}"
        params_t = [usuario]
        conds_t = []

        if filtro_estatus_tel_tele != "Todos los estatus":
          if filtro_estatus_tel_tele == "🔁 No Contesta / Buzón":
            # Filtro combinado: checa tanto los campos de estado en clientes como el historial de llamadas
            conds_t.append(
                """(
                    c.estado_tel1 = 'No Contesta / Buzón' 
                    OR c.estado_tel2 = 'No Contesta / Buzón' 
                    OR c.estado_tel3 = 'No Contesta / Buzón'
                    OR h.accion = 'No Contesta / Buzón'
                )"""
            )
          else:
            val_busq_est = filtro_estatus_tel_tele
            conds_t.append(
                "(c.estado_tel1 = ? OR c.estado_tel2 = ? OR c.estado_tel3 = ?)"
                if ES_SQLITE
                else "(c.estado_tel1 = %s OR c.estado_tel2 = %s OR c.estado_tel3 = %s)"
            )
            params_t.extend([val_busq_est] * 3)

        if filtrar_fa_tele:
          conds_t.append("c.ult_fecha_asignacion = ?" if ES_SQLITE else "c.ult_fecha_asignacion = %s")
          params_t.append(str(fa_tele_esp))

        if busqueda_tele:
          if ES_SQLITE:
            conds_t.append("(c.rfc LIKE ? OR c.nombre LIKE ? OR c.apellido LIKE ? OR c.poliza LIKE ?)")
          else:
            conds_t.append("(c.rfc ILIKE %s OR c.nombre ILIKE %s OR c.apellido ILIKE %s OR c.poliza ILIKE %s)")
          pt = f"%{busqueda_tele}%"
          params_t.extend([pt, pt, pt, pt])

        if conds_t:
          q_t += " AND " + " AND ".join(conds_t)

        df_p = pd.read_sql(q_t, con=engine, params=tuple(params_t))
        if df_p.empty:
          st.info("No se encontraron prospectos con los criterios seleccionados.")
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

    else:
      if opcion == "Prospectos":
        st.header(f"🌐 Banco General de Prospectos (Vista Asesor)")
        col_busq_ase, col_crear_ase = st.columns([3, 1])
        with col_busq_ase:
          busq_a = st.text_input("🔎 Buscar por RFC, Nombre, Apellido o Póliza:")
        with col_crear_ase:
          st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
          if st.button("➕ Crear Nuevo", use_container_width=True, key="btn_crear_prospecto_asesor"):
            modal_crear_prospecto(usuario, rol)

        q_a = """
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1, estado_tel2, estado_tel3 
            FROM clientes
        """
        params_a = []
        if busq_a:
          if ES_SQLITE:
            q_a += " WHERE (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR poliza LIKE ?)"
          else:
            q_a += " WHERE (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR poliza ILIKE %s)"
          pa = f"%{busq_a}%"
          params_a = [pa, pa, pa, pa]

        q_a += " ORDER BY fecha_creacion DESC LIMIT 1000"

        df_pa = pd.read_sql(q_a, con=engine, params=tuple(params_a) if params_a else None)
        if df_pa.empty:
          st.info("No se encontraron prospectos.")
        else:
          renderizar_bloque_con_tabla(
              df_pa, key_suffix="banco_general_asesor", ocultar_tels=True
          )

      elif opcion == "Bolsa de Citas del Día (Asesores)":
        st.header(f"💼 Bolsa de Citas del Día ({usuario})")
        f_hoy = obtener_ahora_mexico().strftime("%Y-%m-%d")
        
        df_b = pd.read_sql(
            f"""
            SELECT rfc_cliente as rfc, id, fecha as "Fecha", hora as "Hora", cliente as "Cliente", telefono as "Teléfono", estado as "Estado", notas as "Notas" 
            FROM citas 
            WHERE fecha = {PH} AND (asesor = {PH} OR asesor = 'Sin Asignar') 
            ORDER BY hora ASC
        """,
            con=engine,
            params=(f_hoy, usuario),
        )
        if df_b.empty:
          st.info("No hay citas en la bolsa para hoy.")
        else:
          renderizar_bloque_con_tabla(
              df_b, key_suffix="bolsa_citas_asesor", ocultar_tels=True
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
        st.header("📊 Reportes de Desempeño y Citas")
        f_rep_a = st.date_input(
            "Fecha Base:", value=obtener_ahora_mexico().date()
        ).strftime("%Y-%m-%d")
        
        df_ra = pd.read_sql(
            f"SELECT * FROM citas WHERE agente = {PH} AND fecha = {PH}",
            con=engine,
            params=(usuario, f_rep_a),
        )
        
        like_op = "LIKE" if ES_SQLITE else "LIKE"
        with engine.connect() as conn_v:
          res_vta = conn_v.exec_driver_sql(
              f"""
              SELECT COUNT(*) FROM historial_llamadas 
              WHERE usuario = {PH} AND accion = 'Cierre / Actualización' AND fecha_registro {like_op} {PH}
          """,
              (usuario, f"{f_rep_a}%"),
          ).fetchone()
        df_ventas_asesor = res_vta[0] if res_vta else 0

        tot_citas_asesor = len(df_ra)
        asis_asesor = (
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
        
        eficacia_cierre = f"{(df_ventas_asesor / asis_asesor * 100):.1f}%" if asistidas > 0 else "0.0%"

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Mis Citas del Día", tot_citas_asesor)
        m2.metric("Citas Asistidas", asis_asesor)
        m3.metric("💼 Cierres / Actualizaciones", df_ventas_asesor)
        m4.metric("🎯 Eficacia de Cierre", eficacia_cierre)

        st.markdown("---")
        if not df_ra.empty:
          st.markdown(
              df_ra.to_html(
                  classes="custom-table", index=False, escape=False
              ),
              unsafe_allow_html=True,
          )
        else:
          st.info("No hay citas registradas para esta fecha.")
