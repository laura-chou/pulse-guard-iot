import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# 加載環境變數（用於本地開發，部署至 Streamlit Cloud 時將使用 st.secrets）
load_dotenv()

# --- 頁面配置與多語系設定 ---
st.set_page_config(page_title="PulseGuard Analytics", layout="wide")

# 從 URL 參數獲取語言設定 (?lang=zh)
query_params = st.query_params
lang_code = query_params.get("lang", "en")
lang = "zh" if lang_code == "zh" else "en"

# 多語系字典
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
        'bpm_trend_title': 'Heart Rate Trend (Avg BPM & EMA BPM)',
        'spo2_trend_title': 'Oxygen Saturation Trend (SpO2)',
        'status_dist_title': 'Overall Health Status Distribution',
        'abnormal_dist_title': 'Abnormal Status Distribution by Time of Day',
        'download_csv': 'Download Filtered Data as CSV',
        'morning': 'Morning (00-11)',
        'afternoon': 'Afternoon (11-17)',
        'night': 'Night (17-24)',
        'status_map': {"NORMAL": "NORMAL", "WARNING": "WARNING", "DANGER": "DANGER"},
        'time_bins': ["Morning", "Afternoon", "Night"],
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
        'bpm_trend_title': '心率趨勢（移動平均與 EMA）',
        'spo2_trend_title': '血氧趨勢（SpO2）',
        'status_dist_title': '整體健康狀態佔比',
        'abnormal_dist_title': '不同時段異常狀態分佈',
        'download_csv': '下載篩選後的資料為 CSV',
        'morning': '早上 (00-11)',
        'afternoon': '中午 (11-17)',
        'night': '晚上 (17-24)',
        'status_map': {"NORMAL": "正常", "WARNING": "警告", "DANGER": "危險"},
        'time_bins': ["早上", "中午", "晚上"],
        'col_time': '時間戳記',
        'col_status': '狀態',
        'col_avg_bpm': '平均心率',
        'col_ema_bpm': 'EMA心率',
        'col_spo2': '血氧飽和度 (%)'
    }
}

t = translations[lang]
local_tz = pytz.timezone('Asia/Taipei')

# --- 資料庫連線與快取 ---
@st.cache_resource
def init_connection():
    """初始化 MongoDB 連線"""
    mongo_uri = os.getenv("MONGO_URI")
    return MongoClient(mongo_uri)

client = init_connection()

@st.cache_data(ttl=600)
def fetch_data(start_date, end_date):
    """從 MongoDB 讀取數據並進行預處理"""
    db_name = os.getenv("MONGO_DB_NAME")
    col_name = os.getenv("MONGO_COL_NAME")

    # 將日期轉換為 UTC 時間戳進行查詢
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)

    db = client[db_name]
    collection = db[col_name]

    # 執行查詢並按時間排序
    cursor = collection.find({
        "timestamp": {"$gte": start_dt, "$lte": end_dt}
    }).sort("timestamp", 1)

    df = pd.DataFrame(list(cursor))
    if not df.empty:
        # 處理時區轉換，防止 tz-naive 錯誤
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(pytz.utc)
        df['timestamp'] = df['timestamp'].dt.tz_convert(local_tz)

        # 移除 MongoDB 內部 ID
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)
    return df

