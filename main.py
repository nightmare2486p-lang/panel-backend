import os
import base64
import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# These read from the cloud platform's environment configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER")      # Your GitHub username
REPO_NAME = os.getenv("REPO_NAME")        # Your private repository name

# Base URL for the GitHub API to fetch file contents
GITHUB_API_URL = f"https://github.com{REPO_OWNER}/{REPO_NAME}/contents/"

class LoginRequest(BaseModel):
    username: str
    password: str

def fetch_github_file(filename: str) -> str:
    """Safely connects to GitHub API using the private token to get a file."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    response = requests.get(GITHUB_API_URL + filename, headers=headers)
    
    if response.status_code == 200:
        file_data = response.json()
        # GitHub encodes file text into Base64 strings; we must decode it back to plain text
        decoded_bytes = base64.b64decode(file_data['content'])
        return decoded_bytes.decode('utf-8')
    return None

@app.get("/")
def health_check():
    """Simple connection check to confirm the API is online."""
    return {"status": "online"}

@app.post("/login")
def login(data: LoginRequest):
    # 1. Fetch the user database from your private GitHub
    users_content = fetch_github_file("users.json")
    if not users_content:
        raise HTTPException(status_code=500, detail="Database inaccessible")
    
    try:
        users_db = json.loads(users_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Database corruption error")
    
    # 2. Check credentials
    if data.username in users_db:
        if users_db[data.username] == data.password:
            
            # 3. If correct, fetch Main.py from the private repo
            main_code = fetch_github_file("Main.py")
            if not main_code:
                raise HTTPException(status_code=500, detail="Main script missing")
                
            return {"status": "success", "code": main_code}
            
    # Generic failure message to prevent username guessing
    raise HTTPException(status_code=401, detail="Invalid username or password")
