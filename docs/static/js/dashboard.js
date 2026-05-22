let currentTimespan = 'realtime';
let currentSort = 'heat';
let currentCategory = null;
var BASE_PATH = (document.body && document.body.getAttribute('data-base-path')) || '/';

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

// --- Static mode helpers ---
function _staticTimespanHours() {
    switch (currentTimespan) {
        case 'realtime': return 1;
        case 'hourly': return 6;
        case 'daily': return 24;
        default: return 24;
    }
}

function _filterSortEvents(events, hours, sort) {
    const now = new Date();
    const cutoff = new Date(now.getTime() - hours * 3600000).toISOString();
    let filtered = events.filter(function(e) { return e.last_updated_at >= cutoff; });
    switch (sort) {
        case 'heat':
            filtered.sort(function(a, b) { return (b.latest_heat || 0) - (a.latest_heat || 0); });
            break;
        case 'personal':
            filtered.sort(function(a, b) {
                var aHas = a.personal_impact && a.personal_impact !== '[]' && a.personal_impact !== '';
                var bHas = b.personal_impact && b.personal_impact !== '[]' && b.personal_impact !== '';
                if (aHas && !bHas) return -1;
                if (!aHas && bHas) return 1;
                return (b.latest_heat || 0) - (a.latest_heat || 0);
            });
            break;
        case 'time':
            filtered.sort(function(a, b) { return b.last_updated_at.localeCompare(a.last_updated_at); });
            break;
        case 'source':
            filtered.sort(function(a, b) {
                return (a.source_platform || '').localeCompare(b.source_platform || '') || (b.latest_heat || 0) - (a.latest_heat || 0);
            });
            break;
    }
    return filtered;
}

// --- Tab switching ---
document.getElementById('time-tabs').addEventListener('click', function(e) {
    if (!e.target.classList.contains('tab')) return;
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    e.target.classList.add('active');
    currentTimespan = e.target.dataset.timespan;
    if (currentTimespan === 'ondemand') {
        if (window.IS_STATIC) {
            document.getElementById('events-list').innerHTML = '<div class="loading">' + _t('loading') + ' — ' + _t('no_data') + '</div>';
            return;
        }
        fetch(BASE_PATH + 'api/refresh', {method: 'POST'}).then(function() { loadDashboard(); });
    } else {
        loadDashboard();
    }
});

// --- Sort switching ---
document.addEventListener('click', function(e) {
    if (!e.target.classList.contains('sort-btn')) return;
    document.querySelectorAll('.sort-btn').forEach(function(b) { b.classList.remove('active'); });
    e.target.classList.add('active');
    currentSort = e.target.dataset.sort;
    loadDashboard();
});

// --- Language toggle (triggers re-render, no page reload) ---
window.toggleLang = function() {
    var newLang = window.I18N.getLang() === 'zh' ? 'en' : 'zh';
    window.I18N.setLang(newLang);
    loadDashboard();
};

// Listen for lang changes and re-render
window.addEventListener('langChange', function() { loadDashboard(); });

// --- Load dashboard ---
function loadDashboard() {
    return Promise.all([loadStats(), loadMainList(), loadCharts()]);
}

// --- Stats ---
function loadStats() {
    if (window.IS_STATIC && window.__PRELOADED_STATS__) {
        return Promise.resolve(renderStats(window.__PRELOADED_STATS__));
    }
    return fetch(BASE_PATH + 'api/stats').then(function(r) { return r.json(); }).then(renderStats);
}

function renderStats(data) {
    document.getElementById('stat-total').textContent = data.total_events + ' ' + _t('items');
    document.getElementById('stat-rising').textContent = data.rising_count + ' ' + _t('items');
    document.getElementById('stat-regions').textContent = data.region_count + ' ' + _t('regions');
    document.getElementById('stat-categories').textContent = data.category_count + ' ' + _t('categories');
    document.getElementById('update-time').textContent = _t('updated_at') + ' ' + new Date().toLocaleTimeString();
}

