#!/usr/bin/env python3
"""
Daily Briefing AI Agent
-----------------------
A personal aggregator that collects content from various sources, summarizes it,
and delivers it via email and Amazon Alexa.
"""

import os
import logging
import argparse
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import feedparser
import json
from jinja2 import Template
from transformers import pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("daily_briefing.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuration (ideally moved to a config file or env vars in production)
CONFIG = {
    "arxiv": {
        "url": "http://export.arxiv.org/api/query",
        "params": {
            "search_query": "cat:cs.AI",
            "start": 0,
            "max_results": 5
        }
    },
    "hacker_news": {
        "top_stories_url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "item_url": "https://hacker-news.firebaseio.com/v0/item/{}.json",
        "num_stories": 5
    },
    "rss_feeds": [
        {"name": "Zen Habits", "url": "https://zenhabits.net/feed/"}
        # Add more feeds or newsletters here, e.g. {"name": "Morning Brew", "url": "..."}
    ],
    "summarization": {
        "max_length": 150,
        "min_length": 50
    },
    "email": {
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 587)),
        "username": os.getenv("EMAIL_USERNAME", "your_email@gmail.com"),
        "password": os.getenv("EMAIL_PASSWORD", "your_app_password"),
        "from_addr": os.getenv("FROM_EMAIL", "your_email@gmail.com"),
        "to_addr": os.getenv("TO_EMAIL", "recipient@example.com"),
        "subject": "Your Daily Briefing for {}"
    },
    "alexa": {
        # If you have an API endpoint or want to store in S3, configure here
        "api_endpoint": os.getenv("ALEXA_API_ENDPOINT", "http://localhost:5000/daily-briefing")
    }
}


class DataFetcher:
    """Handles fetching data from various sources."""
    
    def __init__(self, config):
        self.config = config
    
    def fetch_arxiv_papers(self):
        """Fetch AI/ML research papers from arXiv."""
        logger.info("Fetching papers from arXiv...")
        try:
            response = requests.get(self.config["arxiv"]["url"], params=self.config["arxiv"]["params"])
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            papers = []
            
            for entry in feed.entries:
                paper = {
                    "title": entry.title,
                    "url": entry.link,
                    "abstract": entry.summary,
                    "authors": [author.name for author in entry.authors]
                }
                papers.append(paper)
            
            logger.info(f"Successfully retrieved {len(papers)} papers from arXiv.")
            return papers
        
        except Exception as e:
            logger.error(f"Error fetching papers from arXiv: {e}")
            return []
    
    def fetch_hacker_news(self):
        """Fetch top stories from Hacker News."""
        logger.info("Fetching stories from Hacker News...")
        try:
            # Get top story IDs
            response = requests.get(self.config["hacker_news"]["top_stories_url"])
            response.raise_for_status()
            story_ids = response.json()[:self.config["hacker_news"]["num_stories"]]
            
            # Get details for each story
            stories = []
            for story_id in story_ids:
                story_url = self.config["hacker_news"]["item_url"].format(story_id)
                story_response = requests.get(story_url)
                story_response.raise_for_status()
                story_data = story_response.json()
                
                if "url" in story_data:
                    story = {
                        "title": story_data.get("title", ""),
                        "url": story_data.get("url", ""),
                        "score": story_data.get("score", 0),
                        "comments": f"https://news.ycombinator.com/item?id={story_id}"
                    }
                    stories.append(story)
            
            logger.info(f"Successfully retrieved {len(stories)} stories from Hacker News.")
            return stories
        
        except Exception as e:
            logger.error(f"Error fetching stories from Hacker News: {e}")
            return []
    
    def fetch_rss_feeds(self):
        """Fetch articles from configured RSS feeds."""
        logger.info("Fetching articles from RSS feeds...")
        all_articles = []
        
        for feed_config in self.config["rss_feeds"]:
            try:
                feed_name = feed_config["name"]
                feed_url = feed_config["url"]
                
                logger.info(f"Parsing feed: {feed_name} ({feed_url})")
                feed = feedparser.parse(feed_url)
                
                articles = []
                for entry in feed.entries[:3]:  # Limit to 3 articles per feed
                    article = {
                        "feed_name": feed_name,
                        "title": entry.title,
                        "url": entry.link,
                        "summary": entry.get("summary", "")
                    }
                    articles.append(article)
                
                all_articles.extend(articles)
                logger.info(f"Retrieved {len(articles)} articles from {feed_name}.")
                
            except Exception as e:
                logger.error(f"Error fetching RSS feed {feed_config['name']}: {e}")
        
        return all_articles


