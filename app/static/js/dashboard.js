let currentTimespan = 'realtime';
let currentSort = 'heat';
let currentCategory = null;

// --- Tab switching ---
document.getElementById('time-tabs').addEventListener('click', (e) => {
    if (!e.target.classList.contains('tab')) return;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    currentTimespan = e.target.dataset.timespan;
    if (currentTimespan === 'ondemand') {
        fetch('/api/refresh', {method: 'POST'}).then(() => loadDashboard());
    } else {
        loadDashboard();
    }
});

// --- Sort switching ---
document.addEventListener('click', (e) => {
    if (!e.target.classList.contains('sort-btn')) return;
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentSort = e.target.dataset.sort;
    loadDashboard();
});

// --- Load dashboard ---
async function loadDashboard() {
    await Promise.all([loadStats(), loadMainList(), loadCharts()]);
}

async function loadStats() {
    const resp = await fetch('/api/stats');
    const data = await resp.json();
    document.getElementById('stat-total').textContent = data.total_events + ' 条';
    document.getElementById('stat-rising').textContent = data.rising_count + ' 条';
    document.getElementById('stat-regions').textContent = data.region_count + ' 大地区';
    document.getElementById('stat-categories').textContent = data.category_count + ' 个';
    document.getElementById('update-time').textContent = '⏱ 更新于 ' + new Date().toLocaleTimeString();
}

function parseJsonField(val) {
    if (!val) return [];
    try {
        return typeof val === 'string' ? JSON.parse(val) : val;
    } catch (_) { return []; }
}

async function loadMainList() {
    if (currentSort === 'entity') {
        await loadEntityList();
    } else if (currentSort === 'prediction') {
        await loadPredictions();
    } else {
        await loadEvents();
    }
}

// --- Event list (heat / personal / source / time) ---
async function loadEvents() {
    const params = new URLSearchParams({ timespan: currentTimespan, sort_by: currentSort, limit: '100' });
    if (currentCategory) params.set('category', currentCategory);

    const resp = await fetch('/api/events?' + params);
    const data = await resp.json();
    const container = document.getElementById('events-list');
    if (!data.events.length) {
        container.innerHTML = '<div class="loading">暂无热点数据</div>';
        return;
    }
    container.innerHTML = data.events.map((e, i) => {
        const heatClass = e.latest_heat > 80 ? 'high' : e.latest_heat > 50 ? 'mid' : '';
        const rankClass = i < 3 ? 'r' + (i+1) : (i < 5 ? 'r' + (i+1) : '');
        const trend = e.latest_trend === 'rising' ? ' ↑' : e.latest_trend === 'falling' ? ' ↓' : '';
        const impactPoints = parseJsonField(e.impact_points);
        const personalImpact = parseJsonField(e.personal_impact);
        const entities = parseJsonField(e.entities);
        const hasExpand = impactPoints.length > 0 || personalImpact.length > 0 || entities.length > 0;

        let html = '<div class="event-item" data-eid="' + e.id + '">' +
            '<span class="event-rank ' + rankClass + '">' + (i + 1) + '</span>' +
            '<div class="event-info">' +
            '<div class="event-title-row">' +
            '<span class="event-title-link" onclick="location.href=\'/event/' + e.id + '\'">' + escapeHtml(e.title_cn || e.title) + trend + '</span>';
        if (hasExpand) {
            html += '<button class="expand-toggle" data-eid="' + e.id + '" onclick="toggleExpand(event, ' + e.id + ')">▶</button>';
        }
        html += '</div>';

        if (currentSort === 'personal' && personalImpact.length > 0) {
            html += '<div class="personal-impact-inline">';
            html += personalImpact.map((p, j) => '<span class="pi-tag pi-tag-' + (j + 1) + '">💰 ' + escapeHtml(p) + '</span>').join('');
            html += '</div>';
        }

        if (hasExpand) {
            html += '<div class="event-expand" id="expand-' + e.id + '" style="display:none">';
            if (impactPoints.length > 0) {
                html += '<div class="expand-section"><span class="expand-label">关键影响</span>';
                html += impactPoints.map(p => '<span class="impact-chip">' + escapeHtml(p) + '</span>').join('');
                html += '</div>';
            }
            if (personalImpact.length > 0) {
                html += '<div class="expand-section"><span class="expand-label">💰 财富机会</span>';
                html += personalImpact.map((p, j) => '<div class="pi-item"><span class="pi-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>').join('');
                html += '</div>';
            }
            if (entities.length > 0) {
                html += '<div class="expand-section"><span class="expand-label">🎯 关联实体</span>';
                html += entities.map(en => '<span class="entity-chip entity-chip-' + (en.direction || 'neutral') + '">' +
                    escapeHtml(en.entity || '') + ' <small>' + escapeHtml(en.action || '') + '</small></span>').join('');
                html += '</div>';
            }
            html += '</div>';
        }

        html += '</div>' +
            '<div class="event-meta">' +
            '<span class="event-heat ' + heatClass + '">🔥 ' + (e.latest_heat || '-') + '</span>' +
            '<span class="event-platforms">' + (e.related_count || 1) + ' 平台</span>' +
            '</div>' +
            '</div>';
        return html;
    }).join('');
}

