import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import db
from categories import CATEGORY_LIST, subcategories_for

st.set_page_config(page_title="Split Casal", page_icon="💰", layout="centered")
db.init_db()

st.title("💰 Split Casal")


# ---------- GESTÃO DE GRUPOS ----------

groups = db.get_groups()

with st.expander("➕ Criar novo grupo"):
    new_group_name = st.text_input("Nome do grupo", key="new_group_name", placeholder="Ex: Casa, Viagem com amigos...")
    new_group_members = st.text_input(
        "Participantes (separados por vírgula)",
        key="new_group_members",
        placeholder="Ex: Ivan, Esposa",
    )
    if st.button("Criar grupo"):
        members = [m.strip() for m in new_group_members.split(",") if m.strip()]
        if not new_group_name:
            st.error("Dê um nome ao grupo.")
        elif len(members) < 2:
            st.error("Informe pelo menos 2 participantes.")
        else:
            new_id = db.create_group(new_group_name, members)
            st.success(f"Grupo '{new_group_name}' criado!")
            st.session_state.current_group_id = new_id
            st.rerun()

if not groups:
    st.info("Nenhum grupo criado ainda. Crie o primeiro grupo acima para começar.")
    st.stop()

group_names = {g["id"]: g["name"] for g in groups}
if "current_group_id" not in st.session_state or st.session_state.current_group_id not in group_names:
    st.session_state.current_group_id = groups[0]["id"]

selected_id = st.selectbox(
    "Grupo ativo",
    options=list(group_names.keys()),
    format_func=lambda gid: group_names[gid],
    index=list(group_names.keys()).index(st.session_state.current_group_id),
)
st.session_state.current_group_id = selected_id
current_group = db.get_group(selected_id)
PARTICIPANTS = current_group["members"]

st.caption(f"Participantes: {', '.join(PARTICIPANTS)}")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Saldo", "📋 Histórico", "➕ Novo gasto", "🌐 Consolidado"])


# ---------- HELPERS ----------

def date_range_filter(key_prefix):
    """Filtro de período reutilizável. Padrão: ano corrente inteiro."""
    today = date.today()
    default_start = date(today.year, 1, 1)
    default_end = date(today.year, 12, 31)

    period = st.radio(
        "Período",
        ["Ano corrente", "Personalizado"],
        horizontal=True,
        key=f"{key_prefix}_period_mode",
    )
    if period == "Ano corrente":
        return default_start, default_end
    else:
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("De", value=default_start, key=f"{key_prefix}_start")
        with c2:
            end = st.date_input("Até", value=default_end, key=f"{key_prefix}_end")
        return start, end


def build_long_df(df):
    """Expande splits em linhas por pessoa, pra facilitar agregações."""
    rows = []
    for _, r in df.iterrows():
        for person, val in r["splits"].items():
            rows.append({
                "category": r["category"],
                "subcategory": r["subcategory"],
                "person": person,
                "value": val,
            })
    return pd.DataFrame(rows)


