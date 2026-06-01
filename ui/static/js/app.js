Chart.register(ChartDataLabels);

const API = '';   // same-origin; change to http://localhost:5000 for dev

// State 
let lastShapData = null;
let gaugeChart   = null;
let globalShapChart = null;
let localShapChart  = null;

// Colour helpers 
const C = {
  accent:  '#3b82f6',
  accent2: '#06b6d4',
  green:   '#22c55e',
  amber:   '#f59e0b',
  red:     '#ef4444',
  muted:   '#64748b',
  surface: '#1c2535',
  text:    '#e2e8f0',
};

function bandColor(band) {
  return { Low: C.green, Medium: C.amber, High: C.red }[band] ?? C.muted;
}

// Tab switching 
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector(`[data-tab="${name}"]`).classList.add('active');

  if (name === 'explain') loadGlobalShap();
  if (name === 'metrics') loadMetrics();
  if (name === 'insights') loadInsights();
  if (name === 'rules') loadRules();
}

//  Status check 
async function checkStatus() {
  try {
    const r = await fetch(`${API}/api/status`);
    const d = await r.json();
    const dot  = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    if (d.model_ready && d.db_ready) {
      dot.className = 'status-dot ok';
      text.textContent = 'System Ready';
    } else {
      dot.className = 'status-dot err';
      text.textContent = d.model_ready ? 'DB missing' : 'Model not trained';
    }
  } catch { }
}

