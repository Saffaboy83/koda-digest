"""
Standardize footer across all morning-briefing-koda-YYYY-MM-DD.html files.
Skips 2026-04-03 (already correct) and the undated morning-briefing-koda.html.
"""

import glob
import os

DIGEST_DIR = r"C:\Users\arno_\Digest"

SKIP_FILES = {
    "morning-briefing-koda.html",
    "morning-briefing-koda-2026-04-03.html",
}

STANDARD_FOOTER = '''<!-- Subscribe CTA -->
<section class="w-full py-16 px-6">
    <div class="max-w-xl mx-auto text-center">
        <div class="bg-[#0b1326]/60 backdrop-blur-xl border border-white/[0.06] rounded-2xl p-8 md:p-10 relative overflow-hidden">
            <div class="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-1 bg-gradient-to-r from-[#3B82F6] via-[#8B5CF6] to-[#EC4899] rounded-b-full"></div>
            <h3 class="text-xl font-bold text-white mb-2">Like what you see?</h3>
            <p class="text-[#c2c6d6] text-sm mb-6">Get tomorrow\'s brief delivered to your inbox.</p>
            <form class="flex flex-col sm:flex-row gap-2 max-w-md mx-auto p-1.5 rounded-full bg-[#171f33] border border-white/[0.06]" onsubmit="return kodaSubscribe(this)">
                <input type="email" name="email" required class="bg-transparent border-none outline-none text-white px-5 py-3 sm:py-0 w-full text-sm" placeholder="your@email.com">
                <button type="submit" class="bg-gradient-to-r from-[#3B82F6] to-[#6366F1] text-white px-6 py-3 rounded-full font-bold text-sm whitespace-nowrap hover:shadow-lg hover:shadow-[#3B82F6]/20 transition-all">Subscribe</button>
            </form>
            <p class="text-[10px] text-[#8c909f] mt-3">One email per day. Unsubscribe anytime.</p>
        </div>
    </div>
</section>

<footer class="w-full py-16 px-8 border-t border-white/5 relative overflow-hidden">
    <div class="absolute bottom-0 left-1/2 -translate-x-1/2 w-[500px] h-[200px] bg-gradient-to-t from-[#8B5CF6]/4 to-transparent rounded-full blur-3xl pointer-events-none"></div>
    <div class="max-w-2xl mx-auto text-center relative z-10">
        <div class="flex items-center justify-center gap-3 mb-8">
            <a href="https://x.com/intent/tweet?url=https://www.koda.community" target="_blank" rel="noopener" class="w-9 h-9 rounded-lg bg-white/5 hover:bg-[#3B82F6]/20 flex items-center justify-center text-[#8c909f] hover:text-[#3B82F6] transition-all no-underline" title="Share on X"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
            <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://www.koda.community" target="_blank" rel="noopener" class="w-9 h-9 rounded-lg bg-white/5 hover:bg-[#3B82F6]/20 flex items-center justify-center text-[#8c909f] hover:text-[#3B82F6] transition-all no-underline" title="Share on LinkedIn"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
            <button onclick="navigator.clipboard.writeText('https://www.koda.community');this.querySelector('svg').style.color='#10B981';setTimeout(()=>this.querySelector('svg').style.color='',1500)" class="w-9 h-9 rounded-lg bg-white/5 hover:bg-[#3B82F6]/20 flex items-center justify-center text-[#8c909f] hover:text-[#3B82F6] transition-all" title="Copy link"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg></button>
            <a href="./index.html#archive" class="w-9 h-9 rounded-lg bg-white/5 hover:bg-[#3B82F6]/20 flex items-center justify-center text-[#8c909f] hover:text-[#3B82F6] transition-all no-underline" title="Search"><span class="material-symbols-outlined text-base">search</span></a>
        </div>
        <div class="inline-flex items-center gap-3 mb-6">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#3B82F6] to-[#8B5CF6] flex items-center justify-center text-white font-black text-sm shadow-lg shadow-[#8B5CF6]/20">K</div>
            <span class="text-lg font-bold bg-gradient-to-r from-[#3B82F6] via-[#8B5CF6] to-[#EC4899] bg-clip-text text-transparent">Koda Intelligence</span>
        </div>
        <p class="text-[#c2c6d6] text-sm mb-8">Read. Listen. Watch. Every morning.</p>
        <div class="flex items-center justify-center gap-6 mb-10">
            <a href="./morning-briefing-koda.html" class="text-xs font-semibold text-[#c2c6d6] hover:text-[#3B82F6] transition-colors uppercase tracking-wider no-underline"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">bolt</span>The Signal</a>
            <span class="text-[#8c909f]/30">|</span>
            <a href="./archive/" class="text-xs font-semibold text-[#c2c6d6] hover:text-[#8B5CF6] transition-colors uppercase tracking-wider no-underline"><span class="material-symbols-outlined" style="font-size:12px;vertical-align:-2px;margin-right:2px">lock_open</span>The Vault</a>
            <span class="text-[#8c909f]/30">|</span>
            <a href="https://www.youtube.com/channel/UC8qqiKRGFAd5SwTr_2ZzPJg" target="_blank" rel="noopener" class="text-xs font-semibold text-[#c2c6d6] hover:text-[#EC4899] transition-colors uppercase tracking-wider no-underline">YouTube</a>
        </div>
        <p class="text-[11px] text-[#8c909f]/60">&copy; 2026 Koda Community &middot; <span class="font-mono">koda.community</span></p>
    </div>
</footer>

'''

