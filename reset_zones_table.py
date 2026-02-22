from backend.app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text('DROP TABLE IF EXISTS bin_zones CASCADE'))
    print('bin_zones table dropped successfully')

from backend.app.database import Base
Base.metadata.create_all(bind=engine)
print('All tables created successfully')