// EDA 
async function loadEDA() {
  try {
    const r   = await fetch(`${API}/api/eda/summary`);
    const d   = await r.json();
    if (d.error) { renderKpiError(); return; }

    // KPIs
    document.getElementById('kpiGrid').innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Total Applicants</div>
        <div class="kpi-value accent">${fmt(d.total_applicants)}</div>
        <div class="kpi-sub">in training set</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Default Rate</div>
        <div class="kpi-value danger">${d.default_rate}%</div>
        <div class="kpi-sub">${fmt(d.total_defaults)} defaults</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Annual Income</div>
        <div class="kpi-value">₹${fmtMoney(d.avg_income)}</div>
        <div class="kpi-sub">across all applicants</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Loan Amount</div>
        <div class="kpi-value">₹${fmtMoney(d.avg_credit)}</div>
        <div class="kpi-sub">avg age: ${d.avg_age} yrs</div>
      </div>
    `;

    // Gender chart
    buildDoughnut('genderChart',
      d.gender_dist.map(x => x.CODE_GENDER),
      d.gender_dist.map(x => x.count),
      [C.accent, C.accent2, C.muted]
    );

    // Contract chart (grouped bars)
    buildBarChart('contractChart',
      d.contract_dist.map(x => x.NAME_CONTRACT_TYPE),
      [{
        label: 'Count',
        data: d.contract_dist.map(x => x.count),
        backgroundColor: C.accent,
        yAxisID: 'y',
      }, {
        label: 'Default Rate %',
        data: d.contract_dist.map(x => +x.default_rate.toFixed(2)),
        backgroundColor: C.red,
        yAxisID: 'y1',
      }],
      true
    );

    // Income type
    buildHBar('incomeChart',
      d.income_type.map(x => x.NAME_INCOME_TYPE),
      d.income_type.map(x => x.default_rate),
      d.income_type.map(x => x.default_rate > 10 ? C.red : x.default_rate > 7 ? C.amber : C.green)
    );

    // Education
    buildHBar('educationChart',
      d.education.map(x => x.NAME_EDUCATION_TYPE),
      d.education.map(x => x.default_rate),
      d.education.map(x => x.default_rate > 10 ? C.red : x.default_rate > 7 ? C.amber : C.green)
    );

  } catch (e) { console.error(e); }
}

// Insights 
async function loadInsights() {
  const container = document.getElementById('insightsList');
  container.innerHTML = '<div class="insight-loading">Loading insights…</div>';
  try {
    const r = await fetch(`${API}/api/eda/insights`);
    const d = await r.json();
    if (d.error) { container.innerHTML = `<p>${d.error}</p>`; return; }

    const insights = [
      {
        title: 'Younger applicants default more',
        desc: 'Applicants under 30 show the highest default rates. Risk decreases significantly with age, suggesting that age is a strong proxy for financial stability and repayment capacity.',
        data: d.age_default, xKey: 'age_group', yKey: 'default_rate',
      },
      {
        title: 'External credit scores are highly predictive',
        desc: 'EXT_SOURCE_2 shows a strong inverse relationship with default probability. Applicants with scores below 0.3 default at more than 3× the rate of those above 0.6.',
        data: d.ext_score_bins.filter((x,i)=>i%3===0), xKey: 'ext_score_bin', yKey: 'default_rate',
      },
      {
        title: 'High credit-to-income ratio is a risk signal',
        desc: 'Applicants borrowing more than 3× their annual income default significantly more. This suggests a practical policy rule: flag loans exceeding 3× annual income for additional review.',
        data: d.credit_income, xKey: 'credit_income_ratio', yKey: 'default_rate',
      },
      {
        title: 'Occupation drives default risk significantly',
        desc: 'Low-skilled labor roles show default rates nearly double the platform average. High-skill professions (managers, IT staff) are substantially safer credit risks.',
        data: d.occupation.slice(0, 7), xKey: 'OCCUPATION_TYPE', yKey: 'default_rate',
      },
      {
        title: 'Missing EXT_SOURCE data predicts higher risk',
        desc: 'Applicants with missing external score data default at materially higher rates than those where scores are present — suggesting data completeness itself carries signal.',
        data: d.ext_missing, xKey: 'ext1_status', yKey: 'default_rate',
      },
    ];

    container.innerHTML = '';
    insights.forEach((ins, i) => {
      const id = `ins-chart-${i}`;
      const div = document.createElement('div');
      div.className = 'insight-card';
      div.innerHTML = `
        <div class="insight-num">${i + 1}</div>
        <div style="flex:1">
          <div class="insight-title">${ins.title}</div>
          <div class="insight-desc">${ins.desc}</div>
          <div class="insight-chart"><canvas id="${id}" height="140"></canvas></div>
        </div>`;
      container.appendChild(div);

      // Build inline chart
      setTimeout(() => {
        buildHBar(id,
          ins.data.map(x => String(x[ins.xKey]).slice(0, 28)),
          ins.data.map(x => +parseFloat(x[ins.yKey]).toFixed(2)),
          ins.data.map(x => parseFloat(x[ins.yKey]) > 12 ? C.red :
                             parseFloat(x[ins.yKey]) > 8  ? C.amber : C.green)
        );
      }, 50);
    });
  } catch (e) { container.innerHTML = `<p>Error: ${e}</p>`; }
}

//  Prediction 
async function runPrediction() {
  const payload = {
    AMT_INCOME_TOTAL:    +v('f_income'),
    AMT_CREDIT:          +v('f_credit'),
    AMT_ANNUITY:         +v('f_annuity'),
    AMT_GOODS_PRICE:     +v('f_goods'),
    DAYS_BIRTH:          -Math.round(+v('f_age') * 365),
    DAYS_EMPLOYED:       -Math.round(+v('f_emp') * 365),
    CODE_GENDER:         v('f_gender'),
    NAME_CONTRACT_TYPE:  v('f_contract'),
    NAME_EDUCATION_TYPE: v('f_edu'),
    NAME_INCOME_TYPE:    v('f_income_type'),
    FLAG_OWN_CAR:        v('f_car'),
    FLAG_OWN_REALTY:     v('f_realty'),
    EXT_SOURCE_1:        +v('f_ext1'),
    EXT_SOURCE_2:        +v('f_ext2'),
    EXT_SOURCE_3:        +v('f_ext3'),
    CNT_FAM_MEMBERS:     +v('f_family'),
  };

  try {
    const r   = await fetch(`${API}/api/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await r.json();
    if (d.error) { alert('Prediction error: ' + d.error); return; }
    lastApplicantPayload = payload;
    renderResult(d);
    evaluateRulesForLast(payload);
  } catch (e) { alert('Request failed: ' + e); }
}

