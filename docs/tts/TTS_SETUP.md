# TTS Setup (Optional)

## Issue with Python 3.14

The TTS library (Coqui TTS) currently only supports Python 3.9 - 3.11. If you're using Python 3.14, you have two options:

## Option 1: Use Python 3.11 with pyenv (Recommended for TTS)

1. **Install pyenv** (if not already installed):
   ```bash
   brew install pyenv
   ```

2. **Install Python 3.11**:
   ```bash
   pyenv install 3.11.9
   ```

3. **Create a new virtual environment with Python 3.11**:
   ```bash
   cd <LOCAL_REPO_PATH>
   pyenv local 3.11.9
   rm -rf venv  # Remove old venv
   python -m venv venv
   source venv/bin/activate
   ```

4. **Install all dependencies including TTS**:
   ```bash
   # Uncomment TTS dependencies in backend/requirements.txt first
   pip install -r backend/requirements.txt
   ```

## Option 2: Use Summra without TTS (Current Setup)

The application works perfectly fine without TTS! All core features are available:
- ✅ Generate all 3 types of summaries
- ✅ Browse books in web interface
- ✅ View summaries
- ❌ Text-to-speech (disabled)

You can use the application as-is and the TTS button will show an error message when clicked.

## Alternative TTS Solutions

If you want text-to-speech without downgrading Python, you can:

### 1. Use Browser TTS (Free)
Most modern browsers have built-in text-to-speech. Just select the text and use browser extensions or built-in features.

### 2. Use OpenAI TTS API
Update `backend/tts_handler.py` to use OpenAI's TTS API instead:
```bash
pip install openai
```

Then modify the code to call OpenAI's API.

### 3. Use ElevenLabs API
Similar to OpenAI, update the code to use ElevenLabs for high-quality voices.

### 4. Use gTTS (Google Text-to-Speech)
A simpler alternative:
```bash
pip install gTTS
```

This works with Python 3.14 and provides basic TTS functionality.

## Quick gTTS Implementation

If you want a simple TTS that works with Python 3.14, I can help you replace the VITS implementation with gTTS. Just ask!
