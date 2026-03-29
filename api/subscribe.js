export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { email } = req.body || {};
  if (!email || !email.includes("@")) {
    return res.status(400).json({ error: "Valid email required" });
  }

  const apiKey = process.env.BEEHIIV_API_KEY;
  const rawPubId = process.env.BEEHIIV_PUBLICATION_ID || "";
  const pubId = rawPubId.startsWith("pub_") ? rawPubId : `pub_${rawPubId}`;

  if (!apiKey || !pubId) {
    return res.status(500).json({ error: "Newsletter service not configured" });
  }

  try {
    // Check if subscriber already exists (may be inactive from prior unsubscribe)
    const searchResp = await fetch(
      `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions?email=${encodeURIComponent(email)}`,
      {
        headers: { Authorization: `Bearer ${apiKey}` },
      }
    );

    if (searchResp.ok) {
      const searchData = await searchResp.json();
      const existing = (searchData.data || []).find(
        (s) => s.email.toLowerCase() === email.toLowerCase()
      );

      if (existing && existing.status !== "active") {
        // Delete inactive subscription, then recreate (PATCH doesn't reactivate)
        await fetch(
          `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions/${existing.id}`,
          {
            method: "DELETE",
            headers: { Authorization: `Bearer ${apiKey}` },
          }
        );

        const recreateResp = await fetch(
          `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${apiKey}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              email,
              send_welcome_email: false,
              utm_source: "koda_website",
              referring_site: "https://www.koda.community",
            }),
          }
        );

        if (recreateResp.ok) {
          return res.status(200).json({ ok: true, reactivated: true });
        }

        console.error("Reactivate error:", recreateResp.status, await recreateResp.text());
        return res.status(500).json({ error: "Resubscription failed" });
      }

      if (existing && existing.status === "active") {
        return res.status(200).json({ ok: true, already: true });
      }
    }

    // New subscriber — create fresh
    const resp = await fetch(
      `https://api.beehiiv.com/v2/publications/${pubId}/subscriptions`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          send_welcome_email: true,
          utm_source: "koda_website",
          referring_site: "https://www.koda.community",
        }),
      }
    );

    if (!resp.ok) {
      const body = await resp.text();
      console.error("Beehiiv error:", resp.status, body);
      return res.status(resp.status).json({ error: "Subscription failed" });
    }

    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("Subscribe error:", err);
    return res.status(500).json({ error: "Internal error" });
  }
}