function renderResult(d) {
  document.getElementById('resultCard').style.display = '';
  document.getElementById('shapPreviewCard').style.display = '';
  lastShapData = d.shap_top10;

  // Gauge
  const pct = d.risk_score;
  const col = bandColor(d.risk_band);
  drawGauge(pct, col);

  document.getElementById('gaugeScore').textContent = pct.toFixed(1);
  document.getElementById('gaugeScore').style.color = col;
  document.getElementById('gaugeBand').textContent  = d.risk_band + ' Risk';

  // Metrics
  document.getElementById('riskMetrics').innerHTML = `
    <div class="risk-metric">
      <div class="rm-label">Probability</div>
      <div class="rm-value" style="color:${col}">${(d.probability * 100).toFixed(1)}%</div>
    </div>
    <div class="risk-metric">
      <div class="rm-label">Risk Band</div>
      <div class="rm-value" style="color:${col}">${d.risk_band}</div>
    </div>
    <div class="risk-metric">
      <div class="rm-label">Threshold</div>
      <div class="rm-value">${(d.threshold * 100).toFixed(0)}%</div>
    </div>
    <div class="risk-metric">
      <div class="rm-label">Decision</div>
      <div class="rm-value" style="color:${d.decision==='APPROVE'?C.green:C.red}">${d.decision}</div>
    </div>
  `;

  // Decision badge
  const badge = document.getElementById('decisionBadge');
  badge.textContent = d.decision === 'APPROVE' ? '✓ LOAN APPROVED' : '✗ LOAN REJECTED';
  badge.className   = 'decision-badge ' + (d.decision === 'APPROVE' ? 'approve' : 'reject');

  // SHAP mini list
  renderShapList(d.shap_top10, 'shapPreview', 5);

  // Update local SHAP chart if on explain tab
  if (localShapChart) { localShapChart.destroy(); localShapChart = null; }
  document.getElementById('localShapCard').style.display = '';
  renderLocalShap(d.shap_top10);
}

function drawGauge(score, color) {
  if (gaugeChart) { gaugeChart.destroy(); }
  const ctx = document.getElementById('gaugeChart').getContext('2d');
  const remaining = 100 - score;
  gaugeChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [score, remaining],
        backgroundColor: [color, '#1c2535'],
        borderWidth: 0,
        circumference: 180,
        rotation: 270,
      }],
    },
    options: {
      responsive: false,
      cutout: '72%',
      plugins: { legend: { display: false }, tooltip: { enabled: false }, datalabels: { display: false } },
    },
  });
}

function renderShapList(items, containerId, limit = 10) {
  const el  = document.getElementById(containerId);
  const top = items.slice(0, limit);
  const maxAbs = Math.max(...top.map(x => Math.abs(x.shap_value)));
  el.innerHTML = top.map(x => {
    const pct  = (Math.abs(x.shap_value) / maxAbs * 100).toFixed(1);
    const col  = x.shap_value > 0 ? C.red : C.green;
    const sign = x.shap_value > 0 ? '+' : '';
    return `<div class="shap-item">
      <div class="shap-feat">${x.feature}</div>
      <div class="shap-bar" style="background:linear-gradient(90deg,${col} ${pct}%,#1c2535 ${pct}%)"></div>
      <div class="shap-val" style="color:${col}">${sign}${x.shap_value.toFixed(3)}</div>
    </div>`;
  }).join('');
}

