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

    def create_team_mapping_table(self):
        """Create Mapping table if it does not exist"""
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS team_mapper
                            (
                            id SERIAL PRIMARY KEY,
                            normalized_name TEXT NOT NULL,
                            received_name TEXT NOT NULL, 
                            abbreviation TEXT NOT NULL,
                            league TEXT NOT NULL)
                            ''')
        self.conn.commit()


    def load_teams(self):
        self.cursor.execute("SELECT normalized_name, received_name, abbreviation, league FROM team_mapper")
        return self.cursor.fetchall()

    # def update_mapper_table(self, normalized_name, received_name, abbreviation, league):
    #     self.cursor.execute("SELECT 1 FROM team_mapper WHERE received_name = %s", (received_name,))
    #     if self.cursor.fetchone():
    #         return
    #
    #     self.cursor.execute("""
    #         INSERT INTO team_mapper (normalized_name, received_name, abbreviation, league)
    #         VALUES (%s, %s, %s, %s)
    #     """, (normalized_name, received_name, abbreviation, league))
    #     self.conn.commit()

    def update_mapper_table(self, normalized_name, received_name, abbreviation, league):
        query = """
            SELECT 1 FROM team_mapper
            WHERE LOWER(received_name) = %s AND UPPER(league) = %s
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (received_name.lower(), league.upper()))
            if cursor.fetchone():
                return

            cursor.execute("""
                INSERT INTO team_mapper (normalized_name, received_name, abbreviation, league)
                VALUES (%s, %s, %s, %s)
            """, (normalized_name, received_name, abbreviation, league))
        self.conn.commit()

    def get_all_received_names_and_leagues_from_db(self):
        query = "SELECT received_name, league FROM team_mapper"
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()

        return set((row[0].lower(), row[1].upper()) for row in results)

    def bulk_update_mapper_table(self, data):
        existing_names_leagues = self.get_all_received_names_and_leagues_from_db()

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

            insert_data.append((normalized_name, received_name, abbreviation, league))
        if insert_data:
            self.cursor.executemany("""
                INSERT INTO team_mapper (normalized_name, received_name, abbreviation, league)
                VALUES (%s, %s, %s, %s)
            """, insert_data)
            self.conn.commit()

    def create_not_found_table(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS not_found
                                    (
                                    id SERIAL PRIMARY KEY,
                                    team_name TEXT NOT NULL,
                                    league TEXT NOT NULL)
                                    ''')
        self.conn.commit()

    def insert_not_found(self, team_name, league):
        self.cursor.execute("""
            INSERT INTO not_found (team_name, league)
            VALUES (%s, %s)
        """, (team_name, league))
        self.conn.commit()


    def load_not_found(self):
        self.cursor.execute("SELECT team_name, league FROM not_found")
        return self.cursor.fetchall()

if __name__ == "__main__":
    db = Database()
    db.create_not_found_table()