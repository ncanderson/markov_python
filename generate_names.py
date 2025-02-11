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
    query = """
        with name_union as (
            select
                generated_guid_culture as source_id,
                generated_name_culture as source_language,
                'Generated' as name_origin,
                2 as sort
            from generated_Culture gc
            union
            select
                guid_Language,
                name_language,
                'Real World',
                1
            from name_language
        )
        select
            row_number() over (order by sort, source_language) as row_num,
            source_id,
            source_language,
            name_origin
        from name_union
        order by sort, source_language;
    """
    cursor.execute(query)
    results = cursor.fetchall()

    print("Available Options:")

    # Define column width based on the longest option length (for better formatting)
    max_width = max(len(row.source_language) for row in results) + 5

    # Calculate fixed width for the row number part
    num_width = len(str(len(results))) + 3  # Add a little extra padding for numbers

    # Print results in three columns with dynamic width
    for i, row in enumerate(results):
        # Format the row number with fixed width and align the source_language
        print(f"{row.row_num:>{num_width}}: {row.source_language:<{max_width}}", end='')

        # Add a new line after every third column
        if (i + 1) % 3 == 0:
            print()

    # Ensure a newline if the last row doesn't complete a set of three
    if len(results) % 3 != 0:
        print()


    return results

# Select options and percentages from the user
def get_user_selection(options):
    selections = []

    while len(selections) < 3:
        try:
            # Get the option ID input
            option_id = int(input("Enter an option ID (or -1 to finish): "))

            # Prevent -1 as the first choice if no selections are made
            if option_id == -1 and len(selections) >= 2:
                break  # Allow finishing only if at least 2 selections are made

            if option_id == -1:
                print("You need to select at least 2 options before finishing.")
                continue  # Skip this iteration if -1 is entered too early

            # Get the percentage input
            percentage = float(input("Percentage (numbers should all be decimals or float/int): "))

            # Add the selected option and percentage to the list
            selections.append((option_id, percentage))

        except ValueError:
            print("Invalid input. Please try again.")

    # If less than 2 selections, ask the user to enter more
    if len(selections) < 2:
        print("You need to make at least 2 selections.")
        return get_user_selection(options)  # Retry if less than 2 selections

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