// --- Main list router ---
function loadMainList() {
    if (currentSort === 'entity') {
        return loadEntityList();
    } else if (currentSort === 'prediction') {
        return loadPredictions();
    } else {
        return loadEvents();
    }
}

// --- Shared render helpers ---
function parseJsonField(val) {
    if (!val) return [];
    try {
        return typeof val === 'string' ? JSON.parse(val) : val;
    } catch (_) { return []; }
}

function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(iso) {
    if (!iso) return '';
    var d = new Date(iso + 'Z');
    var locale = window.I18N.getLang() === 'zh' ? 'zh-CN' : 'en-US';
    return d.toLocaleString(locale);
}

function renderEventItem(e, i) {
    var heatClass = e.latest_heat > 80 ? 'high' : e.latest_heat > 50 ? 'mid' : '';
    var rankClass = i < 3 ? 'r' + (i + 1) : (i < 5 ? 'r' + (i + 1) : '');
    var trend = e.latest_trend === 'rising' ? ' ↑' : e.latest_trend === 'falling' ? ' ↓' : '';
    var impactPoints = parseJsonField(_bilingual(e.impact_points, e.impact_points_en));
    var personalImpact = parseJsonField(_bilingual(e.personal_impact, e.personal_impact_en));
    var entities = parseJsonField(e.entities);
    var hasExpand = impactPoints.length > 0 || personalImpact.length > 0 || entities.length > 0;

    var html = '<div class="event-item" data-eid="' + e.id + '">' +
        '<span class="event-rank ' + rankClass + '">' + (i + 1) + '</span>' +
        '<div class="event-info">' +
        '<div class="event-title-row">' +
        '<span class="event-title-link" onclick="location.href=BASE_PATH + \'event/' + e.id + '\'">' + escapeHtml(_bilingual(e.title_cn, e.title_en, e.title)) + trend + '</span>';
    if (hasExpand) {
        html += '<button class="expand-toggle" data-eid="' + e.id + '" onclick="toggleExpand(event, ' + e.id + ')">▶</button>';
    }
    html += '</div>';

    if (currentSort === 'personal' && personalImpact.length > 0) {
        html += '<div class="personal-impact-inline">';
        html += personalImpact.map(function(p, j) { return '<span class="pi-tag pi-tag-' + (j + 1) + '">💰 ' + escapeHtml(p) + '</span>'; }).join('');
        html += '</div>';
    }

    if (hasExpand) {
        html += '<div class="event-expand" id="expand-' + e.id + '" style="display:none">';
        if (impactPoints.length > 0) {
            html += '<div class="expand-section"><span class="expand-label">' + _t('expand_impact') + '</span>';
            html += impactPoints.map(function(p) { return '<span class="impact-chip">' + escapeHtml(p) + '</span>'; }).join('');
            html += '</div>';
        }
        if (personalImpact.length > 0) {
            html += '<div class="expand-section"><span class="expand-label">💰 ' + _t('expand_wealth') + '</span>';
            html += personalImpact.map(function(p, j) { return '<div class="pi-item"><span class="pi-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>'; }).join('');
            html += '</div>';
        }
        if (entities.length > 0) {
            html += '<div class="expand-section"><span class="expand-label">🎯 ' + _t('expand_entities') + '</span>';
            html += entities.map(function(en) {
                return '<span class="entity-chip entity-chip-' + (en.direction || 'neutral') + '">' +
                    escapeHtml(en.entity || '') + ' <small>' + escapeHtml(_bilingual(en.action, en.action_en, '')) + '</small></span>';
            }).join('');
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
}

// --- Event list (heat / personal / source / time) ---
function loadEvents() {
    if (window.IS_STATIC && window.__PRELOADED_EVENTS__) {
        var hours = _staticTimespanHours();
        var events = _filterSortEvents(window.__PRELOADED_EVENTS__, hours, currentSort);
        renderEventList(events);
        return Promise.resolve();
    }
    var params = new URLSearchParams({ timespan: currentTimespan, sort_by: currentSort, limit: '100' });
    if (currentCategory) params.set('category', currentCategory);
    return fetch(BASE_PATH + 'api/events?' + params).then(function(r) { return r.json(); }).then(function(data) {
        renderEventList(data.events || []);
    });
}

function renderEventList(events) {
    var container = document.getElementById('events-list');
    if (!events.length) {
        container.innerHTML = '<div class="loading">' + _t('no_data') + '</div>';
        return;
    }
    container.innerHTML = events.map(renderEventItem).join('');
}

// --- Entity impact list (entity sort tab) ---
function loadEntityList() {
    if (window.IS_STATIC && window.__PRELOADED_ENTITIES__) {
        renderEntityList(window.__PRELOADED_ENTITIES__);
        return Promise.resolve();
    }
    return fetch(BASE_PATH + 'api/entities?timespan=' + currentTimespan).then(function(r) { return r.json(); }).then(function(data) {
        renderEntityList(data.entities || []);
    });
}

function renderEntityList(entities) {
    var container = document.getElementById('events-list');
    if (!entities.length) {
        container.innerHTML = '<div class="loading">' + _t('no_entity_data') + '</div>';
        return;
    }
    container.innerHTML = entities.map(function(en, i) {
        var rankClass = i < 3 ? 'r' + (i + 1) : '';
        var sigClass = (en.signal === 'sell' || en.signal === 'falling') ? 'sig-sell' : (en.signal === 'buy' || en.signal === 'rising') ? 'sig-buy' : 'sig-hold';
        var sigIcon = (en.signal === 'sell' || en.signal === 'falling') ? '📉' : (en.signal === 'buy' || en.signal === 'rising') ? '📈' : '➖';
        var impactStr = (en.total_impact > 0 ? '+' : '') + en.total_impact.toFixed(1);
        var hasEvents = en.events && en.events.length > 0;

        var html = '<div class="entity-main-item">' +
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
            html += en.events.map(function(ev) {
                var evIcon = ev.direction === 'negative' ? '📉' : ev.direction === 'positive' ? '📈' : '➖';
                var evScore = (ev.impact_score > 0 ? '+' : '') + ev.impact_score.toFixed(1);
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
function loadPredictions() {
    var container = document.getElementById('events-list');
    if (window.IS_STATIC && window.__PRELOADED_PREDICTIONS__) {
        renderPredictions(window.__PRELOADED_PREDICTIONS__);
        return Promise.resolve();
    }
    return fetch(BASE_PATH + 'api/predictions').then(function(r) { return r.json(); }).then(function(data) {
        renderPredictions(data.predictions || []);
    }).catch(function() {
        container.innerHTML = '<div class="loading">' + _t('prediction_load_failed') + '</div>';
    });
}

function renderPredictions(predictions) {
    var container = document.getElementById('events-list');
    if (!predictions.length) {
        container.innerHTML = '<div class="loading">' + _t('no_prediction') + ' — <span style="color:var(--muted)">(' + _t('no_data') + ')</span></div>';
        return;
    }
    container.innerHTML = predictions.map(function(p, i) {
        var probClass = p.probability >= 0.7 ? 'prob-high' : p.probability >= 0.4 ? 'prob-mid' : 'prob-low';
        var entities = parseJsonField(p.entities);
        var hasEntities = entities.length > 0;

        var html = '<div class="prediction-item">' +
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
            html += entities.map(function(en) {
                var dirIcon = en.impact_score > 0 ? '📈' : en.impact_score < 0 ? '📉' : '➖';
                var enAction = _bilingual(en.action, en.action_en, '');
                var actClass = enAction === '买入' || enAction === 'Buy' ? 'act-buy' : enAction === '卖出' || enAction === 'Sell' ? 'act-sell' : 'act-hold';
                return '<span class="pred-entity-chip ' + actClass + '">' + dirIcon + ' ' +
                    escapeHtml(en.entity) + ' <small>' + escapeHtml(enAction) + '</small></span>';
            }).join('');
            html += '</div>';
        }

        html += '</div></div>';
        return html;
    }).join('');
}

window.refreshPredictions = function(ev) {
    ev.preventDefault();
    if (window.IS_STATIC) {
        document.getElementById('events-list').innerHTML = '<div class="loading">' + _t('prediction_load_failed') + '</div>';
        return;
    }
    var container = document.getElementById('events-list');
    container.innerHTML = '<div class="loading">' + _t('generating_prediction') + '</div>';
    fetch(BASE_PATH + 'api/predictions/refresh', {method: 'POST'}).then(function(r) { return r.json(); }).then(function(data) {
        if (data.predictions && data.predictions.length) {
            return loadPredictions();
        } else {
            container.innerHTML = '<div class="loading">' + _t('prediction_empty') + '</div>';
        }
    }).catch(function() {
        container.innerHTML = '<div class="loading">' + _t('prediction_failed') + '</div>';
    });
};

window.toggleExpand = function(ev, eid) {
    ev.stopPropagation();
    var el = document.getElementById('expand-' + eid);
    var btn = document.querySelector('.expand-toggle[data-eid="' + eid + '"]');
    if (el.style.display === 'none') {
        el.style.display = 'block';
        if (btn) btn.textContent = '▼';
    } else {
        el.style.display = 'none';
        if (btn) btn.textContent = '▶';
    }
};

// --- Charts ---
function loadCharts() {
    return Promise.all([loadCategoryPie(), loadHeatLine(), loadRegionBar()]);
}

function loadCategoryPie() {
    var chartDom = document.getElementById('chart-category-pie');
    if (!chartDom) return Promise.resolve();
    var chart = echarts.init(chartDom);

    if (window.IS_STATIC && window.__PRELOADED_EVENTS__) {
        var catData = {};
        window.__PRELOADED_EVENTS__.forEach(function(e) {
            if (e.source_platform) {
                var mainCat = e.source_platform.split(',')[0];
                if (!catData[mainCat]) catData[mainCat] = { name: mainCat, count: 0 };
                catData[mainCat].count++;
            }
        });
        chart.setOption({
            tooltip: { trigger: 'item' },
            series: [{
                type: 'pie', radius: ['40%', '70%'],
                data: Object.values(catData).filter(function(d) { return d.count > 0; }),
                label: { color: '#aaa', fontSize: 11 },
            }]
        });
        return Promise.resolve();
    }

    return fetch(BASE_PATH + 'api/categories').then(function(r) { return r.json(); }).then(function(categories) {
        var tsParam = currentTimespan === 'daily' ? 'daily' : 'realtime';
        return fetch(BASE_PATH + 'api/events?timespan=' + tsParam + '&limit=200').then(function(r2) { return r2.json(); }).then(function(eventsData) {
            var catData = {};
            categories.forEach(function(c) { catData[c.slug] = { name: c.name, count: 0 }; });
            (eventsData.events || []).forEach(function(e) {
                if (e.source_platform) {
                    var mainCat = e.source_platform.split(',')[0];
                    if (catData[mainCat]) catData[mainCat].count++;
                }
            });
            chart.setOption({
                tooltip: { trigger: 'item' },
                series: [{
                    type: 'pie', radius: ['40%', '70%'],
                    data: Object.values(catData).filter(function(d) { return d.count > 0; }).map(function(d) { return { name: d.name, value: d.count }; }),
                    label: { color: '#aaa', fontSize: 11 },
                }]
            });
        });
    });
}

function loadHeatLine() {
    var chartDom = document.getElementById('chart-heat-line');
    if (!chartDom) return Promise.resolve();
    var chart = echarts.init(chartDom);

    if (window.IS_STATIC && window.__SNAPSHOTS_TOP5__) {
        var snapshotsMap = window.__SNAPSHOTS_TOP5__;
        var topEvents = _filterSortEvents(window.__PRELOADED_EVENTS__, 720, 'heat').slice(0, 5);
        var series = topEvents.map(function(e) {
            var snaps = snapshotsMap[String(e.id)] || [];
            return {
                name: (e.title_cn || e.title).substring(0, 15),
                type: 'line',
                smooth: true,
                data: snaps.map(function(s) { return [s.snapshot_at, s.heat_score]; }),
            };
        });
        chart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { textStyle: { color: '#888', fontSize: 10 }, bottom: 0 },
            xAxis: { type: 'time', axisLabel: { color: '#888', fontSize: 10 } },
            yAxis: { type: 'value', axisLabel: { color: '#888' } },
            series: series,
        });
        return Promise.resolve();
    }

    return fetch(BASE_PATH + 'api/events?timespan=daily&sort_by=heat&limit=5').then(function(r) { return r.json(); }).then(function(data) {
        var seriesPromises = (data.events || []).slice(0, 5).map(function(e) {
            return fetch(BASE_PATH + 'api/events/' + e.id).then(function(r2) { return r2.json(); }).then(function(detail) {
                return {
                    name: (e.title_cn || e.title).substring(0, 15),
                    type: 'line',
                    smooth: true,
                    data: (detail.snapshots || []).map(function(s) { return [s.snapshot_at, s.heat_score]; }),
                };
            });
        });
        return Promise.all(seriesPromises).then(function(series) {
            chart.setOption({
                tooltip: { trigger: 'axis' },
                legend: { textStyle: { color: '#888', fontSize: 10 }, bottom: 0 },
                xAxis: { type: 'time', axisLabel: { color: '#888', fontSize: 10 } },
                yAxis: { type: 'value', axisLabel: { color: '#888' } },
                series: series,
            });
        });
    });
}

function loadRegionBar() {
    var chartDom = document.getElementById('chart-region-bar');
    if (!chartDom) return Promise.resolve();
    var chart = echarts.init(chartDom);

    if (window.IS_STATIC && window.__PRELOADED_EVENTS__) {
        var regions = {};
        window.__PRELOADED_EVENTS__.forEach(function(e) {
            var r = e.region || 'unknown';
            regions[r] = (regions[r] || 0) + 1;
        });
        chart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'category', data: Object.keys(regions), axisLabel: { color: '#888', fontSize: 10 } },
            yAxis: { type: 'value', axisLabel: { color: '#888' } },
            series: [{ type: 'bar', data: Object.values(regions), itemStyle: { color: '#4a90d9' } }],
        });
        return Promise.resolve();
    }

    return fetch(BASE_PATH + 'api/events?timespan=daily&limit=200').then(function(r) { return r.json(); }).then(function(data) {
        var regions = {};
        (data.events || []).forEach(function(e) {
            var r = e.region || 'unknown';
            regions[r] = (regions[r] || 0) + 1;
        });
        chart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'category', data: Object.keys(regions), axisLabel: { color: '#888', fontSize: 10 } },
            yAxis: { type: 'value', axisLabel: { color: '#888' } },
            series: [{ type: 'bar', data: Object.values(regions), itemStyle: { color: '#4a90d9' } }],
        });
    });
}

