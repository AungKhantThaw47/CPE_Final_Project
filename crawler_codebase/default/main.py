#!/usr/bin/env python3
"""
Mawkun.com News Crawler
Crawls news articles from https://mawkun.com/
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse


class MawkunCrawler:
    """Crawler for mawkun.com Myanmar news website"""
    
    def __init__(self, base_url: str = "https://mawkun.com/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,my;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        self.articles = []
    
    def get_page_content(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch page content with retry mechanism"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"Failed to fetch {url} after {retries} attempts")
                    return None
        return None
    
    def parse_homepage(self) -> List[Dict]:
        """Parse homepage to extract article links"""
        print(f"Fetching homepage: {self.base_url}")
        html = self.get_page_content(self.base_url)
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        article_links = []
        
        # Find all article links
        # Based on the HTML structure, articles are in various sections
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Filter for article URLs (not category or page links)
            if href.startswith('http') and 'mawkun.com' in href and '/category/' not in href:
                # Extract title from link text
                title = link.get_text(strip=True)
                
                # Skip if no title or if it's a navigation link
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
            # Remove script and style tags
            for script in content_div(['script', 'style']):
                script.decompose()
            
            # Get all paragraphs
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
            # Try to get datetime attribute if available
            if time_tag.get('datetime'):
                article_data['published_date'] = time_tag.get('datetime')
        
        # Extract category
        category_tag = soup.find('a', rel='category tag') or soup.find('span', class_='cat-links')
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
                        'url': urljoin(url, img_url),
                        'alt': img.get('alt', '')
                    })
        
        return article_data
    
    def crawl_category(self, category_url: str, max_pages: int = 5) -> List[Dict]:
        """Crawl articles from a specific category"""
        print(f"Crawling category: {category_url}")
        articles = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{category_url}page/{page}/" if page > 1 else category_url
            
            html = self.get_page_content(page_url)
            if not html:
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            article_links = []
            
            # Find article links on category page
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http') and 'mawkun.com' in href and '/category/' not in href:
                    title = link.get_text(strip=True)
                    if title and len(title) > 10:
                        article_links.append({
                            'url': href,
                            'title': title
                        })
            
            if not article_links:
                print(f"No more articles found on page {page}")
                break
            
            # Parse each article
            for article_info in article_links:
                article = self.parse_article(article_info['url'])
                if article:
                    articles.append(article)
                time.sleep(1)  # Be polite to the server
        
        return articles
    
    def crawl_latest_news(self, max_articles: int = 20) -> List[Dict]:
        """Crawl latest news articles from homepage"""
        print(f"Crawling latest {max_articles} articles...")
        
        article_links = self.parse_homepage()
        
        # Limit to max_articles
        article_links = article_links[:max_articles]
        
        articles = []
        for article_info in article_links:
            article = self.parse_article(article_info['url'])
            if article:
                articles.append(article)
                self.articles.append(article)
            time.sleep(1)  # Be polite to the server
        
        return articles
    
    def save_to_json(self, filename: str = 'mawkun_articles.json'):
        """Save crawled articles to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.articles, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(self.articles)} articles to {filename}")
    
    def save_to_csv(self, filename: str = 'mawkun_articles.csv'):
        """Save crawled articles to CSV file"""
        import csv
        
        if not self.articles:
            print("No articles to save")
            return
        
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['url', 'title', 'content', 'author', 'published_date', 'category', 'tags', 'crawled_at']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for article in self.articles:
                row = article.copy()
                row['tags'] = ', '.join(article.get('tags', []))
                row.pop('images', None)  # Remove images for CSV
                writer.writerow(row)
        
        print(f"Saved {len(self.articles)} articles to {filename}")


def main():
    """Main function to run the crawler"""
    crawler = MawkunCrawler()
    
    # Example 1: Crawl latest news from homepage
    print("=" * 80)
    print("Crawling latest news from homepage...")
    print("=" * 80)
    articles = crawler.crawl_latest_news(max_articles=10)
    
    # Display results
    print(f"\n{'=' * 80}")
    print(f"Crawled {len(articles)} articles")
    print("=" * 80)
    
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   URL: {article['url']}")
        print(f"   Category: {article['category']}")
        print(f"   Published: {article['published_date']}")
        print(f"   Content preview: {article['content'][:200]}...")
    
    # Save to files
    crawler.save_to_json('mawkun_articles.json')
    crawler.save_to_csv('mawkun_articles.csv')
    
    # Example 2: Crawl specific category
    # Uncomment to crawl a specific category:
    # news_articles = crawler.crawl_category('https://mawkun.com/category/သတင်း/', max_pages=2)
    # crawler.save_to_json('mawkun_news_category.json')


if __name__ == "__main__":
    main()
