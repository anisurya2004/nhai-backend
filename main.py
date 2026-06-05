import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://db.gobefnqrcgiylupnatbb.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'sb_publishable_BysUEbg2r5bI_7cTPaR45w_Uw8Bxxhb')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# --- Request Models (Auto-Validates JSON) ---
class LoginRequest(BaseModel):
    emp_id: str
    password: str

class RegisterRequest(BaseModel):
    emp_id: str
    name: str
    password: str
    face_embedding: List[float]

class Record(BaseModel):
    emp_id: str
    timestamp: str
    action_type: str

class SyncRequest(BaseModel):
    records: List[Record]

@app.get("/")
def home():
    return {"message": "Server is running!"}

@app.post("/ping")
def ping():
    try:
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/employees?limit=1',
            headers=HEADERS,
            timeout=5
        )
        if response.status_code == 200:
            return {"message": "Database connection successful!"}
        else:
            raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.post("/register")
def register(request: RegisterRequest):
    try:
        # Check if user exists
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/employees?emp_id=eq.{request.emp_id}',
            headers=HEADERS
        )
        if response.json():
            raise HTTPException(status_code=400, detail="Employee ID already exists")
        
        # Insert new employee
        response = requests.post(
            f'{SUPABASE_URL}/rest/v1/employees',
            headers=HEADERS,
            json={
                'emp_id': request.emp_id,
                'name': request.name,
                'password': request.password,
                'face_embedding': request.face_embedding
            }
        )
        
        if response.status_code == 201:
            return {"message": "Registration successful"}
        else:
            raise HTTPException(status_code=500, detail=f"Registration failed: {response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/login")
def login(request: LoginRequest):
    try:
        # Get employee by ID and password
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/employees?emp_id=eq.{request.emp_id}&password=eq.{request.password}',
            headers=HEADERS
        )
        
        data = response.json()
        if not data:
            raise HTTPException(status_code=401, detail="Invalid Credentials")
        
        emp_data = data[0]
        
        # Get last action
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/attendance?emp_id=eq.{request.emp_id}&order=timestamp.desc&limit=1',
            headers=HEADERS
        )
        
        last_action = None
        attendance_data = response.json()
        if attendance_data:
            last_action = attendance_data[0]['action_type']
        
        return {
            "face_embedding": emp_data['face_embedding'],
            "last_action": last_action
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync")
def sync(request: SyncRequest):
    try:
        for record in request.records:
            response = requests.post(
                f'{SUPABASE_URL}/rest/v1/attendance',
                headers=HEADERS,
                json={
                    'emp_id': record.emp_id,
                    'timestamp': record.timestamp,
                    'action_type': record.action_type
                }
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to insert record: {response.text}")
        
        return {"message": "Successfully synced"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))