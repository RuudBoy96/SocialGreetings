const INSIDE_FONT_CLASSES = ['font-classic', 'font-modern', 'font-handwritten', 'font-elegant', 'font-typewriter'];
const INSIDE_SIZE_CLASSES = ['size-small', 'size-medium', 'size-large', 'size-xlarge'];
const INSIDE_ALIGN_CLASSES = ['align-left', 'align-center', 'align-right'];
const INSIDE_ZONE_IDS = ['top', 'middle', 'bottom'];
const DEFAULT_ZONE_ALIGN = { top: 'left', middle: 'center', bottom: 'center' };
const DEFAULT_ZONE_COLOR = 'charcoal';
const DEFAULT_COLOR_HEX = '#2d2a26';

const SLIDE_LABELS = {
    front: 'Front cover',
    front2: 'Page 2',
    inside: 'Inside message',
    back: 'Back cover',
};

class CardViewer {
    constructor(options) {
        this.cardId = options.cardId;
        this.viewport = document.getElementById('card-viewer-viewport');
        this.track = document.getElementById('card-viewer-track');
        this.counterEl = document.getElementById('slide-counter');
        this.btnPrev = document.getElementById('btn-prev');
        this.btnNext = document.getElementById('btn-next');
        this.pageLabels = document.getElementById('page-labels');
        this.thumbStrip = document.getElementById('page-thumb-strip');
        this.controls = document.getElementById('presenter-controls');
        this.insidePanel = document.getElementById('personalise-panel');
        this.saveBtn = document.getElementById('btn-save');
        this.saveStatus = document.getElementById('save-status');
        this.loadingOverlay = document.getElementById('card-loading-overlay');
        this.current = 0;
        this.loaded = false;
        this.slides = [];
        this._refitTimer = null;

        this.bindControls();
        this.setupInsideEditor();
        this.refreshSlides();

        window.addEventListener('card-render-complete', (e) => {
            const slide2 = document.getElementById('carousel-slide-2');
            if (slide2 && e.detail?.showPage2) {
                slide2.classList.add('is-visible');
            }
            this.refreshSlides();
            this.buildThumbnails();
            this.setLoaded(true);
            this.goTo(this.current, false);
        });

        const page1 = document.getElementById('chat-page-1');
        if (page1?.querySelector('.message')) {
            this.refreshSlides();
            this.buildThumbnails();
            this.setLoaded(true);
            this.goTo(0, false);
        }
    }

    setLoaded(loaded) {
        this.loaded = loaded;
        this.loadingOverlay?.classList.toggle('is-hidden', loaded);
        this.controls?.classList.toggle('is-disabled', !loaded);
        this.thumbStrip?.classList.toggle('is-disabled', !loaded);
        document.querySelectorAll('.card-product-wrapper').forEach((el) => {
            el.classList.toggle('is-zoom-disabled', !loaded);
        });
    }

    refreshSlides() {
        this.slides = Array.from(
            document.querySelectorAll('.card-viewer-slide:not(.card-viewer-slide--optional), .card-viewer-slide--optional.is-visible')
        );
        if (this.current >= this.slides.length) {
            this.current = Math.max(0, this.slides.length - 1);
        }
        if (this.loaded) {
            this.goTo(this.current, false);
        }
    }

    bindControls() {
        this.btnPrev?.addEventListener('click', () => this.prev());
        this.btnNext?.addEventListener('click', () => this.next());
        this.saveBtn?.addEventListener('click', () => this.saveEdits());

        document.addEventListener('keydown', (e) => {
            if (!this.loaded) return;
            if (e.key === 'ArrowLeft') this.prev();
            if (e.key === 'ArrowRight') this.next();
        });
    }

    getZoneEditor(zoneId) {
        return document.querySelector(`.inside-zone-editor[data-zone="${zoneId}"]`);
    }

    getZonePickerValue(zoneId, pickerSelector, dataKey, fallback) {
        const editor = this.getZoneEditor(zoneId);
        const selected = editor?.querySelector(`${pickerSelector}.is-selected`);
        return selected?.dataset[dataKey] || fallback;
    }

    getZoneElements(zoneId) {
        return {
            input: document.getElementById(`inside-message-${zoneId}`),
            editor: this.getZoneEditor(zoneId),
            preview: document.querySelector(`.inside-zone--${zoneId}`),
        };
    }

    updateZonePreview(zoneId) {
        const { input, editor, preview } = this.getZoneElements(zoneId);
        if (!preview) return;

        const val = input?.value?.trim() || '';
        let el = preview.querySelector('.inside-message, .inside-placeholder');
        if (!el) {
            el = document.createElement('p');
            preview.appendChild(el);
        }

        if (val) {
            el.textContent = val;
            el.className = 'inside-message';
            preview.classList.remove('is-empty');
        } else if (zoneId === 'middle') {
            el.textContent = 'Your personal message will appear here';
            el.className = 'inside-placeholder';
            preview.classList.remove('is-empty');
        } else {
            el.remove();
            preview.classList.add('is-empty');
        }

        const font = this.getZonePickerValue(zoneId, '.font-tile', 'font', 'classic');
        INSIDE_FONT_CLASSES.forEach((c) => preview.classList.remove(c));
        preview.classList.add(`font-${font}`);

        const size = this.getZonePickerValue(zoneId, '.size-tile', 'size', 'medium');
        INSIDE_SIZE_CLASSES.forEach((c) => preview.classList.remove(c));
        preview.classList.add(`size-${size}`);

        const align = this.getZonePickerValue(zoneId, '.align-tile', 'align', DEFAULT_ZONE_ALIGN[zoneId] || 'center');
        INSIDE_ALIGN_CLASSES.forEach((c) => preview.classList.remove(c));
        preview.classList.add(`align-${align}`);

        const colorBtn = editor?.querySelector('.color-swatch.is-selected');
        const colorHex = colorBtn?.dataset.hex || DEFAULT_COLOR_HEX;
        if (el) {
            el.style.color = colorHex;
        }
    }

