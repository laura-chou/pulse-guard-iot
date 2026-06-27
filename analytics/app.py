import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# 匯入核心邏輯與 UI 元件
from core.i18n import get_translations
from core.database import fetch_data, get_mock_data
from core.processor import calculate_kpis, get_daily_summary, get_hourly_deduplicated, get_default_range
from components.ui import build_combined_physiological_chart, render_aggrid, load_custom_css

def main():
    # --- 1. URL 參數讀取與環境初始化 ---
    query_params = st.query_params
    lang_code = query_params.get("lang", "en")
    t, lang = get_translations(lang_code)

    env_param = query_params.get("env", "prod")
    if env_param not in ["prod", "test"]:
        env_param = "prod"

    device_id = query_params.get("did", "MOCK_DEVICE_001")
    env_mode = "prod" if env_param == "prod" else "test"

    # --- 2. 頁面配置 ---
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    st.set_page_config(
        page_title=t['page_title'],
        page_icon=icon_path if os.path.exists(icon_path) else None,
        layout="wide"
    )

    # --- 3. UI 頁面標題 ---
    st.title(t['title'])
    st.caption(f"Device ID: {device_id}")

    # --- 4. 側邊欄篩選器 ---
    st.sidebar.header(t['sidebar_filters'])
    if env_mode == "test":
        st.warning(t['test_mode_warning'])

    default_start, default_end = get_default_range()
    date_range = st.sidebar.date_input(
        t['date_range'],
        value=(default_start, default_end),
        min_value=datetime(2020, 1, 1).date(),
        max_value=default_end
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

    status_options = ["NORMAL", "WARNING", "DANGER"]
    selected_statuses = st.sidebar.multiselect(
        t['status_filter'],
        options=status_options,
        default=status_options,
        format_func=lambda x: t['status_map'][x]
    )

    st.sidebar.markdown('<div style="height: 600px;"></div>', unsafe_allow_html=True)

    # --- 數據抓取與處理 ---
    fetched_df, connection_error = fetch_data(start_date, end_date, env=env_mode, device_id=device_id)

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

        st.info("展示功能範例數據：" if lang == 'zh' else "Displaying feature sample data:")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(t['kpi_total'], 120)
        m_col2.metric(t['kpi_danger'], 5, delta_color="inverse")
        m_col3.metric(t['kpi_warning'], 12, delta_color="off")

        mock_display = get_mock_data(env_mode, t)

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
- **SpO₂ (%)**: 15-second moving average, providing better clinical representation.
                    """)
        render_aggrid(mock_display, t, t['col_status'])

    else:
        df = raw_df[raw_df['analysis_status'].isin(selected_statuses)].copy()
        df_daily = get_daily_summary(df)
        df_hourly = get_hourly_deduplicated(df)
        total_samples, danger_count, warning_count = calculate_kpis(df_hourly)

        col1, col2, col3 = st.columns(3)
        col1.metric(t['kpi_total'], total_samples)
        col2.metric(t['kpi_danger'], danger_count, delta_color="inverse")
        col3.metric(t['kpi_warning'], warning_count, delta_color="off")

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
                fig_pie.update_traces(hovertemplate=f"%{{label}}<br>{t['tt_count']}: %{{value}}<br>{t['tt_percent']}: %{{percent:.1%}}<extra></extra>")
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': 'hover'})

            with col_s2:
                st.subheader(t['weekly_stats_title'])
                abnormal_df = df_hourly[df_hourly['analysis_status'].isin(["WARNING", "DANGER"])].copy()
                if not abnormal_df.empty:
                    abnormal_df['week'] = abnormal_df['timestamp'].dt.strftime(t['week_format'])
                    weekly_stats = abnormal_df.groupby(['week', 'analysis_status']).size().reset_index(name='count')
                    weekly_stats['status_label'] = weekly_stats['analysis_status'].map(t['status_map'])
                    bar_color_map = {"WARNING": "orange", "DANGER": "crimson"}
                    translated_color_map = {t['status_map'][k]: v for k, v in bar_color_map.items()}
                    fig_bar = px.bar(weekly_stats, x='week', y='count', color='status_label',
                                    color_discrete_map=translated_color_map,
                                    category_orders={"status_label": [t['status_map']['DANGER'], t['status_map']['WARNING']]},
                                    labels={'week': t['tt_week'], 'status_label': t['tt_status'], 'count': t['tt_count']})
                    fig_bar.update_traces(hovertemplate=f"{t['tt_week']}: %{{x}}<br>{t['tt_status']}: %{{fullData.name}}<br>{t['tt_count']}: %{{y}}<extra></extra>")
                    fig_bar.update_layout(xaxis_title="", yaxis_title=t['event_count'], legend_title_text="", yaxis=dict(tickmode='linear', tick0=0, dtick=1))
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
- **SpO₂ (%)**: 15-second moving average, providing better clinical representation.
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
                column_mapping = {'timestamp': t['col_time'], 'analysis_status': t['col_status'], 'avg_bpm': t['col_avg_bpm'], 'ema_bpm': t['col_ema_bpm'], 'spo2': t['col_spo2']}
                display_df = display_df.rename(columns=column_mapping)
                render_aggrid(display_df, t, t['col_status'])
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label=t['download_csv'], data=csv, file_name=f"pulseguard_analytics_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')
            else:
                st.success("此期間無任何異常事件。" if lang == 'zh' else "No abnormal events recorded.")

    load_custom_css()

if __name__ == "__main__":
    main()
