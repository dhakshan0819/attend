import os
import sys
import getpass
import db

# Default admin password to prevent accidental resets
ADMIN_PASSWORD = "sudo@neko"

# ANSI Colors for a premium console interface
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_header():
    print(f"{COLOR_CYAN}{COLOR_BOLD}=================================================={COLOR_RESET}")
    print(f"{COLOR_CYAN}{COLOR_BOLD}     Gatekeeper Attendance System - System Reset  {COLOR_RESET}")
    print(f"{COLOR_CYAN}{COLOR_BOLD}=================================================={COLOR_RESET}")
    print(f"{COLOR_YELLOW}WARNING: This action will permanently delete all:{COLOR_RESET}")
    print(" - Registered students and their face embeddings")
    print(" - Historical daily check-in and check-out logs")
    print(" - Generated attendance records")
    print(f"{COLOR_CYAN}--------------------------------------------------{COLOR_RESET}\n")

def reset_system():
    print_header()
    
    # 1. Password Verification
    try:
        entered_password = getpass.getpass(prompt=f"{COLOR_BOLD}Enter Admin Password:{COLOR_RESET} ")
    except Exception:
        # Fallback if getpass is not supported in the running environment
        entered_password = input("Enter Admin Password: ")
        
    if entered_password != ADMIN_PASSWORD:
        print(f"\n{COLOR_RED}{COLOR_BOLD}[ERROR] Access Denied: Incorrect password.{COLOR_RESET}")
        sys.exit(1)
        
    # 2. Explicit Confirmation Prompt
    print(f"\n{COLOR_RED}{COLOR_BOLD}⚠️  CRITICAL CONFIRMATION REQUIRED{COLOR_RESET}")
    confirm = input("Are you absolutely sure you want to reset the system? Type 'YES' to confirm: ")
    
    if confirm != "YES":
        print(f"\n{COLOR_GREEN}Reset cancelled. No files or records were modified.{COLOR_RESET}")
        sys.exit(0) 
        
    print(f"\n{COLOR_YELLOW}Resetting Gatekeeper system...{COLOR_RESET}")
    
    # 3. Database Deletion & Re-Initialization
    db_file = db.DB_PATH
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f" - Deleted database file: {COLOR_BOLD}{db_file}{COLOR_RESET}")
        else:
            print(" - Database file was not found. Initializing a new database.")
            
        # Re-initialize the tables
        db.init_db()
        print(f" - Re-initialized database schemas and empty tables.")
        
        print(f"\n{COLOR_GREEN}{COLOR_BOLD}[SUCCESS] The attendance system has been reset to a fresh start.{COLOR_RESET}\n")
        
    except Exception as e:
        print(f"\n{COLOR_RED}{COLOR_BOLD}[ERROR] Reset failed: {e}{COLOR_RESET}")
        sys.exit(1)

if __name__ == "__main__":
    reset_system()