    setupInsideEditor() {
        document.querySelectorAll('.inside-zone-editor').forEach((editor) => {
            const zoneId = editor.dataset.zone;
            editor.querySelectorAll('.font-tile, .size-tile, .align-tile, .color-swatch').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const group = btn.closest('.font-picker, .size-picker, .align-picker, .color-picker');
                    group?.querySelectorAll('.is-selected').forEach((el) => {
                        el.classList.remove('is-selected');
                        el.setAttribute('aria-checked', 'false');
                    });
                    btn.classList.add('is-selected');
                    btn.setAttribute('aria-checked', 'true');
                    this.updateZonePreview(zoneId);
                });
            });

            const { input } = this.getZoneElements(zoneId);
            input?.addEventListener('input', () => this.updateZonePreview(zoneId));
        });

        document.querySelectorAll('.inside-preset-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const middleInput = document.getElementById('inside-message-middle');
                const message = btn.dataset.presetMessage || '';
                if (middleInput) {
                    middleInput.value = message;
                    this.updateZonePreview('middle');
                }
            });
        });

        INSIDE_ZONE_IDS.forEach((zoneId) => this.updateZonePreview(zoneId));
    }

    getSlideLabel(slide) {
        const type = slide?.dataset.slideType || 'front';
        return SLIDE_LABELS[type] || 'Page';
    }

    goTo(index, animate = true) {
        if (index < 0 || index >= this.slides.length) return;
        this.current = index;

        this.slides.forEach((slide, i) => {
            slide.classList.toggle('is-active', i === index);
        });

        if (this.counterEl) {
            this.counterEl.textContent = `${index + 1} / ${this.slides.length}`;
        }

        if (this.pageLabels) {
            const label = this.getSlideLabel(this.slides[index]);
            this.pageLabels.innerHTML = `<strong>${label}</strong>`;
        }

        if (this.btnPrev) this.btnPrev.disabled = index === 0;
        if (this.btnNext) this.btnNext.disabled = index === this.slides.length - 1;

        this.thumbStrip?.querySelectorAll('.page-thumb').forEach((thumb, i) => {
            thumb.classList.toggle('is-active', i === index);
        });

        const onInside = this.slides[index]?.dataset.slideType === 'inside';
        this.insidePanel?.classList.toggle('is-highlight', onInside);
        this.scheduleRefit(index);

        if (animate) {
            void this.viewport?.offsetHeight;
        }
    }

    buildThumbnails() {
        if (!this.thumbStrip) return;
        this.thumbStrip.innerHTML = '';

        this.slides.forEach((slide, index) => {
            const cardPage = slide.querySelector('.card-page');
            if (!cardPage) return;

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'page-thumb';
            btn.setAttribute('aria-label', this.getSlideLabel(slide));
            if (index === this.current) btn.classList.add('is-active');

            const inner = document.createElement('div');
            inner.className = 'page-thumb-inner';
            const clone = cardPage.cloneNode(true);
            inner.appendChild(clone);

            const label = document.createElement('span');
            label.className = 'page-thumb-label';
            label.textContent = this.getSlideLabel(slide).replace(' cover', '').replace(' message', '');

            btn.appendChild(inner);
            btn.appendChild(label);
            btn.addEventListener('click', () => this.goTo(index));
            this.thumbStrip.appendChild(btn);
        });
    }

    scheduleRefit(index) {
        clearTimeout(this._refitTimer);
        this._refitTimer = setTimeout(() => this.refitVisibleChatPages(index), 80);
    }

    refitVisibleChatPages(index) {
        const slide = this.slides[index];
        if (!slide || typeof window.refitChatPage !== 'function') return;
        const chatBody = slide.querySelector('.collage-body');
        if (chatBody) {
            const msgCount = chatBody.querySelectorAll('.message').length;
            const opts = slide.dataset.slideType === 'front2'
                ? { startFontSize: 11 * 0.75, isPage2: true }
                : {};
            if (slide.dataset.slideType === 'front2' && msgCount > 60) {
                opts.startFontSize = 11 * 0.68;
            }
            window.refitChatPage(chatBody, opts);
        }
    }

    next() {
        if (this.current < this.slides.length - 1) this.goTo(this.current + 1);
    }

    prev() {
        if (this.current > 0) this.goTo(this.current - 1);
    }

    collectInsideZones() {
        const zones = {};
        INSIDE_ZONE_IDS.forEach((zoneId) => {
            const { input } = this.getZoneElements(zoneId);
            zones[zoneId] = {
                message: input?.value || '',
                font: this.getZonePickerValue(zoneId, '.font-tile', 'font', 'classic'),
                font_size: this.getZonePickerValue(zoneId, '.size-tile', 'size', 'medium'),
                align: this.getZonePickerValue(zoneId, '.align-tile', 'align', DEFAULT_ZONE_ALIGN[zoneId] || 'center'),
                color: this.getZonePickerValue(zoneId, '.color-swatch', 'color', DEFAULT_ZONE_COLOR),
            };
        });
        return zones;
    }

    async saveEdits() {
        const payload = { inside_zones: this.collectInsideZones() };

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

window.CardViewer = CardViewer;
window.CardCarousel = CardViewer;
