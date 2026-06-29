const INSIDE_FONT_CLASSES = ['font-classic', 'font-modern', 'font-handwritten', 'font-elegant', 'font-typewriter'];
const INSIDE_SIZE_CLASSES = ['size-small', 'size-medium', 'size-large', 'size-xlarge'];

const SLIDE_LABELS = {
    front: 'Front cover',
    front2: 'Page 2',
    stats: 'Stats',
    wordmap: 'Word map',
    inside: 'Inside message',
    back: 'Back cover',
};

class CardCarousel {
    constructor(options) {
        this.cardId = options.cardId;
        this.track = document.getElementById('carousel-track');
        this.viewport = document.getElementById('carousel-viewport');
        this.counterEl = document.getElementById('slide-counter');
        this.btnPrev = document.getElementById('btn-prev');
        this.btnNext = document.getElementById('btn-next');
        this.pageSlider = document.getElementById('page-slider');
        this.pageLabels = document.getElementById('page-labels');
        this.insidePanel = document.getElementById('inside-editor-panel');
        this.insideInput = document.getElementById('inside-message-edit');
        this.fontSelect = document.getElementById('inside-font-edit');
        this.sizeSelect = document.getElementById('inside-font-size-edit');
        this.saveBtn = document.getElementById('btn-save');
        this.saveStatus = document.getElementById('save-status');
        this.insideContent = document.querySelector('.inside-content');
        this.current = 0;
        this.touchStartX = 0;
        this.slides = [];

        this.refreshSlides();
        this.bindControls();
        this.setupInsideEditor();
        this.goTo(0, false);

        window.addEventListener('resize', () => {
            this.setSlideWidths();
            this.goTo(this.current, false);
        });

        window.addEventListener('card-render-complete', (e) => {
            const slide2 = document.getElementById('carousel-slide-2');
            if (slide2 && e.detail?.showPage2) {
                slide2.classList.add('is-visible');
            }
            this.refreshSlides();
        });
    }

    refreshSlides() {
        this.slides = Array.from(
            document.querySelectorAll('.carousel-slide:not(.carousel-slide--optional), .carousel-slide--optional.is-visible')
        );
        this.updateSliderRange();
        this.setSlideWidths();
        if (this.current >= this.slides.length) {
            this.current = Math.max(0, this.slides.length - 1);
        }
        this.goTo(this.current, false);
    }

    updateSliderRange() {
        if (!this.pageSlider) return;
        const max = Math.max(0, this.slides.length - 1);
        this.pageSlider.max = max;
        this.pageSlider.value = Math.min(this.current, max);
    }

    setSlideWidths() {
        if (!this.viewport) return;
        const w = this.viewport.clientWidth;
        this.slides.forEach((slide) => {
            slide.style.width = `${w}px`;
            slide.style.minWidth = `${w}px`;
            slide.style.flexBasis = `${w}px`;
        });
    }

    bindControls() {
        this.btnPrev?.addEventListener('click', () => this.prev());
        this.btnNext?.addEventListener('click', () => this.next());
        this.saveBtn?.addEventListener('click', () => this.saveEdits());

        this.pageSlider?.addEventListener('input', () => {
            this.goTo(parseInt(this.pageSlider.value, 10));
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') this.prev();
            if (e.key === 'ArrowRight') this.next();
        });

        if (this.viewport) {
            this.viewport.addEventListener('touchstart', (e) => {
                this.touchStartX = e.changedTouches[0].screenX;
            }, { passive: true });

            this.viewport.addEventListener('touchend', (e) => {
                const diff = e.changedTouches[0].screenX - this.touchStartX;
                if (Math.abs(diff) > 50) {
                    if (diff < 0) this.next();
                    else this.prev();
                }
            }, { passive: true });
        }
    }

    setupInsideEditor() {
        const updateText = () => {
            if (!this.insideContent) return;
            const el = this.insideContent.querySelector('.inside-message, .inside-placeholder');
            if (!el) return;
            const val = this.insideInput?.value || '';
            el.textContent = val || 'Your personal message will appear here';
            el.classList.toggle('inside-placeholder', !val);
            el.classList.toggle('inside-message', !!val);
        };

        const updateFont = () => {
            if (!this.insideContent) return;
            if (this.fontSelect) {
                INSIDE_FONT_CLASSES.forEach((c) => this.insideContent.classList.remove(c));
                this.insideContent.classList.add(`font-${this.fontSelect.value}`);
            }
            if (this.sizeSelect) {
                INSIDE_SIZE_CLASSES.forEach((c) => this.insideContent.classList.remove(c));
                this.insideContent.classList.add(`size-${this.sizeSelect.value}`);
            }
        };

        this.insideInput?.addEventListener('input', updateText);
        this.fontSelect?.addEventListener('change', updateFont);
        this.sizeSelect?.addEventListener('change', updateFont);
    }

