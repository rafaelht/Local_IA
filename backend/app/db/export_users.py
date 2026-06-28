import json
import os
from app.db.session import SessionLocal
from app.db.models import User


def export_users(filename: str = '/app/export/users.json') -> None:
    """Export all users to a JSON file."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        users_data = [
            {
                'email': user.email,
                'nickname': user.nickname,
                'full_name': user.full_name,
                'hashed_password': user.hashed_password,
                'role': user.role,
                'is_active': user.is_active,
            }
            for user in users
        ]
        
        with open(filename, 'w') as f:
            json.dump(users_data, f, indent=2)
        
        print(f"✓ Exported {len(users_data)} users to {filename}")
    finally:
        db.close()


def import_users(filename: str = '/app/export/users.json') -> None:
    """Import users from a JSON file."""
    if not os.path.exists(filename):
        print(f"✗ File not found: {filename}")
        return
    
    db = SessionLocal()
    try:
        with open(filename, 'r') as f:
            users_data = json.load(f)
        
        for user_data in users_data:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data['email']).first()
            if existing_user:
                print(f"⚠ User already exists: {user_data['email']}")
                continue
            
            new_user = User(
                email=user_data['email'],
                nickname=user_data.get('nickname'),
                full_name=user_data.get('full_name'),
                hashed_password=user_data['hashed_password'],
                role=user_data.get('role', 'user'),
                is_active=user_data.get('is_active', True),
            )
            db.add(new_user)
        
        db.commit()
        print(f"✓ Imported users from {filename}")
    except json.JSONDecodeError:
        print(f"✗ Invalid JSON in {filename}")
        db.rollback()
    except Exception as e:
        print(f"✗ Error importing users: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        filename = sys.argv[2] if len(sys.argv) > 2 else '/app/export/users.json'
        
        if command == 'export':
            export_users(filename)
        elif command == 'import':
            import_users(filename)
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print("Usage: python export_users.py [export|import] [filename]")
        sys.exit(1)
