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

// Podcast image lightbox
function openPodcastLightbox() {
    var lb = document.getElementById('podcastLightbox');
    if (lb) { lb.classList.add('active'); document.body.style.overflow = 'hidden'; }
}
function closePodcastLightbox() {
    var lb = document.getElementById('podcastLightbox');
    if (lb) { lb.classList.remove('active'); document.body.style.overflow = ''; }
}

// Click-to-play YouTube (replaces thumbnail with iframe)
function playInlineVideo(container, ytId) {
    if (!container || !ytId) return;
    container.innerHTML = '<iframe width="100%" height="100%" src="https://www.youtube.com/embed/' + ytId + '?autoplay=1" frameborder="0" allow="autoplay" allowfullscreen style="position:absolute;inset:0"></iframe>';
    container.onclick = null;
    container.style.cursor = 'default';
}

// ── In-page search ────────────────────────────────────────────────────
(function() {
    var SECTION_MAP = [
        { id: 'daily-summary', label: 'The Wire', icon: 'bolt', color: '#3B82F6' },
        { id: 'todays-focus', label: 'The Lens', icon: 'center_focus_strong', color: '#8B5CF6' },
        { id: 'market-snapshot', label: 'The Ticker', icon: 'monitoring', color: '#10B981' },
        { id: 'ai-developments', label: 'The Radar', icon: 'auto_awesome', color: '#06B6D4' },
        { id: 'world-news', label: 'The Globe', icon: 'public', color: '#F59E0B' },
        { id: 'newsletter-intelligence', label: 'The Feed', icon: 'mail', color: '#EC4899' },
        { id: 'ai-tool-guide', label: 'Lab Field Notes', icon: 'science', color: '#6366F1' },
        { id: 'competitive-landscape', label: 'The Arena', icon: 'groups', color: '#EF4444' },
        { id: 'todays-editorial', label: 'Deep Dive', icon: 'explore', color: '#8B5CF6' },
        { id: 'infographic', label: 'Infographic', icon: 'image', color: '#06B6D4' }
    ];

    var searchIndex = null;

    function buildIndex() {
        searchIndex = [];
        SECTION_MAP.forEach(function(s) {
            var el = document.getElementById(s.id);
            if (!el) return;
            var text = el.textContent || '';
            // Collapse whitespace
            text = text.replace(/\s+/g, ' ').trim();
            searchIndex.push({ id: s.id, label: s.label, icon: s.icon, color: s.color, text: text.toLowerCase(), raw: text });
        });
    }

    function getSnippet(raw, query) {
        var lower = raw.toLowerCase();
        var idx = lower.indexOf(query.toLowerCase());
        if (idx === -1) return '';
        var start = Math.max(0, idx - 40);
        var end = Math.min(raw.length, idx + query.length + 60);
        var snippet = (start > 0 ? '...' : '') + raw.slice(start, end) + (end < raw.length ? '...' : '');
        // Highlight match
        var re = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        return snippet.replace(re, '<mark>$1</mark>');
    }

    function doSearch(query) {
        var results = document.getElementById('searchResults');
        var empty = document.getElementById('searchEmpty');
        if (!results || !empty) return;
        if (!searchIndex) buildIndex();

        results.innerHTML = '';
        if (!query || query.length < 2) {
            empty.style.display = 'none';
            // Show all sections as quick nav
            searchIndex.forEach(function(s) {
                results.appendChild(makeItem(s, ''));
            });
            return;
        }

        var q = query.toLowerCase();
        var matches = searchIndex.filter(function(s) {
            return s.label.toLowerCase().indexOf(q) !== -1 || s.text.indexOf(q) !== -1;
        });

        if (matches.length === 0) {
            empty.style.display = '';
            return;
        }
        empty.style.display = 'none';
        matches.forEach(function(s) {
            results.appendChild(makeItem(s, query));
        });
    }

    function makeItem(s, query) {
        var div = document.createElement('div');
        div.className = 'search-result-item';
        div.setAttribute('data-section', s.id);
        var snippet = query ? getSnippet(s.raw, query) : '';
        div.innerHTML =
            '<div class="search-result-icon" style="background:' + s.color + '20;color:' + s.color + '">' +
                '<span class="material-symbols-outlined">' + s.icon + '</span>' +
            '</div>' +
            '<div class="search-result-text">' +
                '<div class="search-result-title">' + s.label + '</div>' +
                (snippet ? '<div class="search-result-snippet">' + snippet + '</div>' : '') +
            '</div>';
        div.addEventListener('click', function() { goToSection(s.id); });
        return div;
    }

    function forceVisible(el) {
        // Make section and all ancestors visible (undo IntersectionObserver fade-in)
        var node = el;
        while (node && node !== document.body) {
            if (node.classList.contains('section')) {
                node.style.opacity = '1';
                node.style.transform = 'translateY(0)';
            }
            node = node.parentElement;
        }
    }

    function expandSection(container) {
        if (!container) return;
        var expandable = container.querySelector('.expandable-content');
        if (expandable && (expandable.classList.contains('hidden') || expandable.style.display === 'none')) {
            expandable.classList.remove('hidden');
            expandable.style.display = '';
            var hdr = expandable.previousElementSibling;
            if (hdr && hdr.classList.contains('expandable-header')) {
                hdr.setAttribute('aria-expanded', 'true');
                var chev = hdr.querySelector('.expand-chevron');
                if (chev) chev.style.transform = 'rotate(180deg)';
            }
        }
    }

    function goToSection(id) {
        closeSearch();
        var el = document.getElementById(id);
        if (!el) return;
        // Force ALL sections visible so smooth scroll doesn't pass through invisible content
        document.querySelectorAll('.section').forEach(function(s) {
            s.style.opacity = '1';
            s.style.transform = 'translateY(0)';
        });
        // Auto-expand if collapsed
        expandSection(el);
        var parent = el.closest('.section');
        if (parent && parent !== el) {
            expandSection(parent);
        }
        setTimeout(function() { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 100);
    }

    window.openSearch = function() {
        var so = document.getElementById('searchOverlay');
        if (!so) return;
        so.style.display = '';
        if (!searchIndex) buildIndex();
        var input = document.getElementById('globalSearchInput');
        if (input) { input.value = ''; input.focus(); }
        doSearch('');
        document.body.style.overflow = 'hidden';
    };

    window.closeSearch = function() {
        var so = document.getElementById('searchOverlay');
        if (!so) return;
        so.style.display = 'none';
        document.body.style.overflow = '';
    };

    // Wire up input
    var searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
        var debounceTimer;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            var val = searchInput.value;
            debounceTimer = setTimeout(function() { doSearch(val); }, 150);
        });
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                var first = document.querySelector('.search-result-item');
                if (first) first.click();
            }
        });
    }

    // Ctrl+K / Cmd+K to open search
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            var so = document.getElementById('searchOverlay');
            if (so && so.style.display !== 'none') { closeSearch(); }
            else { openSearch(); }
        }
    });
})();

