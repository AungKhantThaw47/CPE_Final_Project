const axios = require("axios");
const env = require("dotenv").config();
const cheerio = require("cheerio");
const { createHash } = require("crypto");
const fs = require("fs");
const { uploadTextToGCS, uploadJSONToGCS } = require("./utils/gcs_utils");

const CONTENT_HASH = process.env.CONTENT_HASH || "content_hash_placeholder";
const url = "https://burmese.dvb.no/categories/media-news?page=2";
const defaultTargetDate = new Date();
defaultTargetDate.setDate(defaultTargetDate.getDate() - 1); // yesterday
defaultTargetDate.setHours(0, 0, 0, 0);

function formatDate(date) {
    return date.toISOString().split("T")[0];
}

function parseDateInput(value, label) {
    if (!value) {
        return null;
    }

    const matched = String(value).trim().match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!matched) {
        throw new Error(`Invalid ${label}: '${value}'. Expected format DD-MM-YYYY.`);
    }

    const day = Number(matched[1]);
    const month = Number(matched[2]) - 1;
    const year = Number(matched[3]);
    const parsed = new Date(year, month, day);
    parsed.setHours(0, 0, 0, 0);

    if (Number.isNaN(parsed.getTime()) || parsed.getFullYear() !== year || parsed.getMonth() !== month || parsed.getDate() !== day) {
        throw new Error(`Invalid ${label}: '${value}'.`);
    }

    return parsed;
}

function parseCrawlerDateRange() {
    const cliArgs = process.argv.slice(2);
    const argMap = new Map();

    for (let i = 0; i < cliArgs.length; i++) {
        const arg = cliArgs[i];
        if (!arg.startsWith("--")) {
            continue;
        }

        let key;
        let value;

        if (arg.includes("=")) {
            [key, value] = arg.replace(/^--/, "").split("=", 2);
        } else {
            key = arg.replace(/^--/, "");
            const nextArg = cliArgs[i + 1];

            // Support GCP split-arg style: --start-date 20-03-2026
            if (nextArg && !nextArg.startsWith("--")) {
                value = nextArg;
                i += 1;
            } else {
                value = "";
            }
        }

        argMap.set(key, value ?? "");
    }

    const startArg = argMap.get("start-date") || null;
    const endArg = argMap.get("end-date") || null;
    const startEnv = process.env.START_DATE || process.env.CRAWL_START_DATE || null;
    const endEnv = process.env.END_DATE || process.env.CRAWL_END_DATE || null;

    const startRaw = startArg || startEnv;
    const endRaw = endArg || endEnv;

    // Keep backward-compatible behavior: no custom date input => crawl yesterday only.
    if (!startRaw && !endRaw) {
        return {
            startDate: new Date(defaultTargetDate),
            endDate: new Date(defaultTargetDate),
            startDateStr: formatDate(defaultTargetDate),
            endDateStr: formatDate(defaultTargetDate)
        };
    }

    const startDate = parseDateInput(startRaw, "start-date") || new Date(defaultTargetDate);
    const endDate = parseDateInput(endRaw, "end-date") || new Date(startDate);

    if (startDate > endDate) {
        throw new Error(`Invalid date range: start-date ${formatDate(startDate)} is after end-date ${formatDate(endDate)}.`);
    }

    return {
        startDate,
        endDate,
        startDateStr: formatDate(startDate),
        endDateStr: formatDate(endDate)
    };
}

const { startDate, endDate, startDateStr, endDateStr } = parseCrawlerDateRange();

console.log("============================================================");
console.log("DVB Burmese News Crawler");
console.log("============================================================");
console.log(`Target Date Range: ${startDateStr} to ${endDateStr}`);
console.log(`Source URL: ${url}`);
console.log(`Started at: ${new Date().toISOString()}`);
console.log("============================================================\n");

const postdata = [];
let foundOldPosts = false; // stop when posts are older than startDate

function isInTargetRange(postDate) {
    return postDate >= startDate && postDate <= endDate;
}

