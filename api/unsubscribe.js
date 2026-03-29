export default async function handler(req, res) {
  // Accept both GET (email link click) and POST
  const params =
    req.method === "GET" ? req.query : { ...(req.query || {}), ...(req.body || {}) };

  const { email, token } = params;

  if (!email || !token) {
    return res.status(400).send(errorPage("Missing email or token."));
  }

  // Validate HMAC token (inline crypto to avoid import issues)
  const crypto = require("crypto");
  const secret = process.env.UNSUBSCRIBE_SECRET ||
    (process.env.BEEHIIV_API_KEY || "koda-unsub-key").slice(0, 16);
  const expected = crypto
    .createHmac("sha256", secret)
    .update(email.toLowerCase())
    .digest("hex")
    .slice(0, 32);

  if (token !== expected) {
    return res.status(403).send(errorPage("Invalid unsubscribe link."));
  }

  const apiKey = process.env.BEEHIIV_API_KEY;
  const rawPubId = process.env.BEEHIIV_PUBLICATION_ID || "";
  const pubId = rawPubId.startsWith("pub_") ? rawPubId : `pub_${rawPubId}`;

  if (!apiKey || !pubId) {
    return res.status(500).send(errorPage("Newsletter service not configured."));
  }

  try {
    // Find the subscriber by email
    const searchResp = await fetch(
      `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions?email=${encodeURIComponent(email)}`,
      {
        headers: { Authorization: `Bearer ${apiKey}` },
      }
    );

    if (!searchResp.ok) {
      console.error("Beehiiv search error:", searchResp.status);
      return res.status(500).send(errorPage("Could not find subscription."));
    }

    const searchData = await searchResp.json();
    const subs = searchData.data || [];
    const match = subs.find(
      (s) => s.email.toLowerCase() === email.toLowerCase()
    );

    if (!match) {
      return res.status(200).send(successPage(email, "already unsubscribed"));
    }

    // Update subscriber status to inactive
    const updateResp = await fetch(
      `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions/${match.id}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ unsubscribe: true }),
      }
    );

    if (!updateResp.ok) {
      const errText = await updateResp.text();
      console.error("Beehiiv unsubscribe error:", updateResp.status, errText);
      return res.status(500).send(errorPage("Unsubscribe failed. Please try again."));
    }

    return res.status(200).send(successPage(email, "unsubscribed"));
  } catch (err) {
    console.error("Unsubscribe error:", err);
    return res.status(500).send(errorPage("Something went wrong. Please try again."));
  }
}

function successPage(email, status) {
  const maskedEmail = email.replace(/(.{2})(.*)(@.*)/, "$1***$3");
  const message =
    status === "already unsubscribed"
      ? `${maskedEmail} was already unsubscribed.`
      : `${maskedEmail} has been unsubscribed from Koda Digest.`;

  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unsubscribed | Koda Digest</title>
<style>
  body{margin:0;padding:0;background:#0B1326;font-family:Inter,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .card{max-width:440px;padding:48px 32px;text-align:center;background:#0F172A;border:1px solid #1E293B;border-radius:16px}
  .badge{width:48px;height:48px;background:linear-gradient(135deg,#3B82F6,#8B5CF6);border-radius:12px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:20px}
  .badge span{color:white;font-weight:800;font-size:24px}
  h1{color:#E2E8F0;font-size:22px;margin:0 0 12px}
  p{color:#94A3B8;font-size:15px;line-height:1.6;margin:0 0 24px}
  a{color:#3B82F6;text-decoration:none;font-weight:600}
</style></head><body>
<div class="card">
  <div class="badge"><span>K</span></div>
  <h1>You're unsubscribed</h1>
  <p>${message}</p>
  <p style="font-size:13px">Changed your mind? <a href="https://www.koda.community">Re-subscribe at koda.community</a></p>
</div>
</body></html>`;
}

function errorPage(message) {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Error | Koda Digest</title>
<style>
  body{margin:0;padding:0;background:#0B1326;font-family:Inter,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
  .card{max-width:440px;padding:48px 32px;text-align:center;background:#0F172A;border:1px solid #1E293B;border-radius:16px}
  h1{color:#EF4444;font-size:20px;margin:0 0 12px}
  p{color:#94A3B8;font-size:15px;line-height:1.6;margin:0}
</style></head><body>
<div class="card">
  <h1>Oops</h1>
  <p>${message}</p>
</div>
</body></html>`;
}
