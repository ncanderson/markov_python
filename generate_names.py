import json
import pyodbc
import os

# Load configuration file
def load_config(config_file):
    with open(config_file, 'r') as file:
        return json.load(file)

# Connect to Microsoft SQL Server
def connect_to_database(server, database, username, password):
    connection_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
    )
    return pyodbc.connect(connection_string)

# Fetch selectable name options from the database
def fetch_name_options(cursor):
    query = "SELECT id, name FROM LanguageOptions"
    cursor.execute(query)
    results = cursor.fetchall()

    print("Available Options:")
    for row in results:
        print(f"{row.id}: {row.name}")
    return results

# Select options and percentages from the user
def get_user_selection(options):
    selections = []
    while True:
        try:
            option_id = int(input("Enter an option ID (or -1 to finish): "))
            if option_id == -1:
                break
            percentage = float(input("Enter percentage for this option: "))
            selections.append((option_id, percentage))
        except ValueError:
            print("Invalid input. Please try again.")
    return selections

# Fetch generated names based on user selection
def fetch_generated_names(cursor, selections):
    query = "EXEC GenerateNames ?, ?"
    names = []

    for option_id, percentage in selections:
        cursor.execute(query, option_id, percentage)
        names.extend(row[0] for row in cursor.fetchall())
    return names

# Write names to a file
def write_names_to_file(names, filename="generated_names.txt"):
    with open(filename, "w") as file:
        file.write("\n".join(names))
    print(f"Names written to {filename}")

# Save names to the database
def save_names_to_database(cursor, names):
    query = "INSERT INTO GeneratedNames (name) VALUES (?)"
    for name in names:
        cursor.execute(query, name)
    cursor.commit()
    print("Names saved to the database.")

def main():
    # Load config file
    config_file = "config.json"
    if not os.path.exists(config_file):
        print(f"Configuration file {config_file} not found.")
        return

    config = load_config(config_file)

    server = config["server"]
    database = config["database"]
    username = config["username"]
    password = config["password"]
    max_name_length = config["max_name_length"]
    number_of_names = config["number_of_names"]

    # Connect to the database
    conn = connect_to_database(server, database, username, password)
    cursor = conn.cursor()

    # Fetch selectable name options
    options = fetch_name_options(cursor)

    # User selects options and percentages
    selections = get_user_selection(options)

    # Fetch generated names
    names = fetch_generated_names(cursor, selections)

    # Ensure names conform to max length and limit the number
    names = [name[:max_name_length] for name in names][:number_of_names]

    # Write names to a file
    write_names_to_file(names)

    # Prompt user to save names to the database
    save_choice = input("Do you want to save these names to the database? (y/n): ").strip().lower()
    if save_choice == 'y':
        save_names_to_database(cursor, names)

    # Close the connection
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
