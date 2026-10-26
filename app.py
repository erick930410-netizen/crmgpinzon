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

    st.sidebar.info("💻 Modo Pruebas Local (SQLite)")
except Exception as e:
  try:
    db_url = "sqlite:///crm_local_test.db"
    engine = create_engine(db_url, connect_args={"timeout": 30}, poolclass=NullPool)
  except Exception as inner_e:
    st.error(f"⚠️ Error crítico de conexión: {e} / {inner_e}")
    st.stop()

ES_SQLITE = engine.name == "sqlite"
PH = "?" if ES_SQLITE else "%s"
ID_SERIAL = "INTEGER PRIMARY KEY AUTOINCREMENT" if ES_SQLITE else "SERIAL PRIMARY KEY"

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
  if pd.isna(val) or val is None: return ""
  s = str(val).strip()
  if not s or s.lower() == "nan" or s == "0": return ""
  return s.split(" ")[0] if " " in s else s

def parsear_a_date(val):
  s = limpiar_fecha_str(val)
  if not s: return obtener_ahora_mexico().date()
  for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
    try: return datetime.strptime(s, fmt).date()
    except ValueError: continue
  return obtener_ahora_mexico().date()

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
      with engine.begin() as conn_sql: conn_sql.exec_driver_sql(q)
    except Exception: pass

inicializar_base_de_datos()

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
  for r in roles: usuarios.extend(obtener_usuarios_por_rol(r))
  return sorted(list(set(usuarios)))

