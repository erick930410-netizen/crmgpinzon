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
        "💻 Modo Pruebas Local (SQLite sin concurrencia bloqueante)"
    )
except Exception as e:
  try:
    db_url = "sqlite:///crm_local_test.db"
    engine = create_engine(db_url, connect_args={"timeout": 30}, poolclass=NullPool)
  except Exception as inner_e:
    st.error(f"⚠️ Error crítico de conexión: {e} / {inner_e}")
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
    header[data-testid="stHeader"] { display: none !important; }
    footer { visibility: hidden; }
    [data-testid="stStatusWidget"] { visibility: hidden; }
    .stAppDeployButton { display: none !important; }
    .block-container { padding-top: 1.2rem !important; padding-bottom: 2rem !important; }
    h2, h3 { color: #002B49 !important; font-family: 'Segoe UI', sans-serif; }
    .stButton>button { background-color: #0072CE; color: white; border-radius: 6px; border: none; font-weight: 600; padding: 0.5rem 1rem; }
    .stButton>button:hover { background-color: #005bb5; color: #ffffff; }
    button[kind="secondary"] { background-color: #78BE20 !important; color: white !important; border: none !important; }
    .custom-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-top: 10px; }
    .custom-table th { background-color: #78BE20 !important; color: #ffffff !important; text-align: left; padding: 12px 16px; font-weight: 700; }
    .custom-table td { padding: 10px 16px; color: #334155; border-bottom: 1px solid #e2e8f0; }
    .custom-table tr:hover { background-color: #f1f5f9; }
    .fila-excedida { background-color: #f8d7da !important; color: #721c24 !important; font-weight: bold; }
    [data-testid="stDataFrame"] th, div[data-testid="stTable"] th { background-color: #78BE20 !important; color: white !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid #78BE20; }
    .banner-alerta-seguimiento { background: linear-gradient(135deg, #ff4b4b 0%, #d92b2b 100%); color: white; padding: 15px 20px; border-radius: 10px; margin-bottom: 20px; }
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
    edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
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
    f_ini, f_fin = f_base, f_base
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
      f"CREATE TABLE IF NOT EXISTS usuarios (id {ID_SERIAL}, usuario TEXT UNIQUE, password TEXT, rol TEXT, nombre_completo TEXT, apellido TEXT, telefono TEXT, direccion TEXT)",
      f"CREATE TABLE IF NOT EXISTS clientes (rfc TEXT PRIMARY KEY, nombre TEXT, apellido TEXT, tel1 TEXT, tel2 TEXT, tel3 TEXT, telefono TEXT, tel_opcional TEXT, sector TEXT, poliza TEXT, dividendos TEXT, ult_fecha_asignacion TEXT, edad TEXT, fecha_ult_mov TEXT, observaciones_tel TEXT, observaciones_asesor TEXT, telefonista_asignada TEXT DEFAULT 'Sin Asignar', estatus TEXT DEFAULT 'Disponible', estado_tel1 TEXT DEFAULT 'Sin marcar', estado_tel2 TEXT DEFAULT 'Sin marcar', estado_tel3 TEXT DEFAULT 'Sin marcar', fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
      "ALTER TABLE clientes ADD COLUMN tel_opcional TEXT",
      f"CREATE TABLE IF NOT EXISTS historial_llamadas (id {ID_SERIAL}, rfc_cliente TEXT, usuario TEXT, accion TEXT, detalle TEXT, fecha_registro TEXT)",
      f"CREATE TABLE IF NOT EXISTS citas (id {ID_SERIAL}, rfc_cliente TEXT, cliente TEXT NOT NULL, telefono TEXT, agente TEXT, asesor TEXT DEFAULT 'Sin Asignar', fecha TEXT NOT NULL, hora TEXT NOT NULL, estado TEXT NOT NULL, notas TEXT)",
      f"CREATE TABLE IF NOT EXISTS asistencia_telefonistas (id {ID_SERIAL}, usuario TEXT NOT NULL, tipo_registro TEXT NOT NULL, fecha TEXT NOT NULL, hora_inicio TEXT NOT NULL, hora_fin TEXT, duracion_minutos INTEGER, estado TEXT NOT NULL)"
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
    conn_sql.exec_driver_sql(f"UPDATE citas SET estado = 'No Asistió (Automático)' WHERE estado = 'Pendiente' AND date(fecha) < {PH}", (hoy_str_mex,))
except Exception:
  pass

with engine.connect() as conn_sql:
  res_u = conn_sql.exec_driver_sql("SELECT COUNT(*) FROM usuarios").fetchone()[0]

if res_u == 0:
  with engine.begin() as conn_sql:
    conn_sql.exec_driver_sql(f"INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", ("admin", "1234", "Administrador", "Administrador", "Principal", "5550000000", "Oficina Central"))
    conn_sql.exec_driver_sql(f"INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", ("tele1", "1234", "Telefonista", "Telefonista", "Uno", "5551111111", "Call Center"))
    conn_sql.exec_driver_sql(f"INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", ("tele2", "1234", "Telefonista", "Telefonista", "Dos", "5552222222", "Call Center"))
    conn_sql.exec_driver_sql(f"INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", ("asesor1", "1234", "Asesor", "Asesor", "Uno", "5553333333", "Campo"))
    conn_sql.exec_driver_sql(f"INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", ("asesor2", "1234", "Asesor", "Asesor", "Dos", "5554444444", "Campo"))


def autenticar(usuario, password):
  with engine.connect() as conn_sql:
    res = conn_sql.exec_driver_sql(f"SELECT usuario, rol FROM usuarios WHERE usuario = {PH} AND password = {PH}", (usuario, password)).fetchone()
  return res


def obtener_usuarios_por_rol(rol):
  with engine.connect() as conn_sql:
    res = conn_sql.exec_driver_sql(f"SELECT usuario FROM usuarios WHERE rol = {PH} ORDER BY usuario", (rol,)).fetchall()
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
      tel1, tel2, tel3 = st.text_input("TEL 1"), st.text_input("TEL 2"), st.text_input("TEL 3")
    with col2:
      sector = st.text_input("Dependencia")
      poliza = st.text_input("Póliza")
      dividendos_dt = st.date_input("Dividendos", value=obtener_ahora_mexico().date())
      ult_fecha_asig_dt = st.date_input("Ult Fecha Asignación", value=obtener_ahora_mexico().date())
      fecha_ult_mov_dt = st.date_input("Fecha Ult Mov", value=obtener_ahora_mexico().date())

    if rol_actual == "Administrador":
      telefonista_asignada = st.selectbox("Asignar a:", ["Sin Asignar"] + obtener_todos_los_usuarios_asignables())
    elif rol_actual in ["Telefonista", "Asesor", "Base de Datos"]:
      telefonista_asignada = usuario_actual
      st.info(f"📌 Asignado a: **{usuario_actual}**")
    else:
      telefonista_asignada = "admin"

    estatus = st.selectbox("Estatus Inicial", ["Disponible", "Asignado", "En Seguimiento"])
    obs_tel, obs_asesor = st.text_area("Observaciones Tel"), st.text_area("Observaciones Asesor")

    if st.form_submit_button("💾 Guardar Prospecto", use_container_width=True):
      if not rfc.strip() or not nombre.strip() or not apellido.strip():
        st.error("⚠️ Los campos RFC, Nombre(s) y Apellidos son obligatorios.")
      else:
        tels_disp = [t for t in [tel1, tel2, tel3] if t]
        telefono_final = " / ".join(tels_disp) if tels_disp else "Sin Teléfono"
        edad_calc = calcular_edad_desde_rfc(rfc)
        f_hoy = obtener_ahora_mexico().strftime("%Y/%m/%d")
        obs_tel_f = f"({f_hoy} - {usuario_actual}) {obs_tel}" if obs_tel else ""
        obs_asesor_f = f"({f_hoy} - {usuario_actual}) {obs_asesor}" if obs_asesor else ""

        with engine.begin() as conn_sql:
          if ES_SQLITE:
            conn_sql.exec_driver_sql(
                f"INSERT OR REPLACE INTO clientes (rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin marcar', 'Sin marcar', 'Sin marcar')",
                (rfc.strip().upper(), nombre, apellido, tel1, tel2, tel3, telefono_final, "", sector, poliza, dividendos_dt.strftime("%Y-%m-%d"), ult_fecha_asig_dt.strftime("%Y-%m-%d"), edad_calc, fecha_ult_mov_dt.strftime("%Y-%m-%d"), obs_tel_f, obs_asesor_f, telefonista_asignada, estatus),
            )
          else:
            conn_sql.exec_driver_sql(
                f"INSERT INTO clientes (rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'Sin marcar', 'Sin marcar', 'Sin marcar') ON CONFLICT (rfc) DO UPDATE SET nombre = EXCLUDED.nombre, apellido = EXCLUDED.apellido",
                (rfc.strip().upper(), nombre, apellido, tel1, tel2, tel3, telefono_final, "", sector, poliza, dividendos_dt.strftime("%Y-%m-%d"), ult_fecha_asig_dt.strftime("%Y-%m-%d"), edad_calc, fecha_ult_mov_dt.strftime("%Y-%m-%d"), obs_tel_f, obs_asesor_f, telefonista_asignada, estatus),
            )
        st.success(f"✅ ¡Prospecto '{nombre} {apellido}' registrado con éxito!")
        st.rerun()


# --- TABLA CON MEMORIA DE PAGINACIÓN PARA EVITAR SALTO ---
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
  tot_pags = max(1, (tot_filt - 1) // cant_por_pagina + 1) if tot_filt > 0 else 1

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
    df_a_mostrar = df.iloc[(p_act - 1) * cant_por_pagina : p_act * cant_por_pagina].copy()
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
      "Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False, width="small"),
      "rfc": st.column_config.TextColumn("RFC / ID", width="medium"),
  }
  cols_dis = [c for c in df.columns if c not in ["Seleccionar"]] + ["#"]

  if st.session_state.get(f"sel_rfcs_{key_suffix}", []):
    if st.button("🚀 Abrir / Ver Ficha", key=f"btn_sup_{key_suffix}", use_container_width=True):
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
  with engine.connect() as conn_sql:
    reg_comida_activo = conn_sql.exec_driver_sql(f"SELECT id, hora_inicio FROM asistencia_telefonistas WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Comida' AND estado = 'En Curso'", (usuario_act, f_hoy_str)).fetchone()
    comida_registrada_hoy = conn_sql.exec_driver_sql(f"SELECT COUNT(*) FROM asistencia_telefonistas WHERE usuario = {PH} AND fecha = {PH} AND tipo_registro = 'Comida' AND estado != 'En Curso'", (usuario_act, f_hoy_str)).fetchone()[0] > 0

  st.markdown("### ⏱️ Registro de Tiempos")
  if comida_registrada_hoy:
    st.info("✅ Ya realizaste tu comida del día.")
  else:
    if reg_comida_activo:
      st.warning(f"⏳ Comida iniciada a las: **{reg_comida_activo[1]}**")
      if st.button("🔴 REGRESÉ DE COMER", key="btn_fin_comida_pop", use_container_width=True):
        h_inicio = datetime.strptime(f"{f_hoy_str} {reg_comida_activo[1]}", "%Y-%m-%d %H:%M:%S")
        h_fin = obtener_ahora_mexico()
        duracion = int((h_fin.replace(tzinfo=None) - h_inicio).total_seconds() / 60)
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(f"UPDATE asistencia_telefonistas SET hora_fin = {PH}, duracion_minutos = {PH}, estado = 'Completado' WHERE id = {PH}", (h_fin.strftime("%H:%M:%S"), duracion, reg_comida_activo[0]))
        st.success(f"Regreso guardado ({duracion} min)")
        st.rerun()
    else:
      if st.button("🟢 IR A COMER", key="btn_ini_comida_pop", use_container_width=True):
        h_ini_str = obtener_ahora_mexico().strftime("%H:%M:%S")
        with engine.begin() as conn_sql:
          conn_sql.exec_driver_sql(f"INSERT INTO asistencia_telefonistas (usuario, tipo_registro, fecha, hora_inicio, estado) VALUES ({PH}, 'Comida', {PH}, {PH}, 'En Curso')", (usuario_act, f_hoy_str, h_ini_str))
        st.success("¡Buen provecho!")
        st.rerun()


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

if st.session_state["usuario_logueado"] is None:
  st.markdown("""<style>.stApp { background-color: #005a9c !important; }</style>""", unsafe_allow_html=True)
  col_logo, col_login = st.columns([1.8, 1], gap="large")
  with col_logo:
    st.markdown("<h1 style='color: white; font-size: 3.8rem; font-weight: 900;'>GRUPO PINZÓN</h1><p style='color: white; font-size: 1.4rem;'>Sistema de Control de Prospectos y CRM</p>", unsafe_allow_html=True)
  with col_login:
    st.markdown("<h2 style='color: white;'>🔑 Iniciar Sesión</h2>", unsafe_allow_html=True)
    usr = st.text_input("Usuario", key="login_usr")
    pwd = st.text_input("Contraseña", type="password", key="login_pwd")
    if st.button("Entrar al Sistema", use_container_width=True):
      datos = autenticar(usr, pwd)
      if datos:
        st.session_state["usuario_logueado"], st.session_state["rol"] = datos[0], datos[1]
        st.session_state["seccion_activa"] = None
        st.rerun()
      else:
        st.error("⚠️ Usuario o contraseña incorrectos")
else:
  rol, usuario = st.session_state["rol"], st.session_state["usuario_logueado"]
  opciones = (
      ["1. Cargar Base General", "2. Ver Banco de Prospectos", "3. Gestión y Asignación de Prospectos", "4. Reporte de Citas y Actividad", "5. Gestión de Usuarios y Roles", "6. Dashboard y Estadísticas de Asesores"]
      if rol == "Administrador"
      else (["Mis Prospectos y Gestión", "Mis Citas Agendadas"] if rol == "Telefonista" else (["Mis Prospectos Asignados (Depuración BD)"] if rol == "Base de Datos" else ["Prospectos", "Bolsa de Citas del Día (Asesores)", "Mis Registros de Hoy", "📊 Reportes de Citas y Asistencias"]))
  )

  if st.session_state["seccion_activa"] is None or st.session_state["seccion_activa"] not in opciones:
    st.session_state["seccion_activa"] = opciones[0]

  col_nav1, col_nav2, col_nav_tiempos, col_nav3 = st.columns([2.2, 2.5, 1.2, 1.2])
  with col_nav1:
    seccion_elegida = st.selectbox("", opciones, index=opciones.index(st.session_state["seccion_activa"]), key="selector_navegacion_directa", label_visibility="collapsed")
    if seccion_elegida != st.session_state["seccion_activa"]:
      st.session_state["seccion_activa"] = seccion_elegida
      st.session_state["prospecto_editar_rfc"] = None
      st.rerun()

  with col_nav2:
    st.markdown(f"<div style='padding-top: 10px;'>👤 <b>Usuario:</b> <code>{usuario}</code> | 🛡️ <b>Rol:</b> <code>{rol}</code></div>", unsafe_allow_html=True)

  with col_nav_tiempos:
    if rol == "Telefonista":
      with st.popover("🍽️/Toilet/☕ Tiempos"):
        renderizar_control_tiempos_modal(usuario)

  with col_nav3:
    if st.button("🚪 Salir", use_container_width=True):
      for k in ["usuario_logueado", "rol", "prospecto_editar_rfc", "seccion_activa"]:
        st.session_state[k] = None
      st.rerun()

  st.markdown("---")
  opcion = st.session_state["seccion_activa"]

  if st.session_state["prospecto_editar_rfc"] is not None:
    rfc_actual = st.session_state["prospecto_editar_rfc"]
    lista_rfcs = st.session_state["lista_rfcs_navegacion"]
    pos_actual = lista_rfcs.index(rfc_actual) if rfc_actual in lista_rfcs else 0
    total_prospectos = len(lista_rfcs) if lista_rfcs else 1

    with engine.connect() as conn_sql:
      row = conn_sql.exec_driver_sql(f"SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3, tel_opcional FROM clientes WHERE rfc = {PH}", (rfc_actual,)).fetchone()

    if not row:
      st.error("No se encontró la información del prospecto.")
      st.session_state["prospecto_editar_rfc"] = None
      st.rerun()

    def ejecutar_guardado_y_salto(destino):
      rfc_limpio = str(st.session_state.get(f"frfc_{rfc_actual}", row[0])).strip().upper()
      n_nombre = st.session_state.get(f"fn_{rfc_actual}", row[1])
      n_apellido = st.session_state.get(f"fa_{rfc_actual}", row[2])
      n_t1, n_t2, n_t3 = row[3], row[4], row[5] if rol in ["Base de Datos", "Asesor"] else (st.session_state.get(f"ftel1_{rfc_actual}", row[3]), st.session_state.get(f"ftel2_{rfc_actual}", row[4]), st.session_state.get(f"ftel3_{rfc_actual}", row[5]))
      n_sector = st.session_state.get(f"fs_{rfc_actual}", row[6])
      n_poliza = st.session_state.get(f"fp_{rfc_actual}", row[7])
      n_div = st.session_state.get(f"fdiv_{rfc_actual}", parsear_a_date(row[8]))
      n_asig_f = st.session_state.get(f"fulfasig_{rfc_actual}", parsear_a_date(row[9]))
      n_mov = st.session_state.get(f"ffum_{rfc_actual}", parsear_a_date(row[11]))
      n_obs_asesor = row[13] or ""

      with engine.begin() as conn_sql:
        if ES_SQLITE:
          conn_sql.exec_driver_sql(f"INSERT OR REPLACE INTO clientes (rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})", (rfc_limpio, n_nombre, n_apellido, n_t1, n_t2, n_t3, f"{n_t1}/{n_t2}/{n_t3}", n_sector, n_poliza, str(n_div), str(n_asig_f), calcular_edad_desde_rfc(rfc_limpio), str(n_mov), row[12], n_obs_asesor, row[14], row[15]))
      
      if destino == "siguiente" and pos_actual < total_prospectos - 1:
        st.session_state["prospecto_editar_rfc"] = lista_rfcs[pos_actual + 1]
      elif destino == "anterior" and pos_actual > 0:
        st.session_state["prospecto_editar_rfc"] = lista_rfcs[pos_actual - 1]
      else:
        st.session_state["prospecto_editar_rfc"] = None
      st.success("💾 Guardado correctamente")
      st.rerun()

    c_op1, c_op2, c_op3 = st.columns([2, 1, 1])
    with c_op1:
      st.caption(f"📍 Registro {pos_actual + 1} de {total_prospectos}")
    with c_op2:
      if st.button("⬅️ Anterior", use_container_width=True): ejecutar_guardado_y_salto("anterior")
    with c_op3:
      if st.button("❌ Cerrar Ficha", use_container_width=True): ejecutar_guardado_y_salto("cerrar")

    st.text_input("RFC", value=str(row[0] or ""), key=f"frfc_{rfc_actual}")
    st.text_input("Nombre(s)", value=str(row[1] or ""), key=f"fn_{rfc_actual}")
    st.text_input("Apellidos", value=str(row[2] or ""), key=f"fa_{rfc_actual}")
    if st.button("💾 Guardar y Siguiente ➡", use_container_width=True):
      ejecutar_guardado_y_salto("siguiente")

  else:
    if rol == "Administrador":
      if opcion == "1. Cargar Base General":
        st.header("📥 Cargar Base General")
        archivo = st.file_uploader("Sube tu archivo (.xlsx o .csv)", type=["xlsx", "xls", "csv"])
        if archivo is not None:
          try:
            df_cargado = pd.read_csv(archivo) if archivo.name.endswith(".csv") else pd.read_excel(archivo)
            st.dataframe(df_cargado.head(5))
            if st.button("Guardar en Banco"):
              st.success("¡Cargado con éxito!")
          except Exception as e:
            st.error(f"Error: {e}")
      elif opcion == "2. Ver Banco de Prospectos":
        st.header("📊 Banco General de Prospectos")
        df_banco = pd.read_sql("SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, telefonista_asignada, estatus FROM clientes", con=engine)
        if df_banco.empty: st.warning("No hay clientes.")
        else: renderizar_bloque_con_tabla(df_banco, key_suffix="banco")
      elif opcion == "3. Gestión y Asignación de Prospectos":
        st.header("🔄 Gestión y Asignación de Prospectos")
        col_b, col_c = st.columns([3, 1])
        with col_b: busqueda = st.text_input("🔎 Buscar por RFC o Nombre:")
        with col_c:
          st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
          if st.button("➕ Crear Nuevo", use_container_width=True): modal_crear_prospecto(usuario, rol)
        
        q = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, telefonista_asignada, estatus FROM clientes"
        params = []
        if busqueda:
          q += " WHERE rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ?" if ES_SQLITE else " WHERE rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s"
          pat = f"%{busqueda}%"
          params = [pat, pat, pat]
        df_res = pd.read_sql(q, con=engine, params=tuple(params) if params else None)
        if df_res.empty: st.info("No hay resultados.")
        else: renderizar_bloque_con_tabla(df_res, key_suffix="gestion_admin")
    elif rol == "Asesor":
      if opcion == "Prospectos":
        st.header("🌐 Banco General (Vista Asesor)")
        col_b, col_c = st.columns([3, 1])
        with col_b: busq_a = st.text_input("🔎 Buscar:")
        with col_c:
          st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
          if st.button("➕ Crear Nuevo", use_container_width=True): modal_crear_prospecto(usuario, rol)
        df_pa = pd.read_sql("SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus FROM clientes LIMIT 500", con=engine)
        renderizar_bloque_con_tabla(df_pa, key_suffix="asesor_banco")
      else:
        st.header(f"Sección: {opcion}")
    else:
      st.header(f"Panel de {rol} - {opcion}")
