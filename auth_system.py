import time

class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password

class AuthSystem:
    def __init__(self):
        self.users = {}
        self.current_user = None
        self.log = []

    def add_user(self, username, password):
        self.users[username] = User(username, password)

    def login(self, username, password):
        if username in self.users and self.users[username].password == password:
            self.current_user = self.users[username]
            self.log.append(f"{time.ctime()}: {username} logged in")
            return True
        return False

    def logout(self):
        if self.current_user:
            self.log.append(f"{time.ctime()}: {self.current_user.username} logged out")
            self.current_user = None

    def get_current_user(self):
        return self.current_user.username if self.current_user else None
    
    def is_authenticated(self):
        return self.current_user is not None

    def handle_delivery(self):
        if self.current_user:
            self.log.append(f"{time.ctime()}: {self.current_user.username} handled product delivery")
        else:
            print("Error: No user logged in")

    def process_product(self):
        if self.current_user:
            self.log.append(f"{time.ctime()}: {self.current_user.username} processed delivered product")
        else:
            print("Error: No user logged in")

    def print_log(self):
        for entry in self.log:
            print(entry)