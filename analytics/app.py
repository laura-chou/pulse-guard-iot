import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

local_tz = pytz.timezone('Asia/Taipei')

# --- 多語系設定 ---
def get_translations(lang_code):
    translations = {
        'en': {
            'title': 'PulseGuard: Remote Health Analytics Dashboard',
            'sidebar_filters': 'Filters',
            'date_range': 'Date Range',
            'status_filter': 'Status Filter',
            'kpi_total': 'Total Samples',
            'kpi_danger': 'Danger Events',
            'kpi_warning': 'Warning Events',
            'tab_trends': '📈 Physiological Trends',
            'tab_stats': '📊 Status Statistics',
            'tab_logs': '📋 Abnormal Logs & Export',
            'bpm_trend_title': 'Heart Rate Trend (Daily Range & Avg)',
            'spo2_trend_title': 'Oxygen Saturation Trend (Daily Min SpO2)',
            'status_dist_title': 'Overall Health Status Distribution',
            'weekly_stats_title': 'Weekly Abnormal Event Trends',
            'bpm_range': 'BPM Range',
            'avg_bpm_trace': 'Avg BPM',
            'min_spo2_trace': 'Min SpO2',
            'event_count': 'Event Count',
            'tt_week': 'Week',
            'tt_status': 'Status',
            'tt_count': 'Event Count',
            'tt_date': 'Date',
            'tt_avg_bpm': 'Avg BPM',
            'tt_min_spo2': 'Min SpO2',
            'tt_percent': 'Percent',
            'download_csv': 'Download Filtered Data as CSV',
            'status_map': {"NORMAL": "NORMAL", "WARNING": "WARNING", "DANGER": "DANGER"},
            'col_no': '#',
            'col_time': 'Timestamp',
            'col_status': 'Status',
            'col_avg_bpm': 'Avg BPM',
            'col_ema_bpm': 'EMA BPM',
            'col_spo2': 'SpO2 (%)'
        },
        'zh': {
            'title': 'PulseGuard：遠端醫療歷史數據分析看板',
            'sidebar_filters': '篩選條件',
            'date_range': '日期範圍',
            'status_filter': '狀態過濾',
            'kpi_total': '總樣本數',
            'kpi_danger': '危險次數',
            'kpi_warning': '警告次數',
            'tab_trends': '📈 生理趨勢圖',
            'tab_stats': '📊 狀態統計',
            'tab_logs': '📋 異常日誌與匯出',
            'bpm_trend_title': '心率趨勢（日範圍與平均）',
            'spo2_trend_title': '血氧趨勢（每日最低 SpO2）',
            'status_dist_title': '整體健康狀態佔比',
            'weekly_stats_title': '每週異常事件趨勢',
            'bpm_range': '心率範圍',
            'avg_bpm_trace': '平均心率',
            'min_spo2_trace': '最低血氧',
            'event_count': '事件次數',
            'tt_week': '週別',
            'tt_status': '警示級別',
            'tt_count': '事件次數',
            'tt_date': '日期',
            'tt_avg_bpm': '平均心率',
            'tt_min_spo2': '最低血氧',
            'tt_percent': '比例',
            'download_csv': '下載篩選後的資料為 CSV',
            'status_map': {"NORMAL": "正常", "WARNING": "警告", "DANGER": "危險"},
            'col_no': '序號',
            'col_time': '時間戳記',
            'col_status': '狀態',
            'col_avg_bpm': '平均心率',
            'col_ema_bpm': 'EMA心率',
            'col_spo2': '血氧飽和度 (%)'
        }
    }
    lang = "zh" if lang_code == "zh" else "en"
    return translations[lang], lang

def color_status(val, t):
    if val == t['status_map']['DANGER']: color = 'background-color: crimson; color: white'
    elif val == t['status_map']['WARNING']: color = 'background-color: orange; color: black'
    else: color = ''
    return color

# --- 資料庫連線 ---
@st.cache_resource
def init_connection():
    """初始化 MongoDB 連線"""
    mongo_uri = os.getenv("MONGO_URI")
    return MongoClient(mongo_uri)

@st.cache_data(ttl=600)
def fetch_data(start_date, end_date):
    """從 MongoDB 讀取數據並進行預處理"""
    client = init_connection()
    db_name = os.getenv("MONGO_DB_NAME")
    col_name = os.getenv("MONGO_COL_NAME")

    # 將日期轉換為 UTC 時間戳進行查詢
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)

    db = client[db_name]
    collection = db[col_name]

    # 執行查詢並按時間排序，使用投影減少傳輸量
    projection = {
        "timestamp": 1,
        "status": 1,
        "avg_bpm": 1,
        "ema_bpm": 1,
        "spo2": 1,
        "_id": 0
    }
    cursor = collection.find(
        {"timestamp": {"$gte": start_dt, "$lte": end_dt}},
        projection
    ).sort("timestamp", 1)

    df = pd.DataFrame(list(cursor))
    if not df.empty:
        # 處理時區轉換
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(pytz.utc)
        df['timestamp'] = df['timestamp'].dt.tz_convert(local_tz)

        # 移除 MongoDB 內部 ID
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)
    return df

