# app.py
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Acompanhamento de Atendimentos - EBSA", layout="wide")

CANAL_COLS = ["E-mail", ".0300", "WhatsApp", "Instagram", "Facebook"]

@st.cache_data(show_spinner=False)
def load_data(uploaded_file=None, sheet_name=0):
    """Tenta carregar planilha enviada pelo usuário ou presente no diretório do app."""
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        return normalizar_mesano(df)

    default_path = Path("Relatório_EBSA_Acumulado.xlsx")
    if default_path.exists():
        df = pd.read_excel(default_path, sheet_name=sheet_name)
        return normalizar_mesano(df)

    # Caso nenhum arquivo esteja disponível
    st.warning("⚠️ Nenhuma base encontrada. Carregue um arquivo XLSX pela barra lateral.")
    return pd.DataFrame(columns=["Motivo","MÊSANO","ANO","TRIMESTRE","E-mail",".0300","WhatsApp","Instagram","Facebook","Total"])

def normalizar_mesano(df):
    """Garante que exista coluna 'MÊSANO' e converte para datetime."""
    # Renomeia colunas tirando espaços e normalizando acentos
    df.columns = [str(c).strip() for c in df.columns]
    if "MESANO" in df.columns:
        df.rename(columns={"MESANO": "MÊSANO"}, inplace=True)
    elif "MÊSANO" not in df.columns:
        raise ValueError("Coluna 'MÊSANO' não encontrada na base.")

    df["MÊSANO"] = df["MÊSANO"].apply(parse_mesano_to_datetime)
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

def sanitize_and_consolidate(df):
    df = df.copy()
    # Remove colunas Unnamed vazias
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
    for c in unnamed:
        if df[c].isna().all():
            df.drop(columns=[c], inplace=True)
    # Converte colunas numéricas
    cols_exist = [c for c in CANAL_COLS + ["Total"] if c in df.columns]
    for c in cols_exist:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Consolida por Motivo + MÊSANO
    sum_cols = [c for c in CANAL_COLS + ["Total"] if c in df.columns]
    g = df.groupby(["Motivo", "MÊSANO"], dropna=False)[sum_cols].sum(min_count=1).reset_index()
    g["ANO"] = g["MÊSANO"].dt.year
    g["TRIMESTRE"] = g["MÊSANO"].dt.quarter.astype(str) + "TRI" + (g["MÊSANO"].dt.year % 100).astype(str).str.zfill(2)
    if "Total" not in g.columns:
        g["Total"] = g[CANAL_COLS].sum(axis=1, min_count=1)
    else:
        g["Total"] = g["Total"].fillna(g[CANAL_COLS].sum(axis=1, min_count=1))
    return g

# ====== SIDEBAR ======
with st.sidebar:
    st.header("⚙️ Configurações")
    up = st.file_uploader("Carregue a planilha (xlsx)", type=["xlsx"])
    try:
        df_raw = load_data(up)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    df = sanitize_and_consolidate(df_raw)

    # Filtros
    min_dt, max_dt = df["MÊSANO"].min(), df["MÊSANO"].max()
    dt_ini, dt_fim = st.date_input("Período (MÊSANO)", (min_dt.date(), max_dt.date()))
    motivos = sorted(df["Motivo"].dropna().unique())
    sel_motivos = st.multiselect("Motivos", motivos)
    sel_canais = st.multiselect("Canais", [c for c in CANAL_COLS if c in df.columns], default=CANAL_COLS)
    anos = sorted(df["ANO"].dropna().unique())
    sel_anos = st.multiselect("Ano", anos, default=anos)
    tris = sorted(df["TRIMESTRE"].dropna().unique())
    sel_tris = st.multiselect("Trimestre", tris, default=tris)

# ====== FILTRO ======
flt = df[(df["MÊSANO"] >= pd.to_datetime(dt_ini)) & (df["MÊSANO"] <= pd.to_datetime(dt_fim))]
if sel_motivos:
    flt = flt[flt["Motivo"].isin(sel_mo_]()