function groupPostsByDate(posts) {
    const grouped = new Map();

    for (const post of posts) {
        const dateKey = post.date.split("T")[0];
        if (!grouped.has(dateKey)) {
            grouped.set(dateKey, []);
        }
        grouped.get(dateKey).push(post);
    }

    return grouped;
}

function getRequestedDatesInRange() {
    const dates = [];
    const cursor = new Date(startDate);

    while (cursor <= endDate) {
        dates.push(formatDate(cursor));
        cursor.setDate(cursor.getDate() + 1);
    }

    return dates;
}

async function saveAndUploadGroupedMetadata(posts, sourceUrl) {
    const groupedPosts = groupPostsByDate(posts);
    const requestedDates = getRequestedDatesInRange();

    for (const dateStr of requestedDates) {
        const datePosts = groupedPosts.get(dateStr) || [];
        const resultsData = {
            posts: datePosts,
            meta: {
                totalPosts: datePosts.length,
                scrapedAt: new Date().toISOString(),
                scrapedDate: dateStr,
                requestedStartDate: startDateStr,
                requestedEndDate: endDateStr,
                source: sourceUrl
            }
        };

        const localFilePath = `DVB_Burmese_${dateStr}.json`;
        fs.writeFileSync(localFilePath, JSON.stringify(resultsData, null, 2), "utf8");
        console.log(`Saved JSON locally: ${localFilePath}`);

        const gcsPath = `dvb/${CONTENT_HASH}/${dateStr}/DVB_Burmese_${dateStr}.json`;
        await uploadJSONToGCS(resultsData, gcsPath);
        console.log(`Uploaded metadata to GCS: ${gcsPath}`);

        if (datePosts.length === 0) {
            console.log(`No articles found for ${dateStr}; uploaded empty metadata file.`);
        }
    }

    const aggregateData = {
        posts,
        meta: {
            totalPosts: posts.length,
            scrapedAt: new Date().toISOString(),
            requestedStartDate: startDateStr,
            requestedEndDate: endDateStr,
            source: sourceUrl
        }
    };

    fs.writeFileSync("DVB_Burmese.json", JSON.stringify(aggregateData, null, 2), "utf8");
    console.log("Saved aggregate JSON locally: DVB_Burmese.json");

    return requestedDates;
}

async function scrapePage(baseUrl, url, page) {
    try {
        console.log(`\nScraping page ${page}: ${url}`);
        const { data } = await axios.get(url);
        const $ = cheerio.load(data);

        let pagePostCount = 0;
        $("a.block.hover\\:text-blue-600").each((i, el) => {
            const title = $(el).find("div.text-sm").first().text().trim();
            const dateStr = $(el).find("div.text-gray-500 div").first().text().trim();
            const link = $(el).attr("href");

            if (title && dateStr && link) {
                const dateFormat = Date.parse(dateStr);
                const postDate = new Date(dateFormat);
                postDate.setHours(0, 0, 0, 0); // Normalize to start of day

                if (isInTargetRange(postDate)) {
                    postdata.push({
                        title,
                        date: new Date(dateFormat).toISOString(),
                        link: link.startsWith('http') ? link : `https://www.dvb.no${link}`
                    });
                    pagePostCount++;
                } else if (postDate < startDate) {
                    // Found a post older than desired range, stop pagination
                    foundOldPosts = true;
                }
            }
        });

        console.log(`   Found ${pagePostCount} in-range articles on page ${page}`);
        console.log(`   Total collected so far: ${postdata.length} articles`);

        // Get the next page URL
        const nextPageLink = $('div.pagination div.cursor-pointer').last();
        let nextUrl = null;

        // Continue if we haven't found old posts yet
        if (nextPageLink.length > 0 && !foundOldPosts) {
            nextUrl = `${baseUrl.split('?')[0]}?page=${page + 1}`;
        }

        if (nextUrl) {
            await scrapePage(baseUrl, nextUrl, page + 1);
        } else {
            const reason = foundOldPosts ? `Found posts older than ${startDateStr}` : "No more pages";
            console.log(`\nScraping completed! (${reason})`);
            console.log(`Total posts in range ${startDateStr} to ${endDateStr}: ${postdata.length}`);

            // Now fetch content for each post
            await fetchPostContents();

            // Save grouped metadata by each crawled date and upload to each date folder.
            const processedDates = await saveAndUploadGroupedMetadata(postdata, baseUrl);

            console.log("\n============================================================");
            console.log("Crawling completed successfully!");
            console.log(`Finished at: ${new Date().toISOString()}`);
            console.log("============================================================");

            // Trigger text cleaner once for each processed date.
            for (const dateStr of processedDates) {
                await triggerTextCleaner(dateStr);
            }
        }

    } catch (error) {
        console.error("Error fetching the page:", error.message);
    }
}

