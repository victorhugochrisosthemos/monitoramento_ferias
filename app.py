import json
from datetime import date, timedelta
from io import BytesIO

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Planejamento de Férias", layout="wide")

DEFAULT_JSON_NAME = "ferias_colaboradores.json"
OVERLAP_COLOR = "#D62728"
OVERLAP_BG_COLOR = "rgba(255, 80, 80, 0.18)"
COLLABORATOR_PALETTE = [
    "#4F81BD", "#59A14F", "#9C755F", "#B07AA1", "#76B7B2",
    "#F28E2B", "#EDC948", "#E15759", "#FF9DA7", "#BAB0AC",
]


def normalize_records(records):
    normalized = []
    for index, item in enumerate(records):
        try:
            nome = str(item.get("colaborador", "")).strip()
            inicio = pd.to_datetime(item.get("inicio")).date()
            fim = pd.to_datetime(item.get("fim")).date()
            cor = str(item.get("cor", COLLABORATOR_PALETTE[index % len(COLLABORATOR_PALETTE)])).strip() or COLLABORATOR_PALETTE[index % len(COLLABORATOR_PALETTE)]
            if nome and inicio <= fim:
                normalized.append(
                    {
                        "colaborador": nome,
                        "inicio": inicio.isoformat(),
                        "fim": fim.isoformat(),
                        "cor": cor,
                    }
                )
        except Exception:
            continue
    return normalized



def build_dataframe(records):
    if not records:
        return pd.DataFrame(columns=["id", "colaborador", "inicio", "fim", "cor"])
    df = pd.DataFrame(records).copy()
    if "id" not in df.columns:
        df["id"] = [f"item_{i}" for i in range(len(df))]
    df["inicio"] = pd.to_datetime(df["inicio"]).dt.date
    df["fim"] = pd.to_datetime(df["fim"]).dt.date
    if "cor" not in df.columns:
        df["cor"] = [COLLABORATOR_PALETTE[i % len(COLLABORATOR_PALETTE)] for i in range(len(df))]
    df = df.sort_values(["inicio", "fim", "colaborador"]).reset_index(drop=True)
    return df



def daterange(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)



def compute_overlap_days(df):
    counts = {}
    for _, row in df.iterrows():
        for day in daterange(row["inicio"], row["fim"]):
            counts[day] = counts.get(day, 0) + 1
    return {day for day, count in counts.items() if count > 1}



