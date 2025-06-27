const fetch = require("node-fetch");

let cache = { data: null, timestamp: 0 };
const TTL = 15 * 60 * 1000; // cache for 15 minutes

module.exports = async (req, res) => {
  const now = Date.now();
  if (cache.data && now - cache.timestamp < TTL) {
    return res.status(200).json(cache.data);
  }

  const API_KEY = process.env.ACTION_NETWORK_API_KEY;
  const TAG_ID = "2335682"; // your tag ID
  const url = `https://actionnetwork.org/api/v2/tags/${TAG_ID}/people`;

  try {
    const response = await fetch(url, {
      headers: {
        "OSDI-API-Token": API_KEY,
        "Content-Type": "application/json"
      }
    });

    if (!response.ok) throw new Error("Action Network API error");

    const data = await response.json();
    const people = data._embedded?.["osdi:people"] || [];

    const names = people.map(person => {
      const first = person.given_name || "";
      const last = person.family_name || "";
      const fullName = `${first} ${last}`.trim();
      return fullName || "Anonymous";
    });

    const result = {
      count: names.length,
      names
    };

    cache.data = result;
    cache.timestamp = now;

    res.status(200).json(result);
  } catch (err) {
    console.error("API error:", err);
    res.status(500).json({ error: "Failed to fetch supporter data." });
  }
};
