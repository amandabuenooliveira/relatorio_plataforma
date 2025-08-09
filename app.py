from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="Acompanhamento de Atendimentos - EBSA", layout="wide")

# Nomes padronizados que usaremos no app
CANAL_COLS_STD = ["E-mail", ".0300", "WhatsApp", "Instagram", "Facebook"]
ALL_STD = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"] + CANAL_COLS_STD + ["Total"]

# Mapeamento de aliases -> nome padrão
ALIASES = {
    "Motivo": ["Motivo", "Assunto", "Categoria"],
    "MÊSANO": [
        "MÊSANO", "MESANO", "MesAno", "MÊS/ANO", "MES/ANO", "MÊS-ANO", "MES-ANO",
        "MÊS_ANO", "MES_ANO", "MÊS ANO", "MES ANO", "MÊSANO "
    ],
    "E-mail": ["E-mail", "Email", "E_mail", "E mail"],
    ".0300": [".0300", "0300"],
    "WhatsApp": ["WhatsApp", "Whatsapp", "WHATSAPP", "WHATS", "Whats"],
    "Instagram": ["Instagram", "Insta"],
    "Facebook": ["Facebook", "Face"],
    "Total": ["Total", "TOTAL", "Qtd", "Quantidade"]
}

# -------------------
# Normalização de colunas
# -------------------
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [str(c).strip() for c in df.columns]
    rename_map = {}
    for std, variants in ALIASES.items():
        for v in variants:
            if v in cols:
                rename_map[v] = std
                break
    df = df.rename(columns=rename_map)
    # remove colunas Unnamed totalmente vazias
    for c in list(df.columns):
        if str(c).startswith("Unnamed") and df[c].isna().all():
            df = df.drop(columns=c)
    return df

# -------------------
# Parser robusto de MÊSANO
# -------------------
def parse_mesano_to_datetime(s):
    """Converte vários formatos (data completa, 07-24, 07/24, jul/25, JULHO 2025, etc.) para primeiro dia do mês."""
    if pd.isna(s):
        return pd.NaT

    # 1) tenta parse direto de datas (inclui strings tipo '2025-07-01' etc.)
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(dt):
        return pd.Timestamp(dt.year, dt.month, 1)

    # 2) tenta formatos com mês em PT-BR (abreviado e por extenso) + ano (2 ou 4 dígitos)
    mapa = {
        "jan": 1, "janeiro": 1,
        "fev": 2, "fevereiro": 2,
        "mar": 3, "março": 3, "marco": 3,
        "abr": 4, "abril": 4,
        "mai": 5, "maio": 5,
        "jun": 6, "junho": 6,
        "jul": 7, "julho": 7,
        "ago": 8, "agosto": 8,
        "set": 9, "setembro": 9,
        "out": 10, "outubro": 10,
        "nov": 11, "novembro": 11,
        "dez": 12, "dezembro": 12
    }

    s2 = str(s).strip().lower()
    # normaliza separadores em espaço
    s2 = s2.replace("-", " ").replace("/", " ").replace("\\", " ")
    parts = [p for p in s2.split() if p]

    # Casos comuns: ["jul", "25"] | ["julho", "2025"] | ["07", "24"]
    if len(parts) >= 2:
        mm_raw, yy_raw = parts[0], parts[1]

        # tenta mês numérico
        mm = None
        if mm_raw.isdigit():
            try:
                mm_num = int(mm_raw)
                if 1 <= mm_num <= 12:
                    mm = mm_num
            except ValueError:
                mm = None

        # se não for numérico, tenta mapa (abreviação ou por extenso)
        if mm is None:
            mm = mapa.get(mm_raw[:3]) or mapa.get(mm_raw)

        # ano
        try:
            yy = int(yy_raw)
            yy = 2000 + yy if yy < 100 else yy
        except ValueError:
            yy = None

        if mm and yy:
            try:
                return pd.Timestamp(yy, mm, 1)
            except Exception:
                pass

    return pd.NaT

