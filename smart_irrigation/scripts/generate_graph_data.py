import mysql.connector
from mysql.connector import Error
import json
import argparse
import os

# MySQL configuration (same as in main.py)
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "saibaba@1",
    "database": "irrigation_db"
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def fetch_last_100_data_points():
    connection = get_db_connection()
    if not connection:
        return []
    
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT timestamp, temperature, humidity, soil, rain, dryness, motor_status
            FROM sensor_data
            ORDER BY timestamp DESC
            LIMIT 100
        """
        cursor.execute(query)
        data = cursor.fetchall()
        # Convert timestamp to string and motor_status to binary (0 or 1) for JSON serialization
        for row in data:
            row['timestamp'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            row['motor_status'] = 1 if row['motor_status'] == 'on' else 0
        return data
    except Error as e:
        print(f"Error fetching data: {e}")
        return []
    finally:
        cursor.close()
        connection.close()
def save_data_to_json(data, button_name):
    output_dir = "../static/graph_data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{button_name}.json")
    
    try:
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Data saved to {output_path}")
    except Exception as e:
        print(f"Error saving data to {output_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Generate graph data for a specific button")
    parser.add_argument("button", help="Button name (e.g., day1_morning, day1_evening, etc.)")
    args = parser.parse_args()

    button_name = args.button.lower().replace(" ", "_")
    valid_buttons = [
        "day1_morning", "day1_evening",
        "day2_morning", "day2_evening",
        "day3_morning", "day3_evening"
    ]
    
    if button_name not in valid_buttons:
        print(f"Error: Invalid button name. Choose from: {', '.join(valid_buttons)}")
        return
    
    data = fetch_last_100_data_points()
    if data:
        save_data_to_json(data, button_name)
    else:
        print("No data retrieved from database")

if __name__ == "__main__":
    main()