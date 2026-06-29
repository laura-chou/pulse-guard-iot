/**
 * Shared UI Components for PulseGuard Dashboard
 * This helps reduce HTML duplication between main dashboard and test monitor.
 */

/**
 * Renders the Header component
 * @param {Object} config - { titleEn, titleZh, noteEn, noteZh }
 */
export function renderHeader(config) {
    const headerRoot = document.getElementById('header-root');
    if (!headerRoot) return;

    headerRoot.innerHTML = `
        <header>
            <div class="header-main">
                <h1>
                    <span data-lang="en">${config.titleEn}</span>
                    <span data-lang="zh">${config.titleZh}</span>
                </h1>
                <p class="refresh-warning">
                    <span data-lang="en">${config.noteEn}</span>
                    <span data-lang="zh">${config.noteZh}</span>
                </p>
            </div>
            <div class="header-status">
                <div id="connection-status" class="status-indicator">
                    <span data-lang="en">Connecting...</span>
                    <span data-lang="zh">連線中...</span>
                </div>
                <div id="last-update" class="last-update"></div>
            </div>
        </header>
    `;
}

/**
 * Renders the Main Dashboard Body (Cards and Charts)
 */
export function renderDashboardBody() {
    const mainRoot = document.getElementById('main-root');
    if (!mainRoot) return;

    mainRoot.innerHTML = `
        <main>
            <section class="cards">
                <div class="card" id="bpm-card">
                    <h2>
                        <span data-lang="en">Heart Rate</span>
                        <span data-lang="zh">心率</span>
                    </h2>
                    <div class="value"><span id="bpm">--</span> <span class="unit">BPM</span></div>
                </div>
                <div class="card" id="spo2-card">
                    <h2>
                        <span data-lang="en">SpO₂</span>
                        <span data-lang="zh">血氧飽和度</span>
                    </h2>
                    <div class="value"><span id="spo2">--</span> <span class="unit">%</span></div>
                </div>
                <div class="card" id="status-card">
                    <div class="card-header">
                        <h2>
                            <span data-lang="en">HEALTH STATUS</span>
                            <span data-lang="zh">健康狀態</span>
                        </h2>
                        <div class="info-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="info-svg">
                                <path d="M12 17V11"></path>
                                <path d="M12 7H12.01"></path>
                            </svg>
                            <div class="tooltip">
                                <h3 data-lang="en">Health Status Criteria</h3>
                                <h3 data-lang="zh">健康狀態標準</h3>

                                <div class="condition danger">
                                    <strong data-lang="en">DANGER</strong>
                                    <strong data-lang="zh">危險</strong>
                                    <p data-lang="en">SpO₂ &lt; 90% or BPM &lt; 50 or BPM &gt; 120</p>
                                    <p data-lang="zh">血氧 &lt; 90% 或 心率 &lt; 50 或 心率 &gt; 120</p>
                                </div>
                                <div class="condition warning">
                                    <strong data-lang="en">WARNING</strong>
                                    <strong data-lang="zh">警告</strong>
                                    <p data-lang="en">90% ≤ SpO₂ ≤ 94% or 50 ≤ BPM ≤ 59 or 101 ≤ BPM ≤ 120</p>
                                    <p data-lang="zh">90% ≤ 血氧 ≤ 94% 或 50 ≤ 心率 ≤ 59 或 101 ≤ 心率 ≤ 120</p>
                                </div>
                                <div class="condition normal">
                                    <strong data-lang="en">NORMAL</strong>
                                    <strong data-lang="zh">正常</strong>
                                    <p data-lang="en">SpO₂ ≥ 95% and 60 ≤ BPM ≤ 100</p>
                                    <p data-lang="zh">血氧 ≥ 95% 且 60 ≤ 心率 ≤ 100</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="value" id="status">
                        <span data-lang="en">WAITING</span>
                        <span data-lang="zh">待機中</span>
                    </div>
                </div>
            </section>

            <section class="charts-wrapper">
                <div class="chart-container">
                    <canvas id="bpmChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="spo2Chart"></canvas>
                </div>
            </section>
        </main>
    `;
}
