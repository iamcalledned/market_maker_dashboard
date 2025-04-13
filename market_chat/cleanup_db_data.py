import mysql.connector
from config import Config

def clean_ingredient_items(cursor):
    # Select rows where 'item' starts with '- '
    select_query = "SELECT item FROM ingredients WHERE item LIKE '- %'"
    cursor.execute(select_query)

    rows = cursor.fetchall()
    for row in rows:
        old_item = row[0]
        # Remove '- ' from the start of the item
        new_item = old_item[2:]
        # Update the row with the cleaned item
        update_query = "UPDATE ingredients SET item = %s WHERE item = %s"
        cursor.execute(update_query, (new_item, old_item))
    print(f"Cleaned {len(rows)} rows in 'ingredients' table.")

def main():
    db_config = {
        'host': Config.DB_HOST,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'database': Config.DB_NAME
    }

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Clean the ingredients items
        clean_ingredient_items(cursor)
        connection.commit()

        print("Database cleaning completed successfully.")
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    finally:
        if connection:
            connection.close()
if __name__ == "__main__":
    main()
