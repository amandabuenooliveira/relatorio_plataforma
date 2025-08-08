
# Acompanhamento de Atendimentos — EBSA (Streamlit)

Dashboard em **Streamlit** para acompanhar os atendimentos por **Motivo**, **Canal** e **Período** a partir da base consolidada da EBSA.

## ✨ Principais recursos
- Consolidação automática de duplicados por **`Motivo + MÊSANO`** (somando canais e total).
- KPIs: total de atendimentos, registros filtrados, motivo mais frequente e variação vs. mês anterior.
- Tendência mensal (Total).
- Distribuição por canal (barras + participação %).
- Top 10 motivos por volume.
- Filtros por período (`MÊSANO`), canais, motivo, ano e trimestre.
- Tabela detalhada com **download CSV** do recorte filtrado.

## 📁 Estrutura sugerida
```
.
├── relatorio_plataforma_ebsa.py   # app Streamlit
├── requirements.txt               # dependências
└── Relatório_EBSA_Acumulado.xlsx  # (opcional) planilha local; também pode usar o uploader no app
```

## 🧠 Sobre a base de dados
O app espera as colunas (nomes exatos):
- `Motivo`, `MÊSANO`, `ANO`, `TRIMESTRE`, `E-mail`, `.0300`, `WhatsApp`, `Instagram`, `Facebook`, `Total`

**Observações**  
- `MÊSANO` pode vir como data ou texto (ex.: `07-24` ou `jul/25`). O app normaliza para o **1º dia do mês**.
- Se houver colunas `Unnamed` totalmente vazias, o app remove.
- Se `Total` estiver ausente ou nulo, o app recalcula como soma dos canais presentes.


## 📜 Licença
Uso interno EBSA AI / Editora do Brasil.
