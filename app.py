from flask import Flask, render_template, request, jsonify, send_file
import cv2
from reportlab.lib import colors
import pickle
import face_recognition
import numpy as np
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import base64
from datetime import datetime
import mysql.connector  # New import for MySQL connection
from settings.initial_encoder import initialize_student_data

# Initialize Flask app
app = Flask(__name__)
app.secret_key = '24425d9a564c8eada45620220600da20'
initialize_student_data()

# MySQL database connection
try:
    db_connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Keita@1234",
        database="aiiovdft_profdux"
    )
    print("Connected to MySQL DB successfully")
    db_cursor = db_connection.cursor(dictionary=True)
except mysql.connector.Error as err:
    print(f"Error: {err}")
    db_connection, db_cursor = None, None


def update_attendance(id):
    """
    Update student attendance in MySQL
    """
    try:
        db_cursor = db_connection.cursor()
        query = "UPDATE Students SET attendance_time = %s WHERE id = %s"
        attendance_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_cursor.execute(query, (attendance_time, id))
        db_connection.commit()
        db_cursor.close()
    except mysql.connector.Error as e:
        print(f"Error updating attendance for student ID {id}: {e}")

        
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    with open("EncodeFile.p", "rb") as file:
        encodeListKnownWithIds = pickle.load(file)
    encodedFaceKnown, studentIDs = encodeListKnownWithIds

    data = request.get_json()
    img_data = base64.b64decode(data['image'])
    img_array = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    img_small = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
    rgb_img_small = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_img_small)
    face_encodings = face_recognition.face_encodings(rgb_img_small, face_locations)

    attendance_message = "Face Not Recognized"
    for encoding, location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(encodedFaceKnown, encoding)
        face_distances = face_recognition.face_distance(encodedFaceKnown, encoding)
        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            student_id = studentIDs[best_match_index]
            attendance_message = "Attendance Marked"
            update_attendance(student_id)
            break

    return jsonify({"message": attendance_message})

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed', methods=['POST'])
def video_feed():
    # Load known encodings and IDs
    with open("EncodeFile.p", "rb") as file:
        encodeListKnownWithIds = pickle.load(file)
    encodedFaceKnown, studentIDs = encodeListKnownWithIds

    # Get image from the request
    img_data = request.data
    img_array = np.frombuffer(base64.b64decode(img_data), np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # Resize for faster processing
    img_small = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
    rgb_img_small = cv2.cvtColor(img_small, cv2.COLOR_BGR2RGB)

    # Recognize face in the current frame
    face_locations = face_recognition.face_locations(rgb_img_small)
    face_encodings = face_recognition.face_encodings(rgb_img_small, face_locations)

    attendance_message = "Face Not Recognized"
    for encoding, location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(encodedFaceKnown, encoding)
        face_distances = face_recognition.face_distance(encodedFaceKnown, encoding)
        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            student_id = studentIDs[best_match_index]
            attendance_message = "Attendance Marked"

            # Update attendance
            update_attendance(student_id)
            break  # Stop after first match

    # Send the attendance message back to client
    return jsonify({"message": attendance_message})
@app.route("/admin_dashboard")
def admin_dashboard():
    """
    Fetch and display student attendance data on the admin dashboard.
    """
    try:
        db_cursor = db_connection.cursor(dictionary=True)
        query = "SELECT id, name, major, email, attendance_time FROM Students"
        db_cursor.execute(query)
        students = db_cursor.fetchall()
        db_cursor.close()

        current_year = datetime.now().year
        return render_template('admin_dashboard.html', students=students, current_year=current_year)

    except Exception as e:
        print(f"Error fetching admin dashboard data: {e}")
        return "Error loading dashboard"

@app.route("/student_attendance_list")
def student_attendance_list():
    """
    Generate a PDF attendance list for download.
    """
    try:
        db_cursor = db_connection.cursor(dictionary=True)
        db_cursor.execute("SELECT id, name, major, attendance_time FROM Students")
        students = db_cursor.fetchall()
        db_cursor.close()

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setTitle("Attendance List")
        font_path = './static/fonts/arial-unicode-ms.ttf'
        pdfmetrics.registerFont(TTFont('ArialUnicode', font_path))
        c.setFont("ArialUnicode", 12)

        # Title and header section
        logo_path = './static/Files/Neu.jpeg'
        c.drawImage(logo_path, 10, 680, width=100, height=50)
        c.drawString(110, 700, "NEAR EAST UNIVERSITY")
        c.drawString(110, 685, "INTERNATIONAL RESEARCH CENTER FOR AI AND AIOT")
        c.drawString(110, 670, f"Student Attendance List - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Table headers
        dark_red = colors.Color(0.267, 0.012, 0.012)
        c.setFillColor(dark_red)
        c.rect(50, 640, 500, 20, fill=True)
        c.setFillColor(colors.whitesmoke)
        c.drawString(50, 645, "ID")
        c.drawString(130, 645, "Name")
        c.drawString(280, 645, "Major")
        c.drawString(420, 645, "Attendance Time")
        c.setFillColor(colors.black)

        y = 620
        for student in students:
            student_id = student['id']
            name = student['name']
            major = student['major']
            attendance_time = student['attendance_time']

            if isinstance(attendance_time, datetime):
                attendance_time = attendance_time.strftime('%Y-%m-%d %H:%M:%S')

            c.drawString(50, y, str(student_id))
            c.drawString(130, y, name)
            c.drawString(280, y, major)
            c.drawString(420, y, attendance_time or "Absent")
            y -= 20

            if y < 50:
                c.showPage()
                y = 750

        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="attendance_list.pdf", mimetype='application/pdf')

    except Exception as e:
        return f"Error generating student attendance list: {e}"

if __name__ == "__main__":
    app.run(debug=True, port=5004)