// --- Entity impact list (entity sort tab) ---
async function loadEntityList() {
    const resp = await fetch('/api/entities?timespan=' + currentTimespan);
    const data = await resp.json();
    const container = document.getElementById('events-list');
    if (!data.entities.length) {
        container.innerHTML = '<div class="loading">暂无实体影响数据 — 需要更多已分析的事件</div>';
        return;
    }
    container.innerHTML = data.entities.map((en, i) => {
        const rankClass = i < 3 ? 'r' + (i+1) : '';
        const sigClass = (en.signal === 'sell' || en.signal === 'falling') ? 'sig-sell' : (en.signal === 'buy' || en.signal === 'rising') ? 'sig-buy' : 'sig-hold';
        const sigIcon = (en.signal === 'sell' || en.signal === 'falling') ? '📉' : (en.signal === 'buy' || en.signal === 'rising') ? '📈' : '➖';
        const impactStr = (en.total_impact > 0 ? '+' : '') + en.total_impact.toFixed(1);
        const hasEvents = en.events && en.events.length > 0;

        let html = '<div class="entity-main-item">' +
            '<span class="event-rank ' + rankClass + '">' + (i + 1) + '</span>' +
            '<div class="event-info">' +
            '<div class="event-title-row">' +
            '<span class="entity-main-name">' + escapeHtml(en.entity) + '</span>' +
            '<span class="entity-main-type">' + escapeHtml(en.type) + '</span>' +
            '<span class="entity-main-sig ' + sigClass + '">' + sigIcon + ' ' + en.signal_label + '</span>';
        if (hasEvents) {
            html += '<button class="expand-toggle" data-eid="ent-' + i + '" onclick="toggleExpand(event, \'ent-' + i + '\')">▶</button>';
        }
        html += '</div>' +
            '<div class="entity-main-stats">' +
            '<span>综合影响: <strong>' + impactStr + '</strong></span>' +
            '<span>涉及 ' + en.mention_count + ' 条热点</span>' +
            '<span>利好' + en.positive_count + ' / 利空' + en.negative_count + '</span>' +
            '</div>';

        if (hasEvents) {
            html += '<div class="event-expand" id="expand-ent-' + i + '" style="display:none">';
            html += '<div class="expand-section"><span class="expand-label">来源事件</span>';
            html += en.events.map(ev => {
                const evIcon = ev.direction === 'negative' ? '📉' : ev.direction === 'positive' ? '📈' : '➖';
                const evScore = (ev.impact_score > 0 ? '+' : '') + ev.impact_score.toFixed(1);
                return '<div class="entity-event-row" onclick="location.href=\'/event/' + ev.id + '\'">' +
                    '<span class="ee-score">' + evIcon + ' ' + evScore + '</span>' +
                    '<span class="ee-title">' + escapeHtml(ev.title) + '</span>' +
                    '<span class="ee-action">→ ' + escapeHtml(ev.action || '') + '</span>' +
                    '</div>';
            }).join('');
            html += '</div></div>';
        }

        html += '</div>' +
            '<div class="event-meta">' +
            '<span class="entity-bar-impact">' +
            '<span class="bar-fill bar-neg" style="width:' + (Math.abs(Math.min(0, en.total_impact)) * 50) + 'px"></span>' +
            '<span class="bar-fill bar-pos" style="width:' + (Math.max(0, en.total_impact) * 50) + 'px"></span>' +
            '</span>' +
            '</div>' +
            '</div>';
        return html;
    }).join('');
}

