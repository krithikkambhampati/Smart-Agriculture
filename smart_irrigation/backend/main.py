from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import mysql.connector
from mysql.connector import Error

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store sensor data and manual override state
sensor_data = {
    "temperature": None,
    "humidity": None,
    "soil": None,
    "rain": None,
    "dryness": None,
    "motor_status": "off",
    "crop_type": "wheat"  # Default crop type
}

# Track manual override state
manual_override = None  # None, "on" (dryness=100), or "off" (dryness=0)

# List to keep track of connected WebSocket clients
connected_clients = []

class SensorPayload(BaseModel):
    temperature: float
    humidity: float
    soil: float
    rain: float
    dryness: float

# MySQL configuration
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
def store_sensor_data(data):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            crop_type = data.get("crop_type", "wheat")
            threshold = crop_thresholds.get(crop_type, 35)
            print(f"Storing data - crop_type: {crop_type}, threshold: {threshold}")
            sql = """
                INSERT INTO sensor_data (temperature, humidity, soil, rain, dryness, motor_status, crop_type, threshold, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(sql, (
                data["temperature"],
                data["humidity"],
                data["soil"],
                data["rain"],
                data["dryness"],
                data["motor_status"],
                crop_type,
                threshold
            ))
            connection.commit()
        except Error as e:
            print(f"Error storing data: {e}")
        finally:
            cursor.close()
            connection.close()
# Updated crop thresholds
crop_thresholds = {
    "wheat": 45,
    "sugarcane": 40,
    "rice":35,
    "maize":55,
    "cotton":50,
    "pulses":60,
    "millets":65,
    "mustard":50,
    "groundnut":55,
    "potato":40
}

@app.put("/update-sensor")
async def update_sensor(payload: SensorPayload):
    global sensor_data, manual_override
    sensor_data.update({
        "temperature": payload.temperature,
        "humidity": payload.humidity,
        "soil": payload.soil,
        "rain": payload.rain
    })
    threshold = crop_thresholds.get(sensor_data["crop_type"], 35)
    if manual_override is None:
        sensor_data["dryness"] = payload.dryness
        sensor_data["motor_status"] = "on" if payload.dryness > threshold else "off"
    elif manual_override == "on":
        sensor_data["dryness"] = 100
        sensor_data["motor_status"] = "on"
    elif manual_override == "off":
        sensor_data["dryness"] = 0
        sensor_data["motor_status"] = "off"
    store_sensor_data(sensor_data)
    for client in connected_clients:
        try:
            await client.send_text(json.dumps(sensor_data))
        except Exception:
            connected_clients.remove(client)
    return {"status": "received"}

@app.get("/get-sensor")
async def get_sensor():
    return sensor_data

@app.post("/set-manual-override-on")
async def set_manual_override_on():
    global sensor_data, manual_override
    manual_override = "on"
    sensor_data["dryness"] = 100
    sensor_data["motor_status"] = "on"
    store_sensor_data(sensor_data)
    for client in connected_clients:
        try:
            await client.send_text(json.dumps(sensor_data))
        except Exception:
            connected_clients.remove(client)
    return {"status": "manual override on (dryness=100)"}

@app.post("/set-manual-override-off")
async def set_manual_override_off():
    global sensor_data, manual_override
    manual_override = "off"
    sensor_data["dryness"] = 0
    sensor_data["motor_status"] = "off"
    store_sensor_data(sensor_data)
    for client in connected_clients:
        try:
            await client.send_text(json.dumps(sensor_data))
        except Exception:
            connected_clients.remove(client)
    return {"status": "manual override off (dryness=0)"}

@app.post("/remove-manual-override")
async def remove_manual_override():
    global sensor_data, manual_override
    manual_override = None
    threshold = crop_thresholds.get(sensor_data["crop_type"], 35)
    sensor_data["dryness"] = sensor_data.get("dryness", 0)  # Retain last dryness if exists
    sensor_data["motor_status"] = "on" if sensor_data.get("dryness", 0) > threshold else "off"
    store_sensor_data(sensor_data)
    for client in connected_clients:
        try:
            await client.send_text(json.dumps(sensor_data))
        except Exception:
            connected_clients.remove(client)
    return {"status": "manual override removed"}

class CropTypePayload(BaseModel):
    crop: str

@app.post("/set-crop-type")
async def set_crop_type(payload: CropTypePayload):
    global sensor_data
    if payload.crop in crop_thresholds:
        sensor_data["crop_type"] = payload.crop
        threshold = crop_thresholds[payload.crop]
        if manual_override is None:
            sensor_data["motor_status"] = "on" if sensor_data.get("dryness", 0) > threshold else "off"
        store_sensor_data(sensor_data)
        for client in connected_clients:
            try:
                await client.send_text(json.dumps(sensor_data))
            except Exception:
                connected_clients.remove(client)
        return {"status": f"crop type set to {payload.crop}"}
    return {"status": "invalid crop type"}
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps(sensor_data))
        while True:
            await websocket.receive_text()
    except Exception:
        connected_clients.remove(websocket)
        await websocket.close()


app.mount("/static", StaticFiles(directory="../static"), name="static")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
