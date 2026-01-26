#!/usr/bin/env python3
"""
Mawkun.com News Crawler using Selenium (for JavaScript-heavy pages)
This version uses Selenium WebDriver for pages that require JavaScript rendering
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from typing import List, Dict, Optional


class MawkunSeleniumCrawler:
    """Selenium-based crawler for mawkun.com"""
    
    def __init__(self, base_url: str = "https://mawkun.com/", headless: bool = True):
        self.base_url = base_url
        self.articles = []
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize driver
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            print(f"Error initializing Chrome driver: {e}")
            print("Please make sure Chrome and ChromeDriver are installed.")
            print("Install with: brew install chromedriver (macOS)")
            raise
    
    def __del__(self):
        """Cleanup driver on deletion"""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def get_page_content(self, url: str) -> Optional[str]:
        """Fetch page content using Selenium"""
        try:
            print(f"Loading: {url}")
            self.driver.get(url)
            
            # Wait for page to load (adjust selector as needed)
            time.sleep(2)  # Wait for JavaScript to execute
            
            return self.driver.page_source
        except Exception as e:
            print(f"Error loading {url}: {e}")
            return None
    
    def scroll_to_load_more(self, scroll_pause: float = 2.0, max_scrolls: int = 5):
        """Scroll page to load more content (for infinite scroll)"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        
        while scrolls < max_scrolls:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            
            # Calculate new height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
            
            last_height = new_height
            scrolls += 1
            print(f"Scrolled {scrolls} times...")
    
    def parse_homepage(self, scroll: bool = False) -> List[Dict]:
        """Parse homepage to extract article links"""
        print(f"Fetching homepage: {self.base_url}")
        html = self.get_page_content(self.base_url)
        
        if scroll:
            self.scroll_to_load_more()
            html = self.driver.page_source
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        article_links = []
        
        # Find all article links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Filter for article URLs
            if href.startswith('http') and 'mawkun.com' in href and '/category/' not in href:
                title = link.get_text(strip=True)
                
                if title and len(title) > 10:
                    article_links.append({
                        'url': href,
                        'title': title
                    })
        
        # Remove duplicates
        seen = set()
        unique_articles = []
        for article in article_links:
            if article['url'] not in seen:
                seen.add(article['url'])
                unique_articles.append(article)
        
        print(f"Found {len(unique_articles)} unique articles")
        return unique_articles
    
    def parse_article(self, url: str) -> Optional[Dict]:
        """Parse individual article page"""
        print(f"Parsing article: {url}")
        html = self.get_page_content(url)
        
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        article_data = {
            'url': url,
            'title': '',
            'content': '',
            'author': '',
            'published_date': '',
            'category': '',
            'tags': [],
            'images': [],
            'crawled_at': datetime.now().isoformat()
        }
        
        # Extract title
        title_tag = soup.find('h1', class_='entry-title') or soup.find('h1')
        if title_tag:
            article_data['title'] = title_tag.get_text(strip=True)
        
        # Extract content
        content_div = soup.find('div', class_='entry-content') or soup.find('article')
        if content_div:
            for script in content_div(['script', 'style']):
                script.decompose()
            
            paragraphs = content_div.find_all('p')
            article_data['content'] = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # Extract author
        author_tag = soup.find('span', class_='author') or soup.find('a', rel='author')
        if author_tag:
            article_data['author'] = author_tag.get_text(strip=True)
        
        # Extract published date
        time_tag = soup.find('time') or soup.find('span', class_='posted-on')
        if time_tag:
            article_data['published_date'] = time_tag.get_text(strip=True)
            if time_tag.get('datetime'):
                article_data['published_date'] = time_tag.get('datetime')
        
        # Extract category
        category_tag = soup.find('a', rel='category tag')
        if category_tag:
            article_data['category'] = category_tag.get_text(strip=True)
        
        # Extract tags
        tag_links = soup.find_all('a', rel='tag')
        article_data['tags'] = [tag.get_text(strip=True) for tag in tag_links]
        
        # Extract images
        if content_div:
            images = content_div.find_all('img')
            for img in images:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    article_data['images'].append({
                        'url': img_url,
                        'alt': img.get('alt', '')
                    })
        
        return article_data
    
    def crawl_latest_news(self, max_articles: int = 20, scroll: bool = False) -> List[Dict]:
        """Crawl latest news articles from homepage"""
        print(f"Crawling latest {max_articles} articles...")
        
        article_links = self.parse_homepage(scroll=scroll)
        article_links = article_links[:max_articles]
        
        articles = []
        for article_info in article_links:
            article = self.parse_article(article_info['url'])
            if article:
                articles.append(article)
                self.articles.append(article)
            time.sleep(1)
        
        return articles
    
    def save_to_json(self, filename: str = 'mawkun_selenium_articles.json'):
        """Save crawled articles to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.articles, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(self.articles)} articles to {filename}")


def main():
    """Main function"""
    try:
        crawler = MawkunSeleniumCrawler(headless=True)
        
        print("=" * 80)
        print("Crawling with Selenium (JavaScript support)...")
        print("=" * 80)
        
        articles = crawler.crawl_latest_news(max_articles=10, scroll=False)
        
        print(f"\n{'=' * 80}")
        print(f"Crawled {len(articles)} articles")
        print("=" * 80)
        
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   URL: {article['url']}")
            print(f"   Published: {article['published_date']}")
        
        crawler.save_to_json('mawkun_selenium_articles.json')
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'crawler' in locals():
            del crawler


if __name__ == "__main__":
    main()
