from backend.app.database import engine
from sqlalchemy import text

print("Resetting events table...")
with engine.begin() as conn:
    # Drop table using CASCADE to remove dependencies
    conn.execute(text('DROP TABLE IF EXISTS events CASCADE'))
    print('✓ events table dropped')

from backend.app.database import Base
Base.metadata.create_all(bind=engine)
print('✓ All tables recreated (including events)')
