import os
import random
import string

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool
from cryptography.fernet import Fernet


env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

import sys, asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Database:
    _instance = None   # singleton instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, min_size=3, max_size=10, timeout=30):
        if self._initialized:
            return
        self._initialized = True


        load_dotenv(dotenv_path=env_path)
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            db_url = (
                f"dbname={os.getenv('DB_NAME')} "
                f"user={os.getenv('DB_USER')} "
                f"password={os.getenv('DB_PASS')} "
                f"host={os.getenv('DB_HOST')} "
                f"port={os.getenv('DB_PORT')}"
            )

        self.pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            num_workers=3,
            max_lifetime=3600,
            open=False
        )

        self._ready = False

        fernet_key = os.getenv("FERNET_KEY")
        if not fernet_key:
            raise RuntimeError("FERNET_KEY not set in environment")
        self.cipher_suite = Fernet(fernet_key.encode())

    async def ensure_ready(self):
        if self._ready:
            return
        await self.pool.open()
        self._ready = True

    async def create_api_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS api_keys
        (
          id SERIAL PRIMARY KEY,
          client TEXT NOT NULL,
          api_key TEXT NOT NULL,
          created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                await conn.commit()

    async def create_api_key(self, client: str):
        api_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        encrypted_key = self.cipher_suite.encrypt(api_key.encode()).decode()

        sql = "INSERT INTO api_keys (client, api_key) VALUES (%s, %s)"
        async with self.pool.connection() as conn:
            await conn.execute(sql, (client, encrypted_key))
            await conn.commit()

        return api_key

    async def get_api_keys(self):
        sql = "SELECT api_key from api_keys"
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return [self.cipher_suite.decrypt(row[0].encode()).decode() for row in rows]



    async def create_mapping_database(self):
        """Create Mapping table if it does not exist"""
        sql = """
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
        """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                await conn.commit()


    async def load_teams(self):
        sql = "SELECT normalized_name, received_name, abbreviation, league, base_league FROM teams"
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                rows = await cur.fetchall()
                return rows

    async def get_all_received_names(self):
        sql = """
            SELECT received_name FROM teams
            UNION
            SELECT received_name FROM verification_table
        """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                results = await cur.fetchall()
        return set(row[0].lower() for row in results)


    async def get_verification_received_names(self):
        sql = "SELECT received_name FROM verification_table"
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                results = await cur.fetchall()
        return set(row[0].lower() for row in results)

    async def get_all_received_names_and_leagues(self):
        sql = """
            SELECT received_name, league FROM teams
            UNION
            SELECT received_name, league FROM verification_table
        """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                results = await cur.fetchall()
        return set((row[0].lower(), row[1].upper()) for row in results)

    async def update_verification_table(
            self,
            received_name, league, source, sportsbook, original_league,
            normalized_name=None, abbreviation=None
    ):
        check_query = """
             SELECT 1 FROM verification_table
             WHERE LOWER(received_name) = %s AND UPPER(league) = %s
             LIMIT 1
         """
        insert_qury = """
             INSERT INTO verification_table
             (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
             VALUES (%s, %s, %s, %s, %s, %s, %s)
         """
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(check_query, (received_name.lower(), league.upper()))
                if await cur.fetchone():
                    return
                await cur.execute(
                    insert_qury,
                    (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league),
                )
                await conn.commit()

    async def bulk_update_verification_table(self, data):
        existing = await self.get_all_received_names_and_leagues()
        rows = []
        for row in data:
            if not row.get('found'):
                continue
            received = row['original_name']
            league = row['league'].upper()
            if (received.lower(), league) in existing:
                continue
            rows.append((
                row['team_name'],
                received,
                (row['abbreviation'].upper() if row.get('abbreviation') else None),
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
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(insert_query, rows)
                await conn.commit()


if __name__ == "__main__":
    async def main(create_api_key=False, client_name=None, extract_api_keys=False):
        db = Database()
        await db.ensure_ready()

        if create_api_key and client_name:
            api_key = await db.create_api_key(client_name)
            print(f"API Key for {client_name}: {api_key}")

        if extract_api_keys:
            keys = await db.get_api_keys()
            print("API Keys:")
            for key in keys:
                print(key)

    asyncio.run(main(extract_api_keys=True))








#
#
#
#
#
#
#
#
# import os
# import psycopg2
# from dotenv import load_dotenv
#
# env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
#
# class Database:
#     def __init__.py(self):
#         load_dotenv(dotenv_path=env_path)
#         self.conn = self.create_connection()
#         self.cursor = self.conn.cursor()
#
#
#     def create_connection(self):
#         return psycopg2.connect(
#             database=os.getenv("DB_NAME"),
#             host=os.getenv("DB_HOST"),
#             user=os.getenv("DB_USER"),
#             password=os.getenv("DB_PASS"),
#             port=os.getenv("DB_PORT")
#         )
#
#
#     def create_mapping_database(self):
#         """Create Mapping table if it does not exist"""
#         self.cursor.execute('''CREATE TABLE IF NOT EXISTS teams
#                             (
#                             id SERIAL PRIMARY KEY,
#                             normalized_name TEXT NOT NULL,
#                             received_name TEXT NOT NULL,
#                             abbreviation TEXT NOT NULL,
#                             league TEXT NOT NULL,
#                             created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#                             )
#                             ''')
#         self.conn.commit()
#
#
#     def load_teams(self):
#         self.cursor.execute("SELECT normalized_name, received_name, abbreviation, league, base_league FROM teams")
#         return self.cursor.fetchall()
#
#
#     def update_verification_table(self, received_name, league, source, sportsbook, original_league, normalized_name=None, abbreviation=None):
#         query = """
#             SELECT 1 FROM verification_table
#             WHERE LOWER(received_name) = %s AND UPPER(league) = %s
#         """
#         with self.conn.cursor() as cursor:
#             cursor.execute(query, (received_name.lower(), league.upper()))
#             if cursor.fetchone():
#                 return
#
#             cursor.execute("""
#                 INSERT INTO verification_table (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s)
#             """, (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league))
#
#         self.conn.commit()
#
#     def get_all_received_names(self):
#         query = """
#             SELECT received_name FROM teams
#             UNION
#             SELECT received_name FROM verification_table
#         """
#         with self.conn.cursor() as cursor:
#             cursor.execute(query)
#             results = cursor.fetchall()
#         return set(row[0].lower() for row in results)
#
#
#     def get_verification_received_names(self):
#         self.cursor.execute("SELECT received_name FROM verification_table")
#         results = self.cursor.fetchall()
#         return set(row[0].lower() for row in results)
#
#     def get_all_received_names_and_leagues(self):
#         query = """
#             SELECT received_name, league FROM teams
#             UNION
#             SELECT received_name, league FROM verification_table
#         """
#         with self.conn.cursor() as cursor:
#             cursor.execute(query)
#             results = cursor.fetchall()
#
#         return set((row[0].lower(), row[1].upper()) for row in results)
#
#
#     def bulk_update_verification_table(self, data):
#         existing_names_leagues = self.get_all_received_names_and_leagues()
#
#
#         insert_data = []
#         for row in data:
#             if not row.get('found'):
#                 continue
#
#             received_name = row['original_name']
#             league = row['league'].upper()
#
#             # Check if both received_name AND league combo already exists
#             if (received_name.lower(), league) in existing_names_leagues:
#                 continue
#
#             normalized_name = row['team_name']
#             abbreviation = row['abbreviation'].upper() if row['abbreviation'] else None
#             source = row.get('source', 'unknown')
#             sportsbook = row.get('sportsbook', 'unknown')
#             original_league = row.get('original_league', league).upper()
#
#             insert_data.append((normalized_name, received_name, abbreviation, league, source, sportsbook, original_league))
#
#         if insert_data:
#             self.cursor.executemany("""
#                 INSERT INTO verification_table (normalized_name, received_name, abbreviation, league, source, sportsbook, original_league)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s)
#             """, insert_data)
#             self.conn.commit()
#
#
# if __name__ == "__main__":
#     db = Database()
#     db.create_mapping_database()