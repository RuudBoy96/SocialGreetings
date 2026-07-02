(function initCardZoom() {
    function updateZoomPosition(wrapper, clientX, clientY) {
        const rect = wrapper.getBoundingClientRect();
        const x = ((clientX - rect.left) / rect.width) * 100;
        const y = ((clientY - rect.top) / rect.height) * 100;
        wrapper.style.setProperty('--zoom-x', `${x}%`);
        wrapper.style.setProperty('--zoom-y', `${y}%`);
    }

    function onMouseEnter(e) {
        const wrapper = e.currentTarget;
        if (wrapper.classList.contains('is-zoom-disabled')) return;
        wrapper.classList.add('is-hover-zoom');
        updateZoomPosition(wrapper, e.clientX, e.clientY);
    }

    function onMouseMove(e) {
        const wrapper = e.currentTarget;
        if (!wrapper.classList.contains('is-hover-zoom')) return;
        updateZoomPosition(wrapper, e.clientX, e.clientY);
    }

    function onMouseLeave(e) {
        const wrapper = e.currentTarget;
        wrapper.classList.remove('is-hover-zoom');
        wrapper.style.removeProperty('--zoom-x');
        wrapper.style.removeProperty('--zoom-y');
    }

    document.querySelectorAll('.card-product-wrapper').forEach((wrapper) => {
        wrapper.addEventListener('mouseenter', onMouseEnter);
        wrapper.addEventListener('mousemove', onMouseMove);
        wrapper.addEventListener('mouseleave', onMouseLeave);
    });

    document.addEventListener('card-render-complete', () => {
        document.querySelectorAll('.card-product-wrapper:not([data-zoom-bound])').forEach((wrapper) => {
            wrapper.setAttribute('data-zoom-bound', '1');
            wrapper.addEventListener('mouseenter', onMouseEnter);
            wrapper.addEventListener('mousemove', onMouseMove);
            wrapper.addEventListener('mouseleave', onMouseLeave);
        });
    });
})();
