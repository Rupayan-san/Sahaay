## Sahaay — AI Community Coordination Platform

### Prerequisites (Install Once)
- Python 3.11+: https://python.org
- Node.js 18+: https://nodejs.org
- MongoDB Community: https://www.mongodb.com/try/download/community
- Tesseract OCR:
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki
  - Mac: brew install tesseract
- ffmpeg:
  - Windows: https://ffmpeg.org/download.html
  - Mac: brew install ffmpeg

### First Time Setup
1. Clone repo
2. cd backend && run setup.sh (Mac) or setup.bat (Windows)
3. Edit backend/.env — fill in your GEMINI_API_KEY
4. cd frontend && npm install
5. Start MongoDB (run 'mongod' in a terminal)

### Running the App
Mac/Linux: ./start.sh
Windows: start.bat

### Getting API Keys (Free)
- Gemini: https://aistudio.google.com/app/apikey (FREE)
- Google Custom Search: https://developers.google.com/custom-search/v1/overview (100/day free)
- Gmail App Password: Google Account → Security → 2FA → App Passwords

### API Documentation
Visit http://localhost:8000/docs after starting backend.
