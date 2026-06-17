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
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode, DataReturnMode

# 加載環境變數
load_dotenv()

local_tz = pytz.timezone('Asia/Taipei')

# --- 多語系設定 ---
def get_translations(lang_code):
    translations = {
        'en': {
            'page_title': 'PulseGuard Analytics',
            'title': 'PulseGuard | Remote Health Analytics Dashboard',
            'sidebar_filters': 'Filters',
            'date_range': 'Date Range',
            'status_filter': 'Status Filter',
            'env_select': 'Environment',
            'env_prod': 'Production',
            'env_test': 'Test',
            'test_mode_warning': 'Currently in Test Mode. Viewing simulated test data.',
            'expander_title': '🔍 View Status Criteria & Column Descriptions',
            'expander_left_title': '🩺 Health Status Criteria',
            'expander_right_title': '📊 Algorithm Descriptions',
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
            'week_format': '%G-W%V',
            'status_map': {"NORMAL": "NORMAL", "WARNING": "WARNING", "DANGER": "DANGER"},
            'col_no': '#',
            'col_time': 'Timestamp',
            'col_status': 'Status',
            'col_avg_bpm': 'Avg BPM',
            'col_ema_bpm': 'EMA BPM',
            'col_spo2': 'SpO2 (%)',
            'help_status': """
            * 🚨 **DANGER**: SpO2 ≤ 90%, EMA ≤ 50 or ≥ 140, or |ΔBPM| ≥ 50
            * ⚠️ **WARNING**: Metrics outside normal range but not meeting danger criteria
            * 💡 **Note**: This log automatically records non-normal events (DANGER, WARNING) for clinical tracking. Normal historical data can be viewed in the Trends and Statistics tabs..""",
            'help_avg_bpm': "15s Moving Average BPM: Calculates the mean of the last 15 signals to smooth out noise.",
            'help_ema_bpm': "Exponential Moving Average (EMA): Uses a time-series filtering algorithm (30% current, 70% historical) to reduce measurement errors.",
            'help_spo2': "Oxygen Saturation (%): Displays the 15-second moving average, which is more medically representative than raw data. Normal values are usually above 95%."
        },
        'zh': {
            'page_title': '遠端健康數據分析',
            'title': 'PulseGuard｜遠端健康智慧監控分析儀表板',
            'sidebar_filters': '篩選條件',
            'date_range': '日期範圍',
            'status_filter': '狀態過濾',
            'env_select': '運行環境',
            'env_prod': '正式環境',
            'env_test': '測試環境',
            'test_mode_warning': '目前處於測試模式，檢視的數據為模擬測試資料。',
            'expander_title': '🔍 檢視狀態判定標準與欄位說明',
            'expander_left_title': '🩺 狀態判定標準',
            'expander_right_title': '📊 欄位演算法說明',
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
            'week_format': '%G-週%V',
            'status_map': {"NORMAL": "正常", "WARNING": "警告", "DANGER": "危險"},
            'col_no': '序號',
            'col_time': '時間戳記',
            'col_status': '狀態',
            'col_avg_bpm': '平均心率',
            'col_ema_bpm': 'EMA心率',
            'col_spo2': '血氧飽和度 (%)',
            'help_status': """
            * 🚨 **危險 (DANGER)**：滿足任一條件 (SpO2 <= 90%, EMA <= 50 或 >= 140, |ΔBPM| >= 50)
            * ⚠️ **警告 (WARNING)**：未達危急標準，但任一指標超出正常範圍
            * 💡 **說明**：本誌僅自動節錄並留存「非正常（DANGER, WARNING）」之觸發事件，正常（NORMAL）數據請至生理趨勢與統計分頁檢視。""",
            'help_avg_bpm': "15秒移動平均心率 (Moving Average)：計算最近 15 筆訊號均值，用以平滑即時雜訊，呈現穩定的心跳趨勢。",
            'help_ema_bpm': "指數移動平均心率 (EMA)：導入時序濾波演算法（目前 30%，歷史 70% 權重），有效抑制單點量測誤差，精準反映心血管實際生理趨勢。",
            'help_spo2': "血氧飽和度百分比：顯示最近 15 秒的訊號移動平均值，較純即時數值更具醫學代表性。正常值通常在 95% 以上。"
        }
    }
    lang = "zh" if lang_code == "zh" else "en"
    return translations[lang], lang