async function triggerTextCleaner(dateStr) {
    console.log("\n============================================================");
    console.log(`Triggering text cleaner for date: ${dateStr}`);
    console.log("============================================================");

    try {
        const metadataBase = 'http://metadata.google.internal/computeMetadata/v1';
        const metaHeaders = { 'Metadata-Flavor': 'Google' };

        // Get auth token and project ID from GCP metadata server
        const [tokenRes, projectRes] = await Promise.all([
            axios.get(`${metadataBase}/instance/service-accounts/default/token`, { headers: metaHeaders }),
            axios.get(`${metadataBase}/project/project-id`, { headers: metaHeaders })
        ]);

        const accessToken = tokenRes.data.access_token;
        const projectId = projectRes.data;
        const region = process.env.GCP_REGION || 'asia-southeast1';
        const jobName = 'dvb-text-cleaner-job';

        const apiUrl = `https://run.googleapis.com/v2/projects/${projectId}/locations/${region}/jobs/${jobName}:run`;

        await axios.post(apiUrl, {
            overrides: {
                containerOverrides: [{
                    env: [{ name: 'PROCESS_DATE', value: dateStr }]
                }]
            }
        }, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
            }
        });

        console.log(`Text cleaner job triggered successfully for ${dateStr}`);
        console.log("Pipeline: Crawler -> Text Cleaner -> Crisis Classifier");

    } catch (error) {
        // Log error but don't fail the crawler — cleaner has its own scheduler as fallback
        console.error(`Failed to trigger text cleaner: ${error.message}`);
        console.log("Text cleaner will run on its scheduled time as fallback.");
    }
}

async function fetchPostContents() {
    console.log(`\nFetching Full Content for ${postdata.length} Articles\n`);

    for (let i = 0; i < postdata.length; i++) {
        try {
            const post = postdata[i];
            console.log(`[${i + 1}/${postdata.length}] Fetching: ${post.title.substring(0, 50)}...`);

            const { data } = await axios.get(post.link);
            const $ = cheerio.load(data);

            let full_content = "";
            $("div.full_content div p").each((j, el) => {
                const paragraph = $(el).text().trim();
                if (paragraph.length > 0) {
                    full_content += paragraph + "\n";
                }
            });

            const contentHash = createHash("md5").update(full_content).digest("hex");
            const dateStr = post.date.split("T")[0];
            const gcsPath = `dvb/${CONTENT_HASH}/${dateStr}/DVB_${dateStr}_${contentHash}.txt`;

            // Upload to GCS
            const uploadResult = await uploadTextToGCS(full_content, gcsPath);

            if (uploadResult.status === 'success') {
                post.content_file = uploadResult.url;
                console.log(`   Uploaded to: ${gcsPath}`);
            } else {
                post.content_file = "Upload skipped - no GCS bucket configured";
                console.log(`   Upload skipped`);
            }

            // Small delay to avoid overwhelming the server
            await new Promise(resolve => setTimeout(resolve, 100));
        } catch (error) {
            console.error(`Error fetching content for ${postdata[i].link}:`, error.message);
            postdata[i].content_file = "Error fetching content";
        }
    }
    console.log(`\nContent fetching completed!\n`);
}

if (fs.existsSync("DVB_Burmese.json")) {
    fs.unlinkSync("DVB_Burmese.json");
}

console.log(`Starting crawl for date range: ${startDateStr} to ${endDateStr}`);
scrapePage(url, url, 1);