import time

class User:
    def __init__(self, username, password, department=None, role=None):
        self.username = username
        self.password = password
        self.department = department
        self.role = role

class AuthSystem:
    def __init__(self):
        self.users = {}
        self.current_user = None
        self.log = []

    def add_user(self, username, password, department=None, role=None):
        self.users[username] = User(username, password, department, role)

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
    
    def get_current_user_role(self):
        return self.current_user.role if self.current_user else None
    
    def get_current_user_info(self):
        if self.current_user:
         return {
            'username': self.current_user.username,
            'role': self.current_user.role,  # Assuming `user_role` is an attribute of the user model
            'department': self.current_user.department
        }
        return None
        
    
    def is_authenticated(self):
        return self.current_user is not None

    def is_authorized(self, username, department):
        print(f"Checking authorization for username: {username}, department: {department}")
        if username in self.users:
            user = self.users[username]
            print(f"User's department: {user.department}")
            print(f"Product's department: {department}")
            result = user.department.lower().strip() == department.lower().strip()
            print(f"Authorization result: {result}")
            return result
        print(f"User {username} not found in the system")
        return False
    
    def is_butchery_manager(self):
        return self.current_user and self.current_user.department == '2' and self.current_user.role == 'Manager'

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