export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { email } = req.body || {};
  if (!email || !email.includes("@")) {
    return res.status(400).json({ error: "Valid email required" });
  }

  const apiKey = process.env.BEEHIIV_API_KEY;
  const pubId = process.env.BEEHIIV_PUBLICATION_ID;

  if (!apiKey || !pubId) {
    return res.status(500).json({ error: "Newsletter service not configured" });
  }

  try {
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