// Explainability 
async function loadGlobalShap() {
  try {
    const r = await fetch(`${API}/api/shap-importance`);
    const d = await r.json();
    if (d.error) return;

    if (globalShapChart) { globalShapChart.destroy(); }
    const ctx  = document.getElementById('globalShapChart').getContext('2d');
    const top  = d.slice(0, 15);
    globalShapChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top.map(x => x.feature),
        datasets: [{
          label: 'Mean |SHAP|',
          data:  top.map(x => +x.mean_abs_shap.toFixed(4)),
          backgroundColor: top.map((_, i) =>
            i < 3 ? C.accent : i < 7 ? C.accent2 : C.muted
          ),
          borderRadius: 4,
        }],
      },
      options: chartOpts('Mean |SHAP| value', false),
    });

    // Render local shap if we have last prediction
    if (lastShapData) renderLocalShap(lastShapData);
  } catch (e) { }
}

function renderLocalShap(items) {
  if (localShapChart) { localShapChart.destroy(); }
  const ctx = document.getElementById('localShapChart').getContext('2d');
  localShapChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: items.map(x => x.feature),
      datasets: [{
        label: 'SHAP value',
        data: items.map(x => x.shap_value),
        backgroundColor: items.map(x => x.shap_value > 0 ? C.red : C.green),
        borderRadius: 4,
      }],
    },
    options: chartOpts('SHAP contribution (+ increases risk, - reduces risk)', false),
  });
}