KODA_SUBSCRIBE_JS = '''
/* -- Beehiiv Subscribe -- */
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
}'''

TAILWIND_CDN = '<script src="https://cdn.tailwindcss.com"></script>'


def find_footer_start(content):
    """Find the start position of the footer area (subscribe CTA + footer + old footer).
    Returns index into content where the old footer region begins, or None.
    """
    # Comment markers in priority order
    comment_markers = [
        '<!-- Subscribe CTA -->',
        '<!-- ===== FOOTER ===== -->',
        '<!-- Footer -->',
        '<!-- FOOTER -->',
    ]
    for marker in comment_markers:
        idx = content.find(marker)
        if idx != -1:
            return idx

    # For files like 03-22 that use <!-- ── FOOTER ── -->
    idx = content.find('<!-- \u2500\u2500 FOOTER \u2500\u2500 -->')
    if idx != -1:
        return idx

    # For files with a subscribe <section> before the <footer> (03-29 to 04-02)
    # The subscribe section has "Want this every morning?" or similar
    # Look for the <section> that contains the subscribe form, before <footer>
    footer_idx = content.rfind('<footer')
    if footer_idx != -1:
        # Check if there's a subscribe section above the footer
        # Search backwards from the footer for a <section> with subscribe content
        region_before_footer = content[max(0, footer_idx - 2000):footer_idx]
        # Look for the last <section that contains subscribe-like content
        section_search_start = max(0, footer_idx - 2000)
        # Find all <section tags in the region before footer
        search_pos = section_search_start
        last_subscribe_section = -1
        while True:
            pos = content.find('<section', search_pos)
            if pos == -1 or pos >= footer_idx:
                break
            # Check if this section contains subscribe-related content
            section_end = content.find('</section>', pos)
            if section_end != -1 and section_end < footer_idx + 200:
                section_content = content[pos:section_end]
                if 'kodaSubscribe' in section_content or 'every morning' in section_content or 'subscribe' in section_content.lower():
                    last_subscribe_section = pos
            search_pos = pos + 1

        if last_subscribe_section != -1:
            return last_subscribe_section
        else:
            return footer_idx

    # For files that use <div class="footer"> (03-23)
    idx = content.find('<div class="footer">')
    if idx != -1:
        # Check if there's a <!-- FOOTER --> comment right before
        check_region = content[max(0, idx - 50):idx]
        comment_idx = check_region.find('<!-- FOOTER -->')
        if comment_idx != -1:
            return max(0, idx - 50) + comment_idx
        return idx

    return None


