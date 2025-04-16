import logging
import re
import requests
import os
from bs4 import BeautifulSoup
import html
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import error as tg_error

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get('BOT_TOKEN', '7799784006:AAE8qfnrz35poUJilU0_0gNONcylwqsKe7c')
PRIMARY_CHANNEL_ID = os.environ.get('PRIMARY_CHANNEL_ID', '-1001805753779')
SECONDARY_CHANNEL_ID = os.environ.get('SECONDARY_CHANNEL_ID', '-1002505814673')
KEYWORDS = [
    # Termini Chiave per Assenza/Infortunio
    'assente', 'assenti',
    'assenza', 'assenze',
    'infortunio', 'infortuni',
    'indisponibile', 'indisponibili',
    'non disponibile', 'non disponibili',
    'fuori',             # Molto comune e diretto (es. "Rossi fuori per la caviglia")
    'out',              # Equivalente inglese, molto usato
    'ko',               # Gergo comune per indicare fuori gioco
    
    # Problemi Fisici Specifici (che spesso implicano assenza)
    'lesione', 'lesioni',
    'distorsione', 'distorsioni',
    'stiramento', 'stiramenti',
    'contrattura', 'contratture',
    'problemi muscolari', # Mantenuto perché specifico
    'rottura',
    'trauma', 'traumi',
    'acciacco', 'acchiacchi', 
    'acciaccato', 'acciaccati',
    'fastidio', # Mantenuto con cautela, spesso indica dubbio/assenza

    # Stato di Fermo / Stop
    'fermo',            # Più generico ma diretto (es. "fermo per un problema al...")
    'stop',             # Molto comune (es. "stop di due settimane")
    'ai box',           # Comune nel gergo (include "fermo ai box")

    # Stato di Dubbio (Importante per previsioni)
    'in dubbio',
    'in forte dubbio',
    'a rischio',        # Spesso usato per "a rischio forfait" o "a rischio per la partita"
    'non al meglio',    # Implica possibile assenza o prestazione limitata

    # Verbi Indicanti Assenza (Potenziati)
    'salta', 'salterà', 'saltare',         # Es. "salta la partita", "costretto a saltare"
    'manca', 'mancherà', 'mancare',       # Es. "mancherà alla squadra"
    'fermarsi', 'si ferma', 'si è fermato', # Spesso usato per infortuni in allenamento/partita
    'non gioca', 'non giocherà',          # Diretto e inequivocabile
    'non sarà', 'non ci sarà',          # Es. "non sarà della partita" / "non ci sarà contro X"
    'resta fuori', 'restare fuori',
    'dare forfait', 'forfait',          # Termine specifico per rinuncia/assenza

    # Altre Cause Dirette di Assenza
    'squalifica', 'squalificato',
    'influenza', 'influenzato', 'febbre',
    'malattia',
    # 'motivi personali' / 'ragioni familiari' (Valuta tu se includerli, sono assenze ma non fisiche)
    # 'scelta tecnica' / 'non convocato' (Idem, indicano assenza ma non per problemi fisici)

    # Termini Inglesi Comuni (Oltre a 'out')
    'sidelined',        # Indica messo da parte, spesso per infortunio
    'day-to-day',       # Indica valutazione quotidiana -> possibile assenza
    'injury report',    # Nome del bollettino infortuni

    # Termini legati a interventi/diagnosi che *implicano* assenza
    'operato', 'operazione', 'intervento', # Implicano un'assenza significativa
    'esami', 'risonanza', 'ecografia',    # Spesso preludono a notizie su stop/tempi di recupero

    ### ESPAÑOL ###

     # 1. Ausencia/Indisponibilidad General
    'ausente', 'ausentes', 'ausencia', 'ausencias', # Absent / Absence
    'lesión', 'lesiones', 'lesionado', 'lesionados', # Injury / Injured
    'indisponible', 'indisponibles', 'no disponible', 'no disponibles', # Unavailable
    'fuera', 'baja', 'KO', # Out / Unavailable / KO

    # 2. Verbos Indicando Ausencia/Stop
    'se pierde', 'se perderá', # Misses / Will miss (the game)
    'falta', 'faltará', # Is missing / Will miss
    'cae', 'se cae', 'caído', # Falls / Is dropped (from list)
    'no juega', 'no jugará', # Doesn't play / Won't play
    'no está', 'no estará', # Isn't / Won't be (available)
    'baja para', # Out for (specific game/time)
    'no convocado', 'fuera de la convocatoria', # Not selected / Out of the squad list

    # 3. Estado de Paro / Stop
    'parado', # Stopped / Sidelined
    'stop', # Stop (less common than IT/EN, but used)
    'en el dique seco', # Sidelined (idiom: in dry dock)

    # 4. Problemas Físicos Específicos
    'lesión', # Lesion / Injury
    'distensión', # Strain
    'esguince', # Sprain
    'contractura', # Contracture
    'problemas musculares', 'sobrecarga', # Muscle problems / Overload
    'molestias', # Discomfort / Twinge (very common)
    'rotura', # Tear / Rupture
    'trauma', 'golpe', # Trauma / Knock
    'dolencia', # Ailment

    # 5. Estado de Duda / Riesgo Ausencia
    'duda', 'en duda', 'seria duda', # Doubt / Doubtful / Serious doubt
    'riesgo', # At risk
    'pendiente de evolución', 'a evaluar', # Pending evaluation / To be assessed
    'no al cien por cien', 'tocado', # Not 100% / Carrying a knock
    'entre algodones', # Handled with care (idiom)

    # 6. Otras Causas Específicas de Ausencia
    'sanción', 'sancionado', 'sancionados', # Suspension / Suspended
    'gripe', 'proceso gripal', 'fiebre', # Flu / Flu process / Fever
    'enfermedad', # Illness

    # 7. Términos Médicos/Diagnósticos
    'operado', 'operación', 'intervención', 'quirófano', # Surgery / Operation / Operating room
    'pruebas', 'resonancia', 'ecografía', 'chequeos', # Tests / Scans / Checks
    'tratamiento', 'rehabilitación', 'recuperación', # Treatment / Rehab / Recovery

    # 8. Reportes
    'parte médico', # Medical report

    # 9. Llegadas / Fichajes (Signings)
    'fichaje', 'fichajes', 'nuevo fichaje', # Signing / New signing
    'incorporación', 'refuerzo', # Addition / Reinforcement
    'llegada', 'llegadas', # Arrival / Arrivals
    'contratado', 'fichado', # Signed / Hired
    'oficial', # Official (signing)
    'firma', 'firmado', 'ha firmado', # Signs / Signed
    'nuevo jugador', # New player
    'se une a', 'llega desde', # Joins / Arrives from
    'vestirá la camiseta', # Will wear the shirt
    'presentado', 'presentación', # Presented / Presentation

    # 10. Debuts / Estrenos
    'debut', 'estreno', # Debut / Premiere
    'debuta', 'debutará', 'se estrena', 'se estrenará', # Debuts / Will debut
    'primera vez', 'primera aparición', # First time / First appearance
    'listo para debutar', 'posible debut', # Ready for debut / Possible debut
    'primera convocatoria', # First call-up

    ### NEDERLANDS ###

     # 1. Algemene Afwezigheid/Onbeschikbaarheid
    'afwezig', 'afwezigheid', # Absent / Absence
    'blessure', 'blessures', 'geblesseerd', # Injury / Injuries / Injured
    'niet beschikbaar', 'onbeschikbaar', # Unavailable
    'niet inzetbaar', # Not deployable/available
    'out', 'uit de roulatie', # Out / Out of action

    # 2. Werkwoorden die Afwezigheid/Stop aangeven
    'mist', 'zal missen', # Misses / Will miss
    'ontbreekt', 'ontbreken', # Is missing / Are missing
    'speelt niet', 'zal niet spelen', # Doesn't play / Won't play
    'is er niet bij', # Isn't there / Isn't available
    'niet geselecteerd', 'buiten de selectie', # Not selected / Outside the squad

    # 3. Status van Stilstand / Stop
    'staat aan de kant', 'aan de kant', # Is sidelined / Sidelined
    'stop', 'sidelined', # Stop / Sidelined (English terms used)

    # 4. Specifieke Fysieke Problemen
    'blessure', # Injury
    'verrekking', # Strain
    'verstuiking', 'verzwikking', # Sprain
    'spierprobleem', 'spierklachten', # Muscle problem / Muscle complaints
    'overbelasting', # Overload / Strain
    'pijntje', 'klachten', # Minor ache / Complaints, symptoms
    'scheur', 'scheurtje', # Tear / Small tear
    'trauma', 'tik', 'klap', # Trauma / Knock
    'kwetsuur', # Injury (slightly more formal)

    # 5. Status van Twijfel / Risico Afwezigheid
    'twijfelgeval', 'onzeker', # Doubtful case / Uncertain
    'vraagteken', # Question mark
    'niet fit', 'niet geheel fit', # Not fit / Not fully fit
    'aangeslagen', # Affected / Slightly injured

    # 6. Andere Specifieke Oorzaken van Afwezigheid
    'schorsing', 'geschorst', # Suspension / Suspended
    'griep', 'koorts', # Flu / Fever
    'ziekte', 'ziek', # Illness / Sick

    # 7. Medische/Diagnostische Termen
    'geopereerd', 'operatie', 'ingreep', # Operated / Operation / Procedure
    'onderzoek', 'scan', 'echo', 'controle', # Examination / Scan / Ultrasound / Check-up
    'behandeling', 'revalidatie', 'herstel', # Treatment / Rehab / Recovery

    # 8. Rapportage
    'blessure-update', # Injury update

    # 9. Aankomsten / Aanwinsten (Signings)
    'aanwinst', 'aanwinsten', 'nieuwe aanwinst', # Signing / New signing
    'transfer', 'overstap', # Transfer / Switch
    'komst', # Arrival
    'gecontracteerd', 'vastgelegd', # Contracted / Secured
    'officieel', 'rond', # Official / Done deal
    'tekent', 'getekend', 'handtekening', # Signs / Signed / Signature
    'nieuwe speler', # New player
    'komt over van', # Comes over from
    'gaat spelen voor', # Will play for
    'gepresenteerd', 'presentatie', # Presented / Presentation

    # 10. Debuten / Eerste Optredens
    'debuut', # Debut
    'debuteert', 'zal debuteren', 'maakt zijn debuut', # Debuts / Will debut / Makes his debut
    'eerste keer', 'eerste wedstrijd', # First time / First match
    'klaar voor debuut', 'mogelijk debuut', # Ready for debut / Possible debut
    'eerste selectie', # First squad selection
    
]