def ensure_mesano_datetime(df: pd.DataFrame) -> pd.DataFrame:
    if "MÊSANO" not in df.columns:
        raise ValueError("Coluna 'MÊSANO' não encontrada (confira o cabeçalho).")
    df["MÊSANO"] = df["MÊSANO"].apply(parse_mesano_to_datetime)
    return df

# -------------------
# Leitura de arquivos (XLSX ou CSV)
# -------------------
def read_excel_auto(io):
    """Lê Excel: tenta aba 'EBSA'; senão escolhe a maior não vazia."""
    try:
        return pd.read_excel(io, sheet_name="EBSA")
    except Exception:
        sheets = pd.read_excel(io, sheet_name=None)
        non_empty = [d for d in sheets.values() if not d.empty]
        if non_empty:
            return max(non_empty, key=lambda d: d.shape[0] * d.shape[1])
        return list(sheets.values())[0]

def read_any_table(io):
    """Lê CSV ou XLSX, normaliza colunas e MÊSANO."""
    name = str(io if isinstance(io, (str, Path)) else getattr(io, "name", "")).lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io, sep=None, engine="python", encoding="utf-8-sig")
    elif name.endswith((".xlsx", ".xlsm", ".xls")):
        df = read_excel_auto(io)
    else:
        # tenta Excel por padrão (Streamlit uploader pode não ter extensão)
        try:
            df = read_excel_auto(io)
        except Exception:
            df = pd.read_csv(io, sep=None, engine="python", encoding="utf-8-sig")
    df = normalize_columns(df)
    df = ensure_mesano_datetime(df)
    return df

@st.cache_data(show_spinner=False)
def load_data(uploaded_file=None):
    """Tenta carregar: 1) upload; 2) arquivo local do repo; se nada, retorna DF vazio."""
    if uploaded_file is not None:
        return read_any_table(uploaded_file)

    # tente os nomes mais comuns no repo
    candidates = [
        "Relatório_EBSA_Acumulado_Consolidado.xlsx",
        "Relatório_EBSA_Acumulado.xlsx",
        "Relatorio_EBSA_Acumulado_Consolidado.xlsx",
        "Relatorio_EBSA_Acumulado.xlsx",
        "Relatorio_EBSA.csv",
        "Relatório_EBSA.csv",
    ]
    for fn in candidates:
        p = Path(fn)
        if p.exists():
            return read_any_table(p)

    # nenhum arquivo local
    st.warning("⚠️ Nenhuma base local encontrada. Faça upload do arquivo (XLSX/CSV) na barra lateral.")
    return pd.DataFrame(columns=ALL_STD)

# -------------------
# Consolidação e cálculos
# -------------------
def sanitize_and_consolidate(df):
    """Converte numéricos, consolida duplicados por Motivo+MÊSANO, recalcula ANO/TRI e Total."""
    if df.empty:
        return df.copy()

    df = df.copy()
    # garante colunas padrão
    df = normalize_columns(df)

    # canais/total para numérico
    cols_to_num = [c for c in CANAL_COLS_STD + ["Total"] if c in df.columns]
    for c in cols_to_num:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # consolida duplicados
    sum_cols = [c for c in CANAL_COLS_STD + ["Total"] if c in df.columns]
    g = df.groupby(["Motivo", "MÊSANO"], dropna=False)[sum_cols].sum(min_count=1).reset_index()

    # assegura datetime pós-agrupamento
    g["MÊSANO"] = pd.to_datetime(g["MÊSANO"], errors="coerce")
    if g["MÊSANO"].isna().all():
        raise ValueError("Falha ao converter 'MÊSANO' para data. Exemplos aceitos: 07-24, 07/24, jul/25, JULHO 2025.")

    # >>>>>>> AJUSTE: ANO como inteiro e TRIMESTRE sem NaN
    g["ANO"] = g["MÊSANO"].dt.year.astype("Int64")  # inteiro, preserva nulos
    g["TRIMESTRE"] = g.apply(
        lambda row: f"{row['MÊSANO'].quarter}TRI{str(row['MÊSANO'].year % 100).zfill(2)}"
        if pd.notna(row["MÊSANO"]) else pd.NA,
        axis=1
    )
    # <<<<<<<<

    # Total (se ausente ou nulo)
    canais_presentes = [c for c in CANAL_COLS_STD if c in g.columns]
    if "Total" not in g.columns:
        g["Total"] = g[canais_presentes].sum(axis=1, min_count=1)
    else:
        g["Total"] = g["Total"].fillna(g[canais_presentes].sum(axis=1, min_count=1))

    return g

