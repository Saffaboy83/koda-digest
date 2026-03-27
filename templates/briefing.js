// Dark mode
(function(){
    const saved = localStorage.getItem('koda-theme');
    if(saved==='dark') document.documentElement.classList.add('dark-mode');
})();
function toggleDark(){
    document.documentElement.classList.toggle('dark-mode');
    const isDark = document.documentElement.classList.contains('dark-mode');
    localStorage.setItem('koda-theme', isDark ? 'dark' : 'light');
    document.getElementById('darkBtn').textContent = isDark ? '☀ Light' : '🌙 Dark';
}

// Podcast player
function togglePodcast(){
    const w = document.getElementById('podcastPlayer');
    const btn = document.querySelector('.podcast-btn');
    if(!w) return;
    w.classList.toggle('active');
    if(btn) btn.setAttribute('aria-expanded', w.classList.contains('active'));
}

// Video overlay
function toggleVideo(){
    const o = document.getElementById('videoOverlay');
    const f = document.getElementById('videoFrame');
    if(!o) return;
    if(o.classList.contains('active')){
        o.classList.remove('active');
        document.body.style.overflow = '';
        if(f) f.src = '';
    } else {
        o.classList.add('active');
        document.body.style.overflow = 'hidden';
        const ytId = document.body.getAttribute('data-youtube-id');
        if(f && ytId && /^[A-Za-z0-9_-]{11}$/.test(ytId)){
            f.src = 'https://www.youtube.com/embed/' + ytId + '?autoplay=1';
        }
        // Focus close button for keyboard users
        const closeBtn = o.querySelector('.video-overlay-close');
        if(closeBtn) closeBtn.focus();
    }
}

// Escape key closes video overlay
document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
        const o = document.getElementById('videoOverlay');
        if(o && o.classList.contains('active')) toggleVideo();
    }
});

// Day navigation
(function(){
    const d = document.body.getAttribute('data-digest-date');
    if(!d) return;
    const dt = new Date(d + 'T12:00:00');
    const prev = new Date(dt); prev.setDate(prev.getDate() - 1);
    const next = new Date(dt); next.setDate(next.getDate() + 1);
    const fmt = d2 => `${d2.getFullYear()}-${String(d2.getMonth()+1).padStart(2,'0')}-${String(d2.getDate()).padStart(2,'0')}`;
    const pf = 'morning-briefing-koda-' + fmt(prev) + '.html';
    const nf = 'morning-briefing-koda-' + fmt(next) + '.html';
    const pb = document.getElementById('prevBtn'), nb = document.getElementById('nextBtn');
    fetch(pf, {method:'HEAD'}).then(r => { if(r.ok && pb){ pb.href = pf; pb.classList.remove('disabled'); pb.removeAttribute('aria-disabled'); }}).catch(() => {});
    fetch(nf, {method:'HEAD'}).then(r => { if(r.ok && nb){ nb.href = nf; nb.classList.remove('disabled'); nb.removeAttribute('aria-disabled'); }}).catch(() => {});
})();

// Scroll animations (respects reduced motion)
if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    const obs = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if(e.isIntersecting){
                e.target.style.opacity = '1';
                e.target.style.transform = 'translateY(0)';
                obs.unobserve(e.target);
            }
        });
    }, {threshold: 0.08});
    document.querySelectorAll('.section').forEach(s => {
        s.style.opacity = '0';
        s.style.transform = 'translateY(16px)';
        s.style.transition = 'opacity 0.45s ease, transform 0.45s ease';
        obs.observe(s);
    });
}

// Hash scrolling
if(window.location.hash){
    const el = document.querySelector(window.location.hash);
    if(el) setTimeout(() => el.scrollIntoView({behavior: 'smooth'}), 300);
}
