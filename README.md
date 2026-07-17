# Split Casal

App de divisão de gastos (estilo Splitwise) com grupos, categorias/subcategorias,
saldo e histórico filtráveis, e visualização por categoria com drill-down.

Roda 100% sobre Supabase — sem fallback local. As credenciais precisam estar
configuradas antes de rodar o app.

## Setup

1. Crie um projeto gratuito em supabase.com
2. Rode `supabase_schema.sql` no SQL Editor do projeto (cria as tabelas `groups` e `expenses`)
3. Copie o template de secrets:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
4. Edite `.streamlit/secrets.toml` com os dados do seu projeto (Project Settings > API no Supabase):
   ```toml
   [supabase]
   url = "https://SEU-PROJETO.supabase.co"
   key = "SUA_ANON_KEY_AQUI"
   ```
   Use sempre a chave **anon/public**, nunca a `service_role` — a anon key é segura de expor porque o RLS controla os acessos.
5. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
6. Rode:
   ```bash
   streamlit run app.py
   ```
   Sem os secrets configurados, o app para com um erro claro pedindo pra configurar `.streamlit/secrets.toml` — não cai silenciosamente para nenhum outro banco.

## Estrutura

```
split_app/
├── app.py                          # app principal (Streamlit)
├── db.py                           # camada de dados (Supabase)
├── categories.py                   # categorias e subcategorias
├── requirements.txt                # dependências
├── supabase_schema.sql             # schema pra rodar no Supabase (SQL Editor)
├── .gitignore                      # bloqueia secrets.toml
├── README.md
└── .streamlit/
    └── secrets.toml.example        # template — o real NUNCA vai pro GitHub
```

## O que tem no app

- **Grupos**: crie grupos com participantes livres (ex: "Casa" com Ivan/Esposa, "Viagem" com mais gente). Cada grupo tem seu próprio saldo e histórico.
- **Novo gasto**: valor, categoria/subcategoria, quem pagou (um ou vários, com valores), divisão (igual entre todos, ou custom em R$/%).
- **Saldo**: total do período, quanto cada um pagou vs. sua parte justa, saldo líquido (quem deve pra quem), e gráfico empilhado por categoria com drill-down pra subcategoria (clique na barra).
- **Histórico**: lista de gastos com filtro de período e categoria.
- **Consolidado**: visão de todos os grupos juntos, com o saldo de cada um discriminado.

## Importante — nunca suba `.streamlit/secrets.toml` real pro GitHub

O `.gitignore` já bloqueia isso. Antes de qualquer `git commit`, rode `git status` e confirme que `secrets.toml` (sem o `.example`) não aparece na lista.

## Deploy no Streamlit Community Cloud

1. Suba o repo pro GitHub (o `secrets.toml` real fica de fora por causa do `.gitignore`)
2. No painel do Streamlit Cloud: App Settings → Secrets → cole o conteúdo do seu `secrets.toml` real
3. Deploy
4. No iPhone: abre a URL no Safari → botão de compartilhar → "Adicionar à Tela de Início"

## Migrar histórico existente (ex: de outro app)

Se você tiver um histórico de outro app (CSV exportado, por exemplo) que queira importar, não dá pra usar o "Import CSV" nativo do Supabase direto, porque as colunas `payers` e `splits` são JSON — cada linha precisaria já vir formatada nesse padrão. Nesse caso, vale escrever um script Python simples que lê o CSV e insere via `db.add_expense()`, linha por linha, no formato certo.