# Headers for web requests to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    # Updated Accept-Language: Added Spanish (es) and Dutch (nl)
    # Preference order: Italian > Spanish > Dutch > English
    'Accept-Language': 'it-IT,it;q=0.9,es;q=0.8,nl;q=0.7,en-US;q=0.6,en;q=0.5',
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")
    if isinstance(context.error, tg_error.Conflict):
        logger.info("Webhook conflict detected, attempting to delete webhook again...")
        try:
            await context.application.bot.delete_webhook()
            logger.info("Webhook deleted successfully from error handler")
        except Exception as e:
            logger.error(f"Failed to delete webhook from error handler: {e}")
            
async def main():
    # Create the application
    app = Application.builder().token(TOKEN).build()
    
    # Delete any existing webhook before starting with error handling
    try:
        logger.info("Attempting to delete webhook...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Successfully deleted webhook")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        # Wait a moment and try again
        await asyncio.sleep(2)
        try:
            await app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Successfully deleted webhook on second attempt")
        except Exception as e2:
            logger.error(f"Failed to delete webhook on second attempt: {e2}")
    
    # Add handler for channel posts
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Log startup
    logger.info("Bot started. Listening for channel posts...")
    
    # Start the bot with polling
    await app.run_polling(allowed_updates=["channel_post"], drop_pending_updates=True)

if __name__ == '__main__':
    import asyncio
    import nest_asyncio
    
    # Apply nest_asyncio patch to allow nested event loops
    nest_asyncio.apply()
    
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "event loop is already running" in str(e):
            logger.error("Event loop error. Trying alternative approach.")
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise
