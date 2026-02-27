from dotenv import load_dotenv
load_dotenv()
from app.db import init_db
init_db()
print("Database initialized.")