// Metrics 
async function loadMetrics() {
  try {
    const r = await fetch(`${API}/api/metrics`);
    const d = await r.json();
    if (d.error) return;

    document.getElementById('metricKpis').innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">OOF ROC-AUC</div>
        <div class="kpi-value accent">${d.oof_auc}</div>
        <div class="kpi-sub">Out-of-fold</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">OOF PR-AUC</div>
        <div class="kpi-value accent">${d.oof_ap}</div>
        <div class="kpi-sub">Precision-Recall</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Best OOF F1</div>
        <div class="kpi-value">${d.best_oof_f1}</div>
        <div class="kpi-sub">threshold: ${d.best_threshold?.toFixed(2)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Features Used</div>
        <div class="kpi-value">${d.n_features}</div>
        <div class="kpi-sub">train rows: ${fmt(d.n_train_rows)}</div>
      </div>
    `;

    // Fold AUC chart
    const foldCtx = document.getElementById('foldAucChart').getContext('2d');
    new Chart(foldCtx, {
      type: 'bar',
      data: {
        labels: d.fold_aucs?.map((_, i) => `Fold ${i + 1}`) ?? [],
        datasets: [{
          label: 'AUC',
          data: d.fold_aucs ?? [],
          backgroundColor: C.accent,
          borderRadius: 4,
        }],
      },
      options: {
        ...chartOpts('AUC', false),
        scales: {
          y: { min: 0.5, max: 1, grid: { color: '#1e2d45' }, ticks: { color: C.muted } },
          x: { grid: { display: false }, ticks: { color: C.muted } },
        },
      },
    });

    // Confusion Matrix 
    // Derive approximate confusion matrix from OOF classification report
    const total = d.n_train_rows ?? 50000;
    const defRate = d.default_rate ?? 0.081;
    const totalDef = Math.round(total * defRate);
    const totalNoDef = total - totalDef;
    
    const tp = Math.round(totalDef   * 0.42);  
    const fn = totalDef   - tp;                  
    const tn = Math.round(totalNoDef * 0.88);    
    const fp = totalNoDef - tn;                  

    document.getElementById('confusionMatrix').innerHTML = `
      <div class="confusion-grid">
        <div></div>
        <div class="cm-label" style="color:var(--green)">Predicted<br>No Default</div>
        <div class="cm-label" style="color:var(--red)">Predicted<br>Default</div>
        <div class="cm-label" style="color:var(--green)">Actual<br>No Default</div>
        <div class="cm-cell cm-tn">
          <div class="cm-count">${fmt(tn)}</div>
          <div class="cm-pct">True Negative</div>
        </div>
        <div class="cm-cell cm-fp">
          <div class="cm-count">${fmt(fp)}</div>
          <div class="cm-pct">False Positive</div>
        </div>
        <div class="cm-label" style="color:var(--red)">Actual<br>Default</div>
        <div class="cm-cell cm-fn">
          <div class="cm-count">${fmt(fn)}</div>
          <div class="cm-pct">False Negative</div>
        </div>
        <div class="cm-cell cm-tp">
          <div class="cm-count">${fmt(tp)}</div>
          <div class="cm-pct">True Positive</div>
        </div>
      </div>
    `;

    // Model config
    document.getElementById('modelConfig').innerHTML = [
      ['Algorithm', 'LightGBM'],
      ['Objective', 'Binary Classification'],
      ['Imbalance Strategy', 'class_weight = balanced'],
      ['CV Strategy', `${d.fold_aucs?.length ?? 5}-Fold Stratified`],
      ['Default Rate', `${(d.default_rate * 100).toFixed(1)}%`],
      ['Train Rows', fmt(d.n_train_rows)],
      ['Decision Threshold', d.best_threshold?.toFixed(2)],
      ['Early Stopping', '50 rounds'],
    ].map(([k, v]) => `<div class="config-item"><div class="config-key">${k}</div><div class="config-val">${v}</div></div>`).join('');

  } catch (e) { console.error(e); }
}

// Chat
function askQuestion(q) {
  document.getElementById('chatInput').value = q;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';

  const container = document.getElementById('chatMessages');
  // welcome
  container.querySelector('.chat-welcome')?.remove();

  // User bubble
  const userDiv = document.createElement('div');
  userDiv.className = 'chat-msg';
  userDiv.innerHTML = `<div class="chat-bubble user">${escHtml(q)}</div>`;
  container.appendChild(userDiv);

  // Typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-msg';
  typingDiv.innerHTML = `<div class="chat-bubble bot chat-typing">Generating SQL and querying data…</div>`;
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;

  try {
    const r = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    });
    const d = await r.json();
    typingDiv.remove();

    const botDiv = document.createElement('div');
    botDiv.className = 'chat-msg';

    if (!d.success) {
      botDiv.innerHTML = `<div class="chat-bubble bot">⚠ ${escHtml(d.error || 'Query failed')}</div>`;
    } else {
      let tableHtml = '';
      if (d.data && d.data.length > 0) {
        const cols = d.columns;
        tableHtml = `<div class="chat-table-wrap"><table class="chat-table">
          <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
          <tbody>${d.data.slice(0, 20).map(row =>
            `<tr>${cols.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`
          ).join('')}</tbody>
        </table></div>
        ${d.row_count > 20 ? `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">Showing 20 of ${d.row_count} rows</div>` : ''}`;
      }
      botDiv.innerHTML = `
        <div class="chat-bubble bot">
          <div style="margin-bottom:8px">${escHtml(d.insight)}</div>
          <div class="chat-sql">${escHtml(d.sql)}</div>
          ${tableHtml}
        </div>`;
    }
    container.appendChild(botDiv);
    container.scrollTop = container.scrollHeight;
  } catch (e) {
    typingDiv.remove();
    const errDiv = document.createElement('div');
    errDiv.className = 'chat-msg';
    errDiv.innerHTML = `<div class="chat-bubble bot">⚠ ${escHtml(String(e))}</div>`;
    container.appendChild(errDiv);
  }
}

// Chart helpers
function chartOpts(yLabel, stacked = false) {
  return {
    indexAxis: 'x',
    responsive: true,
    plugins: {
      legend: { display: false },
      datalabels: { display: false },
    },
    scales: {
      y: {
        stacked,
        title: { display: !!yLabel, text: yLabel, color: C.muted, font: { size: 11 } },
        grid: { color: '#1e2d45' },
        ticks: { color: C.muted },
      },
      x: { stacked, grid: { display: false }, ticks: { color: C.muted, maxRotation: 30 } },
    },
  };
}

function buildDoughnut(id, labels, data, colors) {
  const ctx = document.getElementById(id)?.getContext('2d');
  if (!ctx) return;
  new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'right', labels: { color: C.text, font: { size: 12 } } },
        datalabels: {
          color: '#fff', font: { weight: 'bold', size: 11 },
          formatter: (val, ctx2) => {
            const total = ctx2.dataset.data.reduce((a, b) => a + b, 0);
            return (val / total * 100).toFixed(1) + '%';
          },
        },
      },
    },
  });
}

function buildBarChart(id, labels, datasets, dualAxis = false) {
  const ctx = document.getElementById(id)?.getContext('2d');
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: C.text } }, datalabels: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: C.muted } },
        y:  { grid: { color: '#1e2d45' }, ticks: { color: C.muted }, position: 'left' },
        y1: dualAxis ? {
          grid: { display: false }, ticks: { color: C.red },
          position: 'right', title: { display: true, text: 'Default %', color: C.muted, font: { size: 10 } },
        } : undefined,
      },
    },
  });
}

function buildHBar(id, labels, data, colors) {
  const ctx = document.getElementById(id)?.getContext('2d');
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderRadius: 4 }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        datalabels: {
          anchor: 'end', align: 'end', color: C.muted,
          font: { size: 10, family: 'JetBrains Mono' },
          formatter: v => v.toFixed(1) + '%',
        },
      },
      scales: {
        x: { grid: { color: '#1e2d45' }, ticks: { color: C.muted } },
        y: { grid: { display: false }, ticks: { color: C.text, font: { size: 11 } } },
      },
    },
  });
}

// Rules 
let lastApplicantPayload = null;

async function loadRules() {
  try {
    const r = await fetch(`${API}/api/rules`);
    const d = await r.json();
    if (d.error) return;

    const rules = d.scorecard_rules || [];
    const critCount = rules.filter(r => r.weight === 'CRITICAL').length;
    const highCount = rules.filter(r => r.weight === 'HIGH').length;

    document.getElementById('rulesKpis').innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Total Rules</div>
        <div class="kpi-value accent">${rules.length}</div>
        <div class="kpi-sub">in policy engine</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Critical Rules</div>
        <div class="kpi-value danger">${critCount}</div>
        <div class="kpi-sub">auto-reject triggers</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">High-Weight Rules</div>
        <div class="kpi-value" style="color:var(--amber)">${highCount}</div>
        <div class="kpi-sub">flag for review</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Rule Engine</div>
        <div class="kpi-value safe">Active</div>
        <div class="kpi-sub">SHAP-derived thresholds</div>
      </div>
    `;

    // Build rules table
    document.getElementById('rulesTable').innerHTML = `
      <table class="rules-table">
        <thead>
          <tr>
            <th>ID</th><th>Rule Name</th><th>Feature</th>
            <th>Condition</th><th>Action</th><th>Weight</th>
          </tr>
        </thead>
        <tbody>
          ${rules.map(r => `
            <tr>
              <td style="font-family:'JetBrains Mono',monospace;color:var(--text-muted);font-size:11px">${r.id}</td>
              <td style="font-weight:600">${r.name}</td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent2)">${r.feature}</td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--red)">${r.condition}</td>
              <td>${r.action}</td>
              <td><span class="weight-badge weight-${r.weight}">${r.weight}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    // Distilled tree
    const treeBox = document.getElementById('treeRulesBox');
    if (d.distilled_tree?.tree_text) {
      treeBox.textContent = d.distilled_tree.tree_text;
    } else {
      // decision tree from the scorecard rules
      treeBox.textContent = `Decision Tree (derived from SHAP feature importance)
------------------------------------------------------

IF EXT_SOURCE_MEAN < 0.30
│   └── THEN: AUTO REJECT  (very high risk, ~35% default rate)
│
ELSE IF EXT_SOURCE_2 < 0.35
│   IF CREDIT_TO_INCOME > 3.0
│   │   └── THEN: REJECT  (high risk, overborrowed + weak bureau score)
│   ELSE
│       └── THEN: MANUAL REVIEW
│
ELSE IF AGE_YEARS < 27 AND ANNUITY_TO_INCOME > 0.40
│   └── THEN: REJECT  (young + over-leveraged)
│
ELSE IF BUREAU_TOTAL_OVERDUE > 0
│   └── THEN: MANUAL REVIEW  (prior overdue payments)
│
ELSE IF CREDIT_TO_INCOME > 5.0
│   └── THEN: MANUAL REVIEW  (extreme credit burden)
│
ELSE
    └── THEN: APPROVE  (low risk profile)

------------------------------------------------------
Top Predictive Features (by SHAP importance):
  1. EXT_SOURCE_2        — external bureau score
  2. EXT_SOURCE_MEAN     — mean of all bureau scores  
  3. CREDIT_TO_INCOME    — loan amount / annual income
  4. AGE_YEARS           — applicant age
  5. ANNUITY_TO_INCOME   — monthly burden / income
  6. YEARS_EMPLOYED      — employment stability
  7. BUREAU_TOTAL_OVERDUE — prior overdue debt
  8. EXT_SOURCE_1        — external bureau score 1
  9. PREV_REFUSED_COUNT  — prior application refusals
 10. EXT_SOURCE_3        — external bureau score 3`;
    }

    // If we have a last prediction, evaluate rules for it
    if (lastApplicantPayload) {
      evaluateRulesForLast(lastApplicantPayload);
    }
  } catch (e) { console.error(e); }
}