def add_padding(min_day, max_day):
    total_days = max((max_day - min_day).days + 1, 1)
    pad = max(2, min(15, total_days // 8 + 1))
    return min_day - timedelta(days=pad), max_day + timedelta(days=pad)


def build_color_map(df):
    color_map = {}
    for i, (_, row) in enumerate(df.iterrows()):
        cor = row.get("cor", "")
        color_map[row["id"]] = cor if cor else COLLABORATOR_PALETTE[i % len(COLLABORATOR_PALETTE)]
    return color_map


def build_segments(start_day, end_day):
    return [(start_day, end_day)]



def create_plotly_gantt(df):
    fig = go.Figure()

    if df.empty:
        fig.add_annotation(
            text="Nenhum período cadastrado.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 18},
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.update_layout(height=420, margin=dict(l=20, r=20, t=20, b=20))
        return fig

    overlap_days = compute_overlap_days(df)
    color_map = build_color_map(df)
    min_day = df["inicio"].min()
    max_day = df["fim"].max()
    x_min, x_max = add_padding(min_day, max_day)

    row_gap = 1.7
    y_positions = [(len(df) - 1 - i) * row_gap for i in range(len(df))]
    line_width = 22
    legend_added = {"normal": False, "conflict": False}

    for day in sorted(overlap_days):
        fig.add_vrect(
            x0=pd.Timestamp(day),
            x1=pd.Timestamp(day) + pd.Timedelta(days=1),
            fillcolor=OVERLAP_BG_COLOR,
            line_width=0,
            layer="below",
        )

    for idx, (_, row) in enumerate(df.iterrows()):
        y = y_positions[idx]
        periodo_texto = f"{row['inicio'].strftime('%d/%m/%Y')} até {row['fim'].strftime('%d/%m/%Y')}"
        base_color = color_map[row["id"]]

        for segment_start, segment_end in build_segments(row["inicio"], row["fim"]):
            fig.add_trace(
                go.Scatter(
                    x=[pd.Timestamp(segment_start), pd.Timestamp(segment_end) + pd.Timedelta(hours=23, minutes=59)],
                    y=[y, y],
                    mode="lines",
                    line=dict(color=base_color, width=line_width),
                    name="Período sem conflito",
                    legendgroup="normal",
                    showlegend=not legend_added["normal"],
                    hovertemplate=(
                        f"<b>{row['colaborador']}</b><br>"
                        f"Período: {periodo_texto}<br>"
                        f"Cor da linha: {base_color}<extra></extra>"
                    ),
                )
            )
            legend_added["normal"] = True

        total_days = (row["fim"] - row["inicio"]).days + 1
        if total_days >= 5:
            middle_day = pd.Timestamp(row["inicio"]) + (pd.Timestamp(row["fim"]) - pd.Timestamp(row["inicio"])) / 2
            fig.add_annotation(
                x=middle_day,
                y=y,
                text=periodo_texto,
                showarrow=False,
                font={"color": "white", "size": 10},
                xanchor="center",
                yanchor="middle",
                bgcolor="rgba(0,0,0,0.18)",
            )

    initial_days = min(31, max(10, (max_day - min_day).days + 1))
    initial_end = min(max_day + timedelta(days=2), x_max)
    initial_start = max(x_min, initial_end - timedelta(days=initial_days))

    if overlap_days:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="lines",
                line=dict(color="rgba(255,80,80,0)", width=10),
                name="Coluna com conflito",
                legendgroup="conflict",
                showlegend=True,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        height=max(460, 220 + len(df) * 85),
        margin=dict(l=20, r=20, t=30, b=30),
        xaxis=dict(
            title="Dias",
            type="date",
            range=[initial_start, initial_end],
            tickformat="%d/%m/%Y",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            rangeslider=dict(visible=True),
            fixedrange=False,
            tickformatstops=[
                dict(dtickrange=[None, 2 * 24 * 60 * 60 * 1000], value="%d/%m/%Y"),
                dict(dtickrange=[2 * 24 * 60 * 60 * 1000, 31 * 24 * 60 * 60 * 1000], value="%d/%m"),
                dict(dtickrange=[31 * 24 * 60 * 60 * 1000, None], value="%m/%Y"),
            ],
        ),
        yaxis=dict(
            title="Colaboradores",
            tickmode="array",
            tickvals=y_positions,
            ticktext=df["colaborador"].tolist(),
            tickfont=dict(size=14),
            range=[-row_gap, max(y_positions) + row_gap],
            fixedrange=False,
            showgrid=False,
            zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        dragmode="pan",
        hovermode="closest",
    )

    return fig


def create_pdf_figure(df):
    if df.empty:
        fig, ax = plt.subplots(figsize=(12, 3))
        ax.text(0.5, 0.5, "Nenhum período cadastrado.", ha="center", va="center", fontsize=14)
        ax.axis("off")
        fig.tight_layout()
        return fig

    overlap_days = compute_overlap_days(df)
    color_map = build_color_map(df)
    min_day = df["inicio"].min()
    max_day = df["fim"].max()
    x_min, x_max = add_padding(min_day, max_day)

    num_rows = len(df)
    fig_height = max(4.5, num_rows * 0.9 + 2)
    fig, ax = plt.subplots(figsize=(16, fig_height))

    row_gap = 1.7
    bar_height = 0.6
    y_positions = [(num_rows - 1 - i) * row_gap for i in range(num_rows)]
    y_labels = []

    for day in sorted(overlap_days):
        ax.axvspan(
            mdates.date2num(day),
            mdates.date2num(day + timedelta(days=1)),
            color="#ff8080",
            alpha=0.22,
            zorder=0,
        )

    for idx, (_, row) in enumerate(df.iterrows()):
        y = y_positions[idx]
        y_labels.append(row["colaborador"])
        base_color = color_map[row["id"]]

        for segment_start, segment_end in build_segments(row["inicio"], row["fim"]):
            ax.broken_barh(
                [(mdates.date2num(segment_start), (segment_end - segment_start).days + 1)],
                (y - bar_height / 2, bar_height),
                facecolors=base_color,
                edgecolors="white",
                linewidth=0.6,
                zorder=2,
            )

        total_days = (row["fim"] - row["inicio"]).days + 1
        if total_days >= 5:
            label_x = row["inicio"] + (row["fim"] - row["inicio"]) / 2
            ax.text(
                mdates.date2num(label_x),
                y,
                f"{row['inicio'].strftime('%d/%m/%Y')} até {row['fim'].strftime('%d/%m/%Y')}",
                ha="center",
                va="center",
                color="white",
                fontsize=7.5,
                fontweight="bold",
            )

    ax.set_ylim(-row_gap, max(y_positions) + row_gap)
    ax.set_xlim(mdates.date2num(x_min), mdates.date2num(x_max))
    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=12)
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.set_xlabel("Dias")
    ax.set_ylabel("Colaboradores")
    if overlap_days:
        ax.legend(
            handles=[Patch(facecolor="#ff8080", alpha=0.22, label="Coluna com conflito")],
            loc="upper left",
        )
    fig.tight_layout()
    return fig


def dataframe_to_json_bytes(df):
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "colaborador": row["colaborador"],
                "inicio": row["inicio"].isoformat(),
                "fim": row["fim"].isoformat(),
                "cor": row["cor"],
            }
        )
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")



