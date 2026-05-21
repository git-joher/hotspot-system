// i18n — client-side translations
// Server passes initial data via window.I18N_DATA in base.html

window.I18N = (function() {
    let lang = localStorage.getItem('lang') || document.documentElement.lang || 'en';
    let dict = window.I18N_DATA || {};

    function t(key) {
        return (dict[lang] && dict[lang][key]) || (dict['en'] && dict['en'][key]) || (dict['zh'] && dict['zh'][key]) || key;
    }

    async function setLang(l) {
        lang = l;
        localStorage.setItem('lang', l);
        document.documentElement.lang = l;
        await fetch('/api/lang/' + l, { method: 'POST' });
        window.dispatchEvent(new CustomEvent('langChange', { detail: { lang: l } }));
    }

    function getLang() {
        return lang;
    }

    return { t, setLang, getLang };
})();

// Convenience alias
function _t(key) { return window.I18N.t(key); }