class ContentProcessor:
    """Processes and summarizes content from various sources."""
    
    def __init__(self, config):
        self.config = config
        # Initialize the summarization pipeline
        try:
            self.summarizer = pipeline(
                "summarization", 
                model="facebook/bart-large-cnn", 
                framework="pt"
            )
            logger.info("Summarization model loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading summarization model: {e}")
            self.summarizer = None
    
    def summarize_text(self, text):
        """Summarize the given text using AI model."""
        if not self.summarizer:
            logger.warning("Summarizer not available. Returning original text.")
            return text
        
        try:
            if len(text.split()) < 40:  # If less than 40 words, don't summarize
                return text
            
            summary = self.summarizer(
                text,
                max_length=self.config["summarization"]["max_length"],
                min_length=self.config["summarization"]["min_length"],
                do_sample=False
            )
            
            return summary[0]['summary_text']
        
        except Exception as e:
            logger.error(f"Error during summarization: {e}")
            return text
    
    def process_arxiv_papers(self, papers):
        """Process and summarize arXiv papers."""
        processed_papers = []
        for paper in papers:
            try:
                summarized_abstract = self.summarize_text(paper["abstract"])
                processed_paper = {
                    "title": paper["title"],
                    "url": paper["url"],
                    "abstract": summarized_abstract,
                    "authors": paper["authors"]
                }
                processed_papers.append(processed_paper)
            except Exception as e:
                logger.error(f"Error processing paper {paper['title']}: {e}")
        return processed_papers
    
    def process_hacker_news(self, stories):
        """Process Hacker News stories (no summarization needed)."""
        return stories
    
    def process_rss_articles(self, articles):
        """Process and summarize RSS feed articles."""
        processed_articles = []
        for article in articles:
            try:
                summarized_content = self.summarize_text(article["summary"])
                processed_article = {
                    "feed_name": article["feed_name"],
                    "title": article["title"],
                    "url": article["url"],
                    "summary": summarized_content
                }
                processed_articles.append(processed_article)
            except Exception as e:
                logger.error(f"Error processing article {article['title']}: {e}")
        return processed_articles