# 保留 color_status 供測試與潛在回退使用
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
def fetch_data(start_date, end_date, env="production"):
    """從 MongoDB 讀取數據並進行預處理，返回 (DataFrame, 是否發生錯誤)"""
    try:
        client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=2000)
        # 測試連線
        client.admin.command('ping')
    except Exception as e:
        # 返回空 DataFrame 與 錯誤標記
        return pd.DataFrame(), True

    db_name = os.getenv("MONGO_DB_NAME")
    col_name = os.getenv("MONGO_COL_NAME")

    # 將日期轉換為 UTC 時間戳進行查詢
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)

    db = client[db_name]
    collection = db[col_name]

    # 執行查詢並按時間排序，使用投影減少傳輸量
    # 排除 RESET 狀態與測試數據 (data_source="test")
    projection = {
        "timestamp": 1,
        "analysis_status": 1,
        "avg_bpm": 1,
        "ema_bpm": 1,
        "spo2": 1,
        "_id": 0
    }
    query = {
        "timestamp": {"$gte": start_dt, "$lte": end_dt},
        "analysis_status": {"$ne": "RESET"},
        "data_source": env
    }
    cursor = collection.find(query, projection).sort("timestamp", 1)

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
    return df, False

def calculate_kpis(df):
    """計算關鍵績效指標 (基於去重後的數據)"""
    # 1. 醫療健康指標
    total_samples = len(df)
    danger_count = len(df[df['analysis_status'] == "DANGER"])
    warning_count = len(df[df['analysis_status'] == "WARNING"])

    return total_samples, danger_count, warning_count

