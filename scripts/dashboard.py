"""
dashboard.py
~~~~~~~~~~~~
Streamlit dashboard for the Global Patent Intelligence Pipeline.

Run:
    streamlit run dashboard.py
"""

import os
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Patent Intelligence",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── Background ── */
.stApp {
    background: #0a0e1a;
    color: #e8eaf0;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0f1424 !important;
    border-right: 1px solid #1e2540;
}
[data-testid="stSidebar"] * {
    color: #c8ccd8 !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #1e2d4a;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: linear-gradient(180deg, #f5a623, #e8520a);
    border-radius: 3px 0 0 3px;
}
[data-testid="stMetricLabel"] {
    color: #7a8099 !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    font-family: 'Space Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    color: #f5a623 !important;
    font-size: 2rem !important;
    font-weight: 600 !important;
    font-family: 'Space Mono', monospace !important;
}
[data-testid="stMetricDelta"] {
    color: #4ec9a0 !important;
}

/* ── Headings ── */
h1, h2, h3 {
    font-family: 'Space Mono', monospace !important;
    color: #f0f2f8 !important;
}
h1 { letter-spacing: -0.02em; }

/* ── Tabs ── */
[data-testid="stTabs"] button {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
    color: #7a8099 !important;
    border-radius: 6px 6px 0 0 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f5a623 !important;
    border-bottom: 2px solid #f5a623 !important;
    background: #111827 !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
    border: 1px solid #1e2540 !important;
    border-radius: 8px !important;
    overflow: hidden;
}
.dvn-scroller { background: #0d1220 !important; }

/* ── Selectbox / slider ── */
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] > div {
    background: #111827 !important;
    border-color: #1e2540 !important;
    color: #e8eaf0 !important;
    border-radius: 8px !important;
}
.stSlider [data-testid="stThumbValue"] { color: #f5a623 !important; }

/* ── Section label ── */
.section-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #f5a623;
    margin-bottom: 0.4rem;
}

/* ── Rank badge ── */
.rank-badge {
    display: inline-block;
    background: #1a2240;
    border: 1px solid #2a3560;
    border-radius: 4px;
    padding: 2px 8px;
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: #f5a623;
    margin-right: 6px;
}

/* ── Chart containers ── */
[data-testid="stPlotlyChart"] {
    border: 1px solid #1e2540;
    border-radius: 12px;
    overflow: hidden;
    background: #0d1220;
}

/* ── Divider ── */
hr { border-color: #1e2540 !important; }

/* ── Info / warning boxes ── */
.stAlert { border-radius: 8px !important; }

/* ── Search input ── */
[data-testid="stTextInput"] input {
    background: #111827 !important;
    border-color: #1e2540 !important;
    color: #e8eaf0 !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ── DB Connection (cached) ────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "patent_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "ambrose"),
    )


@st.cache_data(ttl=300)
def run_query(sql: str, params=None) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


# ── Helper: plotly theme ──────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0d1220",
    plot_bgcolor="#0d1220",
    font=dict(family="DM Sans", color="#c8ccd8"),
    margin=dict(l=16, r=16, t=40, b=16),
    xaxis=dict(gridcolor="#1e2540", zerolinecolor="#1e2540"),
    yaxis=dict(gridcolor="#1e2540", zerolinecolor="#1e2540"),
    colorway=["#f5a623", "#4ec9a0", "#6c9eff", "#e05c97",
               "#b084f5", "#56c8d8", "#ffca28"],
)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚗️ Patent Intel")
    st.markdown("---")

    st.markdown('<div class="section-label">Filters</div>',
                unsafe_allow_html=True)

    # Year range
    year_range = run_query(
        "SELECT MIN(year) AS mn, MAX(year) AS mx FROM patents WHERE year IS NOT NULL"
    )
    min_yr = int(year_range["mn"].iloc[0])
    max_yr = int(year_range["mx"].iloc[0])

    selected_years = st.slider(
        "Year range", min_yr, max_yr, (min_yr, max_yr)
    )

    # Country filter
    countries_df = run_query(
        "SELECT DISTINCT COALESCE(l.country,'?') AS country "
        "FROM inventors i JOIN patent_inventors pi ON pi.inventor_id=i.inventor_id "
        "LEFT JOIN locations l ON l.location_id=i.location_id "
        "ORDER BY 1"
    )
    all_countries = countries_df["country"].tolist()
    top_countries_default = all_countries[:10]
    selected_countries = st.multiselect(
        "Countries", all_countries, default=top_countries_default
    )

    # Top N
    top_n = st.slider("Show top N", 5, 30, 15)

    st.markdown("---")
    st.markdown('<div class="section-label">Data source</div>',
                unsafe_allow_html=True)
    st.caption("USPTO / PatentsView\nCC BY 4.0 License")

    # Load report.json summary if exists
    report_path = Path("reports/report.json")
    if report_path.exists():
        with open(report_path) as f:
            _summary = json.load(f)
        st.caption(f"Last report: {_summary.get('generated_at','–')[:10]}")


