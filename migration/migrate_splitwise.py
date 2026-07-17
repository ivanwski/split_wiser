"""
Migração do histórico do Splitwise (grupo "Casinha") pro Supabase.

Uso:
    python migrate_splitwise.py caminho/para/export.csv

Requer .streamlit/secrets.toml configurado (mesmo usado pelo app.py).
Lê o CSV exportado do Splitwise (formato italiano: Data, Descrizione,
Categorie, Costo, Valuta, <Nome1>, <Nome2>), reconstrói payers/splits
a partir do saldo líquido por pessoa, e insere tudo no grupo indicado.

O CSV do Splitwise só traz o SALDO LÍQUIDO por pessoa (pago - parte devida),
não o valor pago e a divisão separadamente. A reconstrução assume:
  - saldo > 0 para a pessoa A: A pagou o valor total; a divisão real é
    derivada do saldo (ex: saldo = metade do custo -> divisão 50/50)
  - saldo < 0 para a pessoa A: o inverso (a outra pessoa pagou)
  - saldo = 0: pagamento conjunto (cada um contribuiu metade), split 50/50
"""
import sys
import json
import tomllib
import pandas as pd
from pathlib import Path
from supabase import create_client

from category_map import CATEGORY_MAP

# ---------------- Configuração ----------------

GROUP_NAME = "Casinha"
PARTICIPANTS = ["Ivan", "Ariane"]  # nomes usados no app

# Nomes das colunas de pessoa no CSV do Splitwise (ajuste se necessário)
CSV_COL_IVAN = "Ivan Stamborowski"
CSV_COL_ARIANE = "Ariane S"

SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


def load_supabase_client():
    if not SECRETS_PATH.exists():
        sys.exit(f"Não encontrei {SECRETS_PATH}. Configure o secrets.toml antes de rodar a migração.")
    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)
    url = secrets["supabase"]["url"]
    key = secrets["supabase"]["key"]
    return create_client(url, key)


def get_or_create_group(supabase, name, members):
    result = supabase.table("groups").select("*").eq("name", name).execute()
    if result.data:
        group = result.data[0]
        print(f"Grupo '{name}' já existe (id={group['id']}). Usando o existente.")
        return group["id"]
    result = supabase.table("groups").insert({"name": name, "members": members}).execute()
    group_id = result.data[0]["id"]
    print(f"Grupo '{name}' criado (id={group_id}).")
    return group_id


def compute_payers_splits(cost, net_ivan):
    """
    Reconstrói payers e splits a partir do saldo líquido do Ivan naquela transação.
    net_ivan = valor_pago_ivan - parte_devida_ivan
    """
    if abs(net_ivan) < 0.01:
        # saldo zero -> pagamento conjunto, split 50/50
        half = round(cost / 2, 2)
        payers = {"Ivan": half, "Ariane": cost - half}
        splits = {"Ivan": half, "Ariane": cost - half}
    elif net_ivan > 0:
        # Ivan pagou o total; parte devida do Ivan = cost - net_ivan
        ivan_share = round(cost - net_ivan, 2)
        ariane_share = round(cost - ivan_share, 2)
        payers = {"Ivan": cost}
        splits = {"Ivan": ivan_share, "Ariane": ariane_share}
    else:
        # Ariane pagou o total; net_ivan negativo = parte devida do Ivan
        ivan_share = round(-net_ivan, 2)
        ariane_share = round(cost - ivan_share, 2)
        payers = {"Ariane": cost}
        splits = {"Ivan": ivan_share, "Ariane": ariane_share}
    return payers, splits


def main(csv_path):
    df = pd.read_csv(csv_path)
    df = df[df["Descrizione"] != "Bilancio totale"].copy()

    for col in ["Costo", CSV_COL_IVAN, CSV_COL_ARIANE]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    unmapped = set(df["Categorie"].unique()) - set(CATEGORY_MAP.keys())
    if unmapped:
        sys.exit(f"Categorias sem mapeamento em category_map.py: {unmapped}. Ajuste o de-para antes de continuar.")

    supabase = load_supabase_client()
    group_id = get_or_create_group(supabase, GROUP_NAME, PARTICIPANTS)

    inserted, skipped = 0, 0
    for _, row in df.iterrows():
        cost = row["Costo"]
        if pd.isna(cost) or cost <= 0:
            skipped += 1
            continue

        category, subcategory = CATEGORY_MAP[row["Categorie"]]
        payers, splits = compute_payers_splits(cost, row[CSV_COL_IVAN])

        supabase.table("expenses").insert({
            "group_id": group_id,
            "expense_date": row["Data"],
            "description": row["Descrizione"].strip(),
            "category": category,
            "subcategory": subcategory,
            "amount": float(cost),
            "payers": payers,
            "splits": splits,
            "notes": "Importado do Splitwise",
        }).execute()
        inserted += 1

    print(f"\nConcluído: {inserted} gastos inseridos, {skipped} linhas puladas (custo inválido).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python migrate_splitwise.py caminho/para/export.csv")
    main(sys.argv[1])
