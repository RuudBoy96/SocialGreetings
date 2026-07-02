document.addEventListener('DOMContentLoaded', () => {
    const stack = document.getElementById('hero-card-stack');
    if (!stack) return;

    const pages = stack.querySelectorAll('.hero-card-page');
    if (pages.length === 0) return;

    let current = 0;

    setInterval(() => {
        pages[current].classList.remove('hero-card-page--active');
        current = (current + 1) % pages.length;
        pages[current].classList.add('hero-card-page--active');
    }, 3200);
});
