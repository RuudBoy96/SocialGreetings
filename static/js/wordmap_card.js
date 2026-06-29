/** Shrink word cloud to fit card body if overflow occurs. */
document.addEventListener('DOMContentLoaded', () => {
    const cloud = document.getElementById('wordmap-cloud');
    const body = document.querySelector('.wordmap-body');
    if (!cloud || !body) return;

    let scale = 1;
    const minScale = 0.72;

    while (body.scrollHeight > body.clientHeight && scale > minScale) {
        scale -= 0.04;
        cloud.style.transform = `scale(${scale})`;
        cloud.style.transformOrigin = 'center top';
    }
});
