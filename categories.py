"""
Estrutura de categorias e subcategorias.
Categorias sem subcategoria própria usam "Geral" como subcategoria padrão.
"""

CATEGORIES = {
    "Alimentação": ["Mercado", "Restaurante", "Delivery", "Bebidas", "Outros"],
    "Moradia": ["Limpeza", "Acessórios", "Moradia", "Utilities", "Manutenção", "Outros"],
    "Transporte": ["Combustível", "Manutenção", "Passagens", "Outros"],
    "Lazer": ["Geral"],
    "Saúde": ["Médico", "Plano de Saúde", "Farmácia", "Outros"],
    "Discricionário": ["Presentes", "Roupas", "Eletrônicos", "Outros"],
    "Pet": ["Alimentação", "Brinquedos", "Acessórios", "Saúde", "Outros"],
    "Outros gastos": ["Geral"],
}

CATEGORY_LIST = list(CATEGORIES.keys())


def subcategories_for(category: str):
    return CATEGORIES.get(category, ["Geral"])
