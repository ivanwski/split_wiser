"""
Camada de dados -- Supabase (Postgres) exclusivamente.

Requer st.secrets["supabase"]["url"] e st.secrets["supabase"]["key"]
configurados (veja .streamlit/secrets.toml.example). Sem esses secrets,
o app para com um erro claro em vez de cair silenciosamente para outro banco.

Modelo de dados (estilo Splitwise, com grupos):
- groups: {id, name, members: [nomes]}
- expenses: pertencem a um group_id
  - payers: dict {nome: valor_pago}
  - splits: dict {nome: valor_devido} (soma bate com o valor total)
  - category / subcategory: ver categories.py
"""
import streamlit as st
from supabase import create_client


def _get_supabase_secrets():
    try:
        return st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]
    except Exception:
        st.error(
            "Credenciais do Supabase não encontradas. Configure `.streamlit/secrets.toml` "
            "com `[supabase] url = ...` e `key = ...` (veja secrets.toml.example)."
        )
        st.stop()


@st.cache_resource
def get_supabase_client():
    url, key = _get_supabase_secrets()
    return create_client(url, key)


supabase = get_supabase_client()


# ---------------- API pública: grupos ----------------

def init_db():
    # Tabelas já existem via supabase_schema.sql -- nada a fazer aqui.
    pass


def create_group(name: str, members: list):
    result = supabase.table("groups").insert({"name": name, "members": members}).execute()
    return result.data[0]["id"] if result.data else None


def get_groups():
    """Retorna lista de dicts: {id, name, members: [nomes]}"""
    result = supabase.table("groups").select("*").order("id").execute()
    return result.data


def get_group(group_id):
    for g in get_groups():
        if g["id"] == group_id:
            return g
    return None


def update_group_members(group_id, members: list):
    supabase.table("groups").update({"members": members}).eq("id", group_id).execute()


# ---------------- API pública: despesas ----------------

def add_expense(group_id, expense_date, description, category, subcategory, amount, payers: dict, splits: dict, notes=""):
    supabase.table("expenses").insert({
        "group_id": group_id,
        "expense_date": str(expense_date),
        "description": description,
        "category": category,
        "subcategory": subcategory,
        "amount": amount,
        "payers": payers,
        "splits": splits,
        "notes": notes,
    }).execute()


def get_expenses(group_id=None, date_from=None, date_to=None, category=None, limit=None):
    """
    group_id: filtra por grupo específico (None = todos os grupos, usado na visão consolidada)
    date_from / date_to: objetos date ou string 'YYYY-MM-DD' (inclusive)
    category: filtra por categoria específica (opcional)
    """
    import pandas as pd

    query = supabase.table("expenses").select("*")
    if group_id is not None:
        query = query.eq("group_id", group_id)
    if date_from:
        query = query.gte("expense_date", str(date_from))
    if date_to:
        query = query.lte("expense_date", str(date_to))
    if category:
        query = query.eq("category", category)
    query = query.order("expense_date", desc=True).order("id", desc=True)
    if limit:
        query = query.limit(limit)
    result = query.execute()
    df = pd.DataFrame(result.data)

    if not df.empty:
        df["expense_date"] = pd.to_datetime(df["expense_date"]).dt.date
    return df


def delete_expense(expense_id):
    supabase.table("expenses").delete().eq("id", expense_id).execute()


def compute_balance(participants, group_id=None, date_from=None, date_to=None, category=None):
    """
    participants: lista de nomes do grupo (ou de todos os grupos, na visão consolidada)
    Pra cada gasto: total_paid[pessoa] += o que ela pagou
                    fair_share[pessoa] += o que ela devia (via splits)
    net_balance = total_paid - fair_share (positivo = tem a receber)
    """
    df = get_expenses(group_id=group_id, date_from=date_from, date_to=date_to, category=category)
    total_paid = {p: 0.0 for p in participants}
    fair_share = {p: 0.0 for p in participants}

    if df.empty:
        return {
            "total_paid": total_paid,
            "fair_share": fair_share,
            "net_balance": {p: 0.0 for p in participants},
            "settlement": None,
            "total_spent": 0.0,
        }

    for _, row in df.iterrows():
        for person, val in row["payers"].items():
            total_paid[person] = total_paid.get(person, 0.0) + val
        for person, val in row["splits"].items():
            fair_share[person] = fair_share.get(person, 0.0) + val

    net_balance = {p: total_paid.get(p, 0.0) - fair_share.get(p, 0.0) for p in participants}

    settlement = None
    if len(participants) == 2:
        p1, p2 = participants
        diff = net_balance[p1]
        if abs(diff) > 0.01:
            settlement = f"{p2} deve R$ {diff:.2f} para {p1}" if diff > 0 else f"{p1} deve R$ {abs(diff):.2f} para {p2}"
        else:
            settlement = "Contas equilibradas 🎉"
    else:
        # grupo com 3+ pessoas: lista quem deve receber e quem deve pagar
        creditors = {p: v for p, v in net_balance.items() if v > 0.01}
        debtors = {p: -v for p, v in net_balance.items() if v < -0.01}
        if not creditors and not debtors:
            settlement = "Contas equilibradas 🎉"
        else:
            parts = [f"{p} tem a receber R$ {v:.2f}" for p, v in creditors.items()]
            parts += [f"{p} deve R$ {v:.2f}" for p, v in debtors.items()]
            settlement = " • ".join(parts)

    return {
        "total_paid": total_paid,
        "fair_share": fair_share,
        "net_balance": net_balance,
        "settlement": settlement,
        "total_spent": df["amount"].sum(),
    }
