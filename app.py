from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="GRUPO PINZON - CRM", page_icon="🛡️", layout="wide"
)

# --- ESTILOS CSS CON GRUPO PINZÓN FUERTEMENTE EN VERDE METLIFE ---
st.markdown(
    """
<style>
    /* Estilo general de la página */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        background-color: #f4f7f6;
    }
    
    /* Títulos secundarios y generales */
    h2, h3 {
        color: #002B49 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Botones generales */
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

    /* Botones de Selección / Marcar Todos en verde */
    button[kind="secondary"] {
        background-color: #78BE20 !important;
        color: white !important;
        border: none !important;
    }

    /* Tablas personalizadas con Encabezado Verde MetLife */
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

    /* Forzar encabezados de tablas nativas de Streamlit a verde MetLife */
    [data-testid="stDataFrame"] th, div[data-testid="stTable"] th {
        background-color: #78BE20 !important;
        color: white !important;
    }

    /* Tarjetas de Métricas con detalle en Verde MetLife */
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


# --- FUNCIONES DE UTILIDAD PARA FECHAS Y EDAD ---
def calcular_edad_desde_rfc(rfc):
  if not rfc or len(rfc.strip()) < 10 or str(rfc).startswith("TEMP_"):
    return "S/D"
  try:
    limpio = rfc.strip().upper()
    yy = int(limpio[4:6])
    mm = int(limpio[6:8])
    dd = int(limpio[8:10])

    anio_actual = datetime.today().year
    siglo = 2000 if yy <= (anio_actual % 100) else 1900
    anio = siglo + yy

    f_nac = datetime(anio, mm, dd)
    hoy = datetime.today()
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
  if " " in s:
    s = s.split(" ")[0]
  return s


def parsear_a_date(val):
  s = limpiar_fecha_str(val)
  if not s:
    return datetime.today().date()
  for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
    try:
      return datetime.strptime(s, fmt).date()
    except ValueError:
      continue
  return datetime.today().date()


# --- BASE DE DATOS Y MIGRACIÓN AUTOMÁTICA ---
CONN = sqlite3.connect("sistema_citas.db", check_same_thread=False)
CURSOR = CONN.cursor()

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE,
    password TEXT,
    rol TEXT,
    nombre_completo TEXT,
    apellido TEXT,
    telefono TEXT,
    direccion TEXT
)
""")

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    rfc TEXT PRIMARY KEY,
    nombre TEXT,
    apellido TEXT,
    tel1 TEXT,
    tel2 TEXT,
    tel3 TEXT,
    telefono TEXT,
    sector TEXT,
    poliza TEXT,
    dividendos TEXT,
    ult_fecha_asignacion TEXT,
    edad TEXT,
    fecha_ult_mov TEXT,
    observaciones_tel TEXT,
    observaciones_asesor TEXT,
    telefonista_asignada TEXT DEFAULT 'Sin Asignar',
    estatus TEXT DEFAULT 'Disponible',
    estado_tel1 TEXT DEFAULT 'Sin marcar',
    estado_tel2 TEXT DEFAULT 'Sin marcar',
    estado_tel3 TEXT DEFAULT 'Sin marcar',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS historial_llamadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfc_cliente TEXT,
    usuario TEXT,
    accion TEXT,
    detalle TEXT,
    fecha_registro TEXT
)
""")


def asegurar_columnas():
  columnas_requeridas_clientes = {
      "nombre": "TEXT",
      "apellido": "TEXT",
      "tel1": "TEXT",
      "tel2": "TEXT",
      "tel3": "TEXT",
      "telefono": "TEXT",
      "sector": "TEXT",
      "poliza": "TEXT",
      "dividendos": "TEXT",
      "ult_fecha_asignacion": "TEXT",
      "edad": "TEXT",
      "fecha_ult_mov": "TEXT",
      "observaciones_tel": "TEXT",
      "observaciones_asesor": "TEXT",
      "telefonista_asignada": "TEXT DEFAULT 'Sin Asignar'",
      "estatus": "TEXT DEFAULT 'Disponible'",
      "estado_tel1": "TEXT DEFAULT 'Sin marcar'",
      "estado_tel2": "TEXT DEFAULT 'Sin marcar'",
      "estado_tel3": "TEXT DEFAULT 'Sin marcar'",
      "fecha_creacion": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
  }
  CURSOR.execute("PRAGMA table_info(clientes)")
  existentes_clientes = [col[1] for col in CURSOR.fetchall()]
  for col, tipo in columnas_requeridas_clientes.items():
    if col not in existentes_clientes:
      try:
        CURSOR.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")
      except:
        pass

  columnas_requeridas_usuarios = {
      "nombre_completo": "TEXT",
      "apellido": "TEXT",
      "telefono": "TEXT",
      "direccion": "TEXT",
  }
  CURSOR.execute("PRAGMA table_info(usuarios)")
  existentes_usuarios = [col[1] for col in CURSOR.fetchall()]
  for col, tipo in columnas_requeridas_usuarios.items():
    if col not in existentes_usuarios:
      try:
        CURSOR.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
      except:
        pass

  CONN.commit()


asegurar_columnas()

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS citas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfc_cliente TEXT,
    cliente TEXT NOT NULL,
    telefono TEXT,
    agente TEXT,
    asesor TEXT DEFAULT 'Sin Asignar',
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    estado TEXT NOT NULL,
    notas TEXT
)
""")

CURSOR.execute("""
    UPDATE citas 
    SET estado = 'No Asistió (Automático)' 
    WHERE estado = 'Pendiente' AND date(fecha) < date('now', 'localtime')
""")
CONN.commit()