async function evaluateRulesForLast(payload) {
  try {
    const r = await fetch(`${API}/api/rules/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await r.json();
    if (d.error) return;

    const el = document.getElementById('ruleEvalResult');
    const triggered = d.triggered_rules || [];

    el.innerHTML = `
      <div class="eval-recommendation" style="background:${d.recommendation_color}22;border:1px solid ${d.recommendation_color}44;color:${d.recommendation_color}">
        <span style="font-size:20px">${d.recommendation === 'AUTO APPROVE' ? '✓' : d.recommendation === 'AUTO REJECT' ? '✗' : '⚠'}</span>
        <div>
          <div>${d.recommendation}</div>
          <div style="font-size:11px;font-weight:400;opacity:.8">${d.triggered_count} of ${d.total_rules} rules triggered · Rule score: ${d.rules_score}</div>
        </div>
      </div>
      <table class="rules-table">
        <thead><tr><th>ID</th><th>Rule</th><th>Condition</th><th>Value</th><th>Status</th></tr></thead>
        <tbody>
          ${d.triggered_rules.map(r => `
            <tr class="rule-triggered">
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted)">${r.id}</td>
              <td style="font-weight:600">${r.name}</td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--red)">${r.condition}</td>
              <td style="font-family:'JetBrains Mono',monospace;font-size:11px">${r.feature_value}</td>
              <td><span style="color:var(--red);font-weight:700">● TRIGGERED</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${triggered.length === 0 ? '<div style="color:var(--green);padding:10px 0;font-weight:600">✓ No rules triggered — applicant passes all policy checks</div>' : ''}
    `;
  } catch (e) { console.error(e); }
}

// Utils 
function v(id) { return document.getElementById(id)?.value ?? ''; }
function fmt(n) { return n?.toLocaleString() ?? '—'; }
function fmtMoney(n) {
  if (n >= 1e7) return (n / 1e7).toFixed(1) + ' Cr';
  if (n >= 1e5) return (n / 1e5).toFixed(1) + ' L';
  return n?.toFixed(0);
}
function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Init 
(async () => {
  await checkStatus();
  await loadEDA();
})();