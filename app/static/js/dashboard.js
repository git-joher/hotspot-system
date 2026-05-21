let currentTimespan = 'realtime';
let currentSort = 'heat';
let currentCategory = null;

// Pick bilingual field based on current language
function _bilingual(cnVal, enVal, fallbackVal) {
    const lang = window.I18N.getLang();
    if (lang === 'en') {
        const en = (enVal && enVal !== '[]') ? enVal : '';
        const cn = (cnVal && cnVal !== '[]') ? cnVal : '';
        return en || cn || fallbackVal || '';
    }
    const cn = (cnVal && cnVal !== '[]') ? cnVal : '';
    return cn || fallbackVal || '';
}

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

// --- Language toggle ---
window.toggleLang = async function() {
    const newLang = window.I18N.getLang() === 'zh' ? 'en' : 'zh';
    await window.I18N.setLang(newLang);
    location.reload();
};

// --- Load dashboard ---
async function loadDashboard() {
    await Promise.all([loadStats(), loadMainList(), loadCharts()]);
}

async function loadStats() {
    const resp = await fetch('/api/stats');
    const data = await resp.json();
    document.getElementById('stat-total').textContent = data.total_events + ' ' + _t('items');
    document.getElementById('stat-rising').textContent = data.rising_count + ' ' + _t('items');
    document.getElementById('stat-regions').textContent = data.region_count + ' ' + _t('regions');
    document.getElementById('stat-categories').textContent = data.category_count + ' ' + _t('categories');
    document.getElementById('update-time').textContent = _t('updated_at') + ' ' + new Date().toLocaleTimeString();
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
        container.innerHTML = '<div class="loading">' + _t('no_data') + '</div>';
        return;
    }
    container.innerHTML = data.events.map((e, i) => {
        const heatClass = e.latest_heat > 80 ? 'high' : e.latest_heat > 50 ? 'mid' : '';
        const rankClass = i < 3 ? 'r' + (i+1) : (i < 5 ? 'r' + (i+1) : '');
        const trend = e.latest_trend === 'rising' ? ' ↑' : e.latest_trend === 'falling' ? ' ↓' : '';
        const impactPoints = parseJsonField(_bilingual(e.impact_points, e.impact_points_en));
        const personalImpact = parseJsonField(_bilingual(e.personal_impact, e.personal_impact_en));
        const entities = parseJsonField(e.entities);
        const hasExpand = impactPoints.length > 0 || personalImpact.length > 0 || entities.length > 0;

        let html = '<div class="event-item" data-eid="' + e.id + '">' +
            '<span class="event-rank ' + rankClass + '">' + (i + 1) + '</span>' +
            '<div class="event-info">' +
            '<div class="event-title-row">' +
            '<span class="event-title-link" onclick="location.href=\'/event/' + e.id + '\'">' + escapeHtml(_bilingual(e.title_cn, e.title_en, e.title)) + trend + '</span>';
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
                html += '<div class="expand-section"><span class="expand-label">' + _t('expand_impact') + '</span>';
                html += impactPoints.map(p => '<span class="impact-chip">' + escapeHtml(p) + '</span>').join('');
                html += '</div>';
            }
            if (personalImpact.length > 0) {
                html += '<div class="expand-section"><span class="expand-label">💰 ' + _t('expand_wealth') + '</span>';
                html += personalImpact.map((p, j) => '<div class="pi-item"><span class="pi-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>').join('');
                html += '</div>';
            }
            if (entities.length > 0) {
                html += '<div class="expand-section"><span class="expand-label">🎯 ' + _t('expand_entities') + '</span>';
                html += entities.map(en => '<span class="entity-chip entity-chip-' + (en.direction || 'neutral') + '">' +
                    escapeHtml(en.entity || '') + ' <small>' + escapeHtml(_bilingual(en.action, en.action_en, '')) + '</small></span>').join('');
                html += '</div>';
            }
            html += '</div>';
        }

        html += '</div>' +
            '<div class="event-meta">' +
            '<span class="event-heat ' + heatClass + '">🔥 ' + (e.latest_heat || '-') + '</span>' +
            '<span class="event-platforms">' + (e.related_count || 1) + ' ' + _t('platforms') + '</span>' +
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
        container.innerHTML = '<div class="loading">' + _t('no_entity_data') + '</div>';
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
            '<span class="entity-main-name">' + escapeHtml(_bilingual(en.entity_cn, en.entity, '')) + '</span>' +
            '<span class="entity-main-type">' + escapeHtml(_bilingual(en.type, en.type_en, '')) + '</span>' +
            '<span class="entity-main-sig ' + sigClass + '">' + sigIcon + ' ' + escapeHtml(_bilingual(en.signal_label, en.signal_label_en, '')) + '</span>';
        if (hasEvents) {
            html += '<button class="expand-toggle" data-eid="ent-' + i + '" onclick="toggleExpand(event, \'ent-' + i + '\')">▶</button>';
        }
        html += '</div>' +
            '<div class="entity-main-stats">' +
            '<span>' + _t('comprehensive_impact') + ': <strong>' + impactStr + '</strong></span>' +
            '<span>' + en.mention_count + ' ' + _t('mentions') + '</span>' +
            '<span>' + _t('positive_negative') + en.positive_count + ' / ' + en.negative_count + '</span>' +
            '</div>';

        if (hasEvents) {
            html += '<div class="event-expand" id="expand-ent-' + i + '" style="display:none">';
            html += '<div class="expand-section"><span class="expand-label">' + _t('source_events') + '</span>';
            html += en.events.map(ev => {
                const evIcon = ev.direction === 'negative' ? '📉' : ev.direction === 'positive' ? '📈' : '➖';
                const evScore = (ev.impact_score > 0 ? '+' : '') + ev.impact_score.toFixed(1);
                return '<div class="entity-event-row" onclick="location.href=\'/event/' + ev.id + '\'">' +
                    '<span class="ee-score">' + evIcon + ' ' + evScore + '</span>' +
                    '<span class="ee-title">' + escapeHtml(_bilingual(ev.title, ev.title_en, '')) + '</span>' +
                    '<span class="ee-action">→ ' + escapeHtml(ev.action_en || ev.action || '') + '</span>' +
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
            container.innerHTML = '<div class="loading">' + _t('no_prediction') + ' — <a href="#" onclick="refreshPredictions(event)" style="color:var(--accent)">' + _t('refresh_prediction') + '</a></div>';
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
                '<span class="prediction-event-title">' + escapeHtml(_bilingual(p.event_title, p.event_title_en, '')) + '</span>' +
                '<span class="prediction-timeframe">' + escapeHtml(p.timeframe) + '</span>' +
                '<span class="prediction-prob ' + probClass + '">' + escapeHtml(_bilingual(p.probability_label, p.probability_label_en, '')) + ' ' + Math.round(p.probability * 100) + '%</span>' +
                '</div>' +
                '<div class="prediction-scenario">' + escapeHtml(_bilingual(p.scenario, p.scenario_en, '')) + '</div>' +
                '<div class="prediction-reasoning">' + escapeHtml(_bilingual(p.reasoning, p.reasoning_en, '')) + '</div>';

            if (hasEntities) {
                html += '<div class="prediction-entities">';
                html += entities.map(en => {
                    const dirIcon = en.impact_score > 0 ? '📈' : en.impact_score < 0 ? '📉' : '➖';
                    const enAction = _bilingual(en.action, en.action_en, '');
                    const actClass = enAction === '买入' || enAction === 'Buy' ? 'act-buy' : enAction === '卖出' || enAction === 'Sell' ? 'act-sell' : 'act-hold';
                    return '<span class="pred-entity-chip ' + actClass + '">' + dirIcon + ' ' +
                        escapeHtml(en.entity) + ' <small>' + escapeHtml(enAction) + '</small></span>';
                }).join('');
                html += '</div>';
            }

            html += '</div></div>';
            return html;
        }).join('');

    } catch (_) {
        container.innerHTML = '<div class="loading">' + _t('prediction_load_failed') + '</div>';
    }
}

window.refreshPredictions = async function(ev) {
    ev.preventDefault();
    const container = document.getElementById('events-list');
    container.innerHTML = '<div class="loading">' + _t('generating_prediction') + '</div>';
    try {
        const resp = await fetch('/api/predictions/refresh', {method: 'POST'});
        const data = await resp.json();
        if (data.predictions && data.predictions.length) {
            await loadPredictions();
        } else {
            container.innerHTML = '<div class="loading">' + _t('prediction_empty') + '</div>';
        }
    } catch (_) {
        container.innerHTML = '<div class="loading">' + _t('prediction_failed') + '</div>';
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
        document.getElementById('detail-header').innerHTML = '<h2>' + _t('detail_not_found') + '</h2>';
        return;
    }
    const data = await resp.json();
    const e = data.event;

    document.getElementById('detail-header').innerHTML =
        '<h2>' + escapeHtml(_bilingual(e.title_cn, e.title_en, e.title)) + '</h2>' +
        '<div class="detail-meta">' +
        '<span>' + _t('detail_source') + ': ' + escapeHtml(e.source_platform) + '</span>' +
        '<span>' + _t('detail_first_seen') + ': ' + formatTime(e.first_seen_at) + '</span>' +
        '<span>' + _t('detail_region') + ': ' + escapeHtml(e.region) + '</span>' +
        '</div>';

    const summaryText = _bilingual(e.summary_cn, e.summary_en);
    if (summaryText) {
        document.getElementById('detail-summary').innerHTML = '<p><strong>' + _t('detail_ai_summary') + '：</strong>' + escapeHtml(summaryText) + '</p>';
    }

    const impactPoints = parseJsonField(_bilingual(e.impact_points, e.impact_points_en));
    if (impactPoints.length > 0) {
        document.getElementById('detail-impact').innerHTML =
            '<h3>' + _t('detail_impact') + '</h3>' +
            '<ul class="impact-list">' +
            impactPoints.map(p => '<li>' + escapeHtml(p) + '</li>').join('') +
            '</ul>';
    }

    const personalImpact = parseJsonField(_bilingual(e.personal_impact, e.personal_impact_en));
    if (personalImpact.length > 0) {
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">💰 ' + _t('detail_personal_impact') + '</h3>' +
            '<div class="pi-detail-list">' +
            personalImpact.map((p, j) => '<div class="pi-detail-item"><span class="pi-detail-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>').join('') +
            '</div>';
    }

    const entities = parseJsonField(e.entities);
    if (entities.length > 0) {
        const sigIcon = (d) => d === 'negative' ? '📉' : d === 'positive' ? '📈' : '➖';
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">🎯 ' + _t('detail_entity_impact') + '</h3>' +
            '<div class="entity-detail-list">' +
            entities.map(en => '<div class="entity-detail-item">' +
                '<span class="ed-name">' + escapeHtml(en.entity || '') + '</span>' +
                '<span class="ed-type">' + escapeHtml(en.type || '') + '</span>' +
                '<span class="ed-dir">' + sigIcon(en.direction) + ' ' + escapeHtml(en.direction || 'neutral') + '</span>' +
                '<span class="ed-action">→ ' + escapeHtml(_bilingual(en.action, en.action_en, '')) + '</span>' +
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
            yAxis: { type: 'value', name: _t('heat_score'), axisLabel: { color: '#888' } },
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
            '<span class="related-tag" onclick="location.href=\'/event/' + r.id + '\'">' + escapeHtml(_bilingual(r.title_cn, r.title_en, r.title)) + '</span>'
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
    const locale = window.I18N.getLang() === 'zh' ? 'zh-CN' : 'en-US';
    return d.toLocaleString(locale);
}

// --- Init ---
if (document.querySelector('.dashboard')) {
    loadDashboard().catch(console.error);
    setInterval(() => loadDashboard().catch(console.error), 5 * 60 * 1000);
}
