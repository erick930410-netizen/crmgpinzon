elif rol == "Telefonista":
      if opcion == "Mis Prospectos y Gestión":
        st.header(f"📞 Mis Prospectos Asignados ({usuario})")
        col_busq_tele, col_pop_tele = st.columns([2.5, 1.5])
        with col_busq_tele:
          busqueda_tele = st.text_input("🔎 Buscar por Nombre, RFC o Póliza:")
        with col_pop_tele:
          st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
          with st.popover("⚙️ Filtros Avanzados y Reintentos"):
            st.markdown("##### 📞 Estatus de Llamada (Reintentos)")
            filtro_estatus_tel_tele = st.selectbox(
                "Filtrar por estatus de llamada:",
                ["Todos los estatus", "🔁 No Contesta / Buzón (Segundo Toque)", "Sin marcar", "Válido / Contesta", "Número Erróneo / Malo"],
                key="filtro_estatus_tel_tele_sel"
            )
            st.markdown("---")
            st.markdown("##### 📅 Fecha Específica de Asignación")
            filtrar_fa_tele = st.checkbox("Filtrar por esta fecha", key="f_asig_hab_tele")
            fa_tele_esp = st.date_input("Fecha Asignación:", value=obtener_ahora_mexico().date(), key="fa_tele_esp")

        q_t = f"""
            SELECT rfc, nombre, apellido, tel1, tel2, tel3, sector, poliza, dividendos, ult_fecha_asignacion, edad, estatus, estado_tel1, estado_tel2, estado_tel3 
            FROM clientes WHERE telefonista_asignada = {PH}
        """
        params_t = [usuario]
        conds_t = []

        if filtro_estatus_tel_tele != "Todos los estatus":
          if "No Contesta" in filtro_estatus_tel_tele:
            like_str = "%No Contesta%"
            conds_t.append(
                "(estado_tel1 = 'No Contesta / Buzón' OR estado_tel2 = 'No Contesta / Buzón' OR estado_tel3 = 'No Contesta / Buzón' OR observaciones_tel LIKE ?)"
                if ES_SQLITE
                else "(estado_tel1 = 'No Contesta / Buzón' OR estado_tel2 = 'No Contesta / Buzón' OR estado_tel3 = 'No Contesta / Buzón' OR observaciones_tel ILIKE %s)"
            )
            params_t.append(like_str)
          else:
            val_busq_est = filtro_estatus_tel_tele
            conds_t.append(
                "(estado_tel1 = ? OR estado_tel2 = ? OR estado_tel3 = ?)"
                if ES_SQLITE
                else "(estado_tel1 = %s OR estado_tel2 = %s OR estado_tel3 = %s)"
            )
            params_t.extend([val_busq_est] * 3)

        if filtrar_fa_tele:
          conds_t.append("ult_fecha_asignacion = ?" if ES_SQLITE else "ult_fecha_asignacion = %s")
          params_t.append(str(fa_tele_esp))

        if busqueda_tele:
          if ES_SQLITE:
            conds_t.append("(rfc LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR poliza LIKE ?)")
          else:
            conds_t.append("(rfc ILIKE %s OR nombre ILIKE %s OR apellido ILIKE %s OR poliza ILIKE %s)")
          pt = f"%{busqueda_tele}%"
          params_t.extend([pt, pt, pt, pt])

        if conds_t:
          q_t += " AND " + " AND ".join(conds_t)

        df_p = pd.read_sql(q_t, con=engine, params=tuple(params_t))
