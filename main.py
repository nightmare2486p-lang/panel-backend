import os
import base64
import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(redirect_slashes=False)

# Environmental variables managed via Render's dashboard
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER")      
REPO_NAME = os.getenv("REPO_NAME")        

# Structural GitHub API link mapper
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/"

class LoginRequest(BaseModel):
    username: str
    password: str

class AdminActionRequest(BaseModel):
    admin_user: str
    admin_pass: str
    target_user: str
    target_pass: str = ""

def fetch_github_file_with_sha(filename: str):
    """Fetches a file and returns its parsed content along with its unique GitHub SHA hash."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get(GITHUB_API_URL + filename, headers=headers)
    if response.status_code == 200:
        file_data = response.json()
        decoded_text = base64.b64decode(file_data['content']).decode('utf-8')
        return json.loads(decoded_text), file_data['sha']
    elif response.status_code == 404:
        return {}, None
    raise HTTPException(status_code=500, detail=f"Failed to reach database file: {filename}")

def commit_github_file(filename: str, content_dict: dict, sha: str, commit_msg: str):
    """Safely writes updated data structures back to the private GitHub repository."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
    }
    updated_bytes = json.dumps(content_dict, indent=2).encode('utf-8')
    encoded_content = base64.b64encode(updated_bytes).decode('utf-8')
    
    payload = {
        "message": commit_msg,
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(GITHUB_API_URL + filename, json=payload, headers=headers)
    
    # FIX: Restored the missing validation array values
    if response.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Database write rejected by GitHub: {response.text}")


@app.get("/")
def health_check():
    """Simple connectivity verification route."""
    return {"status": "online"}

@app.post("/login/")
def login(data: LoginRequest):
    """Authenticates users and dynamically streams Main.py with the active user injected."""
    users_db, _ = fetch_github_file_with_sha("users.json")
    if data.username in users_db and users_db[data.username] == data.password:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
        resp = requests.get(GITHUB_API_URL + "Main.py", headers=headers)
        if resp.status_code == 200:
            raw_code = base64.b64decode(resp.json()['content']).decode('utf-8')
            # Personalize code output to pass user info inside memory execution layers safely
            personalized_code = raw_code.replace('CURRENT_USER = "Admin"', f'CURRENT_USER = "{data.username}"')
            return {"status": "success", "code": personalized_code}
    raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/request_access/")
def request_access(data: LoginRequest):
    """Logs a prospective client registration entry inside requests.json."""
    users_db, _ = fetch_github_file_with_sha("users.json")
    if data.username in users_db:
        raise HTTPException(status_code=400, detail="Username already active or registered.")
        
    requests_db, sha = fetch_github_file_with_sha("requests.json")
    requests_db[data.username] = data.password
    commit_github_file("requests.json", requests_db, sha, f"Access request submitted by {data.username}")
    return {"status": "pending", "message": "Request logged successfully. Awaiting Admin authorization."}

# FIX 1: Add a trailing slash right after list_requests
@app.post("/admin/list_requests/")
def admin_list_requests(data: LoginRequest):
    """Exposes pending registration requests exclusively to the authorized system administrator."""
    users_db, _ = fetch_github_file_with_sha("users.json")
    if data.username == "nightmare2486p" and users_db.get(data.username) == data.password:
        requests_db, _ = fetch_github_file_with_sha("requests.json")
        return {"status": "success", "requests": requests_db}
    raise HTTPException(status_code=403, detail="Access denied. Administrator privileges required.")

# FIX 2: Add a trailing slash right after approve_request
@app.post("/admin/approve_request/")
def admin_approve_request(data: AdminActionRequest):
    """Validates approval parameters and migrates requests from requests.json into active status inside users.json."""
    users_db, u_sha = fetch_github_file_with_sha("users.json")
    if data.admin_user == "nightmare2486p" and users_db.get(data.admin_user) == data.admin_pass:
        requests_db, r_sha = fetch_github_file_with_sha("requests.json")
        
        if data.target_user not in requests_db:
            raise HTTPException(status_code=404, detail="Target request profile not found.")
            
        # Migrate credentials seamlessly
        users_db[data.target_user] = requests_db[data.target_user]
        del requests_db[data.target_user]
        
        # Sequentially sync adjustments live back onto GitHub storage instances
        commit_github_file("users.json", users_db, u_sha, f"Admin approved account: {data.target_user}")
        commit_github_file("requests.json", requests_db, r_sha, f"Cleaned request pool for: {data.target_user}")
        return {"status": "success", "message": f"Successfully authorized user account: {data.target_user}"}
    raise HTTPException(status_code=403, detail="Access denied.")
