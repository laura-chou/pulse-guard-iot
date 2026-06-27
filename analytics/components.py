import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode, DataReturnMode

def color_status(val, t):
    if val == t['status_map']['DANGER']: color = 'background-color: crimson; color: white'
    elif val == t['status_map']['WARNING']: color = 'background-color: orange; color: black'
    else: color = ''
    return color

def build_combined_physiological_chart(df_daily, t):
    """建立合併的生理趨勢圖 (心率與血氧共用 X 軸)"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(t['bpm_trend_title'], t['spo2_trend_title'])
    )

    # --- Row 1: Heart Rate ---
    # 範圍填充 (Min-Max)
    fig.add_trace(go.Scatter(
        x=pd.concat([df_daily['date'], df_daily['date'][::-1]]),
        y=pd.concat([df_daily['bpm_max'], df_daily['bpm_min'][::-1]]),
        fill='toself',
        fillcolor='rgba(0, 212, 255, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        showlegend=False,
        name=t['bpm_range']
    ), row=1, col=1)

    # 平均線
    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['bpm_mean'],
        name=t['avg_bpm_trace'],
        line=dict(color='#00d4ff', width=2),
        hovertemplate=f"{t['tt_date']}: %{{x}}<br>{t['tt_avg_bpm']}: %{{y:.1f}}<extra></extra>"
    ), row=1, col=1)

    # --- Row 2: SpO₂ ---
    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['spo2_min'],
        name=t['min_spo2_trace'],
        line=dict(color='lime', width=2),
        hovertemplate=f"{t['tt_date']}: %{{x}}<br>{t['tt_min_spo2']}: %{{y:.1f}}<extra></extra>"
    ), row=2, col=1)

    # 添加 90% 危險臨界線
    danger_label = f"{t['status_map']['DANGER']} (90%)"
    fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text=danger_label, row=2, col=1)

    # --- Layout ---
    fig.update_layout(
        height=700,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text=t['col_avg_bpm'], row=1, col=1)
    fig.update_yaxes(title_text=t['col_spo2'], row=2, col=1)
    fig.update_xaxes(title_text=t['col_time'], row=2, col=1)

    return fig

def render_aggrid(df, t, status_col_key):
    """
    統一渲染 AG Grid 的輔助函式
    """
    gb = GridOptionsBuilder.from_dataframe(df)

    # 默認配置：移除功能選單與篩選圖示，預設置中對齊
    gb.configure_default_column(
        suppressMenu=True,
        suppressHeaderFilterButton=True,
        filter=False,
        headerClass='ag-center-aligned-header',
        cellStyle={'textAlign': 'center'},
        flex=1,
        resizable=True
    )

    # 針對數值欄位：靠右對齊 (內容)
    numeric_cols = [t['col_avg_bpm'], t['col_ema_bpm'], t['col_spo2']]
    for col in numeric_cols:
        if col in df.columns:
            gb.configure_column(
                col,
                headerClass='ag-right-aligned-header',
                cellStyle={'textAlign': 'right'}
            )

    # 狀態欄位特殊處理：背景顏色 (JsCode)
    cellsytle_jscode = JsCode(f"""
    function(params) {{
        let baseStyle = {{ 'textAlign': 'center' }};
        if (params.value === '{t['status_map']['DANGER']}') {{
            return {{ ...baseStyle, 'color': 'white', 'backgroundColor': 'crimson' }};
        }} else if (params.value === '{t['status_map']['WARNING']}') {{
            return {{ ...baseStyle, 'color': 'black', 'backgroundColor': 'orange' }};
        }} else {{
            return baseStyle;
        }}
    }};
    """)
    # 狀態欄位：置中對齊且
    gb.configure_column(
        status_col_key,
        cellStyle=cellsytle_jscode,
        maxWidth=120,
        flex=0
    )
    # 序號欄位：置中對齊且固定極小寬度
    if t['col_no'] in df.columns:
        gb.configure_column(
            t['col_no'],
            flex=0,
            width=50,
            maxWidth=60,
            cellStyle={'textAlign': 'center'}
        )

    gridOptions = gb.build()

    # 將 AgGrid 表頭文字置中
    custom_css = {
        ".ag-header-cell-label": {
            "justify-content": "center !important"
        }
    }

    return AgGrid(
        df,
        gridOptions=gridOptions,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        theme='streamlit',
        height=400,
        width='100%',
        custom_css=custom_css
    )

def load_custom_css():
    """載入 CSS 視覺美化"""
    st.markdown("""
    <style>
        [data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            padding: 20px;
            border-radius: 12px;
            border-left: 6px solid #00d4ff;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        div[data-testid="stExpander"] {
            border: none !important;
        }

        /* 側邊欄標籤樣式 (多語系) */
        span[data-baseweb="tag"]:has(span[title="NORMAL"]),
        span[data-baseweb="tag"]:has(span[title="正常"]) {
            background-color: #2E7D32 !important;
        }
        span[data-baseweb="tag"]:has(span[title="WARNING"]),
        span[data-baseweb="tag"]:has(span[title="警告"]) {
            background-color: #EF6C00 !important;
        }
        span[data-baseweb="tag"]:has(span[title="DANGER"]),
        span[data-baseweb="tag"]:has(span[title="危險"]) {
            background-color: #C62828 !important;
        }
        span[data-baseweb="tag"] span {
            color: #FFFFFF !important;
        }
    </style>
    """, unsafe_allow_html=True)