# --- 時間範圍計算 ---
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

    # 計算 KPI
    total_samples = len(df)
    danger_count = len(df[df['status'] == "DANGER"])
    warning_count = len(df[df['status'] == "WARNING"])

    # --- KPI 卡片展示 ---
    col1, col2, col3 = st.columns(3)
    col1.metric(t['kpi_total'], total_samples)
    col2.metric(t['kpi_danger'], danger_count, delta_color="inverse")
    col3.metric(t['kpi_warning'], warning_count, delta_color="off")

    # --- 功能標籤頁 ---
    tab1, tab2, tab3 = st.tabs([t['tab_trends'], t['tab_stats'], t['tab_logs']])

    with tab1:
        # 1. 心率趨勢圖
        st.subheader(t['bpm_trend_title'])
        fig_bpm = go.Figure()
        fig_bpm.add_trace(go.Scatter(x=df['timestamp'], y=df['avg_bpm'], name='Avg BPM', line=dict(color='cyan')))
        fig_bpm.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_bpm'], name='EMA BPM', line=dict(color='magenta')))
        fig_bpm.update_layout(xaxis_title=t['col_time'], yaxis_title="BPM", hovermode="x unified", height=450)
        st.plotly_chart(fig_bpm, use_container_width=True)

        # 2. 血氧趨勢圖
        st.subheader(t['spo2_trend_title'])
        fig_spo2 = px.line(df, x='timestamp', y='spo2', color_discrete_sequence=['lime'])
        # 添加 90% 危險臨界線
        danger_label = f"{t['status_map']['DANGER']} (90%)"
        fig_spo2.add_hline(y=90, line_dash="dash", line_color="red", annotation_text=danger_label)
        fig_spo2.update_layout(xaxis_title=t['col_time'], yaxis_title="SpO2 (%)", height=450)
        st.plotly_chart(fig_spo2, use_container_width=True)

    with tab2:
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            # 健康狀態佔比圓餅圖
            st.subheader(t['status_dist_title'])
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            status_counts['label'] = status_counts['status'].map(t['status_map'])

            color_map = {"NORMAL": "green", "WARNING": "orange", "DANGER": "crimson"}
            fig_pie = px.pie(status_counts, values='count', names='label',
                             color='status', color_discrete_map=color_map)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_s2:
            # 不同時段（早上/中午/晚上）異常狀態分析
            st.subheader(t['abnormal_dist_title'])

            def categorize_hour(hour):
                if 0 <= hour < 11: return t['time_bins'][0]
                elif 11 <= hour < 17: return t['time_bins'][1]
                else: return t['time_bins'][2]

            # 僅針對異常數據進行分析
            abnormal_df = df[df['status'].isin(["WARNING", "DANGER"])].copy()
            if not abnormal_df.empty:
                abnormal_df['TimeOfDay'] = abnormal_df['timestamp'].dt.hour.apply(categorize_hour)

                # 統計與分組
                time_stats = abnormal_df.groupby(['TimeOfDay', 'status']).size().reset_index(name='count')
                time_stats['status_label'] = time_stats['status'].map(t['status_map'])

                # 將 color_map 也對應到翻譯後的標籤
                translated_color_map = {t['status_map'][k]: v for k, v in color_map.items()}

                fig_bar = px.bar(time_stats, x='TimeOfDay', y='count', color='status_label',
                                 barmode='group', color_discrete_map=translated_color_map,
                                 category_orders={"TimeOfDay": t['time_bins']})
                fig_bar.update_layout(xaxis_title="", yaxis_title="Count", legend_title_text="")
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("查無異常數據可供時段分析。" if lang == 'zh' else "No abnormal data to display.")

    with tab3:
        st.subheader(t['tab_logs'])

        # 過濾非 NORMAL 的日誌
        log_df = df[df['status'] != "NORMAL"].copy()

        if not log_df.empty:
            # 整理顯示用欄位
            display_df = log_df[['timestamp', 'status', 'avg_bpm', 'ema_bpm', 'spo2']].copy()
            display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            # 轉換狀態標籤為本地語言
            display_df['status'] = display_df['status'].map(t['status_map'])

            # 自定義表格顏色
            def color_status(val):
                if val == t['status_map']['DANGER']: color = 'background-color: crimson; color: white'
                elif val == t['status_map']['WARNING']: color = 'background-color: orange; color: black'
                else: color = ''
                return color

            st.dataframe(display_df.style.map(color_status, subset=['status']), use_container_width=True)

            # CSV 下載按鈕
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=t['download_csv'],
                data=csv,
                file_name=f"pulseguard_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
            )
        else:
            st.success("此期間無任何異常事件。" if lang == 'zh' else "No abnormal events recorded.")

# --- CSS 視覺美化 (深色背景與霓虹色調) ---
st.markdown("""
<style>
    .stMetric {
        background-color: #1e1e1e;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #00d4ff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stExpander"] {
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)
