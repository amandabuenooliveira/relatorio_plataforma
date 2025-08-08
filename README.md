
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

## ▶️ Executando localmente
1. **Instale as dependências** (de preferência em um ambiente virtual):
   ```bash
   pip install -r requirements.txt
   ```
2. **Coloque a planilha** `Relatório_EBSA_Acumulado.xlsx` na raiz do projeto (ou use o **uploader** no app).
3. **Rode o app**:
   ```bash
   streamlit run relatorio_plataforma_ebsa.py
   ```
4. Acesse o endereço mostrado pelo Streamlit (ex.: `http://localhost:8501`).

## ☁️ Deploy (Streamlit Community Cloud)
1. Suba o repositório para o Git (GitHub/GitLab/Bitbucket).
2. No Streamlit Cloud, crie um novo app apontando para `relatorio_plataforma_ebsa.py`.
3. Certifique-se de que o **requirements.txt** está no repositório.
4. (Opcional) Suba a planilha junto ou use o **file uploader** do app durante o uso.

## 🧰 Troubleshooting
- **Erro ao interpretar `MÊSANO`**: verifique se o formato é algo como `07-24` (mês-ano) ou `jul/25` (abreviação PT/BR). O app tenta normalizar automaticamente.
- **Totais divergentes**: o app recalcula `Total` como soma dos canais quando necessário; se preferir usar o `Total` da planilha, garanta que esteja preenchido.
- **Sem dados na tendência**: confirme se o período selecionado na barra lateral tem registros.

## 📜 Licença
Uso interno EBSA AI / Editora do Brasil.
