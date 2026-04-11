/**
 * Vercel Edge Middleware: redirect social crawlers to dated URLs.
 *
 * When X, Facebook, LinkedIn, etc. crawl morning-briefing-koda.html (or /today),
 * they get 302-redirected to the dated version (e.g., morning-briefing-koda-2026-04-11.html).
 * This ensures each day gets its own OG cache entry — no stale previews.
 *
 * Regular users see the page normally (no redirect).
 */

const CRAWLER_UA =
  /Twitterbot|facebookexternalhit|LinkedInBot|Slackbot|Discordbot|WhatsApp|TelegramBot|Pinterestbot|Applebot/i;

export default function middleware(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  // Only intercept the always-current briefing URL
  if (path !== "/morning-briefing-koda.html" && path !== "/today") {
    return;
  }

  const ua = request.headers.get("user-agent") || "";
  if (!CRAWLER_UA.test(ua)) {
    return; // Regular user — serve normally
  }

  // Build today's date in YYYY-MM-DD (UTC, which is fine — pipeline runs in the morning)
  const now = new Date();
  const yyyy = now.getUTCFullYear();
  const mm = String(now.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(now.getUTCDate()).padStart(2, "0");
  const dated = `morning-briefing-koda-${yyyy}-${mm}-${dd}.html`;

  return Response.redirect(new URL(`/${dated}`, request.url), 302);
}

export const config = {
  matcher: ["/morning-briefing-koda.html", "/today"],
};