    getSlideLabel(slide) {
        const type = slide?.dataset.slideType || 'front';
        return SLIDE_LABELS[type] || 'Page';
    }

    update3dTilt(index) {
        this.slides.forEach((slide, i) => {
            const wrapper = slide.querySelector('.card-3d-wrapper');
            if (!wrapper) return;
            wrapper.classList.remove('tilt-right', 'tilt-center');
            if (i !== index) return;
            const type = slide.dataset.slideType;
            if (type === 'inside') wrapper.classList.add('tilt-center');
            else if (index % 2 === 1) wrapper.classList.add('tilt-right');
        });
    }

    goTo(index, animate = true) {
        if (index < 0 || index >= this.slides.length) return;
        this.current = index;

        const slideWidth = this.viewport?.clientWidth || 0;
        if (this.track && slideWidth > 0) {
            if (!animate) this.track.style.transition = 'none';
            this.track.style.transform = `translateX(-${index * slideWidth}px)`;
            if (!animate) {
                requestAnimationFrame(() => {
                    this.track.style.transition = '';
                });
            }
        }

        if (this.pageSlider) {
            this.pageSlider.value = index;
        }

        if (this.counterEl) {
            this.counterEl.textContent = `${index + 1} / ${this.slides.length}`;
        }

        if (this.pageLabels) {
            const label = this.getSlideLabel(this.slides[index]);
            this.pageLabels.innerHTML = `<strong>${label}</strong>`;
        }

        if (this.btnPrev) this.btnPrev.disabled = index === 0;
        if (this.btnNext) this.btnNext.disabled = index === this.slides.length - 1;

        const onInside = this.slides[index]?.dataset.slideType === 'inside';
        this.insidePanel?.classList.toggle('is-highlight', onInside);
        this.update3dTilt(index);
        this.updateStackPeek(index);
        this.refitVisibleChatPages(index);
    }

    refitVisibleChatPages(index) {
        const slide = this.slides[index];
        if (!slide || typeof window.refitChatPage !== 'function') return;
        const chatBody = slide.querySelector('.collage-body');
        if (chatBody) {
            const msgCount = chatBody.querySelectorAll('.message').length;
            const opts = slide.dataset.slideType === 'front2'
                ? { startFontSize: 11 * 0.82 }
                : {};
            if (slide.dataset.slideType === 'front2' && msgCount > 80) {
                opts.startFontSize = 11 * 0.72;
            }
            window.refitChatPage(chatBody, opts);
        }
    }

    updateStackPeek(index) {
        document.querySelectorAll('.card-3d-scene').forEach((scene) => {
            const prevPeek = scene.querySelector('[data-peek="prev"]');
            const nextPeek = scene.querySelector('[data-peek="next"]');
            const sceneSlide = scene.closest('.carousel-slide');
            const slideIndex = this.slides.indexOf(sceneSlide);
            if (slideIndex < 0) return;

            const showPrev = slideIndex === index && index > 0;
            const showNext = slideIndex === index && index < this.slides.length - 1;

            if (prevPeek) {
                prevPeek.classList.toggle('is-visible', showPrev);
                const label = prevPeek.querySelector('.card-stack-peek-label');
                if (label && showPrev) {
                    label.textContent = this.getSlideLabel(this.slides[index - 1]);
                }
            }
            if (nextPeek) {
                nextPeek.classList.toggle('is-visible', showNext);
                const label = nextPeek.querySelector('.card-stack-peek-label');
                if (label && showNext) {
                    label.textContent = this.getSlideLabel(this.slides[index + 1]);
                }
            }
        });
    }

    next() {
        if (this.current < this.slides.length - 1) this.goTo(this.current + 1);
    }

    prev() {
        if (this.current > 0) this.goTo(this.current - 1);
    }

    async saveEdits() {
        const payload = {
            inside_message: this.insideInput?.value || '',
            inside_font: this.fontSelect?.value || 'classic',
            inside_font_size: this.sizeSelect?.value || 'medium',
        };

        try {
            const res = await fetch(`/api/card/${this.cardId}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (res.ok && this.saveStatus) {
                this.saveStatus.textContent = 'Saved!';
                setTimeout(() => { this.saveStatus.textContent = ''; }, 2000);
            }
        } catch {
            if (this.saveStatus) this.saveStatus.textContent = 'Save failed';
        }
    }
}

window.CardCarousel = CardCarousel;