// --- Detail page ---
function initDetailPage(eventId) {
    if (window.IS_STATIC && window.__EVENT_DATA__) {
        renderDetailPage(window.__EVENT_DATA__);
        return;
    }
    return fetch(BASE_PATH + 'api/events/' + eventId).then(function(r) {
        if (r.status === 404) {
            document.getElementById('detail-header').innerHTML = '<h2>' + _t('detail_not_found') + '</h2>';
            return;
        }
        return r.json();
    }).then(function(data) {
        if (data) renderDetailPage(data);
    });
}

function renderDetailPage(data) {
    var e = data.event;
    if (!e) {
        document.getElementById('detail-header').innerHTML = '<h2>' + _t('detail_not_found') + '</h2>';
        return;
    }

    document.getElementById('detail-header').innerHTML =
        '<h2>' + escapeHtml(_bilingual(e.title_cn, e.title_en, e.title)) + '</h2>' +
        '<div class="detail-meta">' +
        '<span>' + _t('detail_source') + ': ' + escapeHtml(e.source_platform) + '</span>' +
        '<span>' + _t('detail_first_seen') + ': ' + formatTime(e.first_seen_at) + '</span>' +
        '<span>' + _t('detail_region') + ': ' + escapeHtml(e.region) + '</span>' +
        '</div>';

    var summaryText = _bilingual(e.summary_cn, e.summary_en);
    if (summaryText) {
        document.getElementById('detail-summary').innerHTML = '<p><strong>' + _t('detail_ai_summary') + '：</strong>' + escapeHtml(summaryText) + '</p>';
    }

    var impactPoints = parseJsonField(_bilingual(e.impact_points, e.impact_points_en));
    if (impactPoints.length > 0) {
        document.getElementById('detail-impact').innerHTML =
            '<h3>' + _t('detail_impact') + '</h3>' +
            '<ul class="impact-list">' +
            impactPoints.map(function(p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') +
            '</ul>';
    }

    var personalImpact = parseJsonField(_bilingual(e.personal_impact, e.personal_impact_en));
    if (personalImpact.length > 0) {
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">💰 ' + _t('detail_personal_impact') + '</h3>' +
            '<div class="pi-detail-list">' +
            personalImpact.map(function(p, j) { return '<div class="pi-detail-item"><span class="pi-detail-rank">#' + (j + 1) + '</span>' + escapeHtml(p) + '</div>'; }).join('') +
            '</div>';
    }

    var entities = parseJsonField(e.entities);
    if (entities.length > 0) {
        var sigIcon = function(d) { return d === 'negative' ? '📉' : d === 'positive' ? '📈' : '➖'; };
        document.getElementById('detail-impact').innerHTML +=
            '<h3 style="margin-top:16px">🎯 ' + _t('detail_entity_impact') + '</h3>' +
            '<div class="entity-detail-list">' +
            entities.map(function(en) {
                return '<div class="entity-detail-item">' +
                    '<span class="ed-name">' + escapeHtml(en.entity || '') + '</span>' +
                    '<span class="ed-type">' + escapeHtml(en.type || '') + '</span>' +
                    '<span class="ed-dir">' + sigIcon(en.direction) + ' ' + escapeHtml(en.direction || 'neutral') + '</span>' +
                    '<span class="ed-action">→ ' + escapeHtml(_bilingual(en.action, en.action_en, '')) + '</span>' +
                    '</div>';
            }).join('') +
            '</div>';
    }

    // Timeline chart
    var snapshots = data.snapshots || [];
    if (snapshots.length > 0) {
        var chart = echarts.init(document.getElementById('chart-timeline'));
        chart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'time', axisLabel: { color: '#888' } },
            yAxis: { type: 'value', name: _t('heat_score'), axisLabel: { color: '#888' } },
            series: [{
                type: 'line', smooth: true,
                areaStyle: { color: 'rgba(74,144,217,0.2)' },
                data: snapshots.map(function(s) { return [s.snapshot_at, s.heat_score]; }),
            }],
        });
    }

    // Sources
    var sourcesList = document.getElementById('sources-list');
    if (e.source_platform) {
        sourcesList.innerHTML = e.source_platform.split(',').map(function(p) {
            return '<div class="source-item"><span class="source-platform">' + p.trim() + '</span></div>';
        }).join('');
    }

    // Related events
    var related = data.relations || [];
    if (related.length > 0) {
        document.getElementById('related-list').innerHTML = related.map(function(r) {
            return '<span class="related-tag" onclick="location.href=\'/event/' + r.id + '\'">' + escapeHtml(_bilingual(r.title_cn, r.title_en, r.title)) + '</span>';
        }).join('');
    }
}

// --- Init ---
if (document.querySelector('.dashboard')) {
    loadDashboard().catch(console.error);
    setInterval(function() { loadDashboard().catch(console.error); }, 5 * 60 * 1000);
}