# =======================
# UI
# =======================
with st.sidebar:
    st.header("⚙️ Configurações")
    up = st.file_uploader("Carregue a planilha (XLSX/CSV)", type=["xlsx", "xls", "csv"])
    try:
        df_raw = load_data(up)
    except Exception as e:
        st.error(f"Erro ao carregar base: {e}")
        st.stop()

    if df_raw.empty:
        st.info("Carregue um arquivo para visualizar os dados.")
        st.stop()

    try:
        df = sanitize_and_consolidate(df_raw)
    except Exception as e:
        st.error(f"Erro ao preparar base: {e}")
        st.stop()

    min_dt, max_dt = df["MÊSANO"].min(), df["MÊSANO"].max()
    if pd.isna(min_dt):
        st.error("Não foi possível interpretar 'MÊSANO'.")
        st.stop()

    dt_ini, dt_fim = st.date_input(
        "Período (MÊSANO)",
        value=(min_dt.date(), max_dt.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date(),
    )

    motivos = sorted(df["Motivo"].dropna().unique())
    sel_motivos = st.multiselect("Motivos", motivos)

    canais_disponiveis = [c for c in CANAL_COLS_STD if c in df.columns]
    sel_canais = st.multiselect("Canais", canais_disponiveis, default=canais_disponiveis)

    anos = sorted([int(a) for a in df["ANO"].dropna().unique().tolist()])
    sel_anos = st.multiselect("Ano", anos, default=anos)

    tris = sorted([t for t in df["TRIMESTRE"].dropna().unique().tolist()])
    sel_tris = st.multiselect("Trimestre", tris, default=tris)

# Filtros
flt = df[(df["MÊSANO"] >= pd.to_datetime(dt_ini)) & (df["MÊSANO"] <= pd.to_datetime(dt_fim))].copy()
if sel_motivos:
    flt = flt[flt["Motivo"].isin(sel_motivos)]
if sel_anos:
    flt = flt[flt["ANO"].isin(sel_anos)]
if sel_tris:
    flt = flt[flt["TRIMESTRE"].isin(sel_tris)]
if sel_canais:
    keep = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"] + sel_canais + (["Total"] if "Total" in flt.columns else [])
    flt = flt[[c for c in keep if c in flt.columns]]

# Dashboard
st.title("📊 Acompanhamento dos Atendimentos — EBSA")

col1, col2 = st.columns(2)
with col1:
    st.metric("Atendimentos (Total)", f"{int(flt['Total'].sum()):,}".replace(",", "."))
with col2:
    st.metric("Registros filtrados", f"{len(flt):,}".replace(",", "."))

# 1) Tendência Mensal Total
st.subheader("Tendência Mensal (Total)")
serie = flt.groupby("MÊSANO", as_index=False)["Total"].sum().sort_values("MÊSANO")
st.line_chart(serie.set_index("MÊSANO")["Total"])

# 2) Área empilhada por Canal (evolução)
st.subheader("Evolução por Canal (Área Empilhada)")
if sel_canais:
    area_df = flt.groupby("MÊSANO", as_index=False)[sel_canais].sum().sort_values("MÊSANO")
    area_df = area_df.set_index("MÊSANO")
    st.area_chart(area_df)

# 3) Heatmap Motivo x Mês
st.subheader("Heatmap — Motivo x Mês")
if not flt.empty:
    heat = (flt.assign(Mes=flt["MÊSANO"].dt.strftime("%Y-%m"))
                .groupby(["Motivo", "Mes"], as_index=False)["Total"].sum())
    heat_chart = (
        alt.Chart(heat)
        .mark_rect()
        .encode(
            x=alt.X("Mes:N", sort="ascending", title="Mês"),
            y=alt.Y("Motivo:N", title="Motivo"),
            color=alt.Color("Total:Q", title="Total"),
            tooltip=["Motivo", "Mes", "Total"]
        )
        .properties(height=400)
    )
    st.altair_chart(heat_chart, use_container_width=True)
else:
    st.info("Sem dados para gerar o heatmap no filtro atual.")

# 4) Pareto de Motivos (80/20)
st.subheader("Pareto — Motivos (acumulado no período filtrado)")
if "Total" in flt.columns and not flt.empty:
    pareto = (flt.groupby("Motivo", as_index=False)["Total"].sum()
                .sort_values("Total", ascending=False))
    pareto["% Acum."] = (pareto["Total"].cumsum() / pareto["Total"].sum() * 100).round(1)
    bars = alt.Chart(pareto).mark_bar().encode(
        x=alt.X("Motivo:N", sort="-y", title="Motivo"),
        y=alt.Y("Total:Q", title="Total")
    )
    line = alt.Chart(pareto).mark_line(point=True).encode(
        x=alt.X("Motivo:N", sort="-y"),
        y=alt.Y("% Acum.:Q", axis=alt.Axis(title="% Acumulado", format="~s")),
    )
    st.altair_chart(bars + line, use_container_width=True)
else:
    st.info("Sem dados para Pareto no filtro atual.")

# 5) Movers — maiores variações mês contra mês por Motivo
st.subheader("Variação M/M — Maiores altas e quedas por Motivo")
if not flt.empty:
    mm = (flt.groupby(["Motivo", "MÊSANO"], as_index=False)["Total"].sum()
              .sort_values(["Motivo", "MÊSANO"]))
    # pega último mês disponível no filtro e o anterior
    meses_ord = sorted(mm["MÊSANO"].unique())
    if len(meses_ord) >= 2:
        last, prev = meses_ord[-1], meses_ord[-2]
        base = mm[mm["MÊSANO"].isin([prev, last])].pivot(index="Motivo", columns="MÊSANO", values="Total").fillna(0)
        base["Δ"] = base.get(last, 0) - base.get(prev, 0)
        # evita divisão por zero
        base["%"] = np.where(base.get(prev, 0) == 0, np.nan, (base["Δ"] / base.get(prev, 0) * 100))
        up = base.sort_values("Δ", ascending=False).head(10)[["Δ", "%"]].rename(columns={"Δ":"Δ Absoluto", "%":"Δ %"})
        down = base.sort_values("Δ", ascending=True).head(10)[["Δ", "%"]].rename(columns={"Δ":"Δ Absoluto", "%":"Δ %"})
        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Maiores altas — {prev.date()} → {last.date()}")
            st.dataframe(up.style.format({"Δ Absoluto": "{:,.0f}", "Δ %": "{:+.1f}%"}), use_container_width=True)
        with c2:
            st.caption(f"Maiores quedas — {prev.date()} → {last.date()}")
            st.dataframe(down.style.format({"Δ Absoluto": "{:,.0f}", "Δ %": "{:+.1f}%"}), use_container_width=True)
    else:
        st.info("Precisamos de ao menos dois meses no filtro para calcular variação M/M.")
else:
    st.info("Sem dados para calcular variação M/M no filtro atual.")

# 6) Top Motivos (barras simples)
st.subheader("Top Motivos (Total no período)")
top_mot = flt.groupby("Motivo", as_index=False)["Total"].sum().sort_values("Total", ascending=False).head(10)
if not top_mot.empty:
    st.bar_chart(top_mot.set_index("Motivo")["Total"])
else:
    st.info("Sem dados para os filtros atuais.")

# 7) Detalhe + download
st.subheader("Detalhe dos Registros")
st.dataframe(flt.sort_values(["MÊSANO", "Motivo"]), use_container_width=True)
st.download_button(
    "⬇️ Baixar dados filtrados (CSV)",
    flt.to_csv(index=False).encode("utf-8-sig"),
    "atendimentos_filtrado.csv",
    mime="text/csv",
)
