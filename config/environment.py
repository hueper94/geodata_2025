class Config:
    DEBUG = False
    TESTING = False
    DATABASE_NAME = 'data_lexicon.db'
    PORT = 5001

class ProductionConfig(Config):
    DATABASE_NAME = 'production_lexicon.db'
    PORT = 5001

class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_NAME = 'development_lexicon.db'
    PORT = 5002

# Konfigurationen in einem Dictionary speichern
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 