CURSOR.execute("SELECT COUNT(*) FROM usuarios")
if CURSOR.fetchone()[0] == 0:
  CURSOR.executemany(
      """
        INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
      [
          (
              "admin",
              "1234",
              "Administrador",
              "Administrador",
              "Principal",
              "5550000000",
              "Oficina Central",
          ),
          (
              "tele1",
              "1234",
              "Telefonista",
              "Telefonista",
              "Uno",
              "5551111111",
              "Call Center",
          ),
          (
              "tele2",
              "1234",
              "Telefonista",
              "Telefonista",
              "Dos",
              "5552222222",
              "Call Center",
          ),
          (
              "asesor1",
              "1234",
              "Asesor",
              "Asesor",
              "Uno",
              "5553333333",
              "Campo",
          ),
          (
              "asesor2",
              "1234",
              "Asesor",
              "Asesor",
              "Dos",
              "5554444444",
              "Campo",
          ),
      ],
  )
  CONN.commit()


def autenticar(usuario, password):
  CURSOR.execute(
      "SELECT usuario, rol FROM usuarios WHERE usuario = ? AND password = ?",
      (usuario, password),
  )
  return CURSOR.fetchone()


def guardar_cita(
    rfc_cliente, cliente, telefono, agente, fecha, hora, estado, notas
):
  CURSOR.execute(
      """
        INSERT INTO citas (rfc_cliente, cliente, telefono, agente, asesor, fecha, hora, estado, notas)
        VALUES (?, ?, ?, ?, 'Sin Asignar', ?, ?, ?, ?)
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
  CONN.commit()


def obtener_usuarios_por_rol(rol):
  CURSOR.execute(
      "SELECT usuario FROM usuarios WHERE rol = ? ORDER BY usuario", (rol,)
  )
  return [row[0] for row in CURSOR.fetchall()]


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
    nom = limpiar_val(fila.get("NOMBRE", ""))
    ape = limpiar_val(fila.get("APELLIDOS", ""))
    if not nom:
      nom = "Sin Nombre"
    if not ape:
      ape = "Sin Apellido"

    t1 = limpiar_val(fila.get("TEL1", ""))
    t2 = limpiar_val(fila.get("TEL2", ""))
    t3 = limpiar_val(fila.get("TEL3", ""))

    tels_disponibles = [t for t in [t1, t2, t3] if t and t != "0"]
    telefono_principal = (
        " / ".join(tels_disponibles) if tels_disponibles else "Sin Teléfono"
    )

    rfc = limpiar_val(fila.get("RFC", ""))
    if not rfc or rfc.upper() == "NONE" or rfc == "":
      rfc = f"TEMP_{datetime.today().strftime('%y%m%d')}_{contador_sin_rfc}"
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

  for reg in registros:
    try:
      CURSOR.execute(
          """
                INSERT OR REPLACE INTO clientes (
                    rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                    poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                    observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Sin Asignar', 'Disponible', 'Sin marcar', 'Sin marcar', 'Sin marcar')
            """,
          reg,
      )
    except Exception as e:
      print("Error insertando registro:", e)
      pass
  CONN.commit()
  return len(registros)


@st.dialog("➕ Registrar Nuevo Prospecto")
def modal_crear_prospecto(usuario_actual, rol_actual):
  with st.form("form_modal_nuevo_prospecto"):
    col1, col2 = st.columns(2)
    with col1:
      rfc = st.text_input("RFC (Identificador Principal) *")
      nombre = st.text_input("Nombre(s) *")
      apellido = st.text_input("Apellidos *")
      tel1 = st.text_input("TEL 1")
      tel2 = st.text_input("TEL 2")
      tel3 = st.text_input("TEL 3")

    with col2:
      sector = st.text_input("Dependencia")
      poliza = st.text_input("Póliza")
      dividendos_dt = st.date_input("Dividendos", value=datetime.today())
      ult_fecha_asig_dt = st.date_input(
          "Ult Fecha Asignación", value=datetime.today()
      )
      fecha_ult_mov_dt = st.date_input("Fecha Ult Mov", value=datetime.today())

    if rol_actual == "Administrador":
      lista_asignables = (
          ["Sin Asignar"]
          + obtener_usuarios_por_rol("Telefonista")
          + obtener_usuarios_por_rol("Asesor")
      )
      telefonista_asignada = st.selectbox("Asignar a:", lista_asignables)
    elif rol_actual == "Telefonista":
      telefonista_asignada = usuario_actual
      st.info(f"📌 Asignado a: **{usuario_actual}**")
    elif rol_actual == "Asesor":
      telefonista_asignada = usuario_actual
      st.info(f"📌 Registrado por Asesor: **{usuario_actual}**")
    else:
      telefonista_asignada = "admin"

    estatus = st.selectbox(
        "Estatus Inicial", ["Disponible", "Asignado", "En Seguimiento"]
    )
    obs_tel = st.text_area("Observaciones Tel")
    obs_asesor = st.text_area("Observaciones Asesor")

    submitted = st.form_submit_button(
        "💾 Guardar Prospecto", use_container_width=True
    )

    if submitted:
      if not rfc.strip() or not nombre.strip() or not apellido.strip():
        st.error("⚠️ Los campos RFC, Nombre(s) y Apellidos son obligatorios.")
      else:
        tels_disp = [t for t in [tel1, tel2, tel3] if t]
        telefono_final = " / ".join(tels_disp) if tels_disp else "Sin Teléfono"
        edad_calc = calcular_edad_desde_rfc(rfc)

        fecha_hoy_str = datetime.today().strftime("%Y/%m/%d")
        obs_tel_final = (
            f"({fecha_hoy_str} - {usuario_actual}) {obs_tel}" if obs_tel else ""
        )
        obs_asesor_final = (
            f"({fecha_hoy_str} - {usuario_actual}) {obs_asesor}"
            if obs_asesor
            else ""
        )

        CURSOR.execute(
            """
                    INSERT OR REPLACE INTO clientes (
                        rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                        poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                        observaciones_tel, observaciones_asesor, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Sin marcar', 'Sin marcar', 'Sin marcar')
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
                obs_tel_final,
                obs_asesor_final,
                telefonista_asignada,
                estatus,
            ),
        )
        CONN.commit()
        st.success(
            f"✅ ¡Prospecto '{nombre} {apellido}' registrado con éxito!"
        )
        st.rerun()


def renderizar_bloque_con_tabla(df_entrada, key_suffix):
  df = df_entrada.copy()

  with st.popover("⚙️ Opciones de Tabla y Multi-Filtros Avanzados"):
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
      if st.button("☑ Seleccionar Todos", key=f"btn_sel_all_{key_suffix}"):
        st.session_state[f"sel_rfcs_{key_suffix}"] = df["rfc"].tolist()
        st.rerun()
    with col_btn2:
      if st.button(
          "❌ Desmarcar Todos", key=f"btn_desel_all_{key_suffix}"
      ):
        st.session_state[f"sel_rfcs_{key_suffix}"] = []
        st.rerun()

    st.markdown("---")
    st.markdown("##### 🗂️ Panel de Multi-Filtros Acumulativos")

    if st.button(
        "🔄 Restablecer / Borrar Filtros",
        key=f"btn_reset_filtros_{key_suffix}",
        use_container_width=True,
    ):
      st.session_state[f"filtro_tel_est_{key_suffix}"] = "Todos"
      st.session_state[f"filtro_mercado_{key_suffix}"] = "Todos"
      st.session_state[f"filtro_est_gral_{key_suffix}"] = "Todos"
      st.session_state[f"filtro_usuario_{key_suffix}"] = "Todos"
      st.session_state[f"chk_edad_{key_suffix}"] = False
      st.session_state[f"chk_div_{key_suffix}"] = False
      st.session_state[f"chk_asig_{key_suffix}"] = False
      st.session_state[f"chk_mov_{key_suffix}"] = False
      st.rerun()

    st.markdown("---")

    filtro_estado_tel = st.selectbox(
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
      mercados_disp = ["Todos"] + sorted(
          [str(x) for x in df["sector"].dropna().unique() if str(x).strip()]
      )
      filtro_mercado = st.selectbox(
          "🏢 Mercado / Dependencia:",
          mercados_disp,
          key=f"filtro_mercado_{key_suffix}",
      )
    else:
      filtro_mercado = "Todos"

    if "estatus" in df.columns:
      estatus_disp = ["Todos"] + sorted(
          [str(x) for x in df["estatus"].dropna().unique() if str(x).strip()]
      )
      filtro_estatus_gral = st.selectbox(
          "📌 Estatus del Prospecto:",
          estatus_disp,
          key=f"filtro_est_gral_{key_suffix}",
      )
    else:
      filtro_estatus_gral = "Todos"

    if "telefonista_asignada" in df.columns:
      usuarios_disp = ["Todos"] + sorted(
          [
              str(x)
              for x in df["telefonista_asignada"]
              .dropna()
              .unique()
              if str(x).strip()
          ]
      )
      filtro_usuario = st.selectbox(
          "👤 Usuario Asignado (Telefonista / Asesor):",
          usuarios_disp,
          key=f"filtro_usuario_{key_suffix}",
      )
    else:
      filtro_usuario = "Todos"

    st.markdown("---")
    usar_filtro_edad = st.checkbox(
        "👥 Filtrar por Rango de Edad", key=f"chk_edad_{key_suffix}"
    )
    if usar_filtro_edad:
      col_e1, col_e2 = st.columns(2)
      with col_e1:
        edad_min = st.number_input(
            "Edad Mínima:",
            min_value=18,
            max_value=120,
            value=18,
            key=f"e_min_{key_suffix}",
        )
      with col_e2:
        edad_max = st.number_input(
            "Edad Máxima:",
            min_value=18,
            max_value=120,
            value=80,
            key=f"e_max_{key_suffix}",
        )

    st.markdown("---")
    usar_filtro_div = st.checkbox(
        "📅 Filtrar por Fecha de Dividendos", key=f"chk_div_{key_suffix}"
    )
    tipo_modo_div = "Rango"
    f_div_ini, f_div_fin = datetime.today(), datetime.today()
    mes_div, anio_div = 1, 2026

    if usar_filtro_div:
      tipo_modo_div = st.radio(
          "Criterio de Dividendos:",
          ["Rango (Desde - Hasta)", "Por Mes Específico", "Por Año Completo"],
          key=f"modo_div_{key_suffix}",
      )
      if tipo_modo_div == "Rango (Desde - Hasta)":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
          f_div_ini = st.date_input(
              "Dividendos Desde:",
              value=datetime.today().replace(year=2024),
              key=f"div_ini_{key_suffix}",
          )
        with col_d2:
          f_div_fin = st.date_input(
              "Dividendos Hasta:",
              value=datetime.today(),
              key=f"div_fin_{key_suffix}",
          )
      elif tipo_modo_div == "Por Mes Específico":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
          mes_div = st.selectbox(
              "Selecciona el Mes:",
              list(range(1, 13)),
              format_func=lambda x: [
                  "Enero",
                  "Febrero",
                  "Marzo",
                  "Abril",
                  "Mayo",
                  "Junio",
                  "Julio",
                  "Agosto",
                  "Septiembre",
                  "Octubre",
                  "Noviembre",
                  "Diciembre",
              ][x - 1],
              key=f"mes_div_{key_suffix}",
          )
        with col_m2:
          anio_div = st.number_input(
              "Año:",
              min_value=2000,
              max_value=2050,
              value=datetime.today().year,
              key=f"anio_div_{key_suffix}",
          )
      else:
        anio_div = st.number_input(
            "Selecciona el Año Completo:",
            min_value=2000,
            max_value=2050,
            value=datetime.today().year,
            key=f"anio_comp_div_{key_suffix}",
        )

    st.markdown("---")
    usar_filtro_asig = st.checkbox(
        "📋 Filtrar por Fecha de Asignación", key=f"chk_asig_{key_suffix}"
    )
    tipo_modo_asig = "Rango"
    f_asig_ini, f_asig_fin = datetime.today(), datetime.today()
    mes_asig, anio_asig = 1, 2026

    if usar_filtro_asig:
      tipo_modo_asig = st.radio(
          "Criterio de Asignación:",
          ["Rango (Desde - Hasta)", "Por Mes Específico", "Por Año Completo"],
          key=f"modo_asig_{key_suffix}",
      )
      if tipo_modo_asig == "Rango (Desde - Hasta)":
        col_as1, col_as2 = st.columns(2)
        with col_as1:
          f_asig_ini = st.date_input(
              "Asignación Desde:",
              value=datetime.today().replace(year=2024),
              key=f"asig_ini_{key_suffix}",
          )
        with col_as2:
          f_asig_fin = st.date_input(
              "Asignación Hasta:",
              value=datetime.today(),
              key=f"asig_fin_{key_suffix}",
          )
      elif tipo_modo_asig == "Por Mes Específico":
        col_am1, col_am2 = st.columns(2)
        with col_am1:
          mes_asig = st.selectbox(
              "Selecciona el Mes:",
              list(range(1, 13)),
              format_func=lambda x: [
                  "Enero",
                  "Febrero",
                  "Marzo",
                  "Abril",
                  "Mayo",
                  "Junio",
                  "Julio",
                  "Agosto",
                  "Septiembre",
                  "Octubre",
                  "Noviembre",
                  "Diciembre",
              ][x - 1],
              key=f"mes_asig_{key_suffix}",
          )
        with col_am2:
          anio_asig = st.number_input(
              "Año:",
              min_value=2000,
              max_value=2050,
              value=datetime.today().year,
              key=f"anio_asig_{key_suffix}",
          )
      else:
        anio_asig = st.number_input(
            "Selecciona el Año Completo:",
            min_value=2000,
            max_value=2050,
            value=datetime.today().year,
            key=f"anio_comp_asig_{key_suffix}",
        )

    st.markdown("---")
    usar_filtro_mov = st.checkbox(
        "🕒 Filtrar por Fecha de Último Movimiento", key=f"chk_mov_{key_suffix}"
    )
    tipo_modo_mov = "Rango"
    f_mov_ini, f_mov_fin = datetime.today(), datetime.today()
    mes_mov, anio_mov = 1, 2026

    if usar_filtro_mov:
      tipo_modo_mov = st.radio(
          "Criterio de Último Movimiento:",
          ["Rango (Desde - Hasta)", "Por Mes Específico", "Por Año Completo"],
          key=f"modo_mov_{key_suffix}",
      )
      if tipo_modo_mov == "Rango (Desde - Hasta)":
        col_mv1, col_mv2 = st.columns(2)
        with col_mv1:
          f_mov_ini = st.date_input(
              "Movimiento Desde:",
              value=datetime.today().replace(year=2024),
              key=f"mov_ini_{key_suffix}",
          )
        with col_mv2:
          f_mov_fin = st.date_input(
              "Movimiento Hasta:",
              value=datetime.today(),
              key=f"mov_fin_{key_suffix}",
          )
      elif tipo_modo_mov == "Por Mes Específico":
        col_mm1, col_mm2 = st.columns(2)
        with col_mm1:
          mes_mov = st.selectbox(
              "Selecciona el Mes:",
              list(range(1, 13)),
              format_func=lambda x: [
                  "Enero",
                  "Febrero",
                  "Marzo",
                  "Abril",
                  "Mayo",
                  "Junio",
                  "Julio",
                  "Agosto",
                  "Septiembre",
                  "Octubre",
                  "Noviembre",
                  "Diciembre",
              ][x - 1],
              key=f"mes_mov_{key_suffix}",
          )
        with col_mm2:
          anio_mov = st.number_input(
              "Año:",
              min_value=2000,
              max_value=2050,
              value=datetime.today().year,
              key=f"anio_mov_{key_suffix}",
          )
      else:
        anio_mov = st.number_input(
            "Selecciona el Año Completo:",
            min_value=2000,
            max_value=2050,
            value=datetime.today().year,
            key=f"anio_comp_mov_{key_suffix}",
        )

  if (
      st.session_state.get(f"filtro_tel_est_{key_suffix}", "Todos") != "Todos"
      and "estado_tel1" in df.columns
  ):
    val_tel_est = st.session_state[f"filtro_tel_est_{key_suffix}"]
    df = df[
        (df["estado_tel1"] == val_tel_est)
        | (df["estado_tel2"] == val_tel_est)
        | (df["estado_tel3"] == val_tel_est)
    ]

  if (
      st.session_state.get(f"filtro_mercado_{key_suffix}", "Todos") != "Todos"
      and "sector" in df.columns
  ):
    val_mercado = st.session_state[f"filtro_mercado_{key_suffix}"]
    df = df[df["sector"] == val_mercado]

  if (
      st.session_state.get(f"filtro_est_gral_{key_suffix}", "Todos") != "Todos"
      and "estatus" in df.columns
  ):
    val_est_gral = st.session_state[f"filtro_est_gral_{key_suffix}"]
    df = df[df["estatus"] == val_est_gral]

  if (
      st.session_state.get(f"filtro_usuario_{key_suffix}", "Todos") != "Todos"
      and "telefonista_asignada" in df.columns
  ):
    val_usu = st.session_state[f"filtro_usuario_{key_suffix}"]
    df = df[df["telefonista_asignada"] == val_usu]

  if (
      st.session_state.get(f"chk_edad_{key_suffix}", False)
      and "edad" in df.columns
  ):
    df["temp_edad"] = pd.to_numeric(df["edad"], errors="coerce")
    e_min = st.session_state.get(f"e_min_{key_suffix}", 18)
    e_max = st.session_state.get(f"e_max_{key_suffix}", 80)
    df = df[(df["temp_edad"] >= e_min) & (df["temp_edad"] <= e_max)]
    df = df.drop(columns=["temp_edad"])

  if (
      st.session_state.get(f"chk_div_{key_suffix}", False)
      and "dividendos" in df.columns
  ):
    df["temp_div_dt"] = pd.to_datetime(df["dividendos"], errors="coerce")
    modo_d = st.session_state.get(
        f"modo_div_{key_suffix}", "Rango (Desde - Hasta)"
    )
    if modo_d == "Rango (Desde - Hasta)":
      d_ini = st.session_state.get(
          f"div_ini_{key_suffix}", datetime.today().date()
      )
      d_fin = st.session_state.get(
          f"div_fin_{key_suffix}", datetime.today().date()
      )
      df = df[
          (df["temp_div_dt"].dt.date >= d_ini)
          & (df["temp_div_dt"].dt.date <= d_fin)
      ]
    elif modo_d == "Por Mes Específico":
      m_d = st.session_state.get(f"mes_div_{key_suffix}", 1)
      a_d = st.session_state.get(
          f"anio_div_{key_suffix}", datetime.today().year
      )
      df = df[
          (df["temp_div_dt"].dt.month == m_d)
          & (df["temp_div_dt"].dt.year == a_d)
      ]
    else:
      a_d = st.session_state.get(
          f"anio_comp_div_{key_suffix}", datetime.today().year
      )
      df = df[df["temp_div_dt"].dt.year == a_d]
    df = df.drop(columns=["temp_div_dt"])

  if (
      st.session_state.get(f"chk_asig_{key_suffix}", False)
      and "ult_fecha_asignacion" in df.columns
  ):
    df["temp_asig_dt"] = pd.to_datetime(
        df["ult_fecha_asignacion"], errors="coerce"
    )
    modo_a = st.session_state.get(
        f"modo_asig_{key_suffix}", "Rango (Desde - Hasta)"
    )
    if modo_a == "Rango (Desde - Hasta)":
      as_ini = st.session_state.get(
          f"asig_ini_{key_suffix}", datetime.today().date()
      )
      as_fin = st.session_state.get(
          f"asig_fin_{key_suffix}", datetime.today().date()
      )
      df = df[
          (df["temp_asig_dt"].dt.date >= as_ini)
          & (df["temp_asig_dt"].dt.date <= as_fin)
      ]
    elif modo_a == "Por Mes Específico":
      m_a = st.session_state.get(f"mes_asig_{key_suffix}", 1)
      a_a = st.session_state.get(
          f"anio_asig_{key_suffix}", datetime.today().year
      )
      df = df[
          (df["temp_asig_dt"].dt.month == m_a)
          & (df["temp_asig_dt"].dt.year == a_a)
      ]
    else:
      a_a = st.session_state.get(
          f"anio_comp_asig_{key_suffix}", datetime.today().year
      )
      df = df[df["temp_asig_dt"].dt.year == a_a]
    df = df.drop(columns=["temp_asig_dt"])

  if (
      st.session_state.get(f"chk_mov_{key_suffix}", False)
      and "fecha_ult_mov" in df.columns
  ):
    df["temp_mov_dt"] = pd.to_datetime(df["fecha_ult_mov"], errors="coerce")
    modo_m = st.session_state.get(
        f"modo_mov_{key_suffix}", "Rango (Desde - Hasta)"
    )
    if modo_m == "Rango (Desde - Hasta)":
      mv_ini = st.session_state.get(
          f"mov_ini_{key_suffix}", datetime.today().date()
      )
      mv_fin = st.session_state.get(
          f"mov_fin_{key_suffix}", datetime.today().date()
      )
      df = df[
          (df["temp_mov_dt"].dt.date >= mv_ini)
          & (df["temp_mov_dt"].dt.date <= mv_fin)
      ]
    elif modo_m == "Por Mes Específico":
      m_mv = st.session_state.get(f"mes_mov_{key_suffix}", 1)
      a_mv = st.session_state.get(
          f"anio_mov_{key_suffix}", datetime.today().year
      )
      df = df[
          (df["temp_mov_dt"].dt.month == m_mv)
          & (df["temp_mov_dt"].dt.year == a_mv)
      ]
    else:
      a_mv = st.session_state.get(
          f"anio_comp_mov_{key_suffix}", datetime.today().year
      )
      df = df[df["temp_mov_dt"].dt.year == a_mv]
    df = df.drop(columns=["temp_mov_dt"])

  if "Seleccionar" not in df.columns:
    df.insert(0, "Seleccionar", False)

  state_key = f"selected_rfc_{key_suffix}"
  if state_key not in st.session_state:
    st.session_state[state_key] = None

  st.session_state["lista_rfcs_navegacion"] = df["rfc"].tolist()

  cant_por_pagina = 100
  total_filas = len(df)

  if total_filas > cant_por_pagina:
    total_paginas = (total_filas // cant_por_pagina) + (
        1 if total_filas % cant_por_pagina > 0 else 0
    )
    pagina_actual = st.selectbox(
        f"📄 Páginas disponibles (Mostrando bloques de 100 de {total_filas}"
        " registros coincidentes):",
        range(1, total_paginas + 1),
        key=f"pag_num_{key_suffix}",
    )
    inicio = (pagina_actual - 1) * cant_por_pagina
    fin = inicio + cant_por_pagina
    df_a_mostrar = df.iloc[inicio:fin].copy()
  else:
    df_a_mostrar = df.copy()

  seleccionados_previos = st.session_state.get(f"sel_rfcs_{key_suffix}", [])
  df_a_mostrar["Seleccionar"] = df_a_mostrar["rfc"].isin(
      seleccionados_previos
  )

  column_config = {
      "Seleccionar": st.column_config.CheckboxColumn(
          "Seleccionar", default=False, width="small"
      ),
      "rfc": st.column_config.TextColumn("RFC / ID", width="medium"),
  }
  columnas_deshabilitadas = [c for c in df.columns if c not in ["Seleccionar"]]

  if seleccionados_previos:
    col_vacia, col_btn = st.columns([3.2, 1.3])
    with col_btn:
      if st.button(
          "🚀 Abrir / Ver Ficha",
          key=f"btn_superior_{key_suffix}",
          use_container_width=True,
      ):
        st.session_state["prospecto_editar_rfc"] = str(
            seleccionados_previos[0]
        )
        st.rerun()

  editor_res = st.data_editor(
      df_a_mostrar,
      key=f"tabla_editor_{key_suffix}",
      use_container_width=True,
      hide_index=True,
      column_config=column_config,
      disabled=columnas_deshabilitadas,
  )

  seleccionados_actuales = editor_res[editor_res["Seleccionar"] == True]
  rfcs_sel_en_vista = seleccionados_actuales["rfc"].tolist()

  rfcs_otros = [
      r
      for r in seleccionados_previos
      if r not in df_a_mostrar["rfc"].tolist()
  ]
  rfcs_finales = list(set(rfcs_otros + rfcs_sel_en_vista))

  if rfcs_finales != seleccionados_previos:
    st.session_state[f"sel_rfcs_{key_suffix}"] = rfcs_finales
    st.rerun()

  return editor_res


if "usuario_logueado" not in st.session_state:
  st.session_state["usuario_logueado"] = None
  st.session_state["rol"] = None

if "prospecto_editar_rfc" not in st.session_state:
  st.session_state["prospecto_editar_rfc"] = None

if "lista_rfcs_navegacion" not in st.session_state:
  st.session_state["lista_rfcs_navegacion"] = []

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

if st.session_state["usuario_logueado"] is None:
  _, col_centro, _ = st.columns([1, 1.5, 1])
  with col_centro:
    st.markdown("### 🔑 Iniciar Sesión en el Sistema")
    usr = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar al Sistema", use_container_width=True):
      datos = autenticar(usr, pwd)
      if datos:
        st.session_state["usuario_logueado"] = datos[0]
        st.session_state["rol"] = datos[1]
        st.rerun()
      else:
        st.error("Usuario o contraseña incorrectos")
else:
  rol = st.session_state["rol"]
  usuario = st.session_state["usuario_logueado"]

  if rol == "Administrador":
    opciones = [
        "1. Cargar Base General",
        "2. Ver Banco de Prospectos",
        "3. Gestión y Asignación de Prospectos",
        "4. Reporte de Citas y Eficiencia",
        "5. Gestión de Usuarios y Roles",
    ]
  elif rol == "Telefonista":
    opciones = [
        "Mis Prospectos y Gestión",
        "Mis Citas Agendadas",
    ]
  else:
    opciones = [
        "Mis Prospectos Asignados",
        "Bolsa de Citas del Día (Asesores)",
        "Mis Registros de Hoy",
        "📊 Reportes de Citas y Asistencias",
    ]

  col_menu_izq, col_info_der = st.columns([1, 3])

  with col_menu_izq:
    with st.popover("∷ Menú"):
      opcion = st.radio("Selecciona una sección:", opciones)
      st.markdown("---")
      if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state["usuario_logueado"] = None
        st.session_state["rol"] = None
        st.session_state["prospecto_editar_rfc"] = None
        st.session_state["lista_rfcs_navegacion"] = []
        st.rerun()

  with col_info_der:
    st.markdown(
        f"<div style='text-align: right; padding-top: 5px;'>👤 <b>Usuario:</b>"
        f" <code>{usuario}</code> &nbsp;|&nbsp; 🛡️ <b>Rol:</b>"
        f" <code>{rol}</code></div>",
        unsafe_allow_html=True,
    )

  st.markdown("---")

  if st.session_state["prospecto_editar_rfc"] is not None:
    rfc_actual = st.session_state["prospecto_editar_rfc"]
    lista_rfcs = st.session_state["lista_rfcs_navegacion"]

    pos_actual = lista_rfcs.index(rfc_actual) if rfc_actual in lista_rfcs else 0
    total_prospectos = len(lista_rfcs) if lista_rfcs else 1

    CURSOR.execute(
        """
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, 
                   dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                   observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                   estado_tel1, estado_tel2, estado_tel3
            FROM clientes WHERE rfc = ?
        """,
        (rfc_actual,),
    )
    row = CURSOR.fetchone()

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

        est_t1 = st.session_state.get(f"est_t1_{rfc_actual}", row[16])
        est_t2 = st.session_state.get(f"est_t2_{rfc_actual}", row[17])
        est_t3 = st.session_state.get(f"est_t3_{rfc_actual}", row[18])

        edad_nueva = calcular_edad_desde_rfc(rfc_limpio)
        tels_disp = [t for t in [n_t1, n_t2, n_t3] if t]
        telefono_general = (
            " / ".join(tels_disp) if tels_disp else "Sin Teléfono"
        )

        asignacion_final = row[14]
        estatus_final = row[15]

        if rfc_limpio != rfc_actual:
          CURSOR.execute("DELETE FROM clientes WHERE rfc = ?", (rfc_actual,))

        CURSOR.execute(
            """
                    INSERT OR REPLACE INTO clientes (
                        rfc, nombre, apellido, tel1, tel2, tel3, telefono, sector, 
                        poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, 
                        observaciones_tel, observaciones_asesor, telefonista_asignada, estatus,
                        estado_tel1, estado_tel2, estado_tel3
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                row[12],
                row[13],
                asignacion_final,
                estatus_final,
                est_t1,
                est_t2,
                est_t3,
            ),
        )
        CONN.commit()

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

      nombre_completo_id = (
          f"{str(row[1]).strip().upper()} {str(row[2]).strip().upper()}"
      )
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
          CURSOR.execute(
              "UPDATE clientes SET telefonista_asignada = ?, estatus ="
              " 'Asignado' WHERE rfc = ?",
              (usuario, rfc_actual),
          )
          CONN.commit()
          st.success("¡Te has asignado el prospecto exitosamente!")
          st.rerun()

      col1, col2 = st.columns(2)
      with col1:
        nuevo_rfc = st.text_input(
            "RFC", value=str(row[0] or ""), key=f"frfc_{rfc_actual}"
        )
        nuevo_nombre = st.text_input(
            "Nombre(s)", value=str(row[1] or ""), key=f"fn_{rfc_actual}"
        )
        nuevo_apellido = st.text_input(
            "Apellidos", value=str(row[2] or ""), key=f"fa_{rfc_actual}"
        )

        st.markdown("---")
        st.markdown("#### 📞 Control de Números Telefónicos y Estatus")

        t1_val = str(row[3] or "")
        est_t1_val = row[16] if row[16] else "Sin marcar"
        opciones_estados = [
            "Sin marcar",
            "Válido / Contesta",
            "Número Erróneo / Malo",
            "No Contesta / Buzón",
        ]
        idx1 = (
            opciones_estados.index(est_t1_val)
            if est_t1_val in opciones_estados
            else 0
        )

        col_t1a, col_t1b = st.columns([1.2, 1.8])
        with col_t1a:
          nuevo_tel1 = st.text_input(
              "TEL 1", value=t1_val, key=f"ftel1_{rfc_actual}"
          )
        with col_t1b:
          st.selectbox(
              "Estatus Tel 1",
              opciones_estados,
              index=idx1,
              key=f"est_t1_{rfc_actual}",
          )

        t2_val = str(row[4] or "")
        est_t2_val = row[17] if row[17] else "Sin marcar"
        idx2 = (
            opciones_estados.index(est_t2_val)
            if est_t2_val in opciones_estados
            else 0
        )

        col_t2a, col_t2b = st.columns([1.2, 1.8])
        with col_t2a:
          nuevo_tel2 = st.text_input(
              "TEL 2", value=t2_val, key=f"ftel2_{rfc_actual}"
          )
        with col_t2b:
          st.selectbox(
              "Estatus Tel 2",
              opciones_estados,
              index=idx2,
              key=f"est_t2_{rfc_actual}",
          )

        t3_val = str(row[5] or "")
        est_t3_val = row[18] if row[18] else "Sin marcar"
        idx3 = (
            opciones_estados.index(est_t3_val)
            if est_t3_val in opciones_estados
            else 0
        )

        col_t3a, col_t3b = st.columns([1.2, 1.8])
        with col_t3a:
          nuevo_tel3 = st.text_input(
              "TEL 3", value=t3_val, key=f"ftel3_{rfc_actual}"
          )
        with col_t3b:
          st.selectbox(
              "Estatus Tel 3",
              opciones_estados,
              index=idx3,
              key=f"est_t3_{rfc_actual}",
          )

      with col2:
        nuevo_sector = st.text_input(
            "Dependencia", value=str(row[6] or ""), key=f"fs_{rfc_actual}"
        )
        nuevo_poliza = st.text_input(
            "Póliza", value=str(row[7] or ""), key=f"fp_{rfc_actual}"
        )

        val_div = parsear_a_date(row[8])
        nuevo_dividendos_dt = st.date_input(
            "Dividendos", value=val_div, key=f"fdiv_{rfc_actual}"
        )

        val_asig = parsear_a_date(row[9])
        nuevo_ult_fecha_asig_dt = st.date_input(
            "Ult Fecha Asignación",
            value=val_asig,
            key=f"fulfasig_{rfc_actual}",
        )

        edad_calculada = calcular_edad_desde_rfc(nuevo_rfc)
        st.text_input(
            "Edad (Calculada/Registrada)",
            value=str(row[10] or edad_calculada),
            disabled=True,
            key=f"fedad_{rfc_actual}",
        )

        val_mov = parsear_a_date(row[11])
        nuevo_fecha_ult_mov_dt = st.date_input(
            "Fecha Ult Mov", value=val_mov, key=f"ffum_{rfc_actual}"
        )

      st.markdown("---")
      st.subheader("📅 Cita Generada Activa")
      CURSOR.execute(
          """
            SELECT id, fecha, hora, estado, agente, notas FROM citas 
            WHERE rfc_cliente = ? ORDER BY id DESC LIMIT 1
        """,
          (rfc_actual,),
      )
      cita_reciente = CURSOR.fetchone()

      if cita_reciente:
        c_id, c_fecha, c_hora, c_estado, c_agente, c_notas = cita_reciente
        st.info(
            f"📌 **Fecha:** {c_fecha} | **Hora:** {c_hora} | **Agente/Tele:**"
            f" {c_agente} | **Estado:** `{c_estado}`"
        )
        if c_notas:
          st.caption(f"Notas: {c_notas}")

        col_c_btn1, col_c_btn2, col_c_vacio = st.columns([1, 1, 2])
        with col_c_btn1:
          if st.button("✅ Asistió", key=f"asistio_{c_id}"):
            CURSOR.execute(
                "UPDATE citas SET estado = 'Asistida / Atendida' WHERE id = ?",
                (c_id,),
            )
            CURSOR.execute(
                "UPDATE clientes SET estatus = 'Cita Asistida' WHERE rfc = ?",
                (rfc_actual,),
            )
            CONN.commit()
            st.success("¡Cita marcada como Asistida!")
            st.rerun()
        with col_c_btn2:
          if st.button("❌ No Asistió", key=f"no_asistio_{c_id}"):
            CURSOR.execute(
                "UPDATE citas SET estado = 'No Asistió' WHERE id = ?", (c_id,)
            )
            CURSOR.execute(
                "UPDATE clientes SET estatus = 'No Asistió' WHERE rfc = ?",
                (rfc_actual,),
            )
            CONN.commit()
            st.warning("Cita marcada como No Asistió.")
            st.rerun()
      else:
        st.caption(
            "No hay citas generadas recientemente para este prospecto."
        )

      st.markdown("---")
      st.subheader("📞 Registro de Llamada / Tareas")

      accion_llamada = st.selectbox(
          "Selecciona opción de llamada:",
          ["Cita", "Posible Asistencia", "Recado", "Mensaje de texto"],
      )

      with st.form(f"form_llamada_{rfc_actual}"):
        detalle_accion = st.text_area(
            "Detalle / Observaciones de la llamada o recado:"
        )

        usa_agenda = accion_llamada in ["Cita", "Posible Asistencia"]

        if usa_agenda:
          f_cita_input = st.date_input("Fecha de Cita", value=datetime.today())

          bloques_horas = []
          for hora_h in range(9, 17):
            for min_m in [0, 30]:
              if hora_h == 16 and min_m > 0:
                break
              bloques_horas.append(f"{hora_h:02d}:{min_m:02d}")

          h_cita_input = st.selectbox(
              "Hora de Cita (Bloques de 30 min - 9:00 AM a 4:00 PM)",
              bloques_horas,
          )
        else:
          st.info(
              f"📌 Campos de fecha y hora ocultos para **{accion_llamada}**."
              " Se registrará automáticamente con la hora actual."
          )
          f_cita_input = datetime.today().date()
          h_cita_input = datetime.now().strftime("%H:%M")

        btn_guardar_llamada = st.form_submit_button(
            "💾 Registrar Acción", use_container_width=True
        )

        if btn_guardar_llamada:
          ahora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          if usa_agenda:
            guardar_cita(
                rfc_actual,
                nombre_completo_id,
                row[3] if row[3] else "Sin Teléfono",
                usuario,
                f_cita_input,
                h_cita_input,
                "Pendiente",
                detalle_accion,
            )
            estatus_nuevo = (
                "Cita Agendada"
                if accion_llamada == "Cita"
                else "Posible Asistencia"
            )
            CURSOR.execute(
                "UPDATE clientes SET estatus = ? WHERE rfc = ?",
                (estatus_nuevo, rfc_actual),
            )
            st.success(f"✅ ¡{accion_llamada} registrada exitosamente!")
          else:
            CURSOR.execute(
                """
                        INSERT INTO historial_llamadas (rfc_cliente, usuario, accion, detalle, fecha_registro)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                (
                    rfc_actual,
                    usuario,
                    accion_llamada,
                    detalle_accion,
                    ahora_local,
                ),
            )
            CURSOR.execute(
                "UPDATE clientes SET estatus = ? WHERE rfc = ?",
                (f"En Seguimiento ({accion_llamada})", rfc_actual),
            )
            st.success(
                f"✅ ¡{accion_llamada} registrado en el historial con éxito!"
            )

          CONN.commit()
          st.rerun()

      st.markdown("---")
      st.subheader("📜 HISTORIAL DE LLAMADAS")
      df_historial = pd.read_sql_query(
          """
            SELECT fecha_registro as 'Fecha/Hora', usuario as 'Usuario', accion as 'Acción', detalle as 'Detalle'
            FROM historial_llamadas WHERE rfc_cliente = ? ORDER BY id DESC
        """,
          CONN,
          params=(rfc_actual,),
      )

      if df_historial.empty:
        st.info("No hay registros previos en el historial de llamadas.")
      else:
        html_table = df_historial.to_html(
            classes="custom-table", index=False, escape=False
        )
        st.markdown(html_table, unsafe_allow_html=True)

      st.markdown("---")
      col_b1, col_b2, col_b3 = st.columns([1, 1, 1])
      with col_b1:
        if st.button("⬅️ Guardar y Anterior", key=f"btn_ant_{rfc_actual}"):
          ejecutar_guardado_y_salto("anterior")
      with col_b2:
        if st.button("💾 Guardar y Cerrar", key=f"btn_sol_{rfc_actual}"):
          ejecutar_guardado_y_salto("cerrar")
      with col_b3:
        if st.button("💾 Guardar y Siguiente ➡", key=f"btn_sig_{rfc_actual}"):
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
            nombre_archivo = archivo.name.lower()
            if nombre_archivo.endswith(".csv"):
              try:
                df_cargado = pd.read_csv(archivo, encoding="utf-8")
              except UnicodeDecodeError:
                archivo.seek(0)
                df_cargado = pd.read_csv(archivo, encoding="latin1")
            else:
              df_cargado = pd.read_excel(archivo, engine="openpyxl")

            st.dataframe(df_cargado.head(10), use_container_width=True)
            if st.button("Guardar en Banco General"):
              total = cargar_base_general(df_cargado)
              st.success(
                  f"✅ ¡Se cargaron {total} prospectos exitosamente con"
                  " fechas limpias!"
              )
          except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

      elif opcion == "2. Ver Banco de Prospectos":
        st.header("📊 Banco General de Prospectos")
        df_banco = pd.read_sql_query(
            "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza,"
            " dividendos, ult_fecha_asignacion, edad, telefonista_asignada,"
            " estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes",
            CONN,
        )

        if df_banco.empty:
          st.warning("No hay clientes registrados.")
        else:
          renderizar_bloque_con_tabla(df_banco, key_suffix="banco")

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

        filtro_campo_fecha = "Sin filtro de fecha"
        filtro_f_ini = datetime.today().replace(year=2020)
        filtro_f_fin = datetime.today()
        filtro_dependencia = "Todas"
        filtro_estatus_sel = "Todos"
        filtro_asignado_sel = "Todos"

        if activar_filtros:
          with st.expander("🛠 Parámetros de Filtrado Avanzado", expanded=True):
            col_fa1, col_fa2, col_fa3 = st.columns(3)
            with col_fa1:
              filtro_campo_fecha = st.selectbox(
                  "Filtrar por tipo de fecha:",
                  [
                      "Sin filtro de fecha",
                      "Fecha Último Movimiento",
                      "Fecha de Asignación",
                      "Fecha de Dividendos",
                  ],
              )
            with col_fa2:
              filtro_f_ini = st.date_input(
                  "Desde:", value=datetime.today().replace(year=2020)
              )
            with col_fa3:
              filtro_f_fin = st.date_input("Hasta:", value=datetime.today())

            col_fb1, col_fb2, col_fb3 = st.columns(3)
            with col_fb1:
              deps_db = [
                  row[0]
                  for row in CURSOR.execute(
                      "SELECT DISTINCT sector FROM clientes WHERE sector IS NOT NULL AND sector != ''"
                  ).fetchall()
              ]
              filtro_dependencia = st.selectbox(
                  "Dependencia / Sector:", ["Todas"] + deps_db
              )

            with col_fb2:
              estatus_db = [
                  row[0]
                  for row in CURSOR.execute(
                      "SELECT DISTINCT estatus FROM clientes WHERE estatus IS NOT NULL"
                  ).fetchall()
              ]
              filtro_estatus_sel = st.selectbox(
                  "Estatus:", ["Todos"] + estatus_db
              )

            with col_fb3:
              tels_db = obtener_usuarios_por_rol(
                  "Telefonista"
              ) + obtener_usuarios_por_rol("Asesor")
              filtro_asignado_sel = st.selectbox(
                  "Asignado a:", ["Todos", "Sin Asignar"] + tels_db
              )

        condiciones = []
        if busqueda:
          condiciones.append(
              f"(rfc LIKE '%{busqueda}%' OR nombre LIKE '%{busqueda}%' OR apellido LIKE '%{busqueda}%' OR tel1 LIKE '%{busqueda}%')"
          )

        if filtro_campo_fecha != "Sin filtro de fecha":
          columna_bd_map = {
              "Fecha Último Movimiento": "fecha_ult_mov",
              "Fecha de Asignación": "ult_fecha_asignacion",
              "Fecha de Dividendos": "dividendos",
          }
          col_sql = columna_bd_map[filtro_campo_fecha]
          condiciones.append(
              f"({col_sql} BETWEEN '{filtro_f_ini}' AND '{filtro_f_fin}')"
          )

        if filtro_dependencia != "Todas":
          condiciones.append(f"sector = '{filtro_dependencia}'")

        if filtro_estatus_sel != "Todos":
          condiciones.append(f"estatus = '{filtro_estatus_sel}'")

        if filtro_asignado_sel != "Todos":
          condiciones.append(
              f"telefonista_asignada = '{filtro_asignado_sel}'"
          )

        query = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, fecha_ult_mov, telefonista_asignada, estatus, estado_tel1, estado_tel2, estado_tel3 FROM clientes"
        if condiciones:
          query += " WHERE " + " AND ".join(condiciones)
        query += " ORDER BY fecha_creacion DESC LIMIT 1000"

        df_resultados = pd.read_sql_query(query, CONN)

        if df_resultados.empty:
          st.warning(
              "No se encontraron prospectos con los filtros seleccionados."
          )
        else:
          editor_res = renderizar_bloque_con_tabla(
              df_resultados, key_suffix="gestion_admin"
          )
          seleccionados = editor_res[editor_res["Seleccionar"] == True]
          cant_seleccionados = len(seleccionados)

          st.markdown("---")
          st.subheader("⚡ Actualización y Asignación Masiva")
          col1, col2, col3 = st.columns([2, 2, 1])
          with col1:
            tele_destino = st.selectbox(
                "Asignar a:",
                obtener_usuarios_por_rol("Telefonista")
                + obtener_usuarios_por_rol("Asesor"),
            )
          with col2:
            estatus_masivo = st.selectbox(
                "Cambiar Estatus A:",
                [
                    "Asignado",
                    "Disponible",
                    "En Seguimiento",
                    "No Interesado",
                ],
            )
          with col3:
            st.metric("Seleccionados", cant_seleccionados)

          if st.button("🚀 Aplicar Cambios Masivos"):
            if cant_seleccionados == 0:
              st.warning(
                  "⚠️ Marca la casilla 'Seleccionar' en la tabla para aplicar"
                  " cambios."
              )
            else:
              rfcs_a_cambiar = seleccionados["rfc"].tolist()
              rfcs_str = ",".join([f"'{r}'" for r in rfcs_a_cambiar])
              CURSOR.execute(
                  "UPDATE clientes SET telefonista_asignada ="
                  f" '{tele_destino}', estatus = '{estatus_masivo}' WHERE rfc"
                  f" IN ({rfcs_str})"
              )
              CONN.commit()
              st.session_state["sel_rfcs_gestion_admin"] = []
              st.success(
                  f"✅ ¡Se actualizaron {cant_seleccionados} prospectos"
                  " correctamente!"
              )
              st.rerun()

      elif opcion == "4. Reporte de Citas y Eficiencia":
        st.header("📈 Reporte de Citas y Asistencias")

        periodo_rep = st.selectbox(
            "Selecciona Periodo de Reporte:",
            ["Diario", "Semanal", "Mensual", "Anual", "Personalizado"],
        )

        if periodo_rep == "Personalizado":
          col_f1, col_f2 = st.columns(2)
          with col_f1:
            fecha_inicio = st.date_input("Fecha Inicio:", value=datetime.today())
          with col_f2:
            fecha_fin = st.date_input("Fecha Fin:", value=datetime.today())
          filtro_fecha = f"fecha BETWEEN '{fecha_inicio}' AND '{fecha_fin}'"
          tele_filtro = st.selectbox(
              "Filtrar por Telefonista/Agente:",
              ["Todas"] + obtener_usuarios_por_rol("Telefonista"),
          )
        else:
          col_f1, col_f2 = st.columns(2)
          with col_f1:
            fecha_rep = st.date_input("Fecha Base:", value=datetime.today())
          with col_f2:
            tele_filtro = st.selectbox(
                "Filtrar por Telefonista/Agente:",
                ["Todas"] + obtener_usuarios_por_rol("Telefonista"),
            )

          if periodo_rep == "Diario":
            filtro_fecha = f"fecha = '{fecha_rep}'"
          elif periodo_rep == "Semanal":
            filtro_fecha = (
                f"fecha BETWEEN date('{fecha_rep}', 'weekday 0', '-6 days') AND"
                f" date('{fecha_rep}', 'weekday 0')"
            )
          elif periodo_rep == "Mensual":
            filtro_fecha = f"strftime('%Y-%m', fecha) = strftime('%Y-%m', '{fecha_rep}')"
          else:
            filtro_fecha = f"strftime('%Y', fecha) = strftime('%Y', '{fecha_rep}')"

        query_citas = f"SELECT * FROM citas WHERE {filtro_fecha}"
        if tele_filtro != "Todas":
          query_citas += f" AND agente = '{tele_filtro}'"

        df_rep = pd.read_sql_query(query_citas, CONN)

        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        total_citas = len(df_rep)
        asistidas = (
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
        pendientes = (
            len(df_rep[df_rep["estado"] == "Pendiente"])
            if not df_rep.empty
            else 0
        )
        efectividad = (
            f"{(asistidas / total_citas * 100):.1f}%"
            if total_citas > 0
            else "0%"
        )

        m1.metric("Total Citas Agendadas", total_citas)
        m2.metric("Citas Asistidas / Atendidas", asistidas)
        m3.metric("Pendientes", pendientes)
        m4.metric("Tasa de Asistencia", efectividad)

        st.markdown("---")
        if df_rep.empty:
          st.info("No hay registros de citas para el periodo seleccionado.")
        else:
          st.subheader(f"Detalle del Reporte ({periodo_rep})")
          html_table = df_rep.to_html(
              classes="custom-table", index=False, escape=False
          )
          st.markdown(html_table, unsafe_allow_html=True)

      elif opcion == "5. Gestión de Usuarios y Roles":
        st.header("👥 Panel de Administración de Usuarios y Fichas")

        tab_crear, tab_editar = st.tabs(
            ["➕ Crear Nuevo Usuario", "✏️ Editar / Restablecer Usuarios"]
        )

        with tab_crear:
          st.subheader("Registrar Nuevo Usuario y Ficha Personal")
          with st.form("form_crear_usuario", clear_on_submit=True):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
              nuevo_usr = st.text_input("Nombre de Usuario (Login) *")
              nuevo_pwd = st.text_input("Contraseña *", type="password")
              nuevo_rol = st.selectbox(
                  "Rol del Sistema", ["Administrador", "Telefonista", "Asesor"]
              )
            with col_u2:
              nombre_per = st.text_input("Nombre(s) Personal")
              apellido_per = st.text_input("Apellidos")
              tel_per = st.text_input("Teléfono Personal")
              dir_per = st.text_input("Dirección")

            btn_guardar_usr = st.form_submit_button(
                "💾 Crear Usuario", use_container_width=True
            )

            if btn_guardar_usr:
              if not nuevo_usr.strip() or not nuevo_pwd.strip():
                st.error("⚠️ Usuario y contraseña son obligatorios.")
              else:
                try:
                  CURSOR.execute(
                      """
                                    INSERT INTO usuarios (usuario, password, rol, nombre_completo, apellido, telefono, direccion) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                      (
                          nuevo_usr.strip(),
                          nuevo_pwd.strip(),
                          nuevo_rol,
                          nombre_per,
                          apellido_per,
                          tel_per,
                          dir_per,
                      ),
                  )
                  CONN.commit()
                  st.success(
                      f"✅ ¡Usuario '{nuevo_usr}' creado exitosamente como"
                      f" {nuevo_rol} con su ficha personal!"
                  )
                except sqlite3.IntegrityError:
                  st.error(
                      "⚠️ El nombre de usuario ya existe. Elige otro por favor."
                  )

        with tab_editar:
          st.subheader("Modificar Fichas, Roles y Contraseñas de Usuarios")
          df_usuarios = pd.read_sql_query(
              """
                SELECT id, usuario, rol, nombre_completo, apellido, telefono, direccion 
                FROM usuarios ORDER BY id ASC
            """,
              CONN,
          )

          if df_usuarios.empty:
            st.info("No hay usuarios registrados.")
          else:
            for _, u_row in df_usuarios.iterrows():
              u_id = u_row["id"]
              u_name = u_row["usuario"]
              u_rol = u_row["rol"]
              u_nomb = u_row["nombre_completo"] or ""
              u_apel = u_row["apellido"] or ""
              u_tele = u_row["telefono"] or ""
              u_dir = u_row["direccion"] or ""

              with st.expander(
                  f"👤 {u_name} | {u_nomb} {u_apel} (Rol: {u_rol})"
              ):
                with st.form(f"form_edit_usr_{u_id}"):
                  col_e1, col_e2 = st.columns(2)
                  with col_e1:
                    edit_nombre = st.text_input(
                        "Nombre de Usuario (Login)",
                        value=u_name,
                        key=f"name_{u_id}",
                    )
                    roles_opciones = ["Administrador", "Telefonista", "Asesor"]
                    idx_rol = (
                        roles_opciones.index(u_rol)
                        if u_rol in roles_opciones
                        else 1
                    )
                    edit_rol = st.selectbox(
                        "Rol",
                        roles_opciones,
                        index=idx_rol,
                        key=f"rol_{u_id}",
                    )
                    edit_pwd = st.text_input(
                        "Nueva Contraseña (en blanco si no cambia)",
                        type="password",
                        key=f"pwd_{u_id}",
                    )
                  with col_e2:
                    edit_nomb = st.text_input(
                        "Nombre(s)", value=u_nomb, key=f"nomb_{u_id}"
                    )
                    edit_apel = st.text_input(
                        "Apellidos", value=u_apel, key=f"apel_{u_id}"
                    )
                    edit_tele = st.text_input(
                        "Teléfono", value=u_tele, key=f"tele_{u_id}"
                    )
                    edit_dir = st.text_input(
                        "Dirección", value=u_dir, key=f"dir_{u_id}"
                    )

                  col_btn_mod, col_btn_del = st.columns(2)
                  with col_btn_mod:
                    submitted_mod = st.form_submit_button(
                        "💾 Guardar Ficha y Cambios", use_container_width=True
                    )
                  with col_btn_del:
                    submitted_del = st.form_submit_button(
                        "🗑️ Eliminar Usuario", use_container_width=True
                    )

                  if submitted_mod:
                    if not edit_nombre.strip():
                      st.error(
                          "El nombre de usuario login no puede estar vacío."
                      )
                    else:
                      if edit_pwd.strip():
                        CURSOR.execute(
                            """
                                            UPDATE usuarios 
                                            SET usuario = ?, password = ?, rol = ?, nombre_completo = ?, apellido = ?, telefono = ?, direccion = ? 
                                            WHERE id = ?
                                        """,
                            (
                                edit_nombre.strip(),
                                edit_pwd.strip(),
                                edit_rol,
                                edit_nomb,
                                edit_apel,
                                edit_tele,
                                edit_dir,
                                u_id,
                            ),
                        )
                      else:
                        CURSOR.execute(
                            """
                                            UPDATE usuarios 
                                            SET usuario = ?, rol = ?, nombre_completo = ?, apellido = ?, telefono = ?, direccion = ? 
                                            WHERE id = ?
                                        """,
                            (
                                edit_nombre.strip(),
                                edit_rol,
                                edit_nomb,
                                edit_apel,
                                edit_tele,
                                edit_dir,
                                u_id,
                            ),
                        )
                      CONN.commit()
                      st.success(
                          f"✅ ¡Ficha y datos de '{edit_nombre}' actualizados"
                          " con éxito!"
                      )
                      st.rerun()

                  if submitted_del:
                    if u_name == "admin":
                      st.error(
                          "⚠️ No se puede eliminar al usuario administrador"
                          " principal."
                      )
                    else:
                      CURSOR.execute(
                          "DELETE FROM usuarios WHERE id = ?", (u_id,)
                      )
                      CONN.commit()
                      st.warning(
                          f"🗑️ Usuario '{u_name}' eliminado correctamente."
                      )
                      st.rerun()

    elif rol == "Telefonista":
      if opcion == "Mis Prospectos y Gestión":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")

        col_busq, col_vacio, col_btn_crear = st.columns([1, 1.8, 1.2])
        with col_busq:
          busqueda_tele = st.text_input("🔎 Buscar en mis prospectos:")
        with col_btn_crear:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          if st.button("➕ Crear Prospecto Nuevo", use_container_width=True):
            modal_crear_prospecto(usuario, rol)

        query_tele = (
            "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza,"
            " dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1,"
            f" estado_tel2, estado_tel3 FROM clientes WHERE telefonista_asignada"
            f" = '{usuario}'"
        )
        if busqueda_tele:
          query_tele += (
              " AND (rfc LIKE '%"
              + busqueda_tele
              + "%' OR nombre LIKE '%"
              + busqueda_tele
              + "%' OR apellido LIKE '%"
              + busqueda_tele
              + "%' OR tel1 LIKE '%"
              + busqueda_tele
              + "%')"
          )

        df_prospectos = pd.read_sql_query(query_tele, CONN)

        if df_prospectos.empty:
          st.info("No tienes prospectos asignados actualmente.")
        else:
          renderizar_bloque_con_tabla(df_prospectos, key_suffix="gestion_tele")

      elif opcion == "Mis Citas Agendadas":
        st.header(f"📅 Agenda Diaria y Actividad ({usuario})")

        col_filtro_t1, col_filtro_t2 = st.columns(2)
        with col_filtro_t1:
          tipo_agenda_sel = st.selectbox(
              "Ver por tipo:",
              [
                  "Citas Agendadas",
                  "Posible Asistencia",
                  "Recados",
                  "Mensajes de Texto",
                  "Todo el Historial",
              ],
          )
        with col_filtro_t2:
          fecha_agenda_sel = st.date_input(
              "Filtrar por Fecha:", value=datetime.today()
          )

        fecha_str_sel = fecha_agenda_sel.strftime("%Y-%m-%d")

        if tipo_agenda_sel in ["Citas Agendadas", "Posible Asistencia"]:
          query_agenda = f"""
                    SELECT fecha as 'Fecha', hora as 'Hora', cliente as 'Cliente', estado as 'Estado', notas as 'Notas'
                    FROM citas WHERE agente = '{usuario}' AND fecha = '{fecha_str_sel}' ORDER BY hora ASC
                """
          df_agenda = pd.read_sql_query(query_agenda, CONN)
          titulo_tabla = f"{tipo_agenda_sel} para el día {fecha_str_sel}"
        else:
          accion_map = {
              "Recados": "Recado",
              "Mensajes de Texto": "Mensaje de texto",
          }
          if tipo_agenda_sel == "Todo el Historial":
            query_agenda = f"""
                        SELECT h.fecha_registro as 'Fecha/Hora', c.nombre || ' ' || c.apellido as 'Cliente', h.accion as 'Acción', h.detalle as 'Detalle'
                        FROM historial_llamadas h
                        JOIN clientes c ON h.rfc_cliente = c.rfc
                        WHERE h.usuario = '{usuario}' AND date(h.fecha_registro) = '{fecha_str_sel}'
                        ORDER BY h.id DESC
                    """
          else:
            acc_val = accion_map[tipo_agenda_sel]
            query_agenda = f"""
                        SELECT h.fecha_registro as 'Fecha/Hora', c.nombre || ' ' || c.apellido as 'Cliente', h.accion as 'Acción', h.detalle as 'Detalle'
                        FROM historial_llamadas h
                        JOIN clientes c ON h.rfc_cliente = c.rfc
                        WHERE h.usuario = '{usuario}' AND h.accion = '{acc_val}' AND date(h.fecha_registro) = '{fecha_str_sel}'
                        ORDER BY h.id DESC
                    """
          df_agenda = pd.read_sql_query(query_agenda, CONN)
          titulo_tabla = f"Registros de {tipo_agenda_sel} para el día {fecha_str_sel}"

        st.markdown(f"### {titulo_tabla}")
        if df_agenda.empty:
          st.info(f"No hay registros de {tipo_agenda_sel} para esta fecha.")
        else:
          html_table = df_agenda.to_html(
              classes="custom-table", index=False, escape=False
          )
          st.markdown(html_table, unsafe_allow_html=True)

    else:
      if opcion == "Mis Prospectos Asignados":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")

        col_busq_a, col_vacio_a, col_btn_crear_a = st.columns([1, 1.8, 1.2])
        with col_busq_a:
          busqueda_asesor_p = st.text_input("🔎 Buscar en mis prospectos:")
        with col_btn_crear_a:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          if st.button("➕ Crear Prospecto Nuevo", use_container_width=True):
            modal_crear_prospecto(usuario, rol)

        query_asesor_prosp = (
            "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza,"
            " dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1,"
            f" estado_tel2, estado_tel3 FROM clientes WHERE telefonista_asignada"
            f" = '{usuario}'"
        )
        if busqueda_asesor_p:
          query_asesor_prosp += (
              " AND (rfc LIKE '%"
              + busqueda_asesor_p
              + "%' OR nombre LIKE '%"
              + busqueda_asesor_p
              + "%' OR apellido LIKE '%"
              + busqueda_asesor_p
              + "%' OR tel1 LIKE '%"
              + busqueda_asesor_p
              + "%')"
          )

        df_prosp_asesor = pd.read_sql_query(query_asesor_prosp, CONN)

        if df_prosp_asesor.empty:
          st.info("No tienes prospectos asignados actualmente.")
        else:
          renderizar_bloque_con_tabla(
              df_prosp_asesor, key_suffix="gestion_asesor"
          )

      elif opcion == "Bolsa de Citas del Día (Asesores)":
        st.header(f"💼 Bolsa de Citas del Día ({usuario})")

        col_b_asesor, col_btn_nuevo_asesor = st.columns([3, 1])
        with col_b_asesor:
          pass
        with col_btn_nuevo_asesor:
          st.markdown(
              "<div style='margin-top: 28px;'></div>", unsafe_allow_html=True
          )
          if st.button("➕ Crear Prospecto Nuevo", use_container_width=True):
            modal_crear_prospecto(usuario, rol)

        fecha_hoy_str = datetime.today().strftime("%Y-%m-%d")
        query_bolsa = f"""
                SELECT id, fecha as 'Fecha', hora as 'Hora', cliente as 'Cliente', telefono as 'Teléfono', estado as 'Estado', notas as 'Notas'
                FROM citas WHERE fecha = '{fecha_hoy_str}' AND (asesor = '{usuario}' OR asesor = 'Sin Asignar')
                ORDER BY hora ASC
            """
        df_bolsa = pd.read_sql_query(query_bolsa, CONN)

        if df_bolsa.empty:
          st.info("No hay citas en la bolsa para el día de hoy.")
        else:
          html_table = df_bolsa.to_html(
              classes="custom-table", index=False, escape=False
          )
          st.markdown(html_table, unsafe_allow_html=True)

      elif opcion == "Mis Registros de Hoy":
        st.header(f"📝 Mis Registros y Actividad de Hoy ({usuario})")

        fecha_hoy_str = datetime.today().strftime("%Y-%m-%d")
        query_reg_hoy = f"""
                SELECT h.fecha_registro as 'Fecha/Hora', c.nombre || ' ' || c.apellido as 'Cliente', h.accion as 'Acción', h.detalle as 'Detalle'
                FROM historial_llamadas h
                JOIN clientes c ON h.rfc_cliente = c.rfc
                WHERE h.usuario = '{usuario}' AND date(h.fecha_registro) = '{fecha_hoy_str}'
                ORDER BY h.id DESC
            """
        df_reg_hoy = pd.read_sql_query(query_reg_hoy, CONN)

        if df_reg_hoy.empty:
          st.info("No tienes registros en el historial para el día de hoy.")
        else:
          html_table = df_reg_hoy.to_html(
              classes="custom-table", index=False, escape=False
          )
          st.markdown(html_table, unsafe_allow_html=True)

      elif opcion == "📊 Reportes de Citas y Asistencias":
        st.header("📊 Reportes de Asesor")
        periodo_asesor = st.selectbox(
            "Periodo:", ["Diario", "Semanal", "Mensual"]
        )
        fecha_asesor_rep = st.date_input(
            "Fecha Base:", value=datetime.today(), key="f_asesor_rep"
        )
        fecha_rep_str = fecha_asesor_rep.strftime("%Y-%m-%d")

        query_rep_asesor = f"""
                SELECT * FROM citas WHERE agente = '{usuario}' AND fecha = '{fecha_rep_str}'
            """
        df_rep_asesor = pd.read_sql_query(query_rep_asesor, CONN)

        m1, m2 = st.columns(2)
        m1.metric("Mis Citas del Día", len(df_rep_asesor))
        asistidas_a = (
            len(
                df_rep_asesor[
                    df_rep_asesor["estado"].str.contains(
                        "Asistida", case=False, na=False
                    )
                ]
            )
            if not df_rep_asesor.empty
            else 0
        )
        m2.metric("Citas Asistidas", asistidas_a)

        if not df_rep_asesor.empty:
          html_table = df_rep_asesor.to_html(
              classes="custom-table", index=False, escape=False
          )
          st.markdown(html_table, unsafe_allow_html=True)
        else:
          st.info("No hay citas registradas para este filtro.")
