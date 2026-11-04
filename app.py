import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

st.set_page_config(page_title="Produção por pessoa", layout="wide")

CONSULTA = text("""
SELECT
    P.Name AS [Name],
    COUNT(DISTINCT SMIC.ActivityGuided) AS [OS Feitas],
    SUM(SMIC.MasterAmmount) AS [CAIXAS],
    SUM(SMIC.UnitAmmount) AS [Fracoes],
    SUM(SMIC.Weight) AS [peso]
FROM SeparationManifestItemChecking AS SMIC
INNER JOIN Person AS P
    ON P.Id = SMIC.UserChecked
WHERE SMIC.CheckedDate >= :data_inicio
  AND SMIC.CheckedDate < :data_fim
GROUP BY P.Id, P.Name
ORDER BY [CAIXAS] DESC, [Fracoes] DESC, P.Name;
""")

@st.cache_resource
def obter_engine():
    url = URL.create(
        drivername="mssql+pymssql",
        username=st.secrets["MSSQL_USER"],
        password=st.secrets["MSSQL_PASSWORD"],
        host=st.secrets["MSSQL_HOST"],
        database=st.secrets["MSSQL_DATABASE"],
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "login_timeout": 10,
            "timeout": 60,
        },
    )


def consultar_por_data(data):
    inicio = datetime.combine(data, time.min)
    fim = inicio + timedelta(days=1)
    with obter_engine().connect() as conexao:
        return pd.read_sql_query(
            CONSULTA, conexao,
            params={"data_inicio": inicio, "data_fim": fim},
        )


def main():
    st.title("Produção por pessoa")
    st.caption("Totais de caixas, frações e peso por pessoa.")

    data_consulta = st.date_input(
        "Data da conferência",
        value=datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).date(),
        format="DD/MM/YYYY",
    )

    st.button("Atualizar consulta")

    try:
        with st.spinner("Consultando o WMS..."):
            # Cria o DataFrame antes de utilizá-lo.
            df = consultar_por_data(data_consulta)

    except ValueError as erro:
        st.error(str(erro))
        return

    except SQLAlchemyError:
        st.error(
            "Não foi possível consultar o SQL Server. "
            "Verifique rede/VPN, credenciais e permissões."
        )
        return

    if df is None:
        st.error(
            "A função consultar_por_data não retornou o DataFrame. "
            "Confira se ela termina com return df."
        )
        return

    st.subheader(
        f"Conferências de {data_consulta:%d/%m/%Y}"
    )

    if df.empty:
        st.info("Nenhum registro encontrado para essa data.")
        return

    # Mantém somente as colunas do relatório.
    relatorio = df[
        ["Name", "OS Feitas", "CAIXAS", "Fracoes", "peso"]
    ].rename(columns={"Name": "Nome"})

    # Tabela sem botão de exportação CSV.
    st.table(
        relatorio.style
        .format({"peso": "{:.3f}"}, na_rep="—")
        .hide(axis="index")
    )

    st.caption(
        "OS Feitas conta as ordens distintas por pessoa na data. "
        "CAIXAS, Fracoes e peso são as somas dos registros consultados."
    )


if __name__ == "__main__":
    main()

