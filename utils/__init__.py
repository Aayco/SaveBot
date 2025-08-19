from cryptography.fernet import Fernet
import json

class CryptoManager:
    def __init__(self, key):
        self.fernet = Fernet(key.encode())

    def encrypt(self, data):
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, data):
        return self.fernet.decrypt(data.encode()).decode()
