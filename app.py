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
    
    /* ANCHO AMPLIADO PARA EL POPOVER DE FILTROS */
    div[data-testid="stPopoverBody"] {
        width: 420px !important;
        max-width: 420px !important;
        padding: 16px !important;
    }
    div[data-testid="stPopoverBody"] button {
        font-size: 13px !important;
        padding: 6px 10px !important;
        min-height: 34px !important;
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
        telefono_reciente TEXT DEFAULT '',
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
  
  cant_por_pagina = 100
  total_filas = len(df)

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
              "Ver Todos los Prospectos (Asesor)",
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
                   estado_tel1, estado_tel2, estado_tel3, telefono_reciente
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
        n_tel_reciente = st.session_state.get(f"ftel_rec_{rfc_actual}", row[19] or "")

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
                    estado_tel1, estado_tel2, estado_tel3, telefono_reciente
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
                    n_tel_reciente,
                ),
            )
          else:
            conn_sql.exec_driver_sql(
                f"""
                INSERT INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                    estado_tel1, estado_tel2, estado_tel3, telefono_reciente
                )
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
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
                    estado_tel3 = EXCLUDED.estado_tel3,
                    telefono_reciente = EXCLUDED.telefono_reciente
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
                    n_tel_reciente,
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
        st.text_input(
            "📱 Teléfono Opcional / Reciente (Actualizado por Asesor)",
            value=str(row[19] or ""),
            key=f"ftel_rec_{rfc_actual}",
        )

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
            "Edad",
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
      col_obs1, col_obs2 = st.columns(2)
      with col_obs1:
        st.text_area(
            "Observaciones Telefonista",
            value=str(row[12] or ""),
            key=f"fobs_tel_{rfc_actual}",
        )
      with col_obs2:
        st.text_area(
            "Observaciones Asesor",
            value=str(row[13] or ""),
            key=f"fobs_asesor_{rfc_actual}",
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
        
        # --- BARRA DE OPCIONES Y MULTI-FILTROS AVANZADOS AMPLIADOS ---
        with st.popover("⚙️ Opciones de Tabla y Multi-Filtros Avanzados", use_container_width=False):
          st.markdown("##### ⚙️ Acciones Rápidas")
          if st.button("✅ Seleccionar 100 de esta página", use_container_width=True):
            pass  # El control de selección se maneja desde la tabla
          
          if st.button("❌ Desmarcar Todos", use_container_width=True):
            st.session_state["sel_rfcs_banco"] = []
            st.rerun()

          sel_count = len(st.session_state.get("sel_rfcs_banco", []))
          st.caption(f"📌 Seleccionados: **{sel_count}**")
          
          st.markdown("---")
          st.markdown("##### 📂 Panel de Multi-Filtros Acumulativos")
          
          if st.button("🔄 Restablecer / Borrar Filtros", use_container_width=True):
            st.session_state.pop("filtro_tel_banco", None)
            st.session_state.pop("filtro_sector_banco", None)
            st.session_state.pop("filtro_estatus_banco", None)
            st.rerun()

          # Filtros acumulativos interactivos dentro del popover ancho
          opciones_est_tel = ["Todos", "Sin marcar", "Válido / Contesta", "Número Erróneo / Malo", "No Contesta / Buzón"]
          f_est_tel = st.selectbox("📞 Estatus de Teléfonos:", opciones_est_tel, key="filtro_tel_banco")

          # Obtener lista única de dependencias / sectores para el filtro
          with engine.connect() as conn_s:
            res_sec = conn_s.exec_driver_sql("SELECT DISTINCT sector FROM clientes WHERE sector IS NOT NULL AND sector != ''").fetchall()
          lista_sectores = ["Todos"] + [r[0] for r in res_sec if r[0]]
          f_sector = st.selectbox("🏢 Mercado / Dependencia:", lista_sectores, key="filtro_sector_banco")

          opciones_estatus_gen = ["Todos", "Disponible", "Asignado", "En Seguimiento", "Cita Agendada", "No Interesado"]
          f_est_gen = st.selectbox("📌 Estatus General:", opciones_estatus_gen, key="filtro_estatus_banco")

        # Construcción de la consulta SQL aplicando los filtros acumulativos seleccionados
        query_banco = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, telefono_reciente, sector, poliza, dividendos, ult_fecha_asignacion, edad, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes"
        
        conds_banco = []
        params_banco = []

        if 'filtro_tel_banco' in st.session_state and st.session_state["filtro_tel_banco"] != "Todos":
          conds_banco.append("(estado_tel1 = ? OR estado_tel2 = ? OR estado_tel3 = ?)" if ES_SQLITE else "(estado_tel1 = %s OR estado_tel2 = %s OR estado_tel3 = %s)")
          params_banco.extend([st.session_state["filtro_tel_banco"]]*3)

        if 'filtro_sector_banco' in st.session_state and st.session_state["filtro_sector_banco"] != "Todos":
          conds_banco.append("sector = ?" if ES_SQLITE else "sector = %s")
          params_banco.append(st.session_state["filtro_sector_banco"])

        if 'filtro_estatus_banco' in st.session_state and st.session_state["filtro_estatus_banco"] != "Todos":
          conds_banco.append("estatus = ?" if ES_SQLITE else "estatus = %s")
          params_banco.append(st.session_state["filtro_estatus_banco"])

        if conds_banco:
          query_banco += " WHERE " + " AND ".join(conds_banco)

        df_banco = pd.read_sql(query_banco, con=engine, params=params_banco if params_banco else None)

        if df_banco.empty:
          st.warning("No hay clientes que coincidan con los filtros seleccionados.")
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
          with st.popover("🔍 Filtros Avanzados y Fechas", use_container_width=True):
            st.markdown("##### 📅 Filtrar por Rango de Fechas")
            usar_filtro_fechas = st.checkbox("Habilitar filtro de fechas de asignación")
            f_inicio = st.date_input("Desde:", value=obtener_ahora_mexico().date())
            f_fin = st.date_input("Hasta:", value=obtener_ahora_mexico().date())
            
            st.markdown("---")
            filtro_estatus_avanzado = st.selectbox(
                "Estatus específico:",
                ["Todos", "Disponible", "Asignado", "En Seguimiento", "Cita Agendada", "No Interesado"]
            )

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

        if 'usar_filtro_fechas' in locals() and usar_filtro_fechas:
          condiciones.append(
              "ult_fecha_asignacion BETWEEN ? AND ?" if ES_SQLITE else "ult_fecha_asignacion BETWEEN %s AND %s"
          )
          params_query.extend([str(f_inicio), str(f_fin)])

        if 'filtro_estatus_avanzado' in locals() and filtro_estatus_avanzado != "Todos":
          condiciones.append(
              "estatus = ?" if ES_SQLITE else "estatus = %s"
          )
          params_query.append(filtro_estatus_avanzado)

        query = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, telefono_reciente, sector, poliza, dividendos, ult_fecha_asignacion, telefonista_asignada, estatus FROM clientes"
        if condiciones:
          query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY fecha_creacion DESC LIMIT 1000"

        df_resultados = pd.read_sql(
            query, con=engine, params=params_query if params_query else None
        )
        if df_resultados.empty:
          st.warning("No se encontraron prospectos con los filtros seleccionados.")
        else:
          renderizar_bloque_con_tabla(
              df_resultados, key_suffix="gestion_admin", ocultar_tels=False
          )

      elif opcion == "4. Reporte de Citas y Actividad":
        st.header("📊 Reporte General de Citas y Actividad")
        f_rep = st.date_input(
            "Fecha Base:", value=obtener_ahora_mexico().date()
        )
        f_rep_str = str(f_rep)

        tab_rep1, tab_rep2, tab_rep3, tab_rep4 = st.tabs([
            "📈 Citas y Eficiencia",
            "📞 Llamadas Telefonistas",
            "⏱️ Auditoría de Tiempos",
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
              len(df_rep[df_rep["estado"].str.contains("Asistida", case=False, na=False)])
              if not df_rep.empty else 0
          )
          pend = len(df_rep[df_rep["estado"] == "Pendiente"]) if not df_rep.empty else 0
          efec = f"{(asis / tot_c * 100):.1f}%" if tot_c > 0 else "0%"

          m1.metric("Total Citas Generadas", tot_c)
          m2.metric("Asistidas", asis)
          m3.metric("Pendientes", pend)
          m4.metric("Tasa de Asistencia", efec)

          st.markdown("---")
          st.subheader("📞 Desglose de Citas por Telefonista / Agente")
          df_resumen_tele = pd.read_sql(
              f"""
                SELECT 
                    agente as "Telefonista / Agente",
                    COUNT(*) as "Total Citas Agendadas",
                    SUM(CASE WHEN estado LIKE '%Asistida%' THEN 1 ELSE 0 END) as "Asistidas",
                    SUM(CASE WHEN estado = 'Pendiente' THEN 1 ELSE 0 END) as "Pendientes"
                FROM citas 
                WHERE fecha = {PH}
                GROUP BY agente
                ORDER BY "Total Citas Agendadas" DESC
              """,
              con=engine,
              params=(f_rep_str,),
          )
          if df_resumen_tele.empty:
            st.info("No hay citas registradas para esta fecha.")
          else:
            st.markdown(
                df_resumen_tele.to_html(classes="custom-table", index=False, escape=False),
                unsafe_allow_html=True,
            )

      elif opcion == "5. Gestión de Usuarios y Roles":
        st.header("👥 Panel de Administración de Usuarios")

    elif rol in ["Telefonista", "Asesor"]:
      titulo_vista = "📞 Todos los Prospectos de la Base" if rol == "Asesor" else f"📞 Mis Prospectos Asignados ({usuario})"
      st.header(titulo_vista)
      
      busq_a = st.text_input("🔎 Buscar por RFC, Nombre o Apellido:")
      
      if rol == "Asesor":
        q_a = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, telefono_reciente, sector, poliza, dividendos, ult_fecha_asignacion, estatus FROM clientes"
        params_a = ()
        if busq_a:
          if ES_SQLITE:
            q_a += " WHERE rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ?"
          else:
            q_a += " WHERE rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s"
          pa = f"%{busq_a}%"
          params_a = (pa, pa, pa)
      else:
        q_a = f"SELECT rfc, nombre, apellido, tel1, tel2, tel3, telefono_reciente, sector, poliza, dividendos, ult_fecha_asignacion, estatus FROM clientes WHERE telefonista_asignada = {PH}"
        params_a = (usuario,)
        if busq_a:
          if ES_SQLITE:
            q_a += " AND (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ?)"
          else:
            q_a += " AND (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s)"
          pa = f"%{busq_a}%"
          params_a = (usuario, pa, pa, pa)

      df_pa = pd.read_sql(q_a, con=engine, params=params_a if params_a else None)
      if df_pa.empty:
        st.info("No se encontraron prospectos.")
      else:
        renderizar_bloque_con_tabla(df_pa, key_suffix="gestion_asesor", ocultar_tels=False)
