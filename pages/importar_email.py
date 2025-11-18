import streamlit as st
import pandas as pd
from email import message_from_bytes
from dateutil import parser as dateparser
import re
import os

# Caminho da planilha usada pelo hub (mesmo arquivo!)
EXCEL_PATH = "Interações com Segurados.xlsx"
SHEET_NAME = "Interações"

# -----------------------------------------------------------
#  Garantir que a planilha exista
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
#  Ler arquivo .eml
# -----------------------------------------------------------
def ler_eml(uploaded_file):
    raw_bytes = uploaded_file.read()
    msg = message_from_bytes(raw_bytes)

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
        try:
            corpo = msg.get_payload(decode=True).decode(errors="replace")
        except:
            corpo = ""

    try:
        data_convertida = dateparser.parse(data)
    except:
        data_convertida = None

    return assunto, data_convertida, corpo


# -----------------------------------------------------------
#  Extrair informações do assunto
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

    # Segurado
    partes = assunto.split("-")
    segurado = partes[-1].strip() if len(partes) >= 2 else ""

    # CNPJ
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", assunto)
    cnpj = cnpj_match.group(0) if cnpj_match else ""

    # Apólice
    apolice_match = re.search(r"-\s*(\d+)$", assunto)
    apolice = apolice_match.group(1) if apolice_match else ""

    integracao = "RCV"

    return segurado, tipo_evento, cnpj, apolice, integracao


# -----------------------------------------------------------
#  INTERFACE
# -----------------------------------------------------------
st.title("📩 Importador de E-mail (.eml) — Alimentar Planilha do Hub")

arquivo = st.file_uploader("Envie um arquivo .eml", type=["eml"])

if arquivo:
    assunto, data_hora, conteudo = ler_eml(arquivo)

    st.subheader("📌 Assunto detectado")
    st.write(assunto)

    st.subheader("📆 Data detectada")
    st.write(data_hora)

    st.subheader("📝 Conteúdo (prévia)")
    st.write(conteudo[:600] + "..." if len(conteudo) > 600 else conteudo)

    # Extrair informações estruturadas
    segurado, tipo_evento, cnpj, apolice, integracao = extrair_info_assunto(assunto)

    st.subheader("✏️ Linha gerada (você pode editar)")
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

    st.download_button(
        "⬇️ Baixar linha (CSV)",
        df_linha.to_csv(index=False).encode("utf-8"),
        "linha.csv"
    )

    if st.button("💾 Salvar na planilha"):
        df = garantir_planilha()
        df = pd.concat([df, df_linha], ignore_index=True)
        df.to_excel(EXCEL_PATH, index=False)
        st.success("Linha salva na planilha com sucesso! 🎉")