// --- Prediction list ---
async function loadPredictions() {
    const container = document.getElementById('events-list');
    try {
        const resp = await fetch('/api/predictions');
        const data = await resp.json();
        const predictions = data.predictions || [];

        if (!predictions.length) {
            container.innerHTML = '<div class="loading">暂无未来预测 — 点击 <a href="#" onclick="refreshPredictions(event)" style="color:var(--accent)">刷新预测</a> 生成</div>';
            return;
        }

        container.innerHTML = predictions.map((p, i) => {
            const probClass = p.probability >= 0.7 ? 'prob-high' : p.probability >= 0.4 ? 'prob-mid' : 'prob-low';
            const entities = parseJsonField(p.entities);
            const hasEntities = entities.length > 0;

            let html = '<div class="prediction-item">' +
                '<span class="prediction-rank pr-' + (i + 1) + '">#' + (i + 1) + '</span>' +
                '<div class="event-info">' +
                '<div class="event-title-row">' +
                '<span class="prediction-event-title">' + escapeHtml(p.event_title) + '</span>' +
                '<span class="prediction-timeframe">' + escapeHtml(p.timeframe) + '</span>' +
                '<span class="prediction-prob ' + probClass + '">' + escapeHtml(p.probability_label) + ' ' + Math.round(p.probability * 100) + '%</span>' +
                '</div>' +
                '<div class="prediction-scenario">' + escapeHtml(p.scenario) + '</div>' +
                '<div class="prediction-reasoning">' + escapeHtml(p.reasoning) + '</div>';

            if (hasEntities) {
                html += '<div class="prediction-entities">';
                html += entities.map(en => {
                    const dirIcon = en.impact_score > 0 ? '📈' : en.impact_score < 0 ? '📉' : '➖';
                    const actClass = en.action === '买入' ? 'act-buy' : en.action === '卖出' ? 'act-sell' : 'act-hold';
                    return '<span class="pred-entity-chip ' + actClass + '">' + dirIcon + ' ' +
                        escapeHtml(en.entity) + ' <small>' + escapeHtml(en.action) + '</small></span>';
                }).join('');
                html += '</div>';
            }

            html += '</div></div>';
            return html;
        }).join('');

    } catch (_) {
        container.innerHTML = '<div class="loading">加载预测失败</div>';
    }
}

window.refreshPredictions = async function(ev) {
    ev.preventDefault();
    const container = document.getElementById('events-list');
    container.innerHTML = '<div class="loading">正在生成预测...（可能需要 30-60 秒）</div>';
    try {
        const resp = await fetch('/api/predictions/refresh', {method: 'POST'});
        const data = await resp.json();
        if (data.predictions && data.predictions.length) {
            await loadPredictions();
        } else {
            container.innerHTML = '<div class="loading">预测生成返回空，请稍后重试</div>';
        }
    } catch (_) {
        container.innerHTML = '<div class="loading">预测生成失败，请重试</div>';
    }
};

window.toggleExpand = function(ev, eid) {
    ev.stopPropagation();
    const el = document.getElementById('expand-' + eid);
    const btn = document.querySelector('.expand-toggle[data-eid="' + eid + '"]');
    if (el.style.display === 'none') {
        el.style.display = 'block';
        if (btn) btn.textContent = '▼';
    } else {
        el.style.display = 'none';
        if (btn) btn.textContent = '▶';
    }
};

async function loadCharts() {
    await Promise.all([loadCategoryPie(), loadHeatLine(), loadRegionBar()]);
}

async function loadCategoryPie() {
    const resp = await fetch('/api/categories');
    const categories = await resp.json();
    const eventsResp = await fetch('/api/events?timespan=' + (currentTimespan === 'daily' ? 'daily' : 'realtime') + '&limit=200');
    const eventsData = await eventsResp.json();

    const chart = echarts.init(document.getElementById('chart-category-pie'));
    const catData = {};
    categories.forEach(c => { catData[c.slug] = { name: c.name, count: 0 }; });
    eventsData.events.forEach(e => {
        if (e.source_platform) {
            const mainCat = e.source_platform.split(',')[0];
            if (catData[mainCat]) catData[mainCat].count++;
        }
    });

    chart.setOption({
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie', radius: ['40%', '70%'],
            data: Object.values(catData).filter(d => d.count > 0).map(d => ({ name: d.name, value: d.count })),
            label: { color: '#aaa', fontSize: 11 },
        }]
    });
}

async function loadHeatLine() {
    const resp = await fetch('/api/events?timespan=daily&sort_by=heat&limit=5');
    const data = await resp.json();
    const chart = echarts.init(document.getElementById('chart-heat-line'));

    const series = await Promise.all(data.events.slice(0, 5).map(async (e) => {
        const detailResp = await fetch('/api/events/' + e.id);
        const detail = await detailResp.json();
        return {
            name: (e.title_cn || e.title).substring(0, 15),
            type: 'line',
            smooth: true,
            data: (detail.snapshots || []).map(s => [s.snapshot_at, s.heat_score]),
        };
    }));

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { textStyle: { color: '#888', fontSize: 10 }, bottom: 0 },
        xAxis: { type: 'time', axisLabel: { color: '#888', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#888' } },
        series: series,
    });
}

