// Tabbed per-platform export guide.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.export-guide').forEach((guide) => {
        const tabs = guide.querySelectorAll('[data-export-tab]');
        const panels = guide.querySelectorAll('[data-export-panel]');

        function activate(id) {
            tabs.forEach((tab) => {
                const on = tab.dataset.exportTab === id;
                tab.classList.toggle('is-active', on);
                tab.setAttribute('aria-selected', on ? 'true' : 'false');
            });
            panels.forEach((panel) => {
                panel.classList.toggle('is-active', panel.dataset.exportPanel === id);
            });
        }

        tabs.forEach((tab) => {
            tab.addEventListener('click', () => activate(tab.dataset.exportTab));
        });
    });
});