# ── WHERE clause helpers ──────────────────────────────────────────────────────
yr_filter = f"p.year BETWEEN {selected_years[0]} AND {selected_years[1]}"

country_str = ", ".join(f"'{c}'" for c in selected_countries) if selected_countries else "''"
country_filter = f"COALESCE(l.country,'?') IN ({country_str})"


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:0'>Global Patent Intelligence</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='color:#7a8099;font-size:0.9rem;margin-top:4px'>"
    "USPTO · PatentsView Disambiguated Data · Interactive Dashboard</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── KPI Row ───────────────────────────────────────────────────────────────────
kpi_sql = f"""
SELECT
    COUNT(DISTINCT p.patent_id)   AS total_patents,
    COUNT(DISTINCT pi.inventor_id) AS total_inventors,
    COUNT(DISTINCT pc.company_id)  AS total_companies,
    COUNT(DISTINCT l.country)      AS total_countries
FROM patents p
LEFT JOIN patent_inventors pi ON pi.patent_id = p.patent_id
LEFT JOIN patent_companies pc ON pc.patent_id = p.patent_id
LEFT JOIN inventors i ON i.inventor_id = pi.inventor_id
LEFT JOIN locations l ON l.location_id = i.location_id
WHERE {yr_filter}
"""
kpis = run_query(kpi_sql).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Patents",    f"{int(kpis['total_patents']):,}")
c2.metric("Unique Inventors", f"{int(kpis['total_inventors']):,}")
c3.metric("Companies",        f"{int(kpis['total_companies']):,}")
c4.metric("Countries",        f"{int(kpis['total_countries']):,}")

