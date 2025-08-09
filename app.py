from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Acompanhamento de Atendimentos - EBSA", layout="wide")

# Nomes padronizados que usaremos no app
CANAL_COLS_STD = ["E-mail", ".0300", "WhatsApp", "Instagram", "Facebook"]
ALL_STD = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"] + CANAL_COLS_STD + ["Total"]

# Mapeamento de aliases -> nome padrão
ALIASES = {
    "Motivo": ["Motivo", "Assunto", "Categoria"],
    "MÊSANO": ["MÊSANO", "MESANO", "MesAno", "MÊS/ANO", "MES/ANO", "MÊS-ANO", "MES-ANO", "MÊS_ANO", "MES_ANO", "MÊS ANO", "MES ANO"],
    "E-mail": ["E-mail", "Email", "E_mail", "E mail"],
    ".0300": [".0300", "0300"],
    "WhatsApp": ["WhatsApp", "Whatsapp", "WHATSAPP", "WHATS", "Whats"],
    "Instagram": ["Instagram", "Insta"],
    "Facebook": ["Facebook", "Face"],
    "Total": ["Total", "TOTAL", "Qtd", "Quantidade"]
}

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

def parse_mesano_to_datetime(s):
    if pd.isna(s):
        return pd.NaT
    # tenta parse direto
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(dt):
        return pd.Timestamp(dt.year, dt.month, 1)
    # tenta formato 'jul/25' em PT-BR
    mapa = {"jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,"jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12}
    try:
        s2 = str(s).strip().lower()
        if "/" in s2:
            mm_str, yy = s2.split("/")
            mm = mapa.get(mm_str[:3])
            yy = int(yy)
            yy = 2000 + yy if yy < 100 else yy
            if mm:
                return pd.Timestamp(yy, mm, 1)
    except Exception:
        pass
    return pd.NaT

def ensure_mesano_datetime(df: pd.DataFrame) -> pd.DataFrame:
    if "MÊSANO" not in df.columns:
        raise ValueError("Coluna 'MÊSANO' não encontrada (tente conferir o cabeçalho).")
    df["MÊSANO"] = df["MÊSANO"].apply(parse_mesano_to_datetime)
    return df

def read_excel_auto(io):
    """Lê Excel: tenta aba 'EBSA'; senão escolhe a maior não vazia."""
    try:
        return pd.read_excel(io, sheet_name="EBSA")
    except Exception:
        sheets = pd.read_excel(io, sheet_name=None)
        # pega a maior não vazia; se todas vazias, pega a primeira
        non_empty = [d for d in sheets.values() if not d.empty]
        if non_empty:
            return max(non_empty, key=lambda d: d.shape[0] * d.shape[1])
        # fallback
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
        raise ValueError("Falha ao converter 'MÊSANO' para data. Verifique o formato (ex.: 07-24, jul/25).")

    # ANO/TRI
    g["ANO"] = g["MÊSANO"].dt.year
    g["TRIMESTRE"] = g["MÊSANO"].dt.quarter.astype(str) + "TRI" + (g["MÊSANO"].dt.year % 100).astype(str).str.zfill(2)

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

    anos = sorted(df["ANO"].dropna().unique())
    sel_anos = st.multiselect("Ano", anos, default=anos)

    tris = sorted(df["TRIMESTRE"].dropna().unique())
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

st.subheader("Tendência Mensal (Total)")
serie = flt.groupby("MÊSANO", as_index=False)["Total"].sum().sort_values("MÊSANO")
st.line_chart(serie.set_index("MÊSANO")["Total"])

st.subheader("Atendimentos por Canal")
if sel_canais:
    por_canal = flt[sel_canais].sum().sort_values(ascending=False)
    st.bar_chart(por_canal)

st.subheader("Top Motivos")
top_mot = flt.groupby("Motivo", as_index=False)["Total"].sum().sort_values("Total", ascending=False).head(10)
if not top_mot.empty:
    st.bar_chart(top_mot.set_index("Motivo")["Total"])

st.subheader("Detalhe dos Registros")
st.dataframe(flt.sort_values(["MÊSANO", "Motivo"]), use_container_width=True)
st.download_button(
    "⬇️ Baixar dados filtrados (CSV)",
    flt.to_csv(index=False).encode("utf-8-sig"),
    "atendimentos_filtrado.csv",
    mime="text/csv",
)
