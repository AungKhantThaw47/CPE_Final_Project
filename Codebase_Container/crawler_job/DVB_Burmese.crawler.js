const axios = require("axios");
const cheerio = require("cheerio");
const { createHash } = require("crypto");
const fs = require("fs");
const { uploadTextToGCS, uploadJSONToGCS } = require("./utils/gcs_utils");

const url = "https://www.dvb.no/category/8/news?page=1";
const filePath = "DVB_Burmese.json";
const yesterday = new Date();
yesterday.setDate(yesterday.getDate() - 1); // Set to yesterday
yesterday.setHours(0, 0, 0, 0); // Set to start of yesterday

console.log("============================================================");
console.log("DVB Burmese News Crawler");
console.log("============================================================");
console.log(`📅 Target Date: ${yesterday.toISOString().split('T')[0]}`);
console.log(`🌐 Source URL: ${url}`);
console.log(`⏰ Started at: ${new Date().toISOString()}`);
console.log("============================================================\n");

const postdata = [];
let foundOldPosts = false; // Flag to stop when we find posts older than yesterday

async function scrapePage(baseUrl , url, page) {
    try {
        console.log(`\n📄 Scraping page ${page}: ${url}`);
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

                // Check if post is from yesterday
                if (postDate.getTime() === yesterday.getTime()) {
                    postdata.push({ 
                        title, 
                        date: new Date(dateFormat).toISOString(), 
                        link: link.startsWith('http') ? link : `https://www.dvb.no${link}`
                    });
                    pagePostCount++;
                } else if (postDate < yesterday) {
                    // Found a post older than yesterday, set flag to stop pagination
                    foundOldPosts = true;
                }
            }
        });

        console.log(`   ✅ Found ${pagePostCount} articles from ${yesterday.toISOString().split('T')[0]} on page ${page}`);
        console.log(`   📊 Total collected so far: ${postdata.length} articles`);



        // Get the next page URL
        const nextPageLink = $('div.pagination div.cursor-pointer').last();
        let nextUrl = null;
        
        // Continue if we haven't found old posts yet
        if (nextPageLink.length > 0 && !foundOldPosts) {
            // Build next page URL
            nextUrl = `${baseUrl.split('?')[0]}?page=${page + 1}`;
        }
        
        if (nextUrl) {\n============================================================`);
            console.log(`✅ Scraping completed! (${reason})`);
            console.log(`📊 Total posts from yesterday: ${postdata.length}`);
            console.log(`============================================================\n
        } else {
            const reason = foundOldPosts ? "Found posts older than yesterday" : "No more pages";
            console.log(`Scraping completed! (${reason})`);
            console.log(`Total posts from yesterday: ${postdata.length}`);
            
            // Now fetch content for each post
            await fetchPostContents();
            
            const resultsData = {
                posts: postdata,
                meta: {
                    totalPosts: postdata.length,
                    scrapedAt: new Date().toISOString(),
                    scrapedDate: yesterday.toISOString().split('T')[0],
                    source: baseUrl
                }
            };
            
            console.log(`💾 Saved JSON locally: ${filePath}`);
            
            // Upload to GCS
            const dateStr = yesterday.toISOString().split('T')[0];
            const gcsPath = `dvb/${dateStr}/DVB_Burmese_${dateStr}.json`;
            await uploadJSONToGCS(resultsData, gcsPath);
            console.log(`☁️  Uploaded metadata to GCS: ${gcsPath}\n`);
            console.log(`============================================================`);
            console.log(`🎉 Crawling completed successfully!`);
            console.log(`⏰ Finished at: ${new Date().toISOString()}`);
            console.log(`============================================================`lit('T')[0];
            const gcsPath = `dvb/${dateStr}/DVB_Burmese_${dateStr}.json`;
            await uploadJSONToGCS(resultsData, gcsPath);
        }

    console.log(`\n============================================================`);
    console.log(`📥 Fetching Full Content for ${postdata.length} Articles`);
    console.log(`============================================================\n`);
    
    for (let i = 0; i < postdata.length; i++) {
        try {
            const post = postdata[i];
            console.log(`[${i + 1}/${postdata.length}] Fetching: ${post.title.substring(0, 50)}...`)
}

async function fetchPostContents() {
    for (let i = 0; i < postdata.length; i++) {
        try {
            const post = postdata[i];
            
            const { data } = await axios.get(post.link);
            const $ = cheerio.load(data);

            let full_content = "";
            $("div.full_content div p").each((i, el) => {
                const paragraph = $(el).text().trim();
                if (paragraph.length > 0){
                    full_content += paragraph + "\n";
                }
                console.log(`   ✅ Uploaded to: ${gcsPath}`);
            } else {
                post.content_file = "Upload skipped - no GCS bucket configured";
                console.log(`   ⚠️  Upload skipped`)
            const contentHash = createHash("md5").update(full_content).digest("hex");
            const dateStr = post.date.split("T")[0];
            const gcsPath = `dvb/${dateStr}/DVB_${dateStr}_${contentHash}.txt`;

            // Upload to GCS
            const uploadResult = await uploadTextToGCS(full_content, gcsPath);
            
            if (uploadResult.status === 'success') {
                post.content_file = uploadResult.url;
            } else {   ❌ Error fetching content for ${postdata[i].link}:`, error.message);
            postdata[i].content_file = "Error fetching content";
        }
    }
    console.log(`\n✅ Content fetching completed!\n`);       
            // Small delay to avoid overwhelming the server
            await new Promise(resolve => setTimeout(resolve, 100));
        } catch (error) {
            console.error(`Error fetching content for ${postdata[i].link}:`, error.message);
            postdata[i].content_file = "Error fetching content";
    }
}

if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
}

console.log(`Starting to scrape DVB Burmese news from: ${yesterday.toISOString().split('T')[0]}`);
scrapePage(url, url, 1);