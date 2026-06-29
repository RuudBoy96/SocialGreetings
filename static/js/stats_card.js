document.addEventListener('DOMContentLoaded', () => {
    const body = document.querySelector('.stats-body');
    if (!body) return;

    let scale = 1;
    const minScale = 0.72;

    function fitStats() {
        body.style.transform = `scale(${scale})`;
        body.style.transformOrigin = 'top center';
        const parent = body.parentElement;
        body.style.width = scale < 1 ? `${100 / scale}%` : '100%';

        while (body.scrollHeight > parent.clientHeight - 52 && scale > minScale) {
            scale -= 0.04;
            body.style.transform = `scale(${scale})`;
            body.style.width = `${100 / scale}%`;
        }
    }

    fitStats();
    window.addEventListener('resize', fitStats);
});