class BriefingFormatter:
    """Formats the processed content into HTML for email and text for Alexa."""
    
    def __init__(self):
        self.html_template = self._load_template()
    
    def _load_template(self):
        template_string = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Your Daily Briefing</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }
                .container { max-width: 800px; margin: 0 auto; }
                h1 { color: #2C3E50; border-bottom: 1px solid #eee; padding-bottom: 10px; }
                h2 { color: #3498DB; margin-top: 30px; }
                .item { margin-bottom: 20px; }
                .item h3 { margin-bottom: 5px; }
                .item p { margin-top: 5px; }
                .item a { color: #2980B9; text-decoration: none; }
                .item a:hover { text-decoration: underline; }
                .meta { color: #7F8C8D; font-size: 0.9em; }
                .section { margin-bottom: 40px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Your Daily Briefing for {{ date }}</h1>
                
                <!-- arXiv Papers Section -->
                <div class="section">
                    <h2>AI/ML Research Papers</h2>
                    {% if papers %}
                        {% for paper in papers %}
                            <div class="item">
                                <h3><a href="{{ paper.url }}">{{ paper.title }}</a></h3>
                                <div class="meta">Authors: {{ paper.authors|join(', ') }}</div>
                                <p>{{ paper.abstract }}</p>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No new research papers today.</p>
                    {% endif %}
                </div>
                
                <!-- Hacker News Section -->
                <div class="section">
                    <h2>Top Tech Stories</h2>
                    {% if stories %}
                        {% for story in stories %}
                            <div class="item">
                                <h3><a href="{{ story.url }}">{{ story.title }}</a></h3>
                                <div class="meta">
                                    Score: {{ story.score }} |
                                    <a href="{{ story.comments }}">Comments</a>
                                </div>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No tech stories available today.</p>
                    {% endif %}
                </div>
                
                <!-- RSS Articles Section -->
                <div class="section">
                    <h2>Articles & Insights</h2>
                    {% if articles %}
                        {% for article in articles %}
                            <div class="item">
                                <h3><a href="{{ article.url }}">{{ article.title }}</a></h3>
                                <div class="meta">Source: {{ article.feed_name }}</div>
                                <p>{{ article.summary }}</p>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No articles available today.</p>
                    {% endif %}
                </div>
                
                <p style="font-size: 0.8em; color: #95A5A6; text-align: center; margin-top: 50px;">
                    This briefing was automatically generated by your Daily Briefing AI Agent.
                </p>
            </div>
        </body>
        </html>
        """
        return Template(template_string)
    
    def format_html_email(self, papers, stories, articles):
        """Format the briefing as HTML for email delivery."""
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        html_content = self.html_template.render(
            date=today,
            papers=papers,
            stories=stories,
            articles=articles
        )
        return html_content
    
    def format_alexa_text(self, papers, stories, articles):
        """Format the briefing as plain text for Alexa speech."""
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        alexa_text = f"Here's your daily briefing for {today}.\n\n"
        
        # Research papers
        alexa_text += "From AI and Machine Learning research:\n"
        if papers:
            for i, paper in enumerate(papers[:3], 1):
                alexa_text += f"{i}. {paper['title']}. "
                first_sentence = paper['abstract'].split('.')[0] + '.'
                alexa_text += f"{first_sentence}\n"
        else:
            alexa_text += "No new research papers today.\n"
        alexa_text += "\n"
        
        # Hacker News
        alexa_text += "Top technology stories today:\n"
        if stories:
            for i, story in enumerate(stories[:3], 1):
                alexa_text += f"{i}. {story['title']}.\n"
        else:
            alexa_text += "No tech stories available today.\n"
        alexa_text += "\n"
        
        # RSS Articles
        alexa_text += "Articles and insights:\n"
        if articles:
            for i, article in enumerate(articles[:3], 1):
                alexa_text += f"{i}. From {article['feed_name']}: {article['title']}.\n"
        else:
            alexa_text += "No articles available today.\n"
        
        alexa_text += "\nThat concludes your daily briefing."
        return alexa_text


class EmailSender:
    """Handles sending the briefing via email."""
    
    def __init__(self, config):
        self.config = config
    
    def send_email(self, html_content):
        """Send the HTML briefing via email."""
        logger.info("Preparing to send email...")
        
        try:
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = self.config["email"]["subject"].format(today)
            msg['From'] = self.config["email"]["from_addr"]
            msg['To'] = self.config["email"]["to_addr"]
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
                server.starttls()
                server.login(self.config["email"]["username"], self.config["email"]["password"])
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {self.config['email']['to_addr']}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False


class AlexaIntegration:
    """Handles integration with Amazon Alexa."""
    
    def __init__(self, config):
        self.config = config
    
    def publish_briefing(self, alexa_text):
        """
        Publish the briefing for Alexa to access. 
        Here, we simply write to a local JSON file (alexa_briefing.json).
        In a real prod setup, you could:
         - Upload to S3 
         - Store in DynamoDB
         - Expose via an API
        """
        logger.info("Publishing briefing for Alexa...")
        
        try:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            alexa_data = {
                "date": today,
                "briefing_text": alexa_text,
                "last_updated": datetime.datetime.now().isoformat()
            }
            
            with open("alexa_briefing.json", "w") as f:
                json.dump(alexa_data, f, indent=2)
            
            logger.info("Briefing data saved to alexa_briefing.json for Alexa.")
            
            # If you'd like to POST this data to an API endpoint:
            # response = requests.post(self.config["alexa"]["api_endpoint"], json=alexa_data)
            # response.raise_for_status()
            
            return True
        
        except Exception as e:
            logger.error(f"Error publishing briefing for Alexa: {e}")
            return False


def main():
    """Main function to run the Daily Briefing AI Agent."""
    parser = argparse.ArgumentParser(description="Daily Briefing AI Agent")
    parser.add_argument("--email-only", action="store_true", help="Only send email, skip Alexa integration")
    parser.add_argument("--alexa-only", action="store_true", help="Only update Alexa, skip email")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (no actual sending)")
    args = parser.parse_args()
    
    logger.info("Starting Daily Briefing AI Agent...")
    
    try:
        # Step 1: Fetch data
        fetcher = DataFetcher(CONFIG)
        papers = fetcher.fetch_arxiv_papers()
        stories = fetcher.fetch_hacker_news()
        articles = fetcher.fetch_rss_feeds()
        
        # Step 2: Process and summarize
        processor = ContentProcessor(CONFIG)
        processed_papers = processor.process_arxiv_papers(papers)
        processed_stories = processor.process_hacker_news(stories)
        processed_articles = processor.process_rss_articles(articles)
        
        # Step 3: Format content
        formatter = BriefingFormatter()
        html_content = formatter.format_html_email(processed_papers, processed_stories, processed_articles)
        alexa_text = formatter.format_alexa_text(processed_papers, processed_stories, processed_articles)
        
        # Step 4: Debug mode: save to local files and exit
        if args.debug:
            with open("debug_email.html", "w") as f:
                f.write(html_content)
            with open("debug_alexa.txt", "w") as f:
                f.write(alexa_text)
            logger.info("Debug files written. Exiting without sending.")
            return
        
        # Step 5: Send Email
        success_email = True
        if not args.alexa_only:
            email_sender = EmailSender(CONFIG)
            success_email = email_sender.send_email(html_content)
        
        # Step 6: Publish for Alexa
        success_alexa = True
        if not args.email_only:
            alexa_integration = AlexaIntegration(CONFIG)
            success_alexa = alexa_integration.publish_briefing(alexa_text)
        
        # Final Status
        if success_email and success_alexa:
            logger.info("Daily briefing successfully delivered!")
        else:
            if not success_email:
                logger.error("Failed to send email briefing.")
            if not success_alexa:
                logger.error("Failed to publish Alexa briefing.")
    
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise
    
    logger.info("Daily Briefing AI Agent completed.")


if __name__ == "__main__":
    main()
