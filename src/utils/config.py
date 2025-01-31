class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///wfs_data.db'  # SQLite statt PostgreSQL
    SQLALCHEMY_TRACK_MODIFICATIONS = False 