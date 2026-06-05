import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

# --- Database Configuration (from Supabase) ---
DB_HOST = 'db.gobefnqrcgiylupnatbb.supabase.co'
DB_PORT = 5432
DB_USER = 'postgres'
DB_PASSWORD = 'johnguthrie@@4Sub'  # Replace with your actual Supabase password
DB_NAME = 'postgres'

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

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

# --- API Endpoints ---

@app.get("/")
def home():
    return {"message": "Server is running!"}

@app.post("/ping")
def ping():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Using your exact version check query
    cur.execute('SELECT version();')
    db_version = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return {
        "message": "Database connection successful!",
        "postgres_version": db_version
    }

@app.post("/register")
def register(request: RegisterRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user already exists
        cur.execute("SELECT emp_id FROM employees WHERE emp_id = %s", (request.emp_id,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Employee ID already exists")

        # Convert embedding list to string for pgvector insertion
        embedding_str = '[' + ','.join(map(str, request.face_embedding)) + ']'
        
        cur.execute(
            "INSERT INTO employees (emp_id, name, password, face_embedding) VALUES (%s, %s, %s, %s)",
            (request.emp_id, request.name, request.password, embedding_str)
        )
        conn.commit()
        return {"message": "Registration successful"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

@app.post("/login")
def login(request: LoginRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT face_embedding FROM employees WHERE emp_id = %s AND password = %s",
        (request.emp_id, request.password)
    )
    result = cur.fetchone()
    
    if not result:
        cur.close()
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    # Fetch the last action for this user
    cur.execute(
        "SELECT action_type FROM attendance WHERE emp_id = %s ORDER BY timestamp DESC LIMIT 1",
        (request.emp_id,)
    )
    last_action_row = cur.fetchone()
    last_action = last_action_row[0] if last_action_row else None
    
    cur.close()
    conn.close()

    return {
        "face_embedding": result[0],
        "last_action": last_action
    }

@app.post("/sync")
def sync(request: SyncRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        for record in request.records:
            cur.execute(
                "INSERT INTO attendance (emp_id, timestamp, action_type) VALUES (%s, %s, %s)",
                (record.emp_id, record.timestamp, record.action_type)
            )
        conn.commit() # Save the changes to the database
        return {"message": "Successfully synced"}
    except Exception as e:
        conn.rollback() # Undo the changes if something crashes
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()