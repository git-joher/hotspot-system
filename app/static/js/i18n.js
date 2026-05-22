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

    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', refreshStaticI18n);
    } else {
        refreshStaticI18n();
    }

    return { t, setLang, getLang, refreshStaticI18n };
})();

// Convenience alias
function _t(key) { return window.I18N.t(key); }
