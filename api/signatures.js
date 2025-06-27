import fetch from "node-fetch";

let cache = { data: null, timestamp: 0 };
const TTL = 15 * 60 * 1000; // 15 minutes
const FORM_ID = "3b5f9f80-b7c7-4331-a052-41582c390dac";

export default async function handler(req, res) {
  try {
    const now = Date.now();

    if (cache.data && now - cache.timestamp < TTL) {
      return res.status(200).json(cache.data);
    }

    const API_KEY = process.env.ACTION_NETWORK_API_KEY;
    if (!API_KEY) {
      throw new Error("Missing ACTION_NETWORK_API_KEY");
    }

    let submissions = [];
    let nextPage = `https://actionnetwork.org/api/v2/forms/${FORM_ID}/submissions/`;

    while (nextPage) {
      const response = await fetch(nextPage, {
        headers: {
          "OSDI-API-Token": API_KEY,
          "Accept": "application/json"
        }
      });

      if (!response.ok) {
        throw new Error(`Error fetching submissions: ${response.status}`);
      }

      const data = await response.json();
      const pageSubmissions = data._embedded?.["osdi:submissions"] || [];
      submissions.push(...pageSubmissions);

      nextPage = data._links?.next?.href || null;
    }

    // Fetch each person's details
    const names = [];
    for (const submission of submissions) {
      const personUrl = submission._links?.["osdi:person"]?.href;
      if (personUrl) {
        try {
          const personRes = await fetch(personUrl, {
            headers: {
              "OSDI-API-Token": API_KEY,
              "Accept": "application/json"
            }
          });

          if (!personRes.ok) {
            console.warn(`Error fetching person: ${personRes.status}`);
            continue;
          }

          const person = await personRes.json();
          const first = person.given_name || "";
          const last = person.family_name || "";
          const fullName = `${first} ${last}`.trim();
          names.push(fullName || "Anonymous");
        } catch (err) {
          console.warn("Failed to fetch person detail:", err.message);
        }
      }
    }

    const result = {
      count: names.length,
      names
    };

    cache.data = result;
    cache.timestamp = now;

    return res.status(200).json(result);
  } catch (err) {
    console.error("Function error:", err.message);
    res.status(500).json({ error: err.message });
  }
}

