import streamlit as st
import pandas as pd
from email import message_from_bytes
from dateutil import parser as dateparser
import re
import base64
import os

# Caminho do arquivo Excel dentro do seu repositório
EXCEL_PATH = "Interações com Segurados.xlsx"
SHEET_NAME = "Interações"

# -----------------------------------------------------------
#  FUNÇÃO: Garantir que a planilha exista ou criar se faltar
# -----------------------------------------------------------
def garantir_planilha():
    if not os.path.exists(EXCEL_PATH):
        df = pd.DataFrame(columns=[
            "segurado",
            "canal",
            "data_hora",
            "conteudo",
            "tipo_evento",
            "integracao",
            "cnpj",
            "apolice"
        ])
        df.to_excel(EXCEL_PATH, index=False)
    return pd.read_excel(EXCEL_PATH)


# -----------------------------------------------------------
#  FUNÇÃO: Leitura e parsing do arquivo .eml
# -----------------------------------------------------------
def ler_eml(uploaded_file):
    raw_bytes = uploaded_file.read()
    msg = message_from_bytes(raw_bytes, strict=False)

    assunto = msg.get("Subject", "").strip()
    data = msg.get("Date", "")
    corpo = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    corpo = part.get_payload(decode=True).decode(errors="replace")
                except:
                    pass
            elif content_type == "text/html" and corpo.strip() == "":
                try:
                    corpo = part.get_payload(decode=True).decode(errors="replace")
                except:
                    pass
    else:
        corpo = msg.get_payload(decode=True).decode(errors="replace")

    try:
        data_convertida = dateparser.parse(data)
    except:
        data_convertida = None

    return assunto, data_convertida, corpo


# -----------------------------------------------------------
#  FUNÇÃO: Extrair infos do ASSUNTO
# -----------------------------------------------------------
def extrair_info_assunto(assunto):

    assunto_limpo = assunto.upper()

    # Tipo do evento
    if "INSTALAÇÃO" in assunto_limpo:
        tipo_evento = "Instalação"
    elif "CAIXA POSTAL" in assunto_limpo:
        tipo_evento = "Caixa Postal"
    elif "ESSOR" in assunto_limpo or "APHICOR" in assunto_limpo:
        tipo_evento = "Abertura"
    else:
        tipo_evento = "Outros"

    # Extrair segurado (última parte depois do "-")
    partes = assunto.split("-")
    segurado = partes[-1].strip() if len(partes) >= 2 else ""

    # Tentar extrair CNPJ
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}", assunto)
    cnpj = cnpj_match.group(0) if cnpj_match else ""

    # Tentar extrair apólice (números no final depois de "-")
    apolice_match = re.search(r"-\s*(\d+)$", assunto)
    apolice = apolice_match.group(1) if apolice_match else ""

    integracao = "RCV"

    return segurado, tipo_evento, cnpj, apolice, integracao


# -----------------------------------------------------------
#  INTERFACE STREAMLIT
# -----------------------------------------------------------
st.title("📩 Importar E-mail (.eml) → Gerar Linha da Planilha")

arquivo = st.file_uploader("Envie um arquivo .eml:", type=["eml"])

if arquivo:
    assunto, data_hora, conteudo = ler_eml(arquivo)

    st.subheader("📌 Assunto detectado")
    st.write(assunto)

    st.subheader("📆 Data detectada")
    st.write(data_hora)

    st.subheader("📝 Corpo do e-mail (resumido)")
    st.write(conteudo[:500] + "..." if len(conteudo) > 500 else conteudo)

    # Extrair informações
    segurado, tipo_evento, cnpj, apolice, integracao = extrair_info_assunto(assunto)

    # Formulário de edição
    st.subheader("✏️ Linha gerada (você pode editar antes de salvar)")
    segurado = st.text_input("Segurado", segurado)
    tipo_evento = st.text_input("Tipo Evento", tipo_evento)
    cnpj = st.text_input("CNPJ", cnpj)
    apolice = st.text_input("Apólice", apolice)
    integracao = st.text_input("Integração", integracao)

    df_linha = pd.DataFrame([{
        "segurado": segurado,
        "canal": "E-mail",
        "data_hora": data_hora,
        "conteudo": conteudo,
        "tipo_evento": tipo_evento,
        "integracao": integracao,
        "cnpj": cnpj,
        "apolice": apolice
    }])

    st.write(df_linha)

    # ---------------------------------------------
    # Baixar CSV
    csv_data = df_linha.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar linha (CSV)",
        csv_data,
        "linha.csv",
        "text/csv"
    )

    # ---------------------------------------------
    # Baixar Excel
    xlsx_data = df_linha.to_excel(index=False).split()[0] if False else None

    # ---------------------------------------------
    # Salvar na planilha
    if st.button("💾 Salvar na planilha do sistema"):
        df = garantir_planilha()
        df = pd.concat([df, df_linha], ignore_index=True)
        df.to_excel(EXCEL_PATH, index=False)
        st.success("Linha salva com sucesso!")