def find_script_after_footer(content, footer_start):
    """Find the <script> tag that comes after the footer."""
    idx = content.find('<script', footer_start)
    if idx != -1:
        return idx
    return None


def has_tailwind(content):
    return 'cdn.tailwindcss.com' in content


def has_koda_subscribe_js(content):
    """Check if the file already has the kodaSubscribe function definition."""
    return 'function kodaSubscribe' in content


def add_tailwind_to_head(content):
    head_end = content.find('</head>')
    if head_end == -1:
        return content, False
    return content[:head_end] + '    ' + TAILWIND_CDN + '\n' + content[head_end:], True


def remove_old_koda_subscribe(content):
    """Remove old kodaSubscribe function from script block so we can add the standardized one."""
    # Find the function definition
    func_start = content.find('function kodaSubscribe')
    if func_start == -1:
        return content

    # Find the opening of the function: walk back to find if there's a comment
    check_before = content[max(0, func_start - 100):func_start]
    # Check for preceding comment like /* -- Beehiiv Subscribe -- */
    comment_markers = ['/* -- Beehiiv Subscribe --', '/* Beehiiv Subscribe', '// Beehiiv', '// Subscribe']
    actual_start = func_start
    for cm in comment_markers:
        cm_idx = check_before.rfind(cm)
        if cm_idx != -1:
            actual_start = max(0, func_start - 100) + cm_idx
            break

    # Find the end: count braces to find matching closing brace
    brace_count = 0
    started = False
    i = func_start
    while i < len(content):
        if content[i] == '{':
            brace_count += 1
            started = True
        elif content[i] == '}':
            brace_count -= 1
            if started and brace_count == 0:
                # Found the end of the function
                func_end = i + 1
                return content[:actual_start] + content[func_end:]
        i += 1

    return content


def process_file(filepath):
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes = []

    # Step 0: Add Tailwind if missing
    if not has_tailwind(content):
        content, added = add_tailwind_to_head(content)
        if added:
            changes.append("Added Tailwind CDN")

    # Step 1: Find footer start
    footer_start = find_footer_start(content)
    if footer_start is None:
        print(f"  WARNING: Could not find footer in {filename}")
        return False

    # Step 2: Find the <script> tag after the footer
    script_start = find_script_after_footer(content, footer_start)
    if script_start is None:
        print(f"  WARNING: Could not find <script> after footer in {filename}")
        return False

    # Step 3: Replace footer region with standard footer
    before_footer = content[:footer_start]
    after_script_tag = content[script_start:]

    content = before_footer + STANDARD_FOOTER + after_script_tag
    changes.append("Replaced footer block")

    # Step 4: Handle kodaSubscribe JS
    if has_koda_subscribe_js(content):
        # Remove old version first
        content = remove_old_koda_subscribe(content)
        changes.append("Removed old kodaSubscribe")

    # Add standardized kodaSubscribe before the last </script>
    last_script_end = content.rfind('</script>')
    if last_script_end != -1:
        content = content[:last_script_end] + KODA_SUBSCRIBE_JS + '\n' + content[last_script_end:]
        changes.append("Added kodaSubscribe JS")

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  OK: {filename} - {', '.join(changes)}")
        return True
    else:
        print(f"  SKIP: {filename} - No changes needed")
        return False


def main():
    pattern = os.path.join(DIGEST_DIR, "morning-briefing-koda-2026-*.html")
    files = sorted(glob.glob(pattern))

    print(f"Found {len(files)} dated briefing files\n")

    modified = 0
    skipped = 0
    errors = 0

    for filepath in files:
        filename = os.path.basename(filepath)

        if filename in SKIP_FILES:
            print(f"  SKIP: {filename} (in skip list)")
            skipped += 1
            continue

        try:
            if process_file(filepath):
                modified += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR: {filename} - {e}")
            import traceback
            traceback.print_exc()
            errors += 1

    print(f"\nDone: {modified} modified, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
