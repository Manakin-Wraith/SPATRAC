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

    def add_user(self, username, password, department, role):
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
                'role': self.current_user.role,
                'department': self.current_user.department
            }
        return None
    
    def is_authenticated(self):
        return self.current_user is not None

    def is_authorized(self, username, department):
        if username in self.users:
            user = self.users[username]
            if user.role == 'Manager' and user.department == 'Delivery':
                return True  # Delivery managers can handle all departments
            return user.department == department
        return False
    
    def is_delivery_manager(self):
        return self.current_user and self.current_user.role == 'Manager' and self.current_user.department == 'Delivery'

    def is_manager(self):
        """Check if the current user has a manager role."""
        if self.current_user and self.current_user.role:
            return self.current_user.role.lower() == 'manager'
        return False

    def handle_delivery(self):
        if self.current_user and self.is_delivery_manager():
            self.log.append(f"{time.ctime()}: {self.current_user.username} handled product delivery")
        else:
            print("Error: No user logged in or user is not a delivery manager")

    def process_product(self, department):
        if self.current_user and self.is_authorized(self.current_user.username, department):
            self.log.append(f"{time.ctime()}: {self.current_user.username} processed product for {department}")
        else:
            print(f"Error: User not authorized to process products for {department}")

    def print_log(self):
        for entry in self.log:
            print(entry)