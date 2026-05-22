// i18n — client-side translations
// Static mode: no server, pure localStorage

window.I18N = (function() {
    let lang = localStorage.getItem('lang') || document.documentElement.lang || 'en';
    let dict = window.I18N_DATA || {};

    function t(key) {
        return (dict[lang] && dict[lang][key]) || (dict['en'] && dict['en'][key]) || (dict['zh'] && dict['zh'][key]) || key;
    }

    function setLang(l) {
        lang = l;
        localStorage.setItem('lang', l);
        document.documentElement.lang = l;
        refreshStaticI18n();
        updateRegionUI();
        // Reset domestic mode when switching away from Chinese
        if (l !== 'zh' && localStorage.getItem('domestic') === 'true') {
            localStorage.setItem('domestic', 'false');
            updateRegionUI();
            window.dispatchEvent(new CustomEvent('domesticChange', { detail: { domestic: false } }));
        }
        window.dispatchEvent(new CustomEvent('langChange', { detail: { lang: l } }));
    }

    function getLang() {
        return lang;
    }

    // Update all [data-i18n] elements on language change
    function refreshStaticI18n() {
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            var key = el.getAttribute('data-i18n');
            if (key) el.textContent = t(key);
        });
        // Language switch button
        var btn = document.getElementById('lang-switch');
        if (btn) btn.textContent = lang === 'zh' ? 'EN' : '中文';
    }

    // Update region toggle visibility and state
    function updateRegionUI() {
        var btn = document.getElementById('region-toggle');
        if (!btn) return;
        var isChinese = lang === 'zh';
        var isDomestic = localStorage.getItem('domestic') === 'true';
        btn.style.display = isChinese ? 'inline-flex' : 'none';
        var icon = document.getElementById('region-icon');
        var label = document.getElementById('region-label');
        if (icon) icon.textContent = isDomestic ? '🇨🇳' : '🌏';
        if (label) label.textContent = isDomestic ? (dict['zh'] && dict['zh']['region_domestic'] || '国内') : (dict[lang] && dict[lang]['region_global'] || 'Global');
        btn.classList.toggle('active', isDomestic);
    }

    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            refreshStaticI18n();
            updateRegionUI();
        });
    } else {
        refreshStaticI18n();
        updateRegionUI();
    }

    return { t, setLang, getLang, refreshStaticI18n, updateRegionUI };
})();

// Convenience alias
function _t(key) { return window.I18N.t(key); }

// Region toggle — exposed globally for onclick
function toggleRegion() {
    var isDomestic = localStorage.getItem('domestic') === 'true';
    var newVal = isDomestic ? 'false' : 'true';
    localStorage.setItem('domestic', newVal);
    if (window.I18N.updateRegionUI) window.I18N.updateRegionUI();
    window.dispatchEvent(new CustomEvent('domesticChange', { detail: { domestic: newVal === 'true' } }));
}
