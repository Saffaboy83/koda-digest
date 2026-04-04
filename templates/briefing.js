// Share buttons
function shareDigest(platform) {
    var url = window.location.href;
    var title = document.title;
    var text = document.querySelector('meta[name="description"]');
    text = text ? text.content : 'Daily AI intelligence briefing';
    if (platform === 'x') {
        window.open('https://x.com/intent/tweet?text=' + encodeURIComponent(title + ' - ' + text) + '&url=' + encodeURIComponent(url), '_blank');
    } else if (platform === 'linkedin') {
        window.open('https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(url), '_blank');
    } else if (platform === 'copy') {
        navigator.clipboard.writeText(url).then(function() {
            var btn = document.querySelector('[title="Copy link"]');
            if (btn) { btn.style.color = '#10B981'; setTimeout(function() { btn.style.color = ''; }, 1500); }
        });
    }
}

// Expandable sections (works on both mobile and desktop)
function toggleExpand(btn) {
    var content = btn.nextElementSibling;
    var chevron = btn.querySelector('.expand-chevron');
    if (!content) return;
    // Check if currently hidden (class or inline style)
    var isHidden = content.classList.contains('hidden') || content.style.display === 'none';
    if (isHidden) {
        content.classList.remove('hidden');
        content.style.display = '';
        btn.setAttribute('aria-expanded', 'true');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
    } else {
        // Use inline style so it overrides lg:block on desktop
        content.style.display = 'none';
        btn.setAttribute('aria-expanded', 'false');
        if (chevron) chevron.style.transform = '';
    }
}

// All sections start collapsed - no auto-expand needed

// Infographic lightbox
function openInfographic(src) {
    var overlay = document.getElementById('infographicOverlay');
    var img = document.getElementById('infographicFull');
    if (!overlay || !img) return;
    img.src = src;
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    var closeBtn = overlay.querySelector('.infographic-overlay-close');
    if (closeBtn) closeBtn.focus();
}
function closeInfographic() {
    var overlay = document.getElementById('infographicOverlay');
    if (!overlay) return;
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Podcast player toggle
function togglePodcast() {
    var w = document.getElementById('podcastPlayer');
    var btn = document.querySelector('.podcast-btn');
    if (!w) return;
    w.classList.toggle('active');
    if (btn) btn.setAttribute('aria-expanded', w.classList.contains('active'));
}

// Video overlay toggle
function toggleVideo() {
    var o = document.getElementById('videoOverlay');
    var f = document.getElementById('videoFrame');
    if (!o) return;
    if (o.classList.contains('active')) {
        o.classList.remove('active');
        document.body.style.overflow = '';
        if (f) f.src = '';
    } else {
        o.classList.add('active');
        document.body.style.overflow = 'hidden';
        var ytId = document.body.getAttribute('data-youtube-id');
        if (f && ytId && /^[A-Za-z0-9_-]{11}$/.test(ytId)) {
            f.src = 'https://www.youtube.com/embed/' + ytId + '?autoplay=1';
        }
        var closeBtn = o.querySelector('.video-overlay-close');
        if (closeBtn) closeBtn.focus();
    }
}

// Escape key closes overlays
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var vid = document.getElementById('videoOverlay');
        if (vid && vid.classList.contains('active')) { toggleVideo(); return; }
        var info = document.getElementById('infographicOverlay');
        if (info && info.classList.contains('active')) { closeInfographic(); return; }
    }
});

// Date picker navigation
(function() {
    var btn = document.getElementById('datePickerBtn');
    var picker = document.getElementById('datePicker');
    if (!btn || !picker) return;
    btn.addEventListener('click', function() { picker.showPicker ? picker.showPicker() : picker.click(); });
    picker.addEventListener('change', function() {
        var v = picker.value;
        if (!v) return;
        var file = 'morning-briefing-koda-' + v + '.html';
        fetch(file, {method: 'HEAD'}).then(function(r) {
            if (r.ok) { window.location.href = file; }
            else { alert('No digest available for ' + v); picker.value = document.body.getAttribute('data-digest-date'); }
        }).catch(function() { alert('No digest available for ' + v); picker.value = document.body.getAttribute('data-digest-date'); });
    });
})();

// Scroll-in animations (respects reduced motion)
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
            if (e.isIntersecting) {
                e.target.style.opacity = '1';
                e.target.style.transform = 'translateY(0)';
                obs.unobserve(e.target);
            }
        });
    }, {threshold: 0.08});
    document.querySelectorAll('.section').forEach(function(s) {
        s.style.opacity = '0';
        s.style.transform = 'translateY(16px)';
        s.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
        obs.observe(s);
    });
}

// Hash scrolling
if (window.location.hash) {
    var el = document.querySelector(window.location.hash);
    if (el) setTimeout(function() { el.scrollIntoView({behavior: 'smooth'}); }, 300);
}

// Scroll progress bar + back-to-top
(function() {
    var bar = document.getElementById('scrollProgress');
    var btn = document.getElementById('backToTop');
    if (!bar) return;
    var ticking = false;
    window.addEventListener('scroll', function() {
        if (!ticking) {
            requestAnimationFrame(function() {
                var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                var docHeight = document.documentElement.scrollHeight - window.innerHeight;
                if (docHeight > 0) {
                    bar.style.width = Math.min((scrollTop / docHeight) * 100, 100) + '%';
                }
                if (btn) {
                    if (scrollTop > 600) btn.classList.add('visible');
                    else btn.classList.remove('visible');
                }
                ticking = false;
            });
            ticking = true;
        }
    });
})();

/* ── Beehiiv Subscribe ──────────────────────────────────────── */
function kodaSubscribe(form) {
    var btn = form.querySelector('button');
    var email = form.querySelector('input[name="email"]').value;
    btn.textContent = 'Subscribing...';
    btn.disabled = true;
    fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
    }).then(function(r) {
        if (r.ok) {
            btn.textContent = 'Subscribed!';
            btn.style.background = '#10B981';
            form.querySelector('input[name="email"]').value = '';
        } else {
            btn.textContent = 'Try again';
            btn.disabled = false;
        }
    }).catch(function() {
        btn.textContent = 'Try again';
        btn.disabled = false;
    });
    return false;
}
