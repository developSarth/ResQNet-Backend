# ResQNet Backend

A Unified Emergency Response Network backend API built with FastAPI.

## 🚀 Quick Start

### Local Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r app/requirements.txt
```

3. Set up environment variables:
```bash
cp app/.env.example app/.env
# Edit .env with your configuration
```

4. Run the development server:
```bash
uvicorn app.main:app --reload
```

### Docker

```bash
docker build -t resqnet-backend .
docker run -p 8000:8000 resqnet-backend
```

## 🌐 Deployment on Render

1. Fork or push this repository to GitHub
2. Connect your GitHub repo to Render
3. Render will auto-detect the Dockerfile
4. Configure environment variables in Render dashboard:
   - `DATABASE_URL` - PostgreSQL connection string
   - `SECRET_KEY` - JWT secret key
   - `GOOGLE_CLIENT_ID` - Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
   - `TWILIO_ACCOUNT_SID` - Twilio SID for SMS
   - `TWILIO_AUTH_TOKEN` - Twilio auth token

## 📚 API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔧 Tech Stack

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Primary database
- **Pydantic** - Data validation
- **JWT** - Authentication tokens
- **OAuth 2.0** - Google authentication

## 📁 Project Structure

```
app/
├── main.py          # Application entry point
├── config.py        # Configuration settings
├── database.py      # Database connection
├── models/          # SQLAlchemy models
├── routes/          # API endpoints
├── auth/            # Authentication logic
├── utils/           # Utility functions
└── ws_handlers/     # WebSocket handlers
```

## 📄 License

MIT License
