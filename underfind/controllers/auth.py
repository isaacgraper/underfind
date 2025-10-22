from underfind.lib.db.supabase_client import get_supabase
from underfind.models.user import User
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AuthController:
    def __init__(self):
        self.client = get_supabase()

    def login(self, email, password) -> User | None:
        if not email or not password:
            return None
            
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })    
            return response.user if response and response.user else None

        except Exception:
            return None

    def register(self, email, password, confirm_password) -> bool:
        if not email or not password or password != confirm_password:
            return False
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
            })
            return True if response and response.user else False
        
        except Exception:
            return False