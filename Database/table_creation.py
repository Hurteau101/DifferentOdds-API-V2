

def create_stat_mapper():
    """Returns the SQL command to create the stat_mapper table."""
    # created_date = UTC Time
    return """
        CREATE TABLE IF NOT EXISTS stat_mapper
        (
          raw_name VARCHAR(255) PRIMARY KEY,
          mapped_name VARCHAR(255) NOT NULL,
          sport_name VARCHAR(255) NOT NULL,
          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

def create_league_mapper():
    """Returns the SQL command to create the stat_mapper table."""
    # created_date = UTC Time
    return """
        CREATE TABLE IF NOT EXISTS league_mapper
        (
          raw_name VARCHAR(255) PRIMARY KEY,
          mapped_name VARCHAR(255) NOT NULL,
          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

def create_api_table():
    """Returns the SQL command to create the api_keys table."""
    return """
        CREATE TABLE IF NOT EXISTS api_keys
        (
          id SERIAL PRIMARY KEY,
          client TEXT NOT NULL,
          api_key TEXT NOT NULL,
          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

def create_mapping_database():
    """Returns the SQL commands to create the necessary tables for team mapping and verification."""
    return """
            CREATE TABLE IF NOT EXISTS teams
            (
              id SERIAL PRIMARY KEY,
              normalized_name TEXT NOT NULL,
              received_name   TEXT NOT NULL,
              abbreviation    TEXT NOT NULL,
              league          TEXT NOT NULL,
              base_league     TEXT,
              created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS verification_table
            (
              id SERIAL PRIMARY KEY,
              normalized_name TEXT,
              received_name   TEXT NOT NULL,
              abbreviation    TEXT,
              league          TEXT NOT NULL,
              source          TEXT NOT NULL,
              sportsbook      TEXT NOT NULL,
              original_league TEXT NOT NULL,
              created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS AI_Table
            (
              id SERIAL PRIMARY KEY,
              team_name      TEXT NOT NULL,
              league          TEXT NOT NULL,
              solo_game     BOOLEAN DEFAULT FALSE,
              sportsbook      TEXT NOT NULL
            );
            """