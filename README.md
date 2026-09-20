# StudyIntelli - Setup and Execution Guide

StudyIntelli is a production-ready mobile application that allows students to upload course PDFs and generates prioritized important questions, MCQs, and short/long questions using AI.

## 1. Project Structure

The repository contains two main directories:
- `backend/`: Python + Django REST Framework API using Clean Architecture concepts.
- `frontend/`: Flutter mobile application using Riverpod for State Management.

## 2. Environment Setup

### Prerequisites
- **Python 3.10+**
- **Flutter SDK 3.0+**
- **PostgreSQL** database running locally or remotely.
- **Groq API Key** (Get one at [https://console.groq.com/](https://console.groq.com/))

## 3. Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```
2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install django djangorestframework psycopg2-binary python-dotenv PyMuPDF groq djangorestframework-simplejwt django-cors-headers
   ```
4. **Configure Environment Variables**:
   Edit the `.env` file in the `backend/` directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   DB_NAME=studyintelli_db
   DB_USER=postgres
   DB_PASSWORD=your_postgres_password
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```
5. **Database Setup**:
   Ensure your PostgreSQL instance is running and you have created a database named `studyintelli_db`. Then run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
6. **Run the backend server**:
   ```bash
   python manage.py runserver  Or  python manage.py runserver 0.0.0.0:8000
   ```
   The API will be available at `http://127.0.0.1:8000`.

## 4. Flutter Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```
2. **Install Flutter packages**:
   ```bash
   flutter pub get
   ```
3. **API Configuration**:
   In `frontend/lib/core/api_client.dart`, the `baseUrl` is configured as `http://10.0.2.2:8000/api` which points to localhost on an Android emulator. If you are testing on a real device, an iOS simulator, or a web browser, change this URL to your machine's local IP address (e.g., `http://192.168.1.x:8000/api`).
4. **Run the application**:
   Start your Android Emulator or iOS Simulator, then run:
   ```bash
   flutter run
   ```

## 5. Usage Guide
1. **Signup/Login**: Create a new account or login.
2. **Upload PDF**: Click the floating action button to select and upload a course PDF.
3. **Wait for AI**: The system will extract text and call the Groq LLM to generate the structured materials.
4. **Review Materials**: Tap on the generated material to see prioritized important questions, MCQs, fill-in-the-blanks, and more!