// Escape key closes overlays
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var so = document.getElementById('searchOverlay');
        if (so && so.style.display !== 'none') { closeSearch(); return; }
        var vid = document.getElementById('videoOverlay');
        if (vid && vid.classList.contains('active')) { toggleVideo(); return; }
        var info = document.getElementById('infographicOverlay');
        if (info && info.classList.contains('active')) { closeInfographic(); return; }
        var pod = document.getElementById('podcastLightbox');
        if (pod && pod.classList.contains('active')) { closePodcastLightbox(); return; }
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

// Hash scrolling with auto-expand for collapsed sections
if (window.location.hash) {
    var hashTarget = document.querySelector(window.location.hash);
    if (hashTarget) {
        var expandable = hashTarget.querySelector('.expandable-content');
        if (expandable && (expandable.classList.contains('hidden') || expandable.style.display === 'none')) {
            expandable.classList.remove('hidden');
            expandable.style.display = '';
            var btn = expandable.previousElementSibling;
            if (btn && btn.classList.contains('expandable-header')) {
                btn.setAttribute('aria-expanded', 'true');
                var chev = btn.querySelector('.expand-chevron');
                if (chev) chev.style.transform = 'rotate(180deg)';
            }
        }
        setTimeout(function() { hashTarget.scrollIntoView({behavior: 'smooth'}); }, 300);
    }
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
