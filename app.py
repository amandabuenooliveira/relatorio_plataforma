
# app.py
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Acompanhamento de Atendimentos - EBSA", layout="wide")

# ====== CONFIG ======
CANAL_COLS = ["E-mail", ".0300", "WhatsApp", "Instagram", "Facebook"]
KEY_COLS = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"]

# ====== FUNÇÕES AUX ======
@st.cache_data(show_spinner=False)
def load_data(uploaded_file=None, sheet_name=0):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    else:
        df = pd.read_excel("Relatório_EBSA_Acumulado.xlsx", sheet_name=sheet_name)
    return df

def parse_mesano_to_datetime(s):
    if pd.isna(s):
        return pd.NaT
    dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if not pd.isna(dt):
        return pd.Timestamp(year=dt.year, month=dt.month, day=1)
    mapa = {"jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,
            "jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12}
    try:
        s2 = str(s).strip().lower()
        if "/" in s2:
            mm_str, yy = s2.split("/")
            mm = mapa.get(mm_str[:3])
            yy = int(yy)
            yy = 2000 + yy if yy < 100 else yy
            if mm:
                return pd.Timestamp(year=yy, month=mm, day=1)
    except Exception:
        pass
    return pd.NaT

def sanitize_and_consolidate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
    for c in unnamed:
        if df[c].isna().all():
            df.drop(columns=[c], inplace=True)
    if "MÊSANO" not in df.columns:
        raise ValueError("Coluna 'MÊSANO' não encontrada.")
    df["MÊSANO"] = df["MÊSANO"].map(parse_mesano_to_datetime)
    cols_exist = [c for c in CANAL_COLS + ["Total"] if c in df.columns]
    for c in cols_exist:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    group_key = ["Motivo", "MÊSANO"]
    sum_cols = [c for c in CANAL_COLS + ["Total"] if c in df.columns]
    g = (df.groupby(group_key, dropna=False)[sum_cols]
           .sum(min_count=1)
           .reset_index())
    g["ANO"] = g["MÊSANO"].dt.year
    tri = g["MÊSANO"].dt.quarter
    yy = (g["MÊSANO"].dt.year % 100).astype("Int64")
    g["TRIMESTRE"] = tri.astype("Int64").astype(str) + "TRI" + yy.astype(str).str.zfill(2)
    canais_presentes = [c for c in CANAL_COLS if c in g.columns]
    if canais_presentes:
        g["Total_calc"] = g[canais_presentes].sum(axis=1, min_count=1)
        if "Total" not in g.columns:
            g["Total"] = g["Total_calc"]
        else:
            g["Total"] = g["Total"].fillna(g["Total_calc"])
        g.drop(columns=["Total_calc"], inplace=True)
    ordered = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"] + canais_presentes + ["Total"]
    others = [c for c in g.columns if c not in ordered]
    g = g[ordered + others]
    return g

def compute_prev_change(series_df: pd.DataFrame, date_col="MÊSANO", value_col="Total"):
    if date_col not in series_df.columns or value_col not in series_df.columns:
        return None
    s = (series_df.groupby(date_col, as_index=False)[value_col]
                  .sum()
                  .sort_values(date_col))
    if len(s) < 2:
        return None
    last = s.iloc[-1][value_col]
    prev = s.iloc[-2][value_col]
    if pd.isna(last) or pd.isna(prev) or prev == 0:
        return None
    return float((last - prev) / prev * 100.0), s.iloc[-2][date_col], s.iloc[-1][date_col]

# ====== SIDEBAR / LOAD ======
with st.sidebar:
    st.header("⚙️ Configurações")
    up = st.file_uploader("Carregue a planilha (xlsx)", type=["xlsx"])
    df_raw = load_data(up)
    df = sanitize_and_consolidate(df_raw)
    min_dt = df["MÊSANO"].min()
    max_dt = df["MÊSANO"].max()
    if pd.isna(min_dt):
        st.error("Não foi possível interpretar 'MÊSANO'.")
        st.stop()
    dt_ini, dt_fim = st.date_input(
        "Período (MÊSANO)",
        value=(min_dt.date(), max_dt.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date()
    )
    motivos = sorted(df["Motivo"].dropna().unique().tolist())
    sel_motivos = st.multiselect("Motivos", motivos)
    canais_disponiveis = [c for c in CANAL_COLS if c in df.columns]
    sel_canais = st.multiselect("Canais", canais_disponiveis, default=canais_disponiveis)
    anos = sorted(df["ANO"].dropna().astype(int).unique().tolist()) if "ANO" in df.columns else []
    sel_anos = st.multiselect("Ano", anos, default=anos)
    tris = sorted(df["TRIMESTRE"].dropna().unique().tolist()) if "TRIMESTRE" in df.columns else []
    sel_tris = st.multiselect("Trimestre", tris, default=tris)

# ====== APLICA FILTROS ======
flt = df.copy()
flt = flt[(flt["MÊSANO"] >= pd.to_datetime(dt_ini)) & (flt["MÊSANO"] <= pd.to_datetime(dt_fim))]
if sel_motivos:
    flt = flt[flt["Motivo"].isin(sel_motivos)]
if sel_canais:
    keep_cols = ["Motivo", "MÊSANO", "ANO", "TRIMESTRE"] + sel_canais + (["Total"] if "Total" in flt.columns else [])
    flt = flt[[c for c in keep_cols if c in flt.columns]]
if sel_anos and "ANO" in flt.columns:
    flt = flt[flt["ANO"].isin(sel_anos)]
if sel_tris and "TRIMESTRE" in flt.columns:
    flt = flt[flt["TRIMESTRE"].isin(sel_tris)]

# ====== KPIs ======
st.title("📊 Acompanhamento dos Atendimentos — EBSA")
st.caption("Dashboard interativo com indicadores por motivo, canal e período.")
col1, col2, col3, col4 = st.columns(4)
total_atend = int(flt["Total"].sum()) if "Total" in flt.columns else 0
with col1:
    st.metric("Atendimentos (Total)", f"{total_atend:,}".replace(",", "."))
registros = len(flt)
with col2:
    st.metric("Registros filtrados", f"{registros:,}".replace(",", "."))
if not flt.empty:
    top_m = (flt.groupby("Motivo", as_index=False)["Total"]
               .sum()
               .sort_values("Total", ascending=False)
               .head(1))
    motivo_top = top_m.iloc[0]["Motivo"]
    motivo_top_val = int(top_m.iloc[0]["Total"])
else:
    motivo_top, motivo_top_val = "-", 0
with col3:
    st.metric("Motivo mais frequente", f"{motivo_top} ({motivo_top_val})")
var_info = compute_prev_change(flt, "MÊSANO", "Total")
if var_info is not None:
    pct, dprev, dlast = var_info
    with col4:
        st.metric(
            "Variação vs mês anterior",
            f"{pct:+.1f}%",
            help=f"Comparação de {dlast.date()} vs {dprev.date()}"
        )
else:
    with col4:
        st.metric("Variação vs mês anterior", "—")

# ====== GRÁFICOS ======
st.subheader("Tendência Mensal (Total)")
if "MÊSANO" in flt.columns and "Total" in flt.columns:
    serie = (flt.groupby("MÊSANO", as_index=False)["Total"]
               .sum()
               .sort_values("MÊSANO"))
    st.line_chart(serie.set_index("MÊSANO")["Total"])
else:
    st.info("Sem colunas necessárias para a tendência.")

st.subheader("Atendimentos por Canal")
if sel_canais:
    por_canal = {}
    for c in sel_canais:
        por_canal[c] = flt[c].sum() if c in flt.columns else 0
    por_canal_df = (pd.Series(por_canal, name="Qtd")
                      .sort_values(ascending=False)
                      .to_frame())
    st.bar_chart(por_canal_df)
    total_canais = float(por_canal_df["Qtd"].sum()) or 1.0
    part = (por_canal_df["Qtd"] / total_canais * 100).round(1)
    st.caption("Participação por canal (%): " + ", ".join([f"{k}: {v:.1f}%" for k, v in part.items()]))
else:
    st.info("Nenhum canal selecionado.")

st.subheader("Top Motivos")
if "Motivo" in flt.columns and "Total" in flt.columns:
    top_mot = (flt.groupby("Motivo", as_index=False)["Total"]
                 .sum()
                 .sort_values("Total", ascending=False)
                 .head(10))
    if not top_mot.empty:
        st.bar_chart(top_mot.set_index("Motivo")["Total"])
    else:
        st.info("Sem dados para os filtros atuais.")
else:
    st.info("Coluna 'Motivo' ou 'Total' ausente.")

# ====== TABELA DETALHADA + DOWNLOAD ======
st.subheader("Detalhe dos Registros")
st.dataframe(flt.sort_values(["MÊSANO","Motivo"]), use_container_width=True)
csv = flt.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ Baixar dados filtrados (CSV)", data=csv, file_name="atendimentos_filtrado.csv", mime="text/csv")
st.caption("💡 Dica: ajuste os filtros na barra lateral para explorar motivos e canais específicos.")