async function loadRegionBar() {
    const resp = await fetch('/api/events?timespan=daily&limit=200');
    const data = await resp.json();
    const regions = {};
    data.events.forEach(e => {
        const r = e.region || 'unknown';
        regions[r] = (regions[r] || 0) + 1;
    });

    const chart = echarts.init(document.getElementById('chart-region-bar'));
    chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: Object.keys(regions), axisLabel: { color: '#888', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#888' } },
        series: [{ type: 'bar', data: Object.values(regions), itemStyle: { color: '#4a90d9' } }],
    });
}

// --- Detail page ---
async function initDetailPage(eventId) {
    const resp = await fetch('/api/events/' + eventId);
    if (resp.status === 404) {
        document.getElementById('detail-header').innerHTML = '<h2>事件未找到</h2>';
        return;
    }
    const data = await resp.json();
    const e = data.event;

    document.getElementById('detail-header').innerHTML =
        '<h2>' + escapeHtml(e.title_cn || e.title) + '</h2>' +
        '<div class="detail-meta">' +
        '<span>来源: ' + escapeHtml(e.source_platform) + '</span>' +
        '<span>首次出现: ' + formatTime(e.first_seen_at) + '</span>' +
        '<span>地区: ' + escapeHtml(e.region) + '</span>' +
        '</div>';

    if (e.summary_cn) {
        document.getElementById('detail-summary').innerHTML = '<p><strong>AI 摘要：</strong>' + escapeHtml(e.summary_cn) + '</p>';
    }

    const impactPoints = parseJsonField(e.impact_points);
    if (impactPoints.length > 0) {
        document.getElementById('detail-impact').innerHTML =
            '<h3>关键影响</h3>' +
            '<ul class="impact-list">' +
            impactPoints.map(p => '<li>' + escapeHtml(p) + '</li>').join('') +
            '</ul>';
    }

    const personalImpact = parseJsonField(e.personal_impact);
    if (personalImpact.length > 0) {
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">💰 个人财富机会</h3>' +
            '<div class="pi-detail-list">' +
            personalImpact.map((p, j) => '<div class="pi-detail-item"><span class="pi-detail-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>').join('') +
            '</div>';
    }

    const entities = parseJsonField(e.entities);
    if (entities.length > 0) {
        const sigIcon = (d) => d === 'negative' ? '📉' : d === 'positive' ? '📈' : '➖';
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">🎯 关联实体影响</h3>' +
            '<div class="entity-detail-list">' +
            entities.map(en => '<div class="entity-detail-item">' +
                '<span class="ed-name">' + escapeHtml(en.entity || '') + '</span>' +
                '<span class="ed-type">' + escapeHtml(en.type || '') + '</span>' +
                '<span class="ed-dir">' + sigIcon(en.direction) + ' ' + escapeHtml(en.direction || 'neutral') + '</span>' +
                '<span class="ed-action">→ ' + escapeHtml(en.action || '关注') + '</span>' +
                '</div>').join('') +
            '</div>';
    }

    // Timeline chart
    const snapshots = data.snapshots || [];
    if (snapshots.length > 0) {
        const chart = echarts.init(document.getElementById('chart-timeline'));
        chart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'time', axisLabel: { color: '#888' } },
            yAxis: { type: 'value', name: '热度', axisLabel: { color: '#888' } },
            series: [{
                type: 'line', smooth: true,
                areaStyle: { color: 'rgba(74,144,217,0.2)' },
                data: snapshots.map(s => [s.snapshot_at, s.heat_score]),
            }],
        });
    }

    // Sources
    const sourcesList = document.getElementById('sources-list');
    if (e.source_platform) {
        sourcesList.innerHTML = e.source_platform.split(',').map(p =>
            '<div class="source-item"><span class="source-platform">' + p.trim() + '</span></div>'
        ).join('');
    }

    // Related events
    const related = data.relations || [];
    if (related.length > 0) {
        document.getElementById('related-list').innerHTML = related.map(r =>
            '<span class="related-tag" onclick="location.href=\'/event/' + r.id + '\'">' + escapeHtml(r.title_cn || r.title) + '</span>'
        ).join('');
    }
}

// --- Utils ---
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'Z');
    return d.toLocaleString('zh-CN');
}

// --- Init ---
if (document.querySelector('.dashboard')) {
    loadDashboard().catch(console.error);
    setInterval(() => loadDashboard().catch(console.error), 5 * 60 * 1000);
}
