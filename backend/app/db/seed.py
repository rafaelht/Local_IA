from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import User, UserPreference
from app.core.security import hash_password


def create_initial_admin() -> None:
    """Create an initial admin user if none exists."""
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.email == 'admin@local').first()
        if admin:
            print("✓ Admin user already exists")
            return
        
        # Create admin user
        admin_user = User(
            email='admin@local',
            nickname='admin',
            full_name='Administrador Local',
            hashed_password=hash_password('admin'),
            role='admin',
            is_active=True,
        )
        db.add(admin_user)
        db.flush()
        
        # Create default preferences
        preferences = UserPreference(user_id=admin_user.id)
        db.add(preferences)
        
        db.commit()
        print("✓ Admin user created: admin@local / admin")
    except Exception as e:
        print(f"✗ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    create_initial_admin()