def calculate_kpis(df):
    """計算關鍵績效指標"""
    total_samples = len(df)
    danger_count = len(df[df['status'] == "DANGER"])
    warning_count = len(df[df['status'] == "WARNING"])
    return total_samples, danger_count, warning_count

def get_daily_summary(df):
    """將原始數據按日聚合，用於趨勢圖"""
    if df.empty:
        return df
    df_daily = df.copy()
    df_daily['date'] = df_daily['timestamp'].dt.date
    summary = df_daily.groupby('date').agg({
        'avg_bpm': ['min', 'max', 'mean'],
        'spo2': 'min'
    }).reset_index()
    # 扁平化多級索引列名
    summary.columns = ['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min']
    return summary

def get_hourly_deduplicated(df):
    """將原始數據按小時去重，僅保留每小時最高優先級的事件"""
    if df.empty:
        return df

    # 定義優先級：DANGER > WARNING > NORMAL
    priority_map = {"DANGER": 2, "WARNING": 1, "NORMAL": 0}
    df_hourly = df.copy()
    df_hourly['priority'] = df_hourly['status'].map(priority_map)
    df_hourly['hour'] = df_hourly['timestamp'].dt.floor('h')

    # 按小時分組，並找出每組中優先級最高的索引
    # 若優先級相同，則保留最早出現的紀錄
    idx = df_hourly.groupby('hour')['priority'].idxmax()
    return df_hourly.loc[idx].drop(columns=['priority', 'hour'])

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

    # --- Row 2: SpO2 ---
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

def get_default_range():
    """計算過去兩個完整日曆月的範圍"""
    today = datetime.now(local_tz)
    # 本月第一天
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 結束日期：上個月最後一天
    end_date = (first_day_this_month - timedelta(seconds=1)).date()
    # 上個月第一天
    first_day_prev_month = (first_day_this_month - timedelta(days=1)).replace(day=1)
    # 開始日期：前一個月的第一天
    start_date = (first_day_prev_month - timedelta(days=1)).replace(day=1).date()
    return start_date, end_date

