import logging
import re
import requests
import os
from bs4 import BeautifulSoup
import html
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get('BOT_TOKEN', '7799784006:AAE8qfnrz35poUJilU0_0gNONcylwqsKe7c')
PRIMARY_CHANNEL_ID = os.environ.get('PRIMARY_CHANNEL_ID', '-1001805753779')
SECONDARY_CHANNEL_ID = os.environ.get('SECONDARY_CHANNEL_ID', '-1002505814673')
KEYWORDS = ['infortunio', 'infortuni', 'assenza', 'assenze', 'rottura', 'acquisto', 'cessione', 'rinforzo', 'problemi', 'problemi muscolari', 'acchiacchi', 'acciaccati', 'fermo ai box', 'fermo a causa', 
 'assenti', 'assente']

# Headers for web requests to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def extract_urls(text):
    """Extract URLs from text."""
    url_pattern = re.compile(r'https?://\S+')
    return url_pattern.findall(text)

def resolve_shortened_url(url):
    """Resolve a shortened URL to its full form."""
    try:
        # Make a HEAD request to get the redirect location
        response = requests.head(url, allow_redirects=False, timeout=10)
        
        # If it's a redirect (status codes 300-399)
        if 300 <= response.status_code < 400 and 'location' in response.headers:
            return response.headers['location']
        return url
    except requests.RequestException as e:
        logger.error(f"Error resolving shortened URL: {e}")
        return url

def fetch_article_content(url):
    """Fetch the content of an article from a URL."""
    try:
        # Set a higher timeout and explicitly allow redirects
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Log the final URL after redirects
        logger.info(f"Original URL: {url} redirected to: {response.url}")
        
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching article: {e}")
        return None

def parse_article(html_content, url):
    """Parse HTML to extract article title and main text."""
    if not html_content:
        return None, None
    
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract title (try different common patterns)
    title = None
    title_candidates = [
        soup.find('h1'),
        soup.find('meta', property='og:title'),
        soup.find('meta', property='twitter:title'),
        soup.find('title')
    ]
    
    for candidate in title_candidates:
        if candidate:
            if candidate.name == 'meta':
                title = candidate.get('content')
            else:
                title = candidate.text
            break
    
    if not title:
        title = "Article from " + url
    
    # Extract main content (try different common patterns)
    article_text = ""
    
    # Try to find article content in common containers
    article_container = (
        soup.find('article') or 
        soup.find('div', class_=re.compile(r'article|content|post|story', re.I)) or
        soup.find('main')
    )
    
    if article_container:
        # Get all paragraphs from the article container
        paragraphs = article_container.find_all('p')
        article_text = ' '.join([p.text.strip() for p in paragraphs])
    else:
        # Fallback: get all paragraphs from the page
        paragraphs = soup.find_all('p')
        article_text = ' '.join([p.text.strip() for p in paragraphs])
    
    return title.strip(), article_text.strip()

def find_keywords_with_context(text, keywords):
    """Find keywords in text and return them with their context sentences."""
    if not text:
        return []
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    results = []
    for sentence in sentences:
        for keyword in keywords:
            # Case-insensitive search
            if re.search(r'\b' + re.escape(keyword) + r'\b', sentence, re.IGNORECASE):
                # Bold the keyword in the sentence
                highlighted_sentence = re.sub(
                    r'\b(' + re.escape(keyword) + r')\b', 
                    r'**\1**', 
                    sentence, 
                    flags=re.IGNORECASE
                )
                results.append((keyword, highlighted_sentence))
    
    return results

def format_notification(title, url, keyword_contexts):
    """Format the notification message."""
    if not keyword_contexts:
        return None
    
    # Extract unique keywords found
    keywords_found = list(set([kw.lower() for kw, _ in keyword_contexts]))
    
    # Format the message
    message = f"⚠️ {title} ▶️"
    message += f'<a href="{url}"> Apri articolo</a>\n\n'
    message += f"ℹ️: {', '.join(keywords_found)}\n\n"
    message += "Context:\n"
    
    # Add context for each keyword
    for _, context in keyword_contexts:
        # Replace **keyword** with <b>keyword</b> for HTML formatting
        html_context = context.replace('**', '<b>', 1).replace('**', '</b>', 1)
        message += f"- {html_context}\n"
    
    return message

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle new posts in the primary channel."""
    # Check if update has channel_post attribute
    if not hasattr(update, 'channel_post') or update.channel_post is None:
        return
        
    # Check if the message is from the primary channel
    if str(update.channel_post.chat_id) != str(PRIMARY_CHANNEL_ID):
        return
    
    message_text = update.channel_post.text or update.channel_post.caption or ""
    
    # Extract URLs from the message
    urls = extract_urls(message_text)
    if not urls:
        return
    
    # Process the first URL found
    url = urls[0]
    
    # Resolve the URL if it's shortened
    if "ift.tt" in url:
        resolved_url = resolve_shortened_url(url)
        logger.info(f"Resolved shortened URL: {url} -> {resolved_url}")
        url = resolved_url
    
    # Fetch and parse the article
    html_content = fetch_article_content(url)
    title, article_text = parse_article(html_content, url)
    
    if not article_text:
        logger.warning(f"Could not extract article text from {url}")
        return
    
    # Find keywords with context
    keyword_contexts = find_keywords_with_context(article_text, KEYWORDS)
    
    if keyword_contexts:
        # Format and send notification
        notification = format_notification(title, url, keyword_contexts)
        if notification:
            try:
                await context.bot.send_message(
                    chat_id=SECONDARY_CHANNEL_ID,
                    text=notification,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                logger.info(f"Notification sent for article: {title}")
            except Exception as e:
                logger.error(f"Error sending notification: {e}")

if __name__ == '__main__':
    # Create the application
    app = Application.builder().token(TOKEN).build()
    
    # Add handler for channel posts
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    
    # Log startup
    logger.info("Bot started. Listening for channel posts...")
    
    # Start the bot with simplified polling approach
    app.run_polling(allowed_updates=["channel_post"], drop_pending_updates=True, close_loop=False)