st.markdown("<br>", unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_inventors, tab_companies, tab_countries, tab_trends, tab_explore = st.tabs([
    "📈  Overview",
    "🧑‍🔬  Inventors",
    "🏢  Companies",
    "🌍  Countries",
    "📅  Trends",
    "🔍  Explore",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        PLOTLY = True
    except ImportError:
        PLOTLY = False
        st.warning("Install `plotly` for interactive charts: `pip install plotly`")

    col_l, col_r = st.columns(2)

    # ── Yearly trend ──
    with col_l:
        st.markdown('<div class="section-label">Patents granted per year</div>',
                    unsafe_allow_html=True)
        trend_df = run_query(
            f"SELECT year, COUNT(*) AS patents FROM patents "
            f"WHERE {yr_filter} GROUP BY year ORDER BY year"
        )
        if PLOTLY and not trend_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend_df["year"], y=trend_df["patents"],
                mode="lines+markers",
                line=dict(color="#f5a623", width=2.5),
                marker=dict(size=6, color="#f5a623"),
                fill="tozeroy",
                fillcolor="rgba(245,166,35,0.08)",
                name="Patents",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=300,
                              xaxis_title="Year", yaxis_title="Patents")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(trend_df, use_container_width=True)

    # ── Top 10 companies mini chart ──
    with col_r:
        st.markdown('<div class="section-label">Top companies (snapshot)</div>',
                    unsafe_allow_html=True)
        top_co_sql = f"""
            SELECT c.name AS company, COUNT(DISTINCT pc.patent_id) AS patents
            FROM companies c
            JOIN patent_companies pc ON pc.company_id = c.company_id
            JOIN patents p ON p.patent_id = pc.patent_id
            WHERE {yr_filter}
            GROUP BY c.name ORDER BY patents DESC LIMIT 10
        """
        co_df = run_query(top_co_sql)
        if PLOTLY and not co_df.empty:
            fig2 = go.Figure(go.Bar(
                x=co_df["patents"][::-1],
                y=co_df["company"][::-1],
                orientation="h",
                marker_color="#6c9eff",
                marker_line_width=0,
            ))
            fig2.update_layout(**PLOTLY_LAYOUT, height=300,
                               xaxis_title="Patents", yaxis_title="")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.dataframe(co_df, use_container_width=True)

    # ── Country pie ──
    st.markdown("---")
    st.markdown('<div class="section-label">Patent share by country</div>',
                unsafe_allow_html=True)
    ctry_sql = f"""
        SELECT COALESCE(l.country,'?') AS country,
               COUNT(DISTINCT pi.patent_id) AS patents
        FROM patent_inventors pi
        JOIN inventors i ON i.inventor_id = pi.inventor_id
        LEFT JOIN locations l ON l.location_id = i.location_id
        JOIN patents p ON p.patent_id = pi.patent_id
        WHERE {yr_filter}
        GROUP BY l.country ORDER BY patents DESC LIMIT 12
    """
    ctry_df = run_query(ctry_sql)
    if PLOTLY and not ctry_df.empty:
        fig3 = px.pie(
            ctry_df, names="country", values="patents",
            hole=0.45,
            color_discrete_sequence=["#f5a623","#4ec9a0","#6c9eff","#e05c97",
                                      "#b084f5","#56c8d8","#ffca28","#ff7043",
                                      "#aed581","#ef5350","#26c6da","#ab47bc"],
        )
        fig3.update_layout(**PLOTLY_LAYOUT, height=380,
                           legend=dict(orientation="v", x=1.02))
        fig3.update_traces(textfont_color="#e8eaf0", textfont_size=12)
        st.plotly_chart(fig3, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INVENTORS  (Q1 + Q7)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_inventors:
    st.markdown("### Q1 · Top Inventors by Patent Count")

    inv_sql = f"""
        SELECT
            i.name                          AS inventor,
            COALESCE(l.country,'?')         AS country,
            COUNT(DISTINCT pi.patent_id)    AS patents
        FROM inventors i
        JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
        JOIN patents p ON p.patent_id = pi.patent_id
        LEFT JOIN locations l ON l.location_id = i.location_id
        WHERE {yr_filter}
          AND {country_filter}
        GROUP BY i.name, l.country
        ORDER BY patents DESC
        LIMIT {top_n}
    """
    inv_df = run_query(inv_sql)

    col_l, col_r = st.columns([3, 2])

    with col_l:
        if PLOTLY and not inv_df.empty:
            fig = go.Figure(go.Bar(
                x=inv_df["patents"][::-1],
                y=inv_df["inventor"][::-1],
                orientation="h",
                marker=dict(
                    color=inv_df["patents"][::-1],
                    colorscale=[[0,"#1a2240"],[1,"#f5a623"]],
                    line_width=0,
                ),
                text=inv_df["patents"][::-1],
                textposition="outside",
                textfont=dict(color="#f5a623", size=11,
                              family="Space Mono"),
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=max(350, top_n * 32),
                              xaxis_title="Patents", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-label">Data table</div>',
                    unsafe_allow_html=True)
        # Styled rank table
        for idx, row in inv_df.iterrows():
            rank = idx + 1
            st.markdown(
                f'<span class="rank-badge">#{rank}</span>'
                f'<b style="color:#e8eaf0">{row["inventor"]}</b>'
                f'<span style="color:#7a8099;font-size:0.82rem"> '
                f'· {row["country"]} · {row["patents"]:,} patents</span>',
                unsafe_allow_html=True,
            )

    # ── Q7: Window function ranking ──
    st.markdown("---")
    st.markdown("### Q7 · Ranked Inventors (Window Functions)")
    rank_sql = f"""
        WITH counts AS (
            SELECT
                i.name AS inventor,
                COALESCE(l.country,'?') AS country,
                COUNT(DISTINCT pi.patent_id) AS patents
            FROM inventors i
            JOIN patent_inventors pi ON pi.inventor_id = i.inventor_id
            JOIN patents p ON p.patent_id = pi.patent_id
            LEFT JOIN locations l ON l.location_id = i.location_id
            WHERE {yr_filter}
            GROUP BY i.name, l.country
        )
        SELECT
            inventor, country, patents,
            RANK() OVER (ORDER BY patents DESC) AS global_rank,
            RANK() OVER (PARTITION BY country ORDER BY patents DESC) AS country_rank,
            ROUND(100.0 * patents / SUM(patents) OVER(), 4) AS pct
        FROM counts
        ORDER BY global_rank
        LIMIT {top_n}
    """
    rank_df = run_query(rank_sql)
    st.dataframe(
        rank_df.style
            .format({"pct": "{:.4f}%", "patents": "{:,}"})
            .background_gradient(subset=["patents"],
                                 cmap="YlOrBr"),
        use_container_width=True,
        height=400,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPANIES  (Q2 + Q6)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_companies:
    st.markdown("### Q2 · Top Companies by Patent Count")

    comp_sql = f"""
        SELECT
            c.name                          AS company,
            COALESCE(l.country,'?')         AS country,
            COUNT(DISTINCT pc.patent_id)    AS patents
        FROM companies c
        JOIN patent_companies pc ON pc.company_id = c.company_id
        JOIN patents p ON p.patent_id = pc.patent_id
        LEFT JOIN locations l ON l.location_id = c.location_id
        WHERE {yr_filter}
        GROUP BY c.name, l.country
        ORDER BY patents DESC
        LIMIT {top_n}
    """
    comp_df = run_query(comp_sql)

    if PLOTLY and not comp_df.empty:
        fig = px.bar(
            comp_df, x="patents", y="company",
            orientation="h", color="patents",
            color_continuous_scale=["#1a2240", "#4ec9a0"],
            text="patents",
        )
        fig.update_traces(textposition="outside",
                          textfont=dict(color="#4ec9a0",
                                        family="Space Mono", size=10))
        fig.update_layout(**PLOTLY_LAYOUT,
                          height=max(350, top_n * 32),
                          coloraxis_showscale=False,
                          xaxis_title="Patents", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    # ── Q6: CTE – significant companies ──
    st.markdown("---")
    st.markdown("### Q6 · Significant Companies (CTE Query)")
    st.caption("Companies with more than 50 patents and their share of total.")

    cte_sql = f"""
        WITH
        company_counts AS (
            SELECT c.name AS company, COALESCE(l.country,'?') AS country,
                   COUNT(DISTINCT pc.patent_id) AS patents
            FROM companies c
            JOIN patent_companies pc ON pc.company_id = c.company_id
            JOIN patents p ON p.patent_id = pc.patent_id
            LEFT JOIN locations l ON l.location_id = c.location_id
            WHERE {yr_filter}
            GROUP BY c.name, l.country
        ),
        totals AS (SELECT COUNT(*) AS total FROM patents WHERE {yr_filter})
        SELECT company, country, patents,
               ROUND(100.0 * patents / total, 4) AS pct_of_total
        FROM company_counts CROSS JOIN totals
        WHERE patents > 50
        ORDER BY patents DESC
    """
    cte_df = run_query(cte_sql)
    st.dataframe(
        cte_df.style
            .format({"pct_of_total": "{:.4f}%", "patents": "{:,}"})
            .bar(subset=["patents"], color="#1e3a5f"),
        use_container_width=True,
        height=420,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — COUNTRIES  (Q3)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_countries:
    st.markdown("### Q3 · Countries Producing the Most Patents")

    ctry_full_sql = f"""
        SELECT
            COALESCE(l.country,'UNKNOWN') AS country,
            COUNT(DISTINCT pi.patent_id)  AS patents,
            ROUND(100.0 * COUNT(DISTINCT pi.patent_id) /
                  SUM(COUNT(DISTINCT pi.patent_id)) OVER(), 2) AS pct_share
        FROM patent_inventors pi
        JOIN inventors i ON i.inventor_id = pi.inventor_id
        LEFT JOIN locations l ON l.location_id = i.location_id
        JOIN patents p ON p.patent_id = pi.patent_id
        WHERE {yr_filter}
        GROUP BY l.country
        ORDER BY patents DESC
        LIMIT 30
    """
    ctry_full = run_query(ctry_full_sql)

    col_l, col_r = st.columns([3, 2])

    with col_l:
        if PLOTLY and not ctry_full.empty:
            fig = px.bar(
                ctry_full.head(20), x="country", y="patents",
                color="patents",
                color_continuous_scale=["#1a2240","#f5a623"],
                text="pct_share",
            )
            fig.update_traces(
                texttemplate="%{text}%",
                textposition="outside",
                textfont=dict(color="#f5a623", size=10,
                              family="Space Mono"),
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=420,
                              coloraxis_showscale=False,
                              xaxis_title="Country",
                              yaxis_title="Patents")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-label">Full table</div>',
                    unsafe_allow_html=True)
        st.dataframe(
            ctry_full.style
                .format({"patents": "{:,}", "pct_share": "{:.2f}%"})
                .bar(subset=["pct_share"], color="#1e2d4a"),
            use_container_width=True,
            height=420,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — TRENDS  (Q4)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_trends:
    st.markdown("### Q4 · Patent Trends Over Time")

    trend_full_sql = """
        SELECT year, COUNT(*) AS patents,
               COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY year) AS yoy_change
        FROM patents
        WHERE year IS NOT NULL
        GROUP BY year ORDER BY year
    """
    trend_full = run_query(trend_full_sql)

    if PLOTLY and not trend_full.empty:
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown('<div class="section-label">Absolute count</div>',
                        unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend_full["year"], y=trend_full["patents"],
                mode="lines+markers",
                line=dict(color="#f5a623", width=2.5),
                marker=dict(size=5),
                fill="tozeroy", fillcolor="rgba(245,166,35,0.07)",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=350,
                              xaxis_title="Year", yaxis_title="Patents")
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown('<div class="section-label">Year-over-year change</div>',
                        unsafe_allow_html=True)
            yoy = trend_full.dropna(subset=["yoy_change"])
            colors = ["#4ec9a0" if v >= 0 else "#e05c97"
                      for v in yoy["yoy_change"]]
            fig2 = go.Figure(go.Bar(
                x=yoy["year"], y=yoy["yoy_change"],
                marker_color=colors,
                marker_line_width=0,
            ))
            fig2.add_hline(y=0, line_color="#7a8099", line_dash="dot")
            fig2.update_layout(**PLOTLY_LAYOUT, height=350,
                               xaxis_title="Year",
                               yaxis_title="YoY Change")
            st.plotly_chart(fig2, use_container_width=True)

    # Full data table
    st.markdown("---")
    st.dataframe(
        trend_full.style
            .format({"patents": "{:,}", "yoy_change": "{:+,.0f}"})
            .applymap(lambda v: "color:#4ec9a0" if isinstance(v, (int,float)) and v > 0
                      else ("color:#e05c97" if isinstance(v,(int,float)) and v < 0 else ""),
                      subset=["yoy_change"]),
        use_container_width=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — EXPLORE  (Q5 JOIN)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_explore:
    st.markdown("### Q5 · Explore Patents (JOIN Query)")
    st.caption("Search patents with their inventors and assignee companies.")

    search_col, country_col = st.columns([3, 1])
    search_term = search_col.text_input("🔍  Search patent title", "")
    exp_country = country_col.selectbox("Inventor country", ["All"] + all_countries)

    join_sql = f"""
        SELECT
            p.patent_id,
            p.title,
            p.grant_date,
            p.year,
            i.name   AS inventor,
            il.country AS inv_country,
            c.name   AS company,
            cl.country AS co_country
        FROM patents p
        JOIN patent_inventors pi  ON pi.patent_id  = p.patent_id
        JOIN inventors i          ON i.inventor_id = pi.inventor_id
        LEFT JOIN locations il    ON il.location_id = i.location_id
        LEFT JOIN patent_companies pc ON pc.patent_id = p.patent_id
        LEFT JOIN companies c     ON c.company_id  = pc.company_id
        LEFT JOIN locations cl    ON cl.location_id = c.location_id
        WHERE {yr_filter}
        {"AND p.title ILIKE '%" + search_term + "%'" if search_term else ""}
        {"AND il.country = '" + exp_country + "'" if exp_country != "All" else ""}
        ORDER BY p.grant_date DESC
        LIMIT 500
    """

    with st.spinner("Running JOIN query …"):
        join_df = run_query(join_sql)

    st.markdown(
        f'<p style="color:#7a8099;font-size:0.82rem">'
        f'Showing {len(join_df):,} results</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(join_df, use_container_width=True, height=500)

    # Download button
    csv_data = join_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇  Download results as CSV",
        data=csv_data,
        file_name="patent_search_results.csv",
        mime="text/csv",
    )
