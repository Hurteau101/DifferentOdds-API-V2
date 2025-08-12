import os
import psycopg2
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

class Database:
    def __init__(self):
        load_dotenv(dotenv_path=env_path)
        self.conn = self.create_connection()
        self.cursor = self.conn.cursor()


    def create_connection(self):
        return psycopg2.connect(
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            port=os.getenv("DB_PORT")
        )


    def create_mapping_database(self):
        """Create Mapping table if it does not exist"""
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS teams
                            (
                            id SERIAL PRIMARY KEY,
                            normalized_name TEXT NOT NULL,
                            received_name TEXT NOT NULL, 
                            abbreviation TEXT NOT NULL,
                            league TEXT NOT NULL,
                            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                            ''')
        self.conn.commit()


    def load_teams(self):
        self.cursor.execute("SELECT normalized_name, received_name, abbreviation, league, base_league FROM teams")
        return self.cursor.fetchall()


    def update_verification_table(self, received_name, league, source, sportsbook, original_league, normalized_name=None, abbreviation=None):
        query = """
            SELECT 1 FROM verification_table
            WHERE LOWER(received_name) = %s AND UPPER(league) = %s
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (received_name.lower(), league.upper()))
            if cursor.fetchone():
                return

            cursor.execute("""
                INSERT INTO verification_table (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league))

        self.conn.commit()

    def get_all_received_names(self):
        query = """
            SELECT received_name FROM teams
            UNION
            SELECT received_name FROM verification_table
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
        return set(row[0].lower() for row in results)


    def get_verification_received_names(self):
        self.cursor.execute("SELECT received_name FROM verification_table")
        results = self.cursor.fetchall()
        return set(row[0].lower() for row in results)

    def get_all_received_names_and_leagues(self):
        query = """
            SELECT received_name, league FROM teams
            UNION
            SELECT received_name, league FROM verification_table
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()

        return set((row[0].lower(), row[1].upper()) for row in results)


    def bulk_update_verification_table(self, data):
        existing_names_leagues = self.get_all_received_names_and_leagues()


        insert_data = []
        for row in data:
            if not row.get('found'):
                continue

            received_name = row['original_name']
            league = row['league'].upper()

            # Check if both received_name AND league combo already exists
            if (received_name.lower(), league) in existing_names_leagues:
                continue

            normalized_name = row['team_name']
            abbreviation = row['abbreviation'].upper() if row['abbreviation'] else None
            source = row.get('source', 'unknown')
            sportsbook = row.get('sportsbook', 'unknown')
            original_league = row.get('original_league', league).upper()

            insert_data.append((normalized_name, received_name, abbreviation, league, source, sportsbook, original_league))

        if insert_data:
            self.cursor.executemany("""
                INSERT INTO verification_table (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, insert_data)
            self.conn.commit()


if __name__ == "__main__":
    db = Database()
    db.create_mapping_database()