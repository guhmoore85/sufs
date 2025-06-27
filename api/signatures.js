import fetch from "node-fetch";

let cache = { data: null, timestamp: 0 };
const TTL = 15 * 60 * 1000; // 15 minutes

export default async function handler(req, res) {
  try {
    const now = Date.now();

    // Serve cached data if still fresh
    if (cache.data && now - cache.timestamp < TTL) {
      console.log("Returning cached data");
      return res.status(200).json(cache.data);
    }

    const API_KEY = process.env.ACTION_NETWORK_API_KEY;
    if (!API_KEY) {
      throw new Error("Missing ACTION_NETWORK_API_KEY");
    }

    const TAG_ID = "2335682"; // Replace if needed
    const url = `https://actionnetwork.org/api/v2/tags/${TAG_ID}/people`;

    const response = await fetch(url, {
      headers: {
        "OSDI-API-Token": API_KEY,
        "Content-Type": "application/json"
      }
    });

    if (!response.ok) {
      throw new Error(`Action Network API error: ${response.status}`);
    }

    const data = await response.json();
    const people = data._embedded?.["osdi:people"] || [];

    const names = people.map((person) => {
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

    console.log("Returning new data");
    res.status(200).json(result);
  } catch (error) {
    console.error("Function error:", error);
    res.status(500).json({ error: error.message });
  }
}

