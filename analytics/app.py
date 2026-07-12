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
from core.processor import (
    calculate_kpis, get_daily_summary, get_hourly_deduplicated,
    get_default_range, translate_reason_codes
)
from components.ui import build_combined_physiological_chart, render_aggrid, load_custom_css

def main():
    # --- 1. URL 參數讀取與環境初始化 ---
    query_params = st.query_params
    lang_code = query_params.get("lang", "en")
    t, lang = get_translations(lang_code)

    env_param = query_params.get("env", "prod")
    if env_param not in ["prod", "test"]:
        env_param = "prod"

    env_mode = "prod" if env_param == "prod" else "test"

    # 裝置 ID 邏輯處理
    device_id = query_params.get("did")
    if not device_id:
        if env_mode == "test":
            device_id = "MOCK_DEVICE_001"
        else:
            # prod 環境若缺少 did 則顯示錯誤並中斷
            st.error(t['missing_did'])
            return

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

    raw_df = fetched_df

    if raw_df.empty:
        if connection_error:
            st.error(t['db_connection_error_mock'])
        else:
            st.warning(t['no_data_found'])
            return

        st.info(t['sample_data_info'])
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(t['kpi_total'], 120)
        m_col2.metric(t['kpi_danger'], 5, delta_color="inverse")
        m_col3.metric(t['kpi_warning'], 12, delta_color="off")

        mock_display = get_mock_data(env_mode, t)

        with st.expander(t['expander_title']):
            e_col1, e_col2 = st.columns(2)
            with e_col1:
                st.markdown(f"**{t['expander_left_title']}**")
                st.markdown(t['help_status_display'], help=t['help_status_tooltip'])
            with e_col2:
                st.markdown(f"**{t['expander_right_title']}**")
                st.markdown(f"- **{t['col_avg_bpm']}**：{t['help_avg_bpm']}")
                st.markdown(f"- **{t['col_ema_bpm']}**：{t['help_ema_bpm']}")
                st.markdown(f"- **{t['col_spo2']}**：{t['help_spo2']}")
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
                guide_title = t['tab1_guide_title']
                with st.expander(guide_title):
                    st.markdown(t['tab1_guide_content'])
                st.plotly_chart(build_combined_physiological_chart(df_daily, t), width='stretch', config={'displayModeBar': 'hover'})
            else:
                st.info(t['no_trend_data'])

        with tab2:
            # 篩選資料：過濾出 df_hourly 中 analysis_status != "NORMAL" 的資料
            abnormal_df = df_hourly[df_hourly['analysis_status'] != "NORMAL"].copy()
            if abnormal_df.empty:
                st.info(t['no_abnormal_events'])
            else:
                # 異常事件類別統計 (原 異常成因排行榜) - 改成上下排列顯示第一部分
                st.subheader(t['root_cause_title'])

                # 透過 translate_reason_codes 將 reason_codes 轉為具體的語言描述
                abnormal_df['description'] = abnormal_df['reason_codes'].apply(
                    lambda codes: translate_reason_codes(codes, t)
                )

                # 過濾空描述
                cause_df = abnormal_df[abnormal_df['description'] != ""].copy()

                if cause_df.empty:
                    st.info(t['no_abnormal_events'])
                else:
                    # 計算各個 description 的發生次數，排序讓次數最多的排在最上方
                    cause_counts = cause_df['description'].value_counts().reset_index()
                    cause_counts.columns = ['description', 'count']
                    cause_counts = cause_counts.sort_values(by='count', ascending=False)

                    fig_cause = px.bar(
                        cause_counts,
                        x='count',
                        y='description',
                        orientation='h',
                        labels={'count': t['tt_count'], 'description': t['tt_reason']}
                    )
                    # 異常成因排行榜 Hover 提示框移除異常原因
                    fig_cause.update_traces(
                        hovertemplate=f"{t['tt_count']}: %{{x}}<extra></extra>",
                        marker_color='crimson'
                    )
                    fig_cause.update_layout(
                        xaxis_title=t['tt_count'],
                        yaxis_title="",
                        yaxis=dict(autorange="reversed")  # 強制讓最多次數的在最上方
                    )
                    st.plotly_chart(fig_cause, width='stretch', config={'displayModeBar': 'hover'})

                st.markdown("---")

                # 24小時異常時段統計
                st.subheader(t['hourly_dist_title'])

                # 提取 timestamp 欄位的小時 (0-23)
                abnormal_df['hour_num'] = abnormal_df['timestamp'].dt.hour

                # 生成一個涵蓋 0 到 23 的完整 DataFrame
                all_hours_df = pd.DataFrame({'hour_num': range(24)})

                # 計算發生的異常次數並 merge 進去 (補 0)
                hour_counts = abnormal_df['hour_num'].value_counts().reset_index()
                hour_counts.columns = ['hour_num', 'count']

                merged_hours = pd.merge(all_hours_df, hour_counts, on='hour_num', how='left').fillna(0)
                merged_hours['count'] = merged_hours['count'].astype(int)

                # 格式化為 "00:00", "01:00"
                merged_hours['hour_label'] = merged_hours['hour_num'].apply(lambda x: f"{x:02d}:00")

                # 改為 X軸顯示次數，Y軸顯示小時
                fig_hour = px.bar(
                    merged_hours,
                    x='count',
                    y='hour_label',
                    orientation='h',
                    labels={'hour_label': t['tt_hour'], 'count': t['tt_count']}
                )
                # Hover提示框
                fig_hour.update_traces(
                    hovertemplate=f"{t['tt_hour']}: %{{y}}<br>{t['tt_count']}: %{{x}}<extra></extra>",
                    marker_color='orange'
                )
                fig_hour.update_layout(
                    xaxis_title=t['tt_count'],
                    yaxis_title="",
                    yaxis=dict(autorange="reversed")  # 00:00 在最上方，23:00 在最下方
                )
                st.plotly_chart(fig_hour, width='stretch', config={'displayModeBar': 'hover'})

        with tab3:
            with st.expander(t['expander_title']):
                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    st.markdown(f"**{t['expander_left_title']}**")
                    st.markdown(t['help_status_display'], help=t['help_status_tooltip'])
                with e_col2:
                    st.markdown(f"**{t['expander_right_title']}**")
                    st.markdown(f"- {t['help_avg_bpm']}")
                    st.markdown(f"- {t['help_ema_bpm']}")
                    st.markdown(f"- {t['help_spo2']}")

            log_df = df_hourly[df_hourly['analysis_status'] != "NORMAL"].copy()
            if not log_df.empty:
                log_df['description'] = log_df['reason_codes'].apply(lambda codes: translate_reason_codes(codes, t))

                display_df = log_df[['timestamp', 'analysis_status', 'description', 'avg_bpm', 'ema_bpm', 'spo2']].copy()
                display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['analysis_status'] = display_df['analysis_status'].map(t['status_map'])
                display_df['avg_bpm'] = display_df['avg_bpm'].round(1)
                display_df['ema_bpm'] = display_df['ema_bpm'].round(1)
                display_df['spo2'] = display_df['spo2'].round(0).astype(int)
                display_df.insert(0, t['col_no'], range(1, len(display_df) + 1))
                column_mapping = {
                    'timestamp': t['col_time'],
                    'analysis_status': t['col_status'],
                    'description': t['col_desc'],
                    'avg_bpm': t['col_avg_bpm'],
                    'ema_bpm': t['col_ema_bpm'],
                    'spo2': t['col_spo2']
                }
                display_df = display_df.rename(columns=column_mapping)
                render_aggrid(display_df, t, t['col_status'])
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(label=t['download_csv'], data=csv, file_name=f"pulseguard_analytics_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')
            else:
                st.success(t['no_abnormal_events'])

    load_custom_css()

if __name__ == "__main__":
    main()