def figure_to_pdf_bytes(fig):
    buffer = BytesIO()
    fig.savefig(buffer, format="pdf", bbox_inches="tight")
    buffer.seek(0)
    plt.close(fig)
    return buffer.getvalue()



def render_sidebar_data_controls():
    st.sidebar.subheader("Menu")
    section = st.sidebar.radio(
        "Escolha uma área",
        ["Cadastrar férias", "Editar registros"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.subheader("Dados em JSON")
    uploaded_file = st.sidebar.file_uploader("Carregar arquivo JSON", type=["json"])
    if uploaded_file is not None:
        try:
            loaded = json.load(uploaded_file)
            st.session_state.records = [
                {**item, "id": f"item_{i}"} for i, item in enumerate(normalize_records(loaded))
            ]
            st.sidebar.success("JSON carregado com sucesso.")
        except Exception as exc:
            st.sidebar.error(f"Não foi possível carregar o JSON: {exc}")

    if st.sidebar.button("Limpar dados", use_container_width=True):
        st.session_state.records = []
        st.sidebar.success("Dados removidos da sessão.")

    st.sidebar.divider()
    return section



def render_add_form_sidebar():
    st.sidebar.subheader("Cadastrar férias")
    with st.sidebar.form("add_vacation_form", clear_on_submit=True):
        colaborador = st.text_input("Colaborador")
        inicio = st.date_input("Início", value=date.today())
        fim = st.date_input("Fim", value=date.today())
        cor = st.color_picker("Cor da linha", value=COLLABORATOR_PALETTE[len(st.session_state.records) % len(COLLABORATOR_PALETTE)])
        submitted = st.form_submit_button("Adicionar linha", use_container_width=True)

        if submitted:
            nome = colaborador.strip()
            if not nome:
                st.sidebar.error("Informe o nome do colaborador.")
            elif inicio > fim:
                st.sidebar.error("A data inicial não pode ser maior que a data final.")
            else:
                st.session_state.records.append(
                    {
                        "id": f"item_{st.session_state.next_id}",
                        "colaborador": nome,
                        "inicio": inicio.isoformat(),
                        "fim": fim.isoformat(),
                        "cor": cor,
                    }
                )
                st.session_state.next_id += 1
                st.sidebar.success("Período adicionado.")



def render_editor_sidebar():
    st.sidebar.subheader("Editar registros")
    df_edit = build_dataframe(st.session_state.records)

    if df_edit.empty:
        st.sidebar.info("Nenhum período cadastrado ainda.")
        return

    editable_df = df_edit[["colaborador", "inicio", "fim", "cor"]].copy()
    editable_df["inicio"] = pd.to_datetime(editable_df["inicio"])
    editable_df["fim"] = pd.to_datetime(editable_df["fim"])

    edited = st.sidebar.data_editor(
        editable_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "colaborador": st.column_config.TextColumn("Colaborador", required=True),
            "inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY", required=True),
            "fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY", required=True),
            "cor": st.column_config.TextColumn("Cor", required=True),
        },
        hide_index=True,
        key="vacation_editor",
    )

    if st.sidebar.button("Salvar alterações", use_container_width=True):
        try:
            edited_records = []
            for i, (_, row) in enumerate(edited.iterrows()):
                nome = str(row["colaborador"]).strip()
                ini = pd.to_datetime(row["inicio"]).date()
                end = pd.to_datetime(row["fim"]).date()
                if not nome:
                    raise ValueError("Há colaborador sem nome.")
                if ini > end:
                    raise ValueError(f"Período inválido para {nome}.")
                cor = str(row.get("cor", "")).strip() or COLLABORATOR_PALETTE[i % len(COLLABORATOR_PALETTE)]
                edited_records.append(
                    {
                        "id": f"item_{i}",
                        "colaborador": nome,
                        "inicio": ini.isoformat(),
                        "fim": end.isoformat(),
                        "cor": cor,
                    }
                )
            st.session_state.records = edited_records
            st.session_state.next_id = len(edited_records)
            st.sidebar.success("Alterações salvas.")
        except Exception as exc:
            st.sidebar.error(f"Erro ao salvar alterações: {exc}")


