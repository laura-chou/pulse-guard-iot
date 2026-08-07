import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def build_combined_physiological_chart(df_daily, t):
    """建立合併的生理趨勢圖 (心率與血氧獨立 X 軸)"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=False,       # 解耦，使兩個 Row 各自擁有獨立 X 軸與時間標記
        vertical_spacing=0.20,     # 增加間距至 20% 使血氧趨勢更往下一點，避免重疊與擁擠
        subplot_titles=(t['bpm_trend_title'], t['spo2_trend_title'])
    )

    # --- Row 1: Heart Rate ---
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

    # 用 customdata 把 bpm_max 與 bpm_min 綁定到平均心率的圖軌上
    custom_data_bpm = pd.DataFrame({
        'bpm_max': df_daily['bpm_max'],
        'bpm_min': df_daily['bpm_min']
    })

    bpm_hovertemplate = (
        "%{fullData.name}: %{y:.1f}<br>"
        "🔺 最高: %{customdata[0]:.1f}<br>"
        "🔻 最低: %{customdata[1]:.1f}<extra></extra>"
    )

    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['bpm_mean'],
        name=t['avg_bpm_trace'],
        line=dict(color='#00d4ff', width=2),
        customdata=custom_data_bpm,
        hovertemplate=bpm_hovertemplate
    ), row=1, col=1)

    # --- Row 2: 血氧 ---
    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['spo2_min'],
        name=t['min_spo2_trace'],
        line=dict(color='lime', width=2),
        hovertemplate=f"{t['tt_min_spo2']}: %{{y:.1f}}<extra></extra>"
    ), row=2, col=1)

    danger_label = f"{t['status_map']['DANGER']} (90%)"
    fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text=danger_label, row=2, col=1)

    # --- Row 1: 心率臨界線 ---
    fig.add_hline(y=140, line_dash="dash", line_color="red", annotation_text=f"{t['status_map']['DANGER']} (140)", row=1, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text=f"{t['status_map']['DANGER']} (50)", row=1, col=1)

    fig.update_layout(
        height=700,
        hovermode="x unified",
        showlegend=False          # 隱藏右上角標籤
    )
    # 心率趨勢圖（Row 1）Y軸刻度下限設定為 50
    fig.update_yaxes(title_text=t['col_avg_bpm'], range=[50, None], row=1, col=1)
    fig.update_yaxes(title_text=t['col_spo2'], row=2, col=1)

    # 統一 X 軸時間刻度格式為 MM-DD 且各自獨立顯示標題與標籤
    fig.update_xaxes(
        tickformat="%m-%d",
        showticklabels=True,
        title_text=t['col_time'],
        hoverformat="%Y-%m-%d"
    )

    return fig

def render_dataframe(df, t, status_col_key):
    """
    統一渲染 st.dataframe 的輔助函式
    """
    column_config = {}

    if t['col_time'] in df.columns:
        column_config[t['col_time']] = st.column_config.Column(
            width=180
        )

    numeric_cols = [t['col_avg_bpm'], t['col_ema_bpm'], t['col_spo2']]
    for col in numeric_cols:
        if col in df.columns:
            column_config[col] = st.column_config.NumberColumn(
                width=120
            )

    if status_col_key in df.columns:
        column_config[status_col_key] = st.column_config.Column(
            width=100
        )

    # 異常原因 (Description) 欄位
    if t['col_desc'] in df.columns:
        column_config[t['col_desc']] = st.column_config.Column(
            width=250
        )

    if t['col_no'] in df.columns:
        column_config[t['col_no']] = st.column_config.NumberColumn(
            width=60
        )

    # 定義條件格式化上色規則
    def style_status(val):
        if val == t['status_map']['DANGER']:
            return "background-color: crimson; color: white;"
        elif val == t['status_map']['WARNING']:
            return "background-color: orange; color: black;"
        return ""

    # 使用 Pandas Styler (df.style.map) 套用格式化
    styled_df = df
    if status_col_key in df.columns:
        styled_df = df.style.map(style_status, subset=[status_col_key])

    return st.dataframe(
        styled_df,
        column_config=column_config,
        hide_index=True,
        width="stretch"
    )

def load_custom_css():
    """載入 CSS 視覺美化樣式塊"""
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
