import random
import string
from collections.abc import Callable
import psycopg2
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os
from psycopg2.extensions import connection
import psycopg2.extras
from psycopg2.extras import execute_values


class Database:
    load_dotenv()
    def __init__(self):
        self.connection = self._create_connection()
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def _create_connection(self) -> connection:
        """Used to create a connection to the database"""
        return psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
        )


    def _fernet_creator(self) -> Fernet:
        """Creates the Fernet Key instance used for encryption/decryption"""
        fernet_key = os.getenv('FERNET_KEY')
        if not fernet_key:
            raise ValueError("FERNET_KEY environment variable is not set.")

        fernet = Fernet(fernet_key.encode())
        return fernet

    def _decoder(self, key: str) -> str:
        """Decodes a string using Fernet encryption"""
        fernet = self._fernet_creator()
        return fernet.decrypt(key.encode()).decode()

    def _encrypter(self, key: str) -> str:
        """Encrypts a string using Fernet encryption"""
        fernet = self._fernet_creator()
        return fernet.encrypt(key.encode()).decode()


    def get_api_keys(self) -> list:
        self.cursor.execute("SELECT api_key FROM api_keys")
        api_keys = self.cursor.fetchall()
        return [
            self._decoder(api['api_key'])
            for api in api_keys
        ]

    def create_table(self, table_creator_func: Callable):
        """Creates a table in the database using the provided table creator function."""
        sql = table_creator_func()
        if not sql:
            raise ValueError("Table creator function did not return any SQL command.")

        self.cursor.execute(sql)
        self.connection.commit()

    def insert_static_mapper_data(self, database_table_name: str, static_data: dict, sport_name: str = None):
        """Inserts static Stat Types or Leagues data into the appropriate static mapper table"""
        if not static_data or not database_table_name:
            raise ValueError("static_data and/or database_table_name must be provided")

        if database_table_name.lower() == "stat_mapper":
            columns = "(raw_name, mapped_name, sport_name)"
            rows = [(key, value, sport_name) for key, value in static_data.items()]
        else:
            columns = "(raw_name, mapped_name)"
            rows = [(key, value) for key, value in static_data.items()]

        query = f"""
            INSERT INTO {database_table_name} {columns}
            VALUES %s
            ON CONFLICT (raw_name) DO NOTHING;
        """

        execute_values(self.cursor, query, rows)
        self.connection.commit()

    def fetch_all(self, table_name: str) -> list:
        """Fetches all records from the specified table."""
        if not table_name:
            raise ValueError("table_name must be provided")

        query = f"SELECT * FROM {table_name};"
        self.cursor.execute(query)
        # return [item.decode('utf-8') for row in self.cursor.fetchall() for item in row]
        return self.cursor.fetchall()


    def create_api_key(self, client_str: str):
        def client_exist():
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM api_keys WHERE client=%s)", (client_str,))
            return self.cursor.fetchone()[0]

        if not client_str:
            raise ValueError("Client string cannot be empty.")

        does_client_exist = client_exist()
        if does_client_exist:
            raise ValueError("API key for this client already exists.")

        api_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        encrypt_key = self._encrypter(api_key)

        self.cursor.execute(
            "INSERT INTO api_keys (client, api_key) VALUES (%s, %s)",
            (client_str, encrypt_key)
        )

        self.connection.commit()

    def reload_teams(self) -> list:
        """Re-loads all teams from the database."""
        self.cursor.execute("SELECT normalized_name, received_name, abbreviation, league, base_league FROM teams")
        return self.cursor.fetchall()

    def get_verification_league_map(self) -> dict:
        """Fetches all records from the verification table."""
        self.cursor.execute("SELECT received_name, league, original_league FROM verification_table")
        rows = self.cursor.fetchall()
        mapping = {}

        for name, league, orig in rows:
            name = name.lower()
            if name not in mapping:
                mapping[name] = set()

            mapping[name].add(league.upper())
            mapping[name].add(orig.upper())

        return mapping

    def get_ai_teams(self) -> list:
        """Fetches all teams that need AI verification from the verification table."""
        self.cursor.execute("SELECT team_name, league, solo_game, sportsbook FROM ai_table")
        results = self.cursor.fetchall()

        return [
            {
                "team_name": row[0],
                "league": row[1],
                "solo_game": row[2],
                "sportsbook": row[3],
            }
            for row in results
        ]

    def update_verification_table(self, received_name, league, source, sportsbook,
                                  original_league, normalized_name=None, abbreviation=None):

        self.cursor.execute(
            """
            SELECT 1
            FROM verification_table
            WHERE LOWER(received_name) = %s
              AND UPPER(league) = %s
            LIMIT 1
            """,
            (
                received_name.lower(),
                league.upper(),
            )
        )

        result = self.cursor.fetchone()
        if result:
            return

        self.cursor.execute(
            """
            INSERT INTO verification_table
            (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
            VALUES (%s, %s, %s,%s, %s, %s,%s)
            """,
            (
                normalized_name,
                received_name.lower(),
                abbreviation,
                league.upper(),
                source,
                sportsbook,
                original_league,
            )
        )

        self.connection.commit()

    def get_all_receieved_names_and_leagues(self) -> set:
        self.cursor.execute(
            "SELECT received_name, league FROM TEAMS UNION SELECT received_name, original_league FROM verification_table"
        )

        results = self.cursor.fetchall()
        return set((row[0].lower(), row[1].upper()) for row in results)

    def bulk_update_verification_table(self, data: list):
        existing = self.get_all_receieved_names_and_leagues()
        rows = []
        for row in data:
            if not row.get('found'):
                continue
            received = row['original_name']
            league = row['league'].upper()
            if (received.lower(), league) in existing:
                continue

            rows.append((
                row["team_name"],
                received,
                row['abbreviation'].upper() if row.get('abbreviation') else None,
                league,
                row.get('source', 'unknown'),
                row.get('sportsbook', 'unknown'),
                row.get('original_league', league).upper(),
            ))

        if not rows:
            return

        insert_query = """
            INSERT INTO verification_table
            (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        self.cursor.executemany(insert_query, rows)
        self.connection.commit()

    def get_ai_existing_names_and_leageus(self) -> set:
        self.cursor.execute("SELECT team_name, league FROM ai_table")
        results = self.cursor.fetchall()
        return set((row[0].lower(), row[1].upper()) for row in results)

    def bulk_update_ai_table(self, data: list):
        if not data:
            return

        existing = self.get_ai_existing_names_and_leageus()
        rows = []
        for row in data:
            team_name = row.get("team_name")
            league = row.get("league")

            if not team_name or not league:
                continue

            key = (team_name.lower(), league.upper())
            if key in existing:
                continue

            rows.append((
                team_name.lower(),
                league.upper(),
                row.get("solo_game"),
                row.get("sportsbook"),
            ))

        if not rows:
            return

        insert_query = """
            INSERT INTO ai_table (team_name, league, solo_game, sportsbook)
            VALUES (%s, %s, %s, %s)
        """

        self.cursor.executemany(insert_query, rows)
        self.connection.commit()

    def delete_ai_rows(self, names_and_leagues: set):
        if not names_and_leagues:
            return

        names = [n.lower() for n, _ in names_and_leagues]
        leagues = [l.upper() for _, l in names_and_leagues]

        sql = """
            DELETE FROM ai_table
            WHERE team_name = ANY(%s)
            AND league = ANY(%s)
        """

        self.cursor.execute(sql, (names, leagues))
        self.connection.commit()

    def get_auto_sgp_configs(self) -> list:
        """Re-loads all teams from the database."""
        self.cursor.execute("SELECT * FROM autospg_configs ")

        return [dict(row) for row in self.cursor.fetchall()]


if __name__ == "__main__":
    from table_creation import create_autosgp_table
    db = Database()
    data = db.get_auto_sgp_configs()

    # db.create_api_key(client_str="DifferentOdds-Internal")
    # api = db.get_api_keys()




