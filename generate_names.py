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

# Generate or show?
def get_activity():
    while True:
        print("\nHello. Please select an option:")
        print("1. Generate new names")
        print("2. Get existing names")

        choice = input("Enter 1 or 2: ").strip()

        if choice in {"1", "2"}:
            return choice.strip()
        else:
            print("Invalid input. Please enter 1 or 2.")

# Get and display all generated cultures
def fetch_and_display_generated_names(cursor):
    # Query to fetch generated cultures
    query_cultures = """
        select generated_guid_culture, generated_name_culture
        from generated_Culture
        order by generated_name_culture;
    """

    cursor.execute(query_cultures)
    cultures = cursor.fetchall()

    if not cultures:
        print("No generated cultures found.")
        return

    print("\nAvailable Generated Cultures:\n")

    # Extract and format results
    formatted_cultures = [(i + 1, row.generated_guid_culture, row.generated_name_culture) for i, row in enumerate(cultures)]

    # Determine column width for alignment
    max_culture_length = max(len(row[2]) for row in formatted_cultures) + 5
    max_num_length = len(str(len(formatted_cultures))) + 2
    col_count = 3  # Number of columns for cultures

    # Display cultures in columns
    for i, (row_num, _, culture_name) in enumerate(formatted_cultures):
        print(f"{row_num:>{max_num_length}}: {culture_name:<{max_culture_length}}", end='')

        if (i + 1) % col_count == 0:
            print()

    if len(formatted_cultures) % col_count != 0:
        print("\n")

    # Get user selection
    while True:
        try:
            selection = int(input("Enter the number of the culture to view names: ").strip())
            if 1 <= selection <= len(formatted_cultures):
                selected_uuid = formatted_cultures[selection - 1][1]
                break
            else:
                print("Invalid selection. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Query to fetch names associated with the selected culture
    query_names = """
        select generated_name
        from generated_name gn
        join generated_Culture gc
            on gn.generated_guid_culture = gc.generated_guid_culture
        were gc.generated_guid_culture = ?
        order by generated_name
    """
    cursor.execute(query_names, (selected_uuid,))
    names = cursor.fetchall()

    if not names:
        print("No names found for the selected culture.")
        return

    print("\nGenerated Names:\n")

    # Extract names from results
    name_list = [row.generated_Name for row in names]

    # Determine column width
    max_name_length = max(len(name) for name in name_list) + 5
    col_count = 4  # Number of columns for names

    # Display names in columns
    for i, name in enumerate(name_list):
        print(f"{name:<{max_name_length}}", end='')

        if (i + 1) % col_count == 0:
            print()

    if len(name_list) % col_count != 0:
        print("\n")

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
            @final_name_count = ?, @max_name_length = ?, @min_name_length = ?
    """

   # Create a tuple of parameters
    params = (
        langs[0], percentages[0],
        langs[1], percentages[1],
        langs[2], percentages[2],
        final_name_count, max_name_length, min_name_length
    )

    # Print parameters before executing for debugging
    print("Executing [markov_Complete] with parameters:", params)
    print("...")

    # Execute the stored procedure
    cursor.execute(query, params)

    # Get the generated names
    results = [row[0] for row in cursor.fetchall()]

    # Commit
    cursor.connection.commit()

    # Then return
    return results

# Write names to a file
def write_names_to_file(names, language_meta, selections, filename=None):
    # Generate base filename using the current date and the generated culture
    date_str = datetime.now().strftime("%Y%m%d")
    culture_name = language_meta.get("generated_culture", "UnknownCulture").replace(" ", "_")  # Ensure valid filename
    base_filename = f"{date_str}_{culture_name}"

    # Determine the final filename (increment if needed)
    if filename is None:
        filename = f"./output/{base_filename}.txt"
        count = 1

        # Check if file already exists and increment filename
        while os.path.exists(filename):
            filename = f"{base_filename}_{count}.txt"
            count += 1

    # Write metadata, selections, and names to the file
    with open(filename, "w") as file:
        # Write metadata at the top
        file.write("=== Language Metadata ===\n")
        for key, value in language_meta.items():
            file.write(f"{key}: {value}\n")

        # Write the selected names and ratios
        file.write("\n=== Selected Languages and Counts ===\n")
        for language, parts in selections:
            file.write(f"{language}: {parts}\n")

        # Write the generated names
        file.write("\n=== Generated Names ===\n")
        file.write("\n".join(names))

    print(f"Names written to {filename}")

def update_config_from_user_input(config):
    """
    Prompts the user to update the configuration parameters for name generation.

    Args:
        config (dict): The configuration dictionary loaded from file.

    Returns:
        dict: The updated configuration dictionary.
    """
    print("\nUpdate Configuration Parameters (Press Enter to keep the current value)")

    # Helper function to get user input with a default fallback
    def get_int_input(prompt, current_value):
        user_input = input(f"{prompt} [{current_value}]: ").strip()
        return int(user_input) if user_input.isdigit() else current_value

    # Prompt user for changes
    config["final_name_count"] = get_int_input("Final name count", config["final_name_count"])
    config["max_name_length"] = get_int_input("Max name length", config["max_name_length"])
    config["min_name_length"] = get_int_input("Min name length", config["min_name_length"])

    print("\nConfiguration updated successfully.")
    return config

# Save names to the database
def save_names_to_database(cursor, language_meta, selections):
    # Extract metadata values (with defaults to avoid KeyErrors)
    generated_culture = language_meta.get("generated_culture", "")
    generated_era = language_meta.get("generated_era", "")
    batch_notes = language_meta.get("batch_notes", "")

    # Append selections to batch_notes
    selection_notes = "; ".join(f"{name}: {ratio}" for name, ratio in selections)

    if batch_notes:
        batch_notes += f" | Selections: {selection_notes}"
    else:
        batch_notes = f"Selections: {selection_notes}"

    # Define stored procedure query
    query = """
        EXEC markov_Cache_Generated_Names
            @generated_culture = ?,
            @generated_era = ?,
            @batch_notes = ?
    """

    # Create a tuple of parameters
    params = (
        generated_culture,
        generated_era,
        batch_notes
    )

    # Print parameters before executing for debugging
    print("Executing [markov_Cache_Generated_Names] with parameters:", params)
    print("...")

    # Execute the stored procedure
    cursor.execute(query, params)

    # Commit transaction
    cursor.connection.commit()

    print("Generated names saved to the database.")


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

    # This flag will be set to true if the user enters new config, so we can track
    # whether to prompt the user to save the new values.
    config_dirty = False

    # Connect to the database
    conn = connect_to_database(server, database, username, password)
    cursor = conn.cursor()

    while True:
        activity = get_activity()

        if activity == '1':
            break  # Continue to generate names
        elif activity == '2':
            fetch_and_display_generated_names(cursor)

    # Fetch selectable name options
    options = fetch_name_options(cursor)

    # User selects options and percentages
    selections = get_user_selection(options)

    # Prompt a user to enter some text that will be inserted as meta-data
    # for the generation run.
    language_meta = get_generated_language_meta()

    while True:
        # Fetch generated names
        names = fetch_generated_names(cursor, selections, language_meta, config)

        print(names)

        # Write names to a file
        write_names_to_file(names, language_meta, selections)

        # Offer user the choice to regenerate or proceed
        print("\nOptions:")
        print("1. Re-generate words with the same parameters")
        print("2. Re-generate words with new source languages")
        print("3. Re-generate words with new meta-data")
        print("4. Change generation parameters")
        print("5. Exit and save names")

        choice = input("Select an option (1-5): ").strip()

        if choice == '1':
            continue  # Just re-fetch names with the same parameters
        elif choice == '2':
            options = fetch_name_options(cursor)
            selections = get_user_selection(options)  # Re-select languages, keep meta-data
        elif choice == '3':
            language_meta = get_generated_language_meta()  # Update meta-data, keep selections
        elif choice == '4':
            config = update_config_from_user_input(config) # Change sample size, word size, etc
            config_dirty = True
        elif choice == '5':
            break  # Exit loop and proceed to saving

    # Prompt user to save names to the database
    save_choice = input("Do you want to save these names to the database? (y/n): ").strip().lower()
    if save_choice == 'y':
        save_names_to_database(cursor, language_meta, selections)

    # Prompt user to save the updated config file
    if config_dirty == True:
        save_config_choice = input("Do you want to save the updated config to file? (y/n): ").strip().lower()
        if save_config_choice == 'y' :
            with open("config.json", "w") as config_file:
                json.dump(config, config_file, indent=4)
            print("Configuration saved to config.json")

    # Close the connection
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
