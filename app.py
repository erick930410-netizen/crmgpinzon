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

  # Recuperar o mantener la página actual en session_state para que no salte
  key_pag_state = f"pag_idx_guardada_{key_suffix}"
  if key_pag_state not in st.session_state:
    st.session_state[key_pag_state] = 1

  if tot_filt > cant_por_pagina:
    # Asegurar que la página guardada no rebase el total
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