def get_daily_summary(df):
    """將原始數據按日聚合，用於趨勢圖"""
    if df.empty:
        # 返回具有正確結構但為空的 DataFrame，避免後續聚合報錯
        return pd.DataFrame(columns=['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min'])

    df_copy = df.copy()
    df_copy['date'] = df_copy['timestamp'].dt.date
    summary = df_copy.groupby('date').agg({
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
    df_hourly['priority'] = df_hourly['analysis_status'].map(priority_map)
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
    """計算過去一個月的範圍 (30天前到今天)"""
    today = datetime.now(local_tz).date()
    start_date = today - timedelta(days=30)
    return start_date, today

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

def main():
    # --- 1. URL 參數讀取與環境初始化 ---
    # 使用 Streamlit 最新推薦的 st.query_params 讀取 URL 參數
    # 支援參數：env (prod/test), lang (zh/en)
    query_params = st.query_params

    # 處理語系參數 (預設為英文 'en')
    lang_code = query_params.get("lang", "en")
    t, lang = get_translations(lang_code)

    # 處理環境參數：根據規格，預設或 env=prod 進入正式環境，env=test 進入測試環境
    env_param = query_params.get("env", "prod")
    if env_param not in ["prod", "test"]:
        env_param = "prod"

    # 內部邏輯對照：prod -> production, test -> test
    initial_env = "production" if env_param == "prod" else "test"

    # --- 2. 頁面配置 ---
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")

    st.set_page_config(
        page_title=t['page_title'],
        page_icon=icon_path if os.path.exists(icon_path) else None,
        layout="wide"
    )

    # --- 3. UI 頁面標題 ---
    st.title(t['title'])

    # --- 4. 側邊欄篩選器 ---
    st.sidebar.header(t['sidebar_filters'])

    # 環境切換：根據 URL 參數設定預設選項
    env_options = ["production", "test"]
    env_index = env_options.index(initial_env)

    env_mode = st.sidebar.selectbox(
        t['env_select'],
        options=env_options,
        index=env_index,
        format_func=lambda x: t['env_prod'] if x == "production" else t['env_test'],
        key="env_selector"
    )

    # 當使用者透過側邊欄手動切換環境時，同步更新 URL 參數
    current_env_param = "prod" if env_mode == "production" else "test"
    if current_env_param != env_param:
        # 更新 URL 參數並觸發頁面重整以確保環境切換生效
        st.query_params["env"] = current_env_param
        st.rerun()

    if env_mode == "test":
        st.warning(t['test_mode_warning'])

    default_start, default_end = get_default_range()
    date_range = st.sidebar.date_input(
        t['date_range'],
        value=(default_start, default_end),
        min_value=datetime(2020, 1, 1).date(),
        max_value=default_end
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

    # 底部緩衝空間：在日期選擇器下方增加垂直空間
    # 目的：確保當使用者點擊 st.date_input 時，下方有足夠餘裕讓彈出面板顯示，
    # 從而防止 Streamlit (及底層 BaseWeb 元件) 因為偵測到靠近視窗底部而自動將面板轉向（向上彈出）。
    # 這裡使用 600px 的隱形區塊來確保面板能穩定向下開啟。
    st.sidebar.markdown('<div style="height: 600px;"></div>', unsafe_allow_html=True)

    # --- 數據抓取與處理 ---
    fetched_df, connection_error = fetch_data(start_date, end_date, env=env_mode)

    # 強制過濾所有 OFF-CHIP 紀錄 (確保 legacy 數據也不會顯示)
    if not fetched_df.empty:
        raw_df = fetched_df[fetched_df['analysis_status'] != "OFF-CHIP"].copy()
    else:
        raw_df = fetched_df

    if raw_df.empty:
        if connection_error:
            st.error("無法連線至資料庫，顯示模擬數據供參考。" if lang == 'zh' else "Database connection failed, showing mock data for reference.")
        else:
            st.warning("所選範圍內查無數據。" if lang == 'zh' else "No data found for the selected range.")
            return

        # --- 建立模擬數據供展示 (僅在資料庫連線失敗時) ---
        st.info("展示功能範例數據：" if lang == 'zh' else "Displaying feature sample data:")

        # 模擬數據下的 KPI 展示 (固定數值)
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(t['kpi_total'], 120)
        m_col2.metric(t['kpi_danger'], 5, delta_color="inverse")
        m_col3.metric(t['kpi_warning'], 12, delta_color="off")

        if env_mode == "production":
            mock_records = [
                {
                    "timestamp": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
                    "analysis_status": "NORMAL",
                    "avg_bpm": 72.4,
                    "ema_bpm": 71.8,
                    "spo2": 98.5
                }
            ]
        else:
            mock_records = [
                {
                    "timestamp": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
                    "analysis_status": "DANGER",
                    "avg_bpm": 145.0,
                    "ema_bpm": 142.5,
                    "spo2": 88.0
                },
                {
                    "timestamp": (datetime.now(local_tz) - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S'),
                    "analysis_status": "WARNING",
                    "avg_bpm": 105.0,
                    "ema_bpm": 102.0,
                    "spo2": 94.0
                }
            ]
        mock_data = pd.DataFrame(mock_records)

        # 轉換為顯示格式
        mock_display = mock_data.copy()
        mock_display['analysis_status'] = mock_display['analysis_status'].map(lambda x: t['status_map'].get(x, x))
        
        # 統一模擬數據的數值精度
        mock_display['avg_bpm'] = mock_display['avg_bpm'].round(1)
        mock_display['ema_bpm'] = mock_display['ema_bpm'].round(1)
        mock_display['spo2'] = mock_display['spo2'].round(0).astype(int)
        
        mock_display.insert(0, t['col_no'], range(1, len(mock_display) + 1))
        mock_display = mock_display.rename(columns={
            'timestamp': t['col_time'],
            'analysis_status': t['col_status'],
            'avg_bpm': t['col_avg_bpm'],
            'ema_bpm': t['col_ema_bpm'],
            'spo2': t['col_spo2']
        })

        # 渲染模擬數據的說明
        with st.expander(t['expander_title']):
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                st.markdown(f"**{t['expander_left_title']}**")
                st.markdown(t['help_status'])
            with e_col2:
                st.markdown(f"**{t['expander_right_title']}**")
                if lang == 'zh':
                    st.markdown("""
- **平均心率**：最近 15 筆訊號的移動平均值，用以平滑即時雜訊，呈現穩定的心跳趨勢。
- **EMA心率**：指數移動平均 (EMA)，導入時序濾波演算法（目前 30%，歷史 70% 權重），有效抑制單點量測誤差。
- **血氧飽和度 (%)**：顯示最近 15 秒的訊號移動平均值，較純即時數值更具醫學代表性。
                    """)
                else:
                    st.markdown("""
- **Avg BPM**: Moving average of the last 15 signals to smooth out noise.
- **EMA BPM**: Exponential Moving Average (30% current, 70% historical) to suppress measurement errors.
- **SpO2 (%)**: 15-second moving average, providing better clinical representation.
                    """)

        # 使用 AgGrid 顯示模擬數據
        render_aggrid(mock_display, t, t['col_status'])

    else:
        # 根據選取狀態過濾數據
        df = raw_df[raw_df['analysis_status'].isin(selected_statuses)].copy()

        # 預先生成聚合數據
        df_daily = get_daily_summary(df)
        df_hourly = get_hourly_deduplicated(df)

        # 計算 KPI
        total_samples, danger_count, warning_count = calculate_kpis(df_hourly)

        # --- KPI 卡片展示 ---
        col1, col2, col3 = st.columns(3)
        col1.metric(t['kpi_total'], total_samples)
        col2.metric(t['kpi_danger'], danger_count, delta_color="inverse")
        col3.metric(t['kpi_warning'], warning_count, delta_color="off")

        # --- 功能標籤頁 ---
        tab1, tab2, tab3 = st.tabs([t['tab_trends'], t['tab_stats'], t['tab_logs']])

        with tab1:
            if not df_daily.empty:
                st.plotly_chart(build_combined_physiological_chart(df_daily, t), use_container_width=True, config={'displayModeBar': 'hover'})
            else:
                st.info("所選篩選條件下無有效生理數據可供繪製趨勢圖。" if lang == 'zh' else "No valid physiological data available for trends under current filters.")

        with tab2:
            col_s1, col_s2 = st.columns(2)

            with col_s1:
                st.subheader(t['status_dist_title'])
                status_counts = df_hourly['analysis_status'].value_counts().reset_index()
                status_counts.columns = ['analysis_status', 'count']
                status_counts['label'] = status_counts['analysis_status'].map(t['status_map'])

                color_map = {"NORMAL": "green", "WARNING": "orange", "DANGER": "crimson"}
                fig_pie = px.pie(status_counts, values='count', names='label',
                                color='analysis_status', color_discrete_map=color_map,
                                labels={'label': t['tt_status'], 'count': t['tt_count']})

                fig_pie.update_traces(
                    hovertemplate=f"%{{label}}<br>{t['tt_count']}: %{{value}}<br>{t['tt_percent']}: %{{percent:.1%}}<extra></extra>"
                )
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': 'hover'})

            with col_s2:
                st.subheader(t['weekly_stats_title'])
                abnormal_df = df_hourly[df_hourly['analysis_status'].isin(["WARNING", "DANGER"])].copy()

                if not abnormal_df.empty:
                    abnormal_df['week'] = abnormal_df['timestamp'].dt.strftime(t['week_format'])

                    weekly_stats = abnormal_df.groupby(['week', 'analysis_status']).size().reset_index(name='count')
                    weekly_stats['status_label'] = weekly_stats['analysis_status'].map(t['status_map'])

                    bar_color_map = {
                        "WARNING": "orange",
                        "DANGER": "crimson"
                    }
                    translated_color_map = {t['status_map'][k]: v for k, v in bar_color_map.items()}

                    fig_bar = px.bar(weekly_stats, x='week', y='count', color='status_label',
                                    color_discrete_map=translated_color_map,
                                    category_orders={"status_label": [
                                        t['status_map']['DANGER'],
                                        t['status_map']['WARNING']
                                    ]},
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

            with st.expander(t['expander_title']):
                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    st.markdown(f"**{t['expander_left_title']}**")
                    st.markdown(t['help_status'])
                with e_col2:
                    st.markdown(f"**{t['expander_right_title']}**")
                    if lang == 'zh':
                        st.markdown("""
- **平均心率**：最近 15 筆訊號的移動平均值，用以平滑即時雜訊，呈現穩定的心跳趨勢。
- **EMA心率**：指數移動平均 (EMA)，導入時序濾波演算法（目前 30%，歷史 70% 權重），有效抑制單點量測誤差。
- **血氧飽和度 (%)**：顯示最近 15 秒的訊號移動平均值，較純即時數值更具醫學代表性。
                        """)
                    else:
                        st.markdown("""
- **Avg BPM**: Moving average of the last 15 signals to smooth out noise.
- **EMA BPM**: Exponential Moving Average (30% current, 70% historical) to suppress measurement errors.
- **SpO2 (%)**: 15-second moving average, providing better clinical representation.
                        """)

            log_df = df_hourly[df_hourly['analysis_status'] != "NORMAL"].copy()

            if not log_df.empty:
                display_df = log_df[['timestamp', 'analysis_status', 'avg_bpm', 'ema_bpm', 'spo2']].copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['analysis_status'] = display_df['analysis_status'].map(t['status_map'])

                display_df['avg_bpm'] = display_df['avg_bpm'].round(1)
                display_df['ema_bpm'] = display_df['ema_bpm'].round(1)
                display_df['spo2'] = display_df['spo2'].round(0).astype(int)

                display_df.insert(0, t['col_no'], range(1, len(display_df) + 1))

                column_mapping = {
                    'timestamp': t['col_time'],
                    'analysis_status': t['col_status'],
                    'avg_bpm': t['col_avg_bpm'],
                    'ema_bpm': t['col_ema_bpm'],
                    'spo2': t['col_spo2']
                }
                display_df = display_df.rename(columns=column_mapping)

                # 使用 AgGrid 顯示異常日誌
                render_aggrid(display_df, t, t['col_status'])

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

if __name__ == "__main__":
    main()
