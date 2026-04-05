from fastapi import FastAPI, Query, Body, HTTPException
from typing import List, Optional
import uvicorn
import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Dict, List, Optional
from datetime import datetime

app = FastAPI(title="AlphaStreet Scraper API", description="Extract complete earnings call transcripts with all spoken content")

class AlphaStreetScraper:
    """Scraper for AlphaStreet earnings call transcripts"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = "https://news.alphastreet.com"
    
    def find_transcript_url(self, ticker: str, year: int, quarter: str) -> Optional[str]:
        """Find the transcript URL by searching the transcripts page"""
        quarter_clean = quarter.upper()
        if not quarter_clean.startswith('Q'):
            quarter_clean = f"Q{quarter_clean}"
        
        quarter_param = f"{quarter_clean}-{year}"
        search_url = f"{self.base_url}/transcripts/?ticker={ticker.lower()}&quarter={quarter_param}"
        
        try:
            response = requests.get(search_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all transcript rows
            transcript_rows = soup.find_all('article', class_='transcript-row')
            
            for row in transcript_rows:
                ticker_elem = row.find('a', class_='ticker-link')
                quarter_elem = row.find('span', class_='quarter-badge')
                
                if ticker_elem and quarter_elem:
                    row_ticker = ticker_elem.get_text(strip=True).replace('$', '').lower()
                    row_quarter = quarter_elem.get_text(strip=True)
                    
                    if row_ticker == ticker.lower() and row_quarter == f"{quarter_clean} {year}":
                        title_link = row.find('h3', class_='transcript-title')
                        if title_link:
                            link = title_link.find('a')
                            if link and link.get('href'):
                                return link.get('href')
                        
                        read_btn = row.find('a', class_='read-transcript-btn')
                        if read_btn and read_btn.get('href'):
                            return read_btn.get('href')
            
            return None
            
        except Exception as e:
            print(f"Error finding transcript URL for {ticker} {quarter_clean} {year}: {e}")
            return None
    
    def parse_transcript(self, html_content: str, url: str = None) -> Dict:
        """Parse a single transcript HTML and extract all data"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'url': url,
            'title': None,
            'company': None,
            'ticker': None,
            'quarter': None,
            'year': None,
            'date': None,
            'transcript_type': None,
            'participants': {
                'corporate': [],
                'analysts': []
            },
            'presentation': [],
            'qa_session': [],
            'full_transcript': []
        }
        
        # Extract title
        title_elem = soup.find('h1', class_='st-title')
        if title_elem:
            result['title'] = title_elem.get_text(strip=True)
            self._parse_title_info(result['title'], result)
        
        # Extract ticker
        ticker_link = soup.find('a', class_='st-ticker-link')
        if ticker_link:
            result['ticker'] = ticker_link.get_text(strip=True).replace('$', '')
        
        # Extract date
        date_span = soup.find('span', class_='st-date')
        if date_span:
            date_text = date_span.get_text(strip=True)
            result['date'] = self._parse_date(date_text)
        
        # Extract transcript type
        badge = soup.find('span', class_='st-type-badge')
        if badge:
            result['transcript_type'] = badge.get_text(strip=True)
        
        # Extract participants
        self._extract_participants(soup, result)
        
        # Extract transcript body with actual content
        transcript_body = soup.find('div', class_='st-transcript-body')
        if transcript_body:
            result['full_transcript'], result['presentation'], result['qa_session'] = self._extract_full_transcript(transcript_body)
        
        return result
    
    def _parse_title_info(self, title: str, result: Dict):
        """Extract company, quarter, year from title"""
        patterns = [
            r'^(.*?)\s*\(([A-Z]+)\)\s*Q([1-4])\s*(\d{4})',
            r'^(.*?)\s*Q([1-4])\s*(\d{4})',
            r'^(.*?)\s*-\s*Q([1-4])\s*(\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                groups = match.groups()
                result['company'] = groups[0].strip()
                if len(groups) >= 4:
                    result['ticker'] = groups[1]
                    result['quarter'] = f"Q{groups[2]}"
                    result['year'] = groups[3]
                elif len(groups) >= 3:
                    result['quarter'] = f"Q{groups[1]}"
                    result['year'] = groups[2]
                break
    
    def _parse_date(self, date_text: str) -> str:
        """Parse date string to ISO format"""
        try:
            date_text = date_text.replace('Jan.', 'January').replace('Feb.', 'February')
            date_text = date_text.replace('Mar.', 'March').replace('Apr.', 'April')
            date_text = date_text.replace('Jun.', 'June').replace('Jul.', 'July')
            date_text = date_text.replace('Aug.', 'August').replace('Sep.', 'September')
            date_text = date_text.replace('Oct.', 'October').replace('Nov.', 'November')
            date_text = date_text.replace('Dec.', 'December')
            dt = datetime.strptime(date_text, '%B %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except:
            return date_text
    
    def _extract_participants(self, soup: BeautifulSoup, result: Dict):
        """Extract corporate participants and analysts"""
        participants_section = soup.find('section', id='participants')
        if not participants_section:
            return
        
        # Extract corporate participants
        corp_box = participants_section.find('div', class_='participant-box')
        if corp_box and 'participant-analysts' not in corp_box.get('class', []):
            for p in corp_box.find_all('p'):
                text = p.get_text(strip=True)
                if '—' in text:
                    name, role = text.split('—', 1)
                    result['participants']['corporate'].append({
                        'name': name.strip(),
                        'role': role.strip().replace('_', '').strip()
                    })
        
        # Extract analysts
        analysts_box = participants_section.find('div', class_='participant-analysts')
        if analysts_box:
            names_grid = analysts_box.find('div', class_='participant-names-grid')
            if names_grid:
                search_area = names_grid
            else:
                search_area = analysts_box
                
            for p in search_area.find_all('p'):
                text = p.get_text(strip=True)
                if '—' in text:
                    name, firm = text.split('—', 1)
                    result['participants']['analysts'].append({
                        'name': name.strip(),
                        'firm': firm.strip()
                    })
    
    def _extract_full_transcript(self, transcript_body):
        """Extract complete transcript by traversing DOM in order"""
        full_transcript = []
        presentation = []
        qa_session = []
        
        current_section = None
        current_speaker = None
        current_title = None
        current_text = []
        
        # Get all direct children of transcript_body
        for elem in transcript_body.children:
            if elem.name is None:
                continue
            
            # Check for section headings
            if elem.name == 'h2':
                # Save previous speech if any
                if current_speaker and current_text:
                    speech_data = {
                        'speaker': current_speaker,
                        'title': current_title,
                        'text': ' '.join(current_text)
                    }
                    full_transcript.append(speech_data)
                    if current_section == 'presentation':
                        presentation.append(speech_data)
                    elif current_section == 'qa':
                        qa_session.append(speech_data)
                    current_text = []
                
                # Update current section
                heading_text = elem.get_text(strip=True).lower()
                if 'presentation' in heading_text:
                    current_section = 'presentation'
                elif 'question' in heading_text or 'q&a' in heading_text:
                    current_section = 'qa'
                
                full_transcript.append({
                    'type': 'section',
                    'heading': elem.get_text(strip=True)
                })
                continue
            
            # Skip ad divs
            if elem.get('class') and 'st-inline-ad' in ' '.join(elem.get('class', [])):
                continue
            
            # Handle paragraphs
            if elem.name == 'p':
                text = elem.get_text(strip=True)
                if not text or text.startswith('Advertisement'):
                    continue
                
                # Check for speaker label
                strong = elem.find('strong')
                if strong:
                    # Save previous speech
                    if current_speaker and current_text:
                        speech_data = {
                            'speaker': current_speaker,
                            'title': current_title,
                            'text': ' '.join(current_text)
                        }
                        full_transcript.append(speech_data)
                        if current_section == 'presentation':
                            presentation.append(speech_data)
                        elif current_section == 'qa':
                            qa_session.append(speech_data)
                        current_text = []
                    
                    # Extract speaker info
                    speaker_text = strong.get_text(strip=True)
                    
                    # Check for em tag for title
                    em = elem.find('em')
                    span = elem.find('span', class_='speaker-designation')
                    
                    if '—' in speaker_text:
                        parts = speaker_text.split('—', 1)
                        current_speaker = parts[0].strip()
                        current_title = parts[1].strip() if len(parts) > 1 else None
                    elif em:
                        current_speaker = speaker_text
                        current_title = em.get_text(strip=True)
                    elif span:
                        current_speaker = speaker_text
                        current_title = span.get_text(strip=True)
                    else:
                        current_speaker = speaker_text
                        current_title = None
                    
                    # Get remaining text after speaker label
                    remaining = text.replace(strong.get_text(), '')
                    if em:
                        remaining = remaining.replace(em.get_text(), '')
                    if span:
                        remaining = remaining.replace(span.get_text(), '')
                    remaining = re.sub(r'^[—\s]+', '', remaining).strip()
                    
                    if remaining:
                        current_text.append(remaining)
                
                elif current_speaker:
                    # Continuation of current speaker's speech
                    current_text.append(text)
                else:
                    # Regular paragraph (like opening line)
                    full_transcript.append({
                        'type': 'paragraph',
                        'text': text
                    })
        
        # Save final speech
        if current_speaker and current_text:
            speech_data = {
                'speaker': current_speaker,
                'title': current_title,
                'text': ' '.join(current_text)
            }
            full_transcript.append(speech_data)
            if current_section == 'presentation':
                presentation.append(speech_data)
            elif current_section == 'qa':
                qa_session.append(speech_data)
        
        return full_transcript, presentation, qa_session
    
    def scrape_from_url(self, url: str) -> Dict:
        """Scrape transcript directly from URL"""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return self.parse_transcript(response.text, url)
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_by_ticker_quarter(self, ticker: str, year: int, quarter: str) -> Dict:
        """Find and scrape transcript by ticker, year, and quarter"""
        transcript_url = self.find_transcript_url(ticker, year, quarter)
        
        if not transcript_url:
            return {
                'success': False,
                'error': f"No transcript found for {ticker} {quarter} {year}",
                'ticker': ticker,
                'quarter': quarter,
                'year': year
            }
        
        result = self.scrape_from_url(transcript_url)
        
        if result:
            return {
                'success': True,
                'url': transcript_url,
                'data': result
            }
        else:
            return {
                'success': False,
                'error': f"Failed to scrape transcript from {transcript_url}",
                'ticker': ticker,
                'quarter': quarter,
                'year': year
            }


scraper = AlphaStreetScraper()


