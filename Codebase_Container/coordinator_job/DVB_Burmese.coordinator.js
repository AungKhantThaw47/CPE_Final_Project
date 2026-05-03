const axios = require("axios");
require("dotenv").config();
const cheerio = require("cheerio");
const { uploadJSONToGCS } = require("./utils/gcs_utils");
const GCS_BUCKET = process.env.GCS_BUCKET || null;
const GCP_REGION = process.env.GCP_REGION || "asia-southeast1";
const CRAWLER_JOB_NAME = process.env.CRAWLER_JOB_NAME || "dvb-crawler-job";
const BASE_URL = "https://burmese.dvb.no";

function formatDate(date) {
    return date.toISOString().split("T")[0];
}

function parseDateInput(value, label) {
    if (!value) return null;
    const s = String(value).trim();
    // Accept DD-MM-YYYY
    let m = s.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m) {
        const d = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
        d.setHours(0, 0, 0, 0);
        return d;
    }
    // Accept YYYY-MM-DD
    m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
        const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
        d.setHours(0, 0, 0, 0);
        return d;
    }
    // Fallback: try Date.parse for other common formats
    const parsed = Date.parse(s);
    if (!isNaN(parsed)) {
        const d = new Date(parsed);
        d.setHours(0, 0, 0, 0);
        return d;
    }

    throw new Error(`Invalid ${label}: '${value}'. Expected DD-MM-YYYY or YYYY-MM-DD.`);
}

function parseDateRange() {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0);

    const startRaw = process.env.START_DATE || process.env.CRAWL_START_DATE || null;
    const endRaw = process.env.END_DATE || process.env.CRAWL_END_DATE || null;

    const startDate = parseDateInput(startRaw, "start-date") || yesterday;
    const endDate = parseDateInput(endRaw, "end-date") || new Date(startDate);

    if (startDate > endDate) {
        throw new Error(`start-date ${formatDate(startDate)} is after end-date ${formatDate(endDate)}`);
    }

    return { startDate, endDate };
}

async function scrapeLinks(startDate, endDate) {
    const articles = [];
    let page = 1;
    let stop = false;

    while (!stop) {
        const pageUrl = `${BASE_URL}/categories/news?page=${page}`;
        console.log(`Scraping listing page ${page}: ${pageUrl}`);

        try {
            const { data } = await axios.get(pageUrl);
            const $ = cheerio.load(data);
            let foundOldPost = false;

            $("a.block.hover\\:text-blue-600").each((_, el) => {
                const title = $(el).find("div.text-sm").first().text().trim();
                const dateStr = $(el).find("div.text-gray-500").first().text().trim();
                const href = $(el).attr("href");

                if (!title || !dateStr || !href) return;

                const postDate = new Date(Date.parse(dateStr));
                postDate.setHours(0, 0, 0, 0);

                if (postDate >= startDate && postDate <= endDate) {
                    articles.push({
                        title,
                        date: postDate.toISOString(),
                        link: href.startsWith("http") ? href : `${BASE_URL}${href}`,
                    });
                } else if (postDate < startDate) {
                    foundOldPost = true;
                }
            });

            const hasNext = $(`a[href*="?page=${page + 1}"]`).length > 0;

            if (foundOldPost || !hasNext) {
                stop = true;
            } else {
                page++;
            }
        } catch (err) {
            console.error(`Error scraping page ${page}: ${err.message}`);
            stop = true;
        }
    }

    console.log(`Link discovery complete: ${articles.length} articles across ${page} page(s)`);
    return articles;
}

async function saveLinksManifest(articles, startDate, endDate) {
    const byDate = new Map();
    for (const a of articles) {
        const key = a.date.split("T")[0];
        if (!byDate.has(key)) byDate.set(key, []);
        byDate.get(key).push(a);
    }

    const cursor = new Date(startDate);
    while (cursor <= endDate) {
        const dateStr = formatDate(cursor);
        const dateArticles = byDate.get(dateStr) || [];
        const manifest = {
            date: dateStr,
            articles: dateArticles,
            meta: {
                total: dateArticles.length,
                createdAt: new Date().toISOString(),
                startDate: formatDate(startDate),
                endDate: formatDate(endDate),
            },
        };

        const gcsPath = `dvb/links-manifests/${dateStr}/links-manifest.json`;
        const result = await uploadJSONToGCS(manifest, gcsPath);
        if (result.status === "success") {
            console.log(`Saved links manifest: ${gcsPath} (${dateArticles.length} articles)`);
        } else {
            console.log(`Links manifest upload skipped for ${dateStr}: ${result.status}`);
        }

        cursor.setDate(cursor.getDate() + 1);
    }
}