# ---------- TAB 1: SALDO ----------
with tab1:
    date_from, date_to = date_range_filter("saldo")
    balance = db.compute_balance(PARTICIPANTS, group_id=selected_id, date_from=date_from, date_to=date_to)

    if balance["total_spent"] == 0:
        st.info("Nenhum gasto lançado nesse período.")
    else:
        st.metric("Total gasto no período", f"R$ {balance['total_spent']:.2f}")

        cols = st.columns(len(PARTICIPANTS))
        for i, p in enumerate(PARTICIPANTS):
            with cols[i]:
                st.metric(f"Pago por {p}", f"R$ {balance['total_paid'][p]:.2f}")
                st.caption(f"Parte justa: R$ {balance['fair_share'][p]:.2f}")

        st.divider()
        if "equilibradas" in (balance["settlement"] or ""):
            st.success(balance["settlement"])
        else:
            st.warning(f"**{balance['settlement']}**")

        st.divider()
        st.subheader("Gastos por categoria")
        st.caption("Clique numa barra para ver o detalhamento por subcategoria")

        df = db.get_expenses(group_id=selected_id, date_from=date_from, date_to=date_to)
        long_df = build_long_df(df)

        if "drill_category" not in st.session_state:
            st.session_state.drill_category = None

        if st.session_state.drill_category is None:
            agg = long_df.groupby(["category", "person"], as_index=False)["value"].sum()
            fig = px.bar(
                agg, x="category", y="value", color="person",
                barmode="stack", labels={"value": "R$", "category": "Categoria", "person": "Pessoa"},
            )
            fig.update_layout(clickmode="event+select")
            event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="cat_chart")

            if event and event.get("selection", {}).get("points"):
                clicked_cat = event["selection"]["points"][0].get("x")
                if clicked_cat:
                    st.session_state.drill_category = clicked_cat
                    st.rerun()
        else:
            cat = st.session_state.drill_category
            st.markdown(f"**Detalhamento: {cat}**")
            if st.button("← Voltar para todas as categorias"):
                st.session_state.drill_category = None
                st.rerun()

            sub_df = long_df[long_df["category"] == cat]
            if sub_df.empty:
                st.info("Sem dados de subcategoria para essa categoria no período.")
            else:
                agg_sub = sub_df.groupby(["subcategory", "person"], as_index=False)["value"].sum()
                fig_sub = px.bar(
                    agg_sub, x="subcategory", y="value", color="person",
                    barmode="stack", labels={"value": "R$", "subcategory": "Subcategoria", "person": "Pessoa"},
                )
                st.plotly_chart(fig_sub, use_container_width=True)


# ---------- TAB 2: HISTÓRICO ----------
with tab2:
    date_from, date_to = date_range_filter("hist")
    filter_cat = st.selectbox("Categoria", ["Todas"] + CATEGORY_LIST, key="hist_cat_filter")
    cat_param = None if filter_cat == "Todas" else filter_cat

    df = db.get_expenses(group_id=selected_id, date_from=date_from, date_to=date_to, category=cat_param)

    if df.empty:
        st.info("Nenhum gasto encontrado com esses filtros.")
    else:
        st.caption(f"{len(df)} gasto(s) encontrado(s) • Total: R\\$ {df['amount'].sum():.2f}")
        for _, row in df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                payers_str = ", ".join(f"{k} (R\\$ {v:.2f})" for k, v in row["payers"].items())
                splits_str = ", ".join(f"{k}: R\\$ {v:.2f}" for k, v in row["splits"].items())
                with c1:
                    st.write(f"**{row['description']}**")
                    st.caption(f"{row['category']} › {row['subcategory']} • {row['expense_date']}")
                    st.caption(f"Pago por: {payers_str}")
                with c2:
                    st.write(f"R$ {row['amount']:.2f}")
                    st.caption(f"Divisão: {splits_str}")
                with c3:
                    if st.button("🗑️", key=f"del_{row['id']}"):
                        db.delete_expense(row["id"])
                        st.rerun()