def renderizar_bloque_con_tabla(df_entrada, key_suffix, ocultar_tels=False):
  df = df_entrada.copy()
  if ocultar_tels:
    for col_tel in ["tel1", "tel2", "tel3", "telefono", "Teléfono", "tel_opcional"]:
      if col_tel in df.columns: df[col_tel] = "🔒 ***-ocultos***"

  cant_por_pagina = 100
  sel_prev = st.session_state.get(f"sel_rfcs_{key_suffix}", [])

  if "Seleccionar" not in df.columns:
    df.insert(0, "Seleccionar", False)

  st.session_state["lista_rfcs_navegacion"] = df["rfc"].tolist()
  tot_filt = len(df)
  tot_pags = max(1, (tot_filt - 1) // cant_por_pagina + 1) if tot_filt > 0 else 1

  key_pag_state = f"pag_idx_guardada_{key_suffix}"
  if key_pag_state not in st.session_state: st.session_state[key_pag_state] = 1

  if tot_filt > cant_por_pagina:
    if st.session_state[key_pag_state] > tot_pags: st.session_state[key_pag_state] = tot_pags
    p_act = st.selectbox(f"📄 Páginas (Bloques de 100 de {tot_filt} coincidentes):", range(1, tot_pags + 1), index=st.session_state[key_pag_state] - 1, key=f"pag_num_{key_suffix}")
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

  editor_res = st.data_editor(df_a_mostrar, key=f"tabla_editor_{key_suffix}", use_container_width=True, hide_index=True, column_config=column_config, disabled=cols_dis)
  sel_actual = editor_res[editor_res["Seleccionar"] == True]["rfc"].tolist()
  otros = [r for r in st.session_state.get(f"sel_rfcs_{key_suffix}", []) if r not in df_a_mostrar["rfc"].tolist()]
  final_sel = list(set(otros + sel_actual))

  if final_sel != st.session_state.get(f"sel_rfcs_{key_suffix}", []):
    st.session_state[f"sel_rfcs_{key_suffix}"] = final_sel
    st.rerun()

  return editor_res

for k, v in [("usuario_logueado", None), ("rol", None), ("prospecto_editar_rfc", None), ("lista_rfcs_navegacion", []), ("seccion_activa", None)]:
  if k not in st.session_state: st.session_state[k] = v

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
      else: st.error("⚠️ Usuario o contraseña incorrectos")

else:
  rol, usuario = st.session_state["rol"], st.session_state["usuario_logueado"]
  opciones = (
      ["1. Cargar Base General", "2. Ver Banco de Prospectos", "3. Gestión y Asignación de Prospectos", "4. Reporte de Citas y Actividad", "5. Gestión de Usuarios y Roles", "6. Dashboard y Estadísticas de Asesores"]
      if rol == "Administrador"
      else (["Mis Prospectos y Gestión", "Mis Citas Agendadas"] if rol == "Telefonista" else (["Mis Prospectos Asignados (Depuración BD)"] if rol == "Base de Datos" else ["Prospectos", "Bolsa de Citas del Día (Asesores)", "Mis Registros de Hoy", "📊 Reportes de Citas y Asistencias"]))
  )

  if st.session_state["seccion_activa"] is None or st.session_state["seccion_activa"] not in opciones:
    st.session_state["seccion_activa"] = opciones[0]

  col_nav1, col_nav2, col_nav3 = st.columns([3, 3, 1])
  with col_nav1:
    seccion_elegida = st.selectbox("", opciones, index=opciones.index(st.session_state["seccion_activa"]), key="selector_navegacion_directa", label_visibility="collapsed")
    if seccion_elegida != st.session_state["seccion_activa"]:
      st.session_state["seccion_activa"] = seccion_elegida
      st.session_state["prospecto_editar_rfc"] = None
      st.rerun()

  with col_nav2:
    st.markdown(f"<div style='padding-top: 10px;'>👤 <b>Usuario:</b> <code>{usuario}</code> | 🛡️ <b>Rol:</b> <code>{rol}</code></div>", unsafe_allow_html=True)

  with col_nav3:
    if st.button("🚪 Salir", use_container_width=True):
      for k in ["usuario_logueado", "rol", "prospecto_editar_rfc", "seccion_activa"]: st.session_state[k] = None
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
      st.error("No se encontró el prospecto.")
      st.session_state["prospecto_editar_rfc"] = None
      st.rerun()

    def ejecutar_guardado_y_salto(destino):
      # VALIDACIÓN OBLIGATORIA DE MONTO PARA ASESORES
      if rol == "Asesor":
        accion_sel = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
        if accion_sel == "Cierre / Actualización":
          monto_val = st.session_state.get(f"monto_act_{rfc_actual}", "").strip()
          if not monto_val or monto_val == "0":
            st.error("⚠️ ¡OBLIGATORIO! Debes ingresar el Monto de la Actualización para registrar un Cierre.")
            return False

      rfc_limpio = str(st.session_state.get(f"frfc_{rfc_actual}", row[0])).strip().upper()
      n_nombre = st.session_state.get(f"fn_{rfc_actual}", row[1])
      n_apellido = st.session_state.get(f"fa_{rfc_actual}", row[2])
      n_t1, n_t2, n_t3 = row[3], row[4], row[5] if rol in ["Base de Datos", "Asesor"] else (st.session_state.get(f"ftel1_{rfc_actual}", row[3]), st.session_state.get(f"ftel2_{rfc_actual}", row[4]), st.session_state.get(f"ftel3_{rfc_actual}", row[5]))
      
      n_tel_opcional_input = st.session_state.get(f"ftel_opcional_{rfc_actual}", "").strip() if rol == "Asesor" else ""
      n_tel_opcional = n_tel_opcional_input if n_tel_opcional_input else (row[19] or "")

      n_sector = st.session_state.get(f"fs_{rfc_actual}", row[6])
      n_poliza = st.session_state.get(f"fp_{rfc_actual}", row[7])
      n_div = st.session_state.get(f"fdiv_{rfc_actual}", parsear_a_date(row[8]))
      n_asig_f = st.session_state.get(f"fulfasig_{rfc_actual}", parsear_a_date(row[9]))
      n_mov = st.session_state.get(f"ffum_{rfc_actual}", parsear_a_date(row[11]))
      
      obs_asesor_previas = row[13] or ""
      input_nueva_obs_asesor = st.session_state.get(f"fobs_asesor_{rfc_actual}", "")
      
      n_obs_asesor = obs_asesor_previas
      detalle_formateado_historial = ""
      estatus_general = row[15]
      usuario_asignado_final = usuario if rol == "Asesor" else row[14]

      if rol == "Asesor":
        f_hoy_dt = obtener_ahora_mexico()
        f_hoy_formato = f_hoy_dt.strftime("%Y/%m/%d")
        accion_sel = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
        
        if accion_sel != "-- Seleccionar Acción --":
          extra_detalle = []
          if accion_sel == "Cierre / Actualización":
            monto_act = st.session_state.get(f"monto_act_{rfc_actual}", "").strip()
            extra_detalle.append(f"Monto Act: ${monto_act}")
            hizo_serv = st.session_state.get(f"chk_servicio_{rfc_actual}", False)
            if hizo_serv:
              tipo_s = st.session_state.get(f"tipo_serv_{rfc_actual}", "Dividendos")
              extra_detalle.append(f"Servicio: {tipo_s}")
          elif accion_sel == "Solo Servicio":
            tipo_s = st.session_state.get(f"tipo_serv_solo_{rfc_actual}", "Dividendos")
            extra_detalle.append(f"Servicio: {tipo_s}")

          str_extra = " | ".join(extra_detalle)
          str_tel = f" [Tel Opc: {n_tel_opcional}]" if n_tel_opcional else ""
          str_completo_detalle = f"{str_extra} - {input_nueva_obs_asesor.strip()}" if str_extra and input_nueva_obs_asesor.strip() else (str_extra or input_nueva_obs_asesor.strip())

          if str_completo_detalle:
            obs_formateada = f"({f_hoy_formato} - {usuario}) [{accion_sel}]{str_tel} {str_completo_detalle}"
            n_obs_asesor = f"{obs_asesor_previas}\n{obs_formateada}".strip() if obs_asesor_previas else obs_formateada
            detalle_formateado_historial = str_completo_detalle

          estatus_general = f"Atendido ({accion_sel})"

      with engine.begin() as conn_sql:
        if ES_SQLITE:
          conn_sql.exec_driver_sql(
              f"INSERT OR REPLACE INTO clientes (rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})",
              (rfc_limpio, n_nombre, n_apellido, n_t1, n_t2, n_t3, f"{n_t1}/{n_t2}/{n_t3}", n_tel_opcional, n_sector, n_poliza, str(n_div), str(n_asig_f), calcular_edad_desde_rfc(rfc_limpio), str(n_mov), row[12], n_obs_asesor, usuario_asignado_final, estatus_general),
          )
        else:
          conn_sql.exec_driver_sql(
              f"INSERT INTO clientes (rfc, nombre, apellido, tel1, tel2, tel3, telefono, tel_opcional, sector, poliza, dividendos, ult_fecha_asignacion, edad, fecha_ult_mov, observaciones_tel, observaciones_asesor, telefonista_asignada, estatus) VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH}) ON CONFLICT (rfc) DO UPDATE SET observaciones_asesor = EXCLUDED.observaciones_asesor, estatus = EXCLUDED.estatus, telefonista_asignada = EXCLUDED.telefonista_asignada",
              (rfc_limpio, n_nombre, n_apellido, n_t1, n_t2, n_t3, f"{n_t1}/{n_t2}/{n_t3}", n_tel_opcional, n_sector, n_poliza, str(n_div), str(n_asig_f), calcular_edad_desde_rfc(rfc_limpio), str(n_mov), row[12], n_obs_asesor, usuario_asignado_final, estatus_general),
          )

        if rol == "Asesor" and detalle_formateado_historial:
          accion_sel = st.session_state.get(f"accion_asesor_{rfc_actual}", "-- Seleccionar Acción --")
          ahora_local = obtener_ahora_mexico().strftime("%Y-%m-%d %H:%M:%S")
          conn_sql.exec_driver_sql(
              f"INSERT INTO historial_llamadas (rfc_cliente, usuario, accion, detalle, fecha_registro) VALUES ({PH}, {PH}, {PH}, {PH}, {PH})",
              (rfc_actual, usuario, accion_sel, detalle_formateado_historial, ahora_local),
          )

      if destino == "siguiente" and pos_actual < total_prospectos - 1:
        st.session_state["prospecto_editar_rfc"] = lista_rfcs[pos_actual + 1]
      elif destino == "anterior" and pos_actual > 0:
        st.session_state["prospecto_editar_rfc"] = lista_rfcs[pos_actual - 1]
      else:
        st.session_state["prospecto_editar_rfc"] = None
      st.success("💾 ¡Guardado correctamente!")
      st.rerun()

    col_top1, col_nav_ant, col_nav_sig, col_top2 = st.columns([2.2, 0.6, 0.6, 1.5])
    with col_top1: st.caption(f"📍 Registro **{pos_actual + 1} de {total_prospectos}**")
    with col_nav_ant:
      if st.button("⬅️", use_container_width=True, key="f_ant"): ejecutar_guardado_y_salto("anterior")
    with col_nav_sig:
      if st.button("➡️", use_container_width=True, key="f_sig"): ejecutar_guardado_y_salto("siguiente")
    with col_top2:
      if st.button("❌ Cerrar", use_container_width=True, key="c_ficha"): ejecutar_guardado_y_salto("cerrar")

    st.markdown("### 👤 Ficha del Prospecto")
    st.text_input("RFC", value=str(row[0] or ""), key=f"frfc_{rfc_actual}")
    st.text_input("Nombre(s)", value=str(row[1] or ""), key=f"fn_{rfc_actual}")
    st.text_input("Apellidos", value=str(row[2] or ""), key=f"fa_{rfc_actual}")
    st.text_input("Dependencia", value=str(row[6] or ""), key=f"fs_{rfc_actual}")
    st.text_input("Póliza", value=str(row[7] or ""), key=f"fp_{rfc_actual}")

    if rol == "Asesor":
      st.markdown("---")
      st.markdown("### 🎯 Acción / Resultado del Asesor")
      accion_asesor = st.selectbox(
          "Selecciona el resultado *:",
          ["-- Seleccionar Acción --", "Cierre / Actualización", "Solo Servicio", "No Quiso Nada", "Lo Va a Pensar", "Regresa Después"],
          key=f"accion_asesor_{rfc_actual}",
      )

      if accion_asesor == "Cierre / Actualización":
        st.text_input("💰 Monto de la Actualización (OBLIGATORIO) *:", key=f"monto_act_{rfc_actual}", placeholder="Ej. 15000")
        hizo_servicio_cierre = st.checkbox("¿También se le hizo servicio?", key=f"chk_servicio_{rfc_actual}")
        if hizo_servicio_cierre:
          st.selectbox("Tipo de servicio:", ["Dividendos", "Cambio RFC", "Cambio Beneficiarios", "Otros"], key=f"tipo_serv_{rfc_actual}")

      elif accion_asesor == "Solo Servicio":
        st.selectbox("Tipo de servicio:", ["Dividendos", "Cambio RFC", "Cambio Beneficiarios", "Otros"], key=f"tipo_serv_solo_{rfc_actual}")

      st.text_area("Observaciones del Asesor", value=str(row[13] or ""), key=f"fobs_asesor_{rfc_actual}")

    st.markdown("---")
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
      if st.button("⬅️ Guardar y Anterior", key=f"b_ant_{rfc_actual}"): ejecutar_guardado_y_salto("anterior")
    with cb2:
      if st.button("💾 Guardar y Cerrar", key=f"b_cer_{rfc_actual}"): ejecutar_guardado_y_salto("cerrar")
    with cb3:
      if st.button("💾 Guardar y Siguiente ➡", key=f"b_sig_{rfc_actual}"): ejecutar_guardado_y_salto("siguiente")

  else:
    if rol == "Asesor":
      if opcion == "Prospectos":
        st.header("🌐 Banco General de Prospectos (Vista Asesor)")
        busq_a = st.text_input("🔎 Buscar por RFC, Nombre, Apellido o Póliza:")
        q_a = "SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus FROM clientes"
        params_a = []
        if busq_a:
          if ES_SQLITE: q_a += " WHERE (rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR poliza LIKE ?)"
          else: q_a += " WHERE (rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR poliza ILIKE %s)"
          pa = f"%{busq_a}%"
          params_a = [pa, pa, pa, pa]

        q_a += " ORDER BY fecha_creacion DESC LIMIT 1000"
        df_pa = pd.read_sql(q_a, con=engine, params=tuple(params_a) if params_a else None)
        if df_pa.empty: st.info("No se encontraron prospectos.")
        else: renderizar_bloque_con_tabla(df_pa, key_suffix="banco_general_asesor", ocultar_tels=True)
      else:
        st.header(f"Sección: {opcion}")
    else:
      st.header(f"Panel {rol} - {opcion}")
