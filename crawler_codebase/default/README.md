# Mawkun.com News Crawler

Web crawler for extracting news articles from https://mawkun.com/, a Myanmar news website.

## Features

- 🕷️ **Two crawler implementations:**
  - `main.py` - Fast BeautifulSoup-based crawler (for static HTML)
  - `selenium_crawler.py` - Selenium-based crawler (for JavaScript-heavy pages)

- 📰 **Extracts:**
  - Article title
  - Full content
  - Author
  - Published date
  - Category
  - Tags
  - Images
  - URL

- 💾 **Export formats:**
  - JSON
  - CSV

## Installation

### 1. Install Python dependencies

```bash
pip install requests beautifulsoup4 selenium
```

### 2. Install ChromeDriver (for Selenium crawler)

**macOS:**

```bash
brew install chromedriver
```

**Linux:**

```bash
sudo apt-get install chromium-chromedriver
```

**Windows:**
Download from https://chromedriver.chromium.org/

## Usage

### Option 1: BeautifulSoup Crawler (Recommended - Faster)

```bash
python crawler_codebase/default/main.py
```

This will:

- Crawl 10 latest articles from the homepage
- Save to `mawkun_articles.json` and `mawkun_articles.csv`

### Option 2: Selenium Crawler (For JavaScript-heavy pages)

```bash
python crawler_codebase/default/selenium_crawler.py
```

This uses a headless Chrome browser to render JavaScript before scraping.

## Customization

### Crawl more articles

```python
from crawler_codebase.default.main import MawkunCrawler

crawler = MawkunCrawler()

# Crawl 50 latest articles
articles = crawler.crawl_latest_news(max_articles=50)

# Save results
crawler.save_to_json('my_articles.json')
crawler.save_to_csv('my_articles.csv')
```

### Crawl specific category

```python
# Crawl news category
news_articles = crawler.crawl_category(
    'https://mawkun.com/category/သတင်း/',
    max_pages=5
)
```

### Use Selenium with custom options

```python
from crawler_codebase.default.selenium_crawler import MawkunSeleniumCrawler

# Run with visible browser (not headless)
crawler = MawkunSeleniumCrawler(headless=False)

# Crawl with infinite scroll
articles = crawler.crawl_latest_news(max_articles=20, scroll=True)
```

## Output Format

### JSON Example

```json
{
  "url": "https://mawkun.com/article-url/",
  "title": "Article Title",
  "content": "Full article text...",
  "author": "Author Name",
  "published_date": "2026-01-13",
  "category": "သတင်း",
  "tags": ["tag1", "tag2"],
  "images": [
    {
      "url": "https://example.com/image.jpg",
      "alt": "Image description"
    }
  ],
  "crawled_at": "2026-01-24T10:30:00"
}
```

## Best Practices

1. **Be respectful:** Add delays between requests (already implemented)
2. **Check robots.txt:** Respect the website's crawling policies
3. **Error handling:** The crawler includes retry mechanisms
4. **Rate limiting:** Default 1-second delay between articles

## Troubleshooting

### ChromeDriver issues

If Selenium fails to start:

```bash
# Check ChromeDriver version
chromedriver --version

# Check Chrome version
google-chrome --version  # Linux
# or
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version  # macOS
```

Versions should match. If not, download matching ChromeDriver from:
https://chromedriver.chromium.org/downloads

### UTF-8 encoding issues

The crawler handles Myanmar Unicode text properly. If you see encoding issues:

```python
# When reading JSON
with open('mawkun_articles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
```

## Advanced Features

### Custom headers

```python
crawler = MawkunCrawler()
crawler.session.headers.update({
    'User-Agent': 'Your Custom User Agent',
    'Accept-Language': 'my,en-US;q=0.9'
})
```

### Filtering articles

```python
# Filter by date, category, etc.
filtered = [a for a in crawler.articles if 'specific-keyword' in a['title']]
```

## License

MIT License - Feel free to use and modify

## Support

For issues or questions, please check:

- Mawkun website: https://mawkun.com/
- BeautifulSoup docs: https://www.crummy.com/software/BeautifulSoup/
- Selenium docs: https://selenium-python.readthedocs.io/