async function getGcpMeta() {
    const base = "http://metadata.google.internal/computeMetadata/v1";
    const headers = { "Metadata-Flavor": "Google" };
    const [tokenRes, projectRes] = await Promise.all([
        axios.get(`${base}/instance/service-accounts/default/token`, { headers }),
        axios.get(`${base}/project/project-id`, { headers }),
    ]);
    return { accessToken: tokenRes.data.access_token, projectId: projectRes.data };
}

async function spawnCrawlerJob(startStr, endStr, accessToken, projectId) {
    const apiUrl = `https://run.googleapis.com/v2/projects/${projectId}/locations/${GCP_REGION}/jobs/${CRAWLER_JOB_NAME}:run`;
    // Pass our unversioned manifest prefix so the crawler can find pre-discovered links.
    // Coordinator does NOT track versioning — always writes to dvb/links-manifests/.
    // Crawler must write articles under its own Terraform-injected CONTENT_HASH
    // so the text cleaner (which queries Neo4j for job:dvb-crawler-job's hash)
    // resolves the correct GCS path.
    await axios.post(
        apiUrl,
        {
            overrides: {
                containerOverrides: [{
                    env: [
                        { name: "CRAWL_START_DATE", value: startStr },
                        { name: "CRAWL_END_DATE", value: endStr },
                        { name: "LINKS_MANIFEST_PREFIX", value: `dvb/links-manifests` },
                        { name: "GCS_BUCKET", value: GCS_BUCKET || "" },
                        { name: "GCP_REGION", value: GCP_REGION },
                    ],
                }],
            },
        },
        {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                "Content-Type": "application/json",
            },
        }
    );
}

async function main() {
    const { startDate, endDate } = parseDateRange();

    console.log("============================================================");
    console.log("DVB Burmese Link-Discovery Coordinator");
    console.log("============================================================");
    console.log(`Date range : ${formatDate(startDate)} to ${formatDate(endDate)}`);
    console.log(`Crawler job: ${CRAWLER_JOB_NAME} @ ${GCP_REGION}`);
    console.log(`Started at : ${new Date().toISOString()}`);
    console.log("============================================================\n");

    const articles = await scrapeLinks(startDate, endDate);

    if (articles.length === 0) {
        console.log("No articles found in range. Exiting.");
        return;
    }

    await saveLinksManifest(articles, startDate, endDate);

    // Crawler expects dates in DD-MM-YYYY. formatDate() returns YYYY-MM-DD
    const startStr = (() => {
        const d = startDate.getDate().toString().padStart(2, "0");
        const m = (startDate.getMonth() + 1).toString().padStart(2, "0");
        const y = startDate.getFullYear();
        return `${d}-${m}-${y}`;
    })();
    const endStr = (() => {
        const d = endDate.getDate().toString().padStart(2, "0");
        const m = (endDate.getMonth() + 1).toString().padStart(2, "0");
        const y = endDate.getFullYear();
        return `${d}-${m}-${y}`;
    })();
    console.log(`\nSpawning crawler sub-job for ${startStr} to ${endStr}...`);

    let accessToken, projectId;
    try {
        ({ accessToken, projectId } = await getGcpMeta());
    } catch (err) {
        console.error(`Failed to get GCP metadata: ${err.message}`);
        console.error("Cannot spawn sub-job without GCP credentials. Exiting.");
        process.exitCode = 1;
        return;
    }

    try {
        await spawnCrawlerJob(startStr, endStr, accessToken, projectId);
        console.log(`Crawler sub-job spawned for ${startStr} to ${endStr}`);
    } catch (err) {
        console.error(`Failed to spawn crawler sub-job: ${err.message}`);
        process.exitCode = 1;
        return;
    }

    console.log("\n============================================================");
    console.log(`Coordinator done. 1 crawler sub-job spawned.`);
    console.log(`Finished at: ${new Date().toISOString()}`);
    console.log("============================================================");
}

main().catch(err => {
    console.error("Coordinator error:", err);
    process.exitCode = 1;
});