def main():
    # --- 頁面配置與多語系設定 ---
    st.set_page_config(page_title="PulseGuard Analytics", layout="wide")

    # 從 URL 參數獲取語言設定 (?lang=zh)
    query_params = st.query_params
    lang_code = query_params.get("lang", "en")
    t, lang = get_translations(lang_code)

    # --- UI 頁面標題 ---
    st.title(t['title'])

    # --- 側邊欄篩選器 ---
    st.sidebar.header(t['sidebar_filters'])

    default_start, default_end = get_default_range()
    date_range = st.sidebar.date_input(
        t['date_range'],
        value=(default_start, default_end),
        min_value=datetime(2020, 1, 1).date(),
        max_value=datetime.now().date()
    )

    # 處理日期選擇器的回傳值
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

    # 狀態過濾（多選）
    status_options = ["NORMAL", "WARNING", "DANGER"]
    selected_statuses = st.sidebar.multiselect(
        t['status_filter'],
        options=status_options,
        default=status_options,
        format_func=lambda x: t['status_map'][x]
    )

    # --- 數據抓取與處理 ---
    raw_df = fetch_data(start_date, end_date)

    if raw_df.empty:
        st.warning("所選範圍內查無數據。" if lang == 'zh' else "No data found for the selected range.")
    else:
        # 根據選取狀態過濾數據
        df = raw_df[raw_df['status'].isin(selected_statuses)].copy()

        # 預先生成聚合數據
        df_daily = get_daily_summary(df)
        df_hourly = get_hourly_deduplicated(df)

        # 計算 KPI (使用去重後的數據以保持 UI 一致性)
        total_samples, danger_count, warning_count = calculate_kpis(df_hourly)

        # --- KPI 卡片展示 ---
        col1, col2, col3 = st.columns(3)
        col1.metric(t['kpi_total'], total_samples)
        col2.metric(t['kpi_danger'], danger_count, delta_color="inverse")
        col3.metric(t['kpi_warning'], warning_count, delta_color="off")

        # --- 功能標籤頁 ---
        tab1, tab2, tab3 = st.tabs([t['tab_trends'], t['tab_stats'], t['tab_logs']])

        with tab1:
            st.plotly_chart(build_combined_physiological_chart(df_daily, t), use_container_width=True, config={'displayModeBar': 'hover'})

        with tab2:
            col_s1, col_s2 = st.columns(2)

            with col_s1:
                st.subheader(t['status_dist_title'])
                # 統計使用去重後的數據，以符合「去重後用於統計」的要求
                status_counts = df_hourly['status'].value_counts().reset_index()
                status_counts.columns = ['status', 'count']
                status_counts['label'] = status_counts['status'].map(t['status_map'])

                color_map = {"NORMAL": "green", "WARNING": "orange", "DANGER": "crimson"}
                fig_pie = px.pie(status_counts, values='count', names='label',
                                 color='status', color_discrete_map=color_map,
                                 labels={'label': t['tt_status'], 'count': t['tt_count']})

                # 徹底移除底部的原始英文標籤 (status=NORMAL)
                fig_pie.update_traces(
                    hovertemplate=f"%{{label}}<br>{t['tt_count']}: %{{value}}<br>{t['tt_percent']}: %{{percent:.1%}}<extra></extra>"
                )
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': 'hover'})

            with col_s2:
                st.subheader(t['weekly_stats_title'])

                # 長條圖僅計算 WARNING 與 DANGER
                abnormal_df = df_hourly[df_hourly['status'].isin(["WARNING", "DANGER"])].copy()

                if not abnormal_df.empty:
                    # 計算 ISO 週 (格式: 2026-W18)
                    abnormal_df['week'] = abnormal_df['timestamp'].dt.strftime('%G-W%V')

                    weekly_stats = abnormal_df.groupby(['week', 'status']).size().reset_index(name='count')
                    weekly_stats['status_label'] = weekly_stats['status'].map(t['status_map'])

                    # 徹底隱藏 NORMAL 圖例
                    translated_color_map = {t['status_map'][k]: v for k, v in color_map.items() if k != "NORMAL"}

                    fig_bar = px.bar(weekly_stats, x='week', y='count', color='status_label',
                                     color_discrete_map=translated_color_map,
                                     category_orders={"status_label": [t['status_map']['DANGER'], t['status_map']['WARNING']]},
                                     labels={'week': t['tt_week'], 'status_label': t['tt_status'], 'count': t['tt_count']})

                    fig_bar.update_traces(
                        hovertemplate=f"{t['tt_week']}: %{{x}}<br>{t['tt_status']}: %{{fullData.name}}<br>{t['tt_count']}: %{{y}}<extra></extra>"
                    )

                    fig_bar.update_layout(
                        xaxis_title="",
                        yaxis_title=t['event_count'],
                        legend_title_text="",
                        yaxis=dict(tickmode='linear', tick0=0, dtick=1)
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': 'hover'})
                else:
                    st.info("查無異常數據可供週統計分析。" if lang == 'zh' else "No abnormal data for weekly analysis.")

        with tab3:
            st.subheader(t['tab_logs'])
            log_df = df_hourly[df_hourly['status'] != "NORMAL"].copy()

            if not log_df.empty:
                # 準備顯示用的 DataFrame
                display_df = log_df[['timestamp', 'status', 'avg_bpm', 'ema_bpm', 'spo2']].copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['status'] = display_df['status'].map(t['status_map'])

                # 數據格式化預處理
                display_df['spo2'] = display_df['spo2'].round(1)

                # 插入連續序號欄位
                display_df.insert(0, t['col_no'], range(1, len(display_df) + 1))

                # 欄位名稱轉換為多語系
                column_mapping = {
                    'timestamp': t['col_time'],
                    'status': t['col_status'],
                    'avg_bpm': t['col_avg_bpm'],
                    'ema_bpm': t['col_ema_bpm'],
                    'spo2': t['col_spo2']
                }
                display_df = display_df.rename(columns=column_mapping)

                # 使用 st.dataframe 展示，隱藏索引並優化樣式
                st.dataframe(
                    display_df.style.map(color_status, subset=[t['col_status']], t=t)
                    .format({
                        t['col_spo2']: '{:.1f}',
                        t['col_avg_bpm']: '{:.0f}',
                        t['col_ema_bpm']: '{:.0f}'
                    }),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        t['col_no']: st.column_config.Column(width="small")
                    }
                )

                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label=t['download_csv'],
                    data=csv,
                    file_name=f"pulseguard_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime='text/csv',
                )
            else:
                st.success("此期間無任何異常事件。" if lang == 'zh' else "No abnormal events recorded.")

    # --- CSS 視覺美化 ---
    st.markdown("""
    <style>
        /* 使用 Streamlit 變數實現主題動態切換 */
        [data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            padding: 20px;
            border-radius: 12px;
            border-left: 6px solid #00d4ff;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        /* 隱藏展開器邊框 */
        div[data-testid="stExpander"] {
            border: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