# ---------- TAB 3: NOVO GASTO ----------
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input("Data", value=date.today())
        amount = st.number_input("Valor total (R$)", min_value=0.0, step=1.0, format="%.2f")
    with col2:
        category = st.selectbox("Categoria", CATEGORY_LIST)
        subcategory = st.selectbox("Subcategoria", subcategories_for(category))

    description = st.text_input("Descrição", placeholder="Ex: Mercado do mês, Uber, Restaurante...")

    st.divider()

    # ---------- QUEM PAGOU ----------
    st.markdown("**Quem pagou**")
    multi_payer = st.checkbox("Mais de uma pessoa pagou")

    payers = {}
    if not multi_payer:
        payer = st.selectbox("Pagou", PARTICIPANTS, key="single_payer")
        payers = {payer: amount}
    else:
        st.caption("Informe quanto cada um pagou (a soma precisa bater com o valor total)")
        cols = st.columns(len(PARTICIPANTS))
        for i, p in enumerate(PARTICIPANTS):
            with cols[i]:
                payers[p] = st.number_input(f"{p} pagou", min_value=0.0, step=1.0, format="%.2f", key=f"payer_{p}")
        paid_sum = sum(payers.values())
        diff = amount - paid_sum
        if amount > 0 and abs(diff) > 0.01:
            if diff > 0:
                st.warning(f"Faltam R\\$ {diff:.2f} para o valor total")
            else:
                st.warning(f"Passou R\\$ {abs(diff):.2f} do valor total")

    st.divider()

    # ---------- DIVISÃO ----------
    st.markdown("**Divisão**")
    n_participants = len(PARTICIPANTS)
    split_mode = st.radio("Como dividir", [f"Igual entre todos ({n_participants})", "Custom"], horizontal=True, label_visibility="collapsed")

    splits = {}
    if split_mode.startswith("Igual"):
        splits = {p: round(amount / n_participants, 2) for p in PARTICIPANTS}
    else:
        custom_unit = st.radio("Definir em", ["Valores (R$)", "Porcentagem (%)"], horizontal=True)
        cols = st.columns(n_participants)
        if custom_unit == "Valores (R$)":
            for i, p in enumerate(PARTICIPANTS):
                with cols[i]:
                    splits[p] = st.number_input(f"{p} deve", min_value=0.0, step=1.0, format="%.2f", key=f"split_val_{p}")
            split_sum = sum(splits.values())
            split_diff = amount - split_sum
            if amount > 0 and abs(split_diff) > 0.01:
                if split_diff > 0:
                    st.warning(f"Faltam R\\$ {split_diff:.2f} para o valor total")
                else:
                    st.warning(f"Passou R\\$ {abs(split_diff):.2f} do valor total")
        else:
            pcts = {}
            default_pct = round(100 / n_participants, 2)
            for i, p in enumerate(PARTICIPANTS):
                with cols[i]:
                    pcts[p] = st.number_input(f"{p} (%)", min_value=0.0, max_value=100.0, step=1.0, value=default_pct, key=f"split_pct_{p}")
            pct_sum = sum(pcts.values())
            pct_diff = 100 - pct_sum
            if abs(pct_diff) > 0.01:
                if pct_diff > 0:
                    st.warning(f"Faltam {pct_diff:.0f}% para completar 100%")
                else:
                    st.warning(f"Passou {abs(pct_diff):.0f}% de 100%")
            splits = {p: round(amount * pcts[p] / 100, 2) for p in PARTICIPANTS}

    notes = st.text_input("Observações (opcional)")

    st.divider()
    if st.button("Salvar gasto", use_container_width=True, type="primary"):
        errors = []
        if not description:
            errors.append("Preencha a descrição.")
        if amount <= 0:
            errors.append("O valor total precisa ser maior que zero.")
        if multi_payer and abs(sum(payers.values()) - amount) > 0.01:
            errors.append("A soma de quem pagou não bate com o valor total.")
        if abs(sum(splits.values()) - amount) > 0.01:
            errors.append("A soma da divisão não bate com o valor total.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            db.add_expense(selected_id, expense_date, description, category, subcategory, amount, payers, splits, notes)
            st.success(f"Gasto de R$ {amount:.2f} salvo!")
            st.rerun()


# ---------- TAB 4: CONSOLIDADO ----------
with tab4:
    st.caption("Visão de todos os grupos, com a quebra do saldo em cada um")
    date_from, date_to = date_range_filter("consol")

    total_all = 0.0
    rows_summary = []
    for g in groups:
        g_balance = db.compute_balance(g["members"], group_id=g["id"], date_from=date_from, date_to=date_to)
        total_all += g_balance["total_spent"]
        rows_summary.append({
            "Grupo": g["name"],
            "Participantes": ", ".join(g["members"]),
            "Total gasto": g_balance["total_spent"],
            "Saldo": g_balance["settlement"] or "—",
        })

    st.metric("Total gasto em todos os grupos", f"R$ {total_all:.2f}")
    st.divider()

    for row in rows_summary:
        with st.container(border=True):
            st.markdown(f"**{row['Grupo']}**")
            st.caption(row["Participantes"])
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("Total gasto", f"R$ {row['Total gasto']:.2f}")
            with c2:
                st.write("Saldo:")
                if "equilibradas" in row["Saldo"]:
                    st.success(row["Saldo"])
                elif row["Saldo"] == "—":
                    st.info("Sem gastos no período")
                else:
                    st.warning(row["Saldo"])
