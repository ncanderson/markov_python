import json
import pyodbc
import os
from datetime import datetime

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
        with name_union AS (
            select
                generated_guid_culture AS source_id,
                generated_name_culture AS source_language,
                'Generated' AS name_origin,
                2 AS sort
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
            row_number() over (order by sort, source_language) AS row_num,
            source_id,
            source_language,
            name_origin
        from name_union
        order by sort, source_language;
    """
    cursor.execute(query)
    results = cursor.fetchall()

    print("\nAvailable Options:\n")

    # Extract only row_num and source_language for return
    formatted_results = [(row.row_num, row.source_language) for row in results]

    # Determine max column width for formatting
    max_lang_length = max(len(row[1]) for row in formatted_results)  # Length of language names
    col_width = max_lang_length + 5  # Adjust column spacing

    # Determine max number width
    max_num_length = len(str(len(formatted_results))) + 2  # Row number length + padding

    # Print in three-column format
    col_count = 3  # Number of columns

    for i, (row_num, source_language) in enumerate(formatted_results):
        # Print row number and language name in aligned format
        print(f"{row_num:>{max_num_length}}: {source_language:<{col_width}}", end='')

        # Newline after every third column
        if (i + 1) % col_count == 0:
            print()

    # Ensure final newline if last row doesn't complete a full row
    if len(formatted_results) % col_count != 0:
        print("\n")

    return formatted_results

# Select options and ratio from the user
def get_user_selection(options):
    print("Sample parts will be calculated using relative weighting. All argued parts will be summed,")
    print("and the final percentage derived from the argued max. You could use 20 + 20 + 60, or .2 + .2 + .6, ")
    print("but don't mix int/float and decimal values or the result won't be what you expect.")

    selections = []

    # Convert list of tuples to dictionary {option_id: language_name}
    options_dict = {option_id: language for option_id, language in options}

    while len(selections) < 3:
        try:
            # Get the option ID input
            option_id = int(input("Enter an option ID (or -1 to finish): "))

            # Prevent -1 as the first choice if no selections are made
            if option_id == -1:
                if len(selections) >= 2:
                    break  # Allow finishing only if at least 2 selections are made
                print("You need to select at least 2 options before finishing.")
                continue  # Skip this iteration if -1 is entered too early

            # Validate that the selected option exists
            if option_id not in options_dict:
                print("Invalid option ID. Please select a valid one from the list.")
                continue

            # Get the ratio input
            parts = float(input("Sample parts: "))

            # Add the selected language name and ratio to the list
            selections.append((options_dict[option_id], parts))  # Store the name instead of the ID

        except ValueError:
            print("Invalid input. Please try again.")

    # Ensure at least 2 selections before returning
    if len(selections) < 2:
        print("You need to make at least 2 selections.")
        return get_user_selection(options)  # Retry if less than 2 selections

    return selections

# Prompt the user for metadata about the generation run
def get_generated_language_meta():
    """Prompts the user for metadata related to the generated names and returns it as a dictionary."""

    meta = {
        "generated_culture": input("Name of the culture for this generated set of names: "),
        "generated_era": input("Name of the world era for this generated set of names: "),
        "batch_notes": input("Batch notes for this generated set of names: ")
    }

    return meta


# Fetch generated names based on user selection
def fetch_generated_names(cursor, selections, language_meta, config):
    print(selections)
    # Extract configuration values from the provided config dictionary
    final_name_count = config.get("final_name_count", 100)  # Default: 100
    max_name_length = config.get("max_name_length", 12)  # Default: 12
    min_name_length = config.get("min_name_length", 3)  # Default: 3

    # Extract metadata values (with defaults to avoid KeyErrors)
    generated_culture = language_meta.get("generated_culture", "")
    generated_era = language_meta.get("generated_era", "")
    batch_notes = language_meta.get("batch_notes", "")

    # Extract language selections (up to 3, pad with None/0 if fewer)
    langs = [None] * 3
    percentages = [0.0] * 3  # Default percentage is 0

    for i, (option_id, percentage) in enumerate(selections[:3]):  # Only take up to 3
        langs[i] = option_id
        percentages[i] = percentage

    # Define stored procedure query
    query = """
        EXEC markov_Complete
            @lang1 = ?, @lang1_percentage = ?,
            @lang2 = ?, @lang2_percentage = ?,
            @lang3 = ?, @lang3_percentage = ?,
            @final_name_count = ?, @max_name_length = ?, @min_name_length = ?,
            @generated_culture = ?, @generated_era = ?, @BatchNotes = ?,
            @commit_bit = 0
    """

   # Create a tuple of parameters
    params = (
        langs[0], percentages[0],
        langs[1], percentages[1],
        langs[2], percentages[2],
        final_name_count, max_name_length, min_name_length,
        generated_culture, generated_era, batch_notes
    )

    # Print parameters before executing for debugging
    print("Executing SQL with parameters:", params)
    print("...")

    # Execute the stored procedure
    cursor.execute(query, params)

    # Fetch and return the generated names
    return [row[0] for row in cursor.fetchall()]

# Write names to a file
def write_names_to_file(names, language_meta, filename=None):
    # Generate base filename using the current date and the generated culture
    date_str = datetime.now().strftime("%Y%m%d")
    culture_name = language_meta.get("generated_culture", "UnknownCulture").replace(" ", "_")  # Ensure valid filename
    base_filename = f"{date_str}_{culture_name}"

    # Determine the final filename (increment if needed)
    if filename is None:
        filename = f"{base_filename}.txt"
        count = 1

        # Check if file already exists and increment filename
        while os.path.exists(filename):
            filename = f"{base_filename}_{count}.txt"
            count += 1

    # Write names to the file
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
    final_name_count = config["final_name_count"]
    max_name_length = config["max_name_length"]
    min_name_length = config["min_name_length"]

    # Connect to the database
    conn = connect_to_database(server, database, username, password)
    cursor = conn.cursor()

    # Fetch selectable name options
    options = fetch_name_options(cursor)

    # User selects options and percentages
    selections = get_user_selection(options)

    # Prompt a user to enter some text that will be inserted as meta-data
    # for the generation run.
    language_meta = get_generated_language_meta()

    # Fetch generated names
    names = fetch_generated_names(cursor, selections, language_meta, config)

    print(names)

    # Write names to a file
    write_names_to_file(names, language_meta)

    # Prompt user to save names to the database
    print("This isn't actually working yet, don't enter 'Y'")
    save_choice = input("Do you want to save these names to the database? (y/n): ").strip().lower()
    if save_choice == 'y':
        save_names_to_database(cursor, names)

    # Close the connection
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