if "records" not in st.session_state:
    st.session_state.records = []
if "next_id" not in st.session_state:
    st.session_state.next_id = len(st.session_state.records)

st.title("Planejamento de Férias")
st.caption(
    "Cadastre períodos de férias, destaque conflitos e exporte o gráfico em PDF. "
    "Na visualização, use a rolagem do mouse para aproximar ou afastar os dias."
)

selected_section = render_sidebar_data_controls()
if selected_section == "Cadastrar férias":
    render_add_form_sidebar()
else:
    render_editor_sidebar()

df = build_dataframe(st.session_state.records)

st.subheader("Visualização")
plotly_fig = create_plotly_gantt(df)
st.plotly_chart(
    plotly_fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    },
)

if not df.empty:
    overlap_days = sorted(compute_overlap_days(df))
    if overlap_days:
        st.warning(
            "Existem conflitos nestes dias: "
            + ", ".join(day.strftime("%d/%m/%Y") for day in overlap_days)
        )
    else:
        st.success("Nenhum conflito de férias encontrado.")

    json_bytes = dataframe_to_json_bytes(df)
    pdf_fig = create_pdf_figure(df)
    pdf_bytes = figure_to_pdf_bytes(pdf_fig)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Baixar JSON",
            data=json_bytes,
            file_name=DEFAULT_JSON_NAME,
            mime="application/json",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Baixar PDF do gráfico",
            data=pdf_bytes,
            file_name="grafico_ferias.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
else:
    st.info("Adicione um ou mais períodos para visualizar o gráfico e liberar as exportações.")